import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import CampaignRecap from '@/pages/CampaignRecap'
import CampaignCalendar from '@/pages/campaign/CampaignCalendar'
import ScheduleSheet from '@/pages/campaign/ScheduleSheet'
import { formatTime24 } from '@/lib/format'
import { clear, enqueue, peek, pruneOlderThan } from '@/lib/rewardQueue'
import type { ScheduleRead, SessionRecap } from '@/types'

const { recap, getCampaign, scheduleList, scheduleUpdate, scheduleCreate, navigate } = vi.hoisted(() => ({
  recap: vi.fn(), getCampaign: vi.fn(), scheduleList: vi.fn(), scheduleUpdate: vi.fn(), scheduleCreate: vi.fn(), navigate: vi.fn(),
}))

vi.mock('@/api/client', async (orig) => ({
  ...(await orig<typeof import('@/api/client')>()),
  api: {
    sessions: { recap },
    campaigns: { get: getCampaign, schedule: { list: scheduleList, update: scheduleUpdate, create: scheduleCreate, remove: vi.fn() } },
    share: { recap: vi.fn() },
  },
}))
vi.mock('react-router-dom', async (orig) => ({
  ...(await orig<typeof import('react-router-dom')>()),
  useParams: () => ({ id: '3', sessionId: '9' }),
  useNavigate: () => navigate,
}))
vi.mock('react-i18next', async (orig) => ({
  ...(await orig<typeof import('react-i18next')>()),
  useTranslation: () => ({
    t: (k: string, o?: Record<string, unknown>) => (o ? `${k} ${JSON.stringify(o)}` : k),
    i18n: { language: 'it' },
  }),
}))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }), canShareMessage: () => false }))
vi.mock('@/hooks/useShareMessage', () => ({ useShareMessage: () => ({ mutate: vi.fn(), isPending: false }) }))
vi.mock('@/components/Layout', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/ui/Sheet', () => ({ default: (p: { open: boolean; children: unknown }) => (p.open ? p.children : null) }))
vi.mock('@/components/ui/ConfirmSheet', () => ({ default: () => null }))

afterEach(() => { vi.clearAllMocks() })

const vecchio = {
  version: 1, session_id: 9, campaign_id: 3, campaign_name: 'Saga', number: 2,
  started_at: '2026-11-20T19:00:00', ended_at: '2026-11-20T22:00:00', duration_seconds: 10800,
  characters: [{
    character_id: 1, name: 'Eroe', player_name: null, class_summary: 'Mago 3', level: 3,
    dice: { rolls: 0, nat20: 0, nat1: 0, highest: null }, damage_taken: 0, healed: 0, downed: 0,
    death_saves: { successes: 0, failures: 0 }, spells_cast: 0, slots_used: {}, rests: { short: 0, long: 0 }, conditions: [],
  }],
  combat: { encounters: 0, rounds: 0, monsters: [] },
  items: { gm_grants: [], trades: [], stash: [{ kind: 'gm_stash_add', who: 'gm', summary: 'Corda' }, { kind: 'stash_take', who: 'Eroe', summary: '5 GP' }] },
  lore: [], highlights: [{ key: 'healer', character_id: 1, name: 'Eroe', value: 4 }],
} as unknown as SessionRecap

describe('caccia: campagna e calendario', () => {
  // caccia: {"id": "CB-154", "fonte": "invariante: un riepilogo salvato da una versione precedente (senza places, defeated, condition_levels) si legge ancora", "zona": "flusso:campagna-calendario", "voce": "contratto", "copre": ["route:/campaign/:id/recap/:sessionId"]}
  it('un riepilogo vecchio senza i campi nuovi si mostra intero', async () => {
    recap.mockResolvedValue(vecchio)
    getCampaign.mockResolvedValue({ id: 3, is_gm: true })
    renderWithProviders(<CampaignRecap />)
    expect(await screen.findAllByText('campaign.recap.evening {"n":2}')).not.toHaveLength(0)
    expect(screen.getByText('campaign.recap.gm_stash_add {"who":"gm","what":"Corda"}')).toBeInTheDocument()
    expect(screen.getByText('campaign.recap.stash_take {"who":"Eroe","what":"5 GP"}')).toBeInTheDocument()
    expect(screen.getByText('campaign.recap.hl_healer {"name":"Eroe","v":4}')).toBeInTheDocument()
    expect(screen.queryByText('campaign.recap.places')).toBeNull()
  })

  // caccia: {"id": "CB-155", "fonte": "invariante: se il riepilogo non si può leggere la pagina lo dice e torna alla campagna", "zona": "flusso:campagna-calendario", "voce": "contratto", "copre": ["route:/campaign/:id/recap/:sessionId"]}
  it('un riepilogo negato mostra il messaggio di non disponibile', async () => {
    const { ApiError } = await import('@/api/client')
    recap.mockRejectedValue(new ApiError(403, 'Not allowed'))
    getCampaign.mockResolvedValue({ id: 3, is_gm: false })
    renderWithProviders(<CampaignRecap />)
    expect(await screen.findByText('campaign.recap.unavailable')).toBeInTheDocument()
  })

  // caccia: {"id": "CB-156", "fonte": "invariante: svuotare la nota di una serata la toglie, e l'ora locale scelta parte come ISO UTC", "zona": "flusso:campagna-calendario", "voce": "normale", "copre": ["route:/campaign/:id"]}
  it('spostare una serata con la nota svuotata invia nota nulla e l’ora locale in UTC', async () => {
    const row: ScheduleRead = { id: 5, starts_at: '2026-12-05T20:00:00', note: 'Da Marco', session_id: null, status: 'planned' }
    scheduleUpdate.mockResolvedValue(row)
    renderWithProviders(<ScheduleSheet open campaignId={3} row={row} onClose={vi.fn()} />)
    const nota = await screen.findByDisplayValue('Da Marco')
    await userEvent.clear(nota)
    await userEvent.click(screen.getByText('common.save'))
    await waitFor(() => expect(scheduleUpdate).toHaveBeenCalled())
    const [camp, id, body] = scheduleUpdate.mock.calls[0]
    expect([camp, id, body.note]).toEqual([3, 5, null])
    expect(body.starts_at).toBe(new Date('2026-12-05T20:00:00Z').toISOString())
  })

  // caccia: {"id": "CB-157", "fonte": "invariante: il giorno con una serata programmata e una già giocata mostra entrambe nel dettaglio", "zona": "flusso:campagna-calendario", "voce": "interazione", "copre": ["route:/campaign/:id"]}
  it('un giorno con serata giocata e programmata le elenca entrambe', async () => {
    const adesso = new Date()
    const giorno = new Date(adesso.getFullYear(), adesso.getMonth(), 15, 12)
    const utc = giorno.toISOString().slice(0, 19)
    scheduleList.mockResolvedValue([{ id: 1, starts_at: utc, note: null, session_id: null, status: 'planned' }])
    renderWithProviders(
      <CampaignCalendar campaignId={3} isGm={false} sessions={[{ id: 8, created_at: utc, duration_seconds: 60, number: 1, has_recap: true }]} />,
    )
    await waitFor(() => expect(document.querySelector('[data-mark="planned"]')).not.toBeNull())
    await userEvent.click(screen.getByRole('button', { name: new RegExp('^15 ') }))
    const dettaglio = await screen.findByTestId('day-detail')
    expect(dettaglio.textContent).toContain('campaign.night_n {"n":1}')
    expect(dettaglio.textContent).toContain('campaign.calendar.planned')
  })

  // caccia: {"id": "CB-764", "fonte": "invariante: gli orari del server sono UTC senza fuso e si mostrano nell'ora locale", "zona": "flusso:campagna-calendario", "voce": "persistenza", "copre": ["route:/session/:id"]}
  it('gli orari del feed e l’età dei premi leggono UTC', () => {
    const adesso = new Date()
    const server = adesso.toISOString().slice(0, 19)
    expect(formatTime24(server, 'it')).toBe(formatTime24(adesso, 'it'))
    clear()
    enqueue({ message_id: 1, item_id: 1, item_name: 'x', item_quantity: 1, char_id: 1, granted_at: server })
    pruneOlderThan(60_000)
    expect(peek()?.message_id).toBe(1)
    const vecchio2 = new Date(adesso.getTime() - 120_000).toISOString().slice(0, 19)
    clear()
    enqueue({ message_id: 2, item_id: 1, item_name: 'x', item_quantity: 1, char_id: 1, granted_at: vecchio2 })
    pruneOlderThan(60_000)
    expect(peek()).toBeNull()
  })

  // caccia: {"id": "CB-767", "fonte": "invariante: un doppio tocco non crea due oggetti", "zona": "flusso:campagna-calendario", "voce": "ripetizione", "copre": ["route:/campaign/:id"]}
  it('due tocchi nello stesso istante su Salva creano una sola serata, e un errore lascia riprovare', async () => {
    scheduleCreate.mockRejectedValueOnce(new Error('rete')).mockResolvedValue({ id: 6 })
    renderWithProviders(<ScheduleSheet open campaignId={3} row={null} defaultDate="2030-01-01" onClose={vi.fn()} />)
    const salva = (await screen.findByText('common.save')).closest('button')!
    await waitFor(() => expect(salva).toBeEnabled())
    act(() => { salva.click(); salva.click() })
    await waitFor(() => expect(scheduleCreate).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(salva).toBeEnabled())
    act(() => { salva.click() })
    await waitFor(() => expect(scheduleCreate).toHaveBeenCalledTimes(2))
  })
})


// --- aggiunte del giro del 2026-11-24 (seconda parte) ---
import JoinCampaignSessionSheet from '@/pages/campaign/JoinCampaignSessionSheet'

describe('caccia: campagna e calendario, seconda parte', () => {
  // caccia: {"id": "CB-888", "fonte": "invariante: una serata già giocata compare una volta sola nel calendario, non anche come programmata", "zona": "flusso:campagna-calendario", "voce": "interazione", "copre": ["route:/campaign/:id"]}
  it('una serata programmata e poi giocata si vede una sola volta, come giocata', async () => {
    const giorno = new Date(new Date().getFullYear(), new Date().getMonth(), 15, 12)
    const utc = giorno.toISOString().slice(0, 19)
    scheduleList.mockResolvedValue([{ id: 1, starts_at: utc, note: 'Da Marco', session_id: 8, status: 'done' }])
    renderWithProviders(
      <CampaignCalendar campaignId={3} isGm sessions={[{ id: 8, created_at: utc, duration_seconds: 60, number: 1, has_recap: true }]} />,
    )
    await waitFor(() => expect(scheduleList).toHaveBeenCalled())
    await userEvent.click(screen.getByRole('button', { name: new RegExp('^15 ') }))
    const dettaglio = await screen.findByTestId('day-detail')
    expect(dettaglio.textContent).toContain('campaign.night_n {"n":1}')
    expect(dettaglio.textContent).not.toContain('campaign.calendar.planned')
    expect(dettaglio.textContent).not.toContain('campaign.calendar.skipped')
    expect(dettaglio.textContent).not.toContain('Da Marco')
    expect(document.querySelectorAll('[data-mark="done"]')).toHaveLength(1)
    expect(document.querySelectorAll('[data-mark="planned"], [data-mark="skipped"]')).toHaveLength(0)
  })

  // caccia: {"id": "CB-889", "fonte": "invariante: in italiano la settimana parte dal lunedì (1 novembre 2026 è una domenica: va nell'ultima colonna)", "zona": "flusso:campagna-calendario", "voce": "limiti", "copre": ["route:/campaign/:id"]}
  it('il calendario italiano mette la domenica nell’ultima colonna', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    try {
      vi.setSystemTime(new Date(2026, 10, 15, 12))
      scheduleList.mockResolvedValue([])
      renderWithProviders(<CampaignCalendar campaignId={3} isGm={false} sessions={[]} />)
      const primo = await screen.findByRole('button', { name: new RegExp('^1 ') })
      expect(primo.style.gridColumnStart).toBe('7')
      const intestazioni = screen.getAllByTestId('weekday').map((e) => e.textContent?.toLowerCase())
      expect(intestazioni[0]).toMatch(/^lun/)
      expect(intestazioni[6]).toMatch(/^dom/)
    } finally {
      vi.useRealTimers()
    }
  })

  // caccia: {"id": "CB-890", "fonte": "invariante: una nuova serata parte con l'ora locale scelta (21:00 di default) come ISO UTC e senza nota se è vuota", "zona": "flusso:campagna-calendario", "voce": "normale", "copre": ["route:/campaign/:id"]}
  it('una nuova serata senza nota invia l’ora locale 21:00 in UTC e nessuna nota', async () => {
    scheduleCreate.mockResolvedValue({ id: 6 })
    renderWithProviders(<ScheduleSheet open campaignId={3} row={null} defaultDate="2030-03-10" onClose={vi.fn()} />)
    const salva = (await screen.findByText('common.save')).closest('button')!
    await waitFor(() => expect(salva).toBeEnabled())
    await userEvent.click(salva)
    await waitFor(() => expect(scheduleCreate).toHaveBeenCalledTimes(1))
    const [camp, body] = scheduleCreate.mock.calls[0]
    expect(camp).toBe(3)
    expect(body.starts_at).toMatch(/Z$/)
    const quando = new Date(body.starts_at)
    expect([quando.getFullYear(), quando.getMonth(), quando.getDate(), quando.getHours(), quando.getMinutes()]).toEqual([2030, 2, 10, 21, 0])
    expect('note' in body).toBe(false)
  })

  // caccia: {"id": "CB-891", "fonte": "invariante: il riepilogo mostra ogni personaggio, anche quello eliminato a serata aperta, senza chiavi doppie", "zona": "flusso:campagna-calendario", "voce": "contratto", "copre": ["route:/campaign/:id/recap/:sessionId"]}
  it('il riepilogo con un PG eliminato (id negativo) li mostra tutti e due', async () => {
    const base = (vecchio as SessionRecap).characters[0]
    recap.mockResolvedValue({
      ...vecchio,
      characters: [
        { ...base, character_id: 1, name: 'Eroe', damage_taken: 4, conditions: ['exhaustion'], condition_levels: { exhaustion: 3 } },
        { ...base, character_id: -4, name: 'Eliminato', damage_taken: 7, healing_given: 2 },
      ],
    })
    getCampaign.mockResolvedValue({ id: 3, is_gm: false })
    const errori = vi.spyOn(console, 'error').mockImplementation(() => {})
    renderWithProviders(<CampaignRecap />)
    expect(await screen.findByText('Eliminato')).toBeInTheDocument()
    expect(screen.getByText('Eroe')).toBeInTheDocument()
    expect(errori.mock.calls.flat().join(' ')).not.toContain('same key')
    errori.mockRestore()
  })

  // caccia: {"id": "CB-892", "fonte": "invariante: chi è morto non si propone per entrare in serata; si parte dal PG dell'ultima serata, se vivo, altrimenti dal primo vivo", "zona": "flusso:campagna-calendario", "voce": "regola", "copre": ["route:/campaign/:id"]}
  it('il foglio «chi gioca» esclude il PG morto e preseleziona il primo vivo', async () => {
    const m = (id: number, name: string, status: string) => ({ character_id: id, character_name: name, is_mine: true, status })
    getCampaign.mockResolvedValue({ id: 3, members: [m(1, 'Morto', 'dead'), m(2, 'Vivo', 'active'), m(3, 'Terzo', 'reserve')] })
    renderWithProviders(
      <JoinCampaignSessionSheet open onClose={vi.fn()} item={{ campaign_id: 3, campaign_name: 'Saga', session_id: 9, my_last_character_id: 1 }} />,
    )
    const vivo = await screen.findByText('Vivo')
    expect(screen.queryByText('Morto')).toBeNull()
    expect(vivo.closest('button')!.className).toContain('bg-dnd-gold/20')
    expect(screen.getByText('Terzo').closest('button')!.className).not.toContain('bg-dnd-gold/20')
  })
})
