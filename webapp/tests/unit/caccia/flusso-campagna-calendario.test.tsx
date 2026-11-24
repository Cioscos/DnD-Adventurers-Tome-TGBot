import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import CampaignRecap from '@/pages/CampaignRecap'
import CampaignCalendar from '@/pages/campaign/CampaignCalendar'
import ScheduleSheet from '@/pages/campaign/ScheduleSheet'
import type { ScheduleRead, SessionRecap } from '@/types'

const { recap, getCampaign, scheduleList, scheduleUpdate, navigate } = vi.hoisted(() => ({
  recap: vi.fn(), getCampaign: vi.fn(), scheduleList: vi.fn(), scheduleUpdate: vi.fn(), navigate: vi.fn(),
}))

vi.mock('@/api/client', async (orig) => ({
  ...(await orig<typeof import('@/api/client')>()),
  api: {
    sessions: { recap },
    campaigns: { get: getCampaign, schedule: { list: scheduleList, update: scheduleUpdate, create: vi.fn(), remove: vi.fn() } },
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
})
