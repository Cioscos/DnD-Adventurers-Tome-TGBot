import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../utils/renderWithProviders'
import CampaignCalendar from '@/pages/campaign/CampaignCalendar'
import type { CampaignSessionEntry, ScheduleRead } from '@/types'

const { list, create, update, remove, navigateSpy } = vi.hoisted(() => ({
  list: vi.fn(), create: vi.fn(), update: vi.fn(), remove: vi.fn(), navigateSpy: vi.fn(),
}))

vi.mock('@/api/client', () => ({
  api: { campaigns: { schedule: { list, create, update, remove } } },
  ApiError: class ApiError extends Error { constructor(public status: number, public detail: unknown) { super('x') } },
}))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ info: vi.fn(), error: vi.fn(), success: vi.fn() }) }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useNavigate: () => navigateSpy }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return {
    ...actual,
    useTranslation: () => ({ t: (k: string, o?: Record<string, unknown>) => (o?.time ? `${k} ${o.time}` : o?.n ? `${k} ${o.n}` : k), i18n: { language: 'it' } }),
  }
})
vi.mock('@/components/ui/Sheet', () => ({
  default: ({ open, children }: { open: boolean; children: React.ReactNode }) => (open ? <div role="dialog">{children}</div> : null),
}))

// Mercoledì 18 novembre 2026, mezzogiorno locale.
beforeEach(() => { vi.useFakeTimers({ toFake: ['Date'] }); vi.setSystemTime(new Date(2026, 10, 18, 12, 0, 0)) })
afterEach(() => { vi.useRealTimers(); list.mockReset(); create.mockReset(); update.mockReset(); remove.mockReset(); navigateSpy.mockReset() })

// created_at / starts_at arrivano come UTC naive: ore 12 UTC restano nello stesso giorno ovunque (±12h).
const sessions: CampaignSessionEntry[] = [
  { id: 7, created_at: '2026-11-04T12:00:00', duration_seconds: 3600, number: 1, has_recap: true },
  { id: 8, created_at: '2026-11-06T12:00:00', duration_seconds: 600, number: 2, has_recap: false },
]
const row = (o: Partial<ScheduleRead>): ScheduleRead => ({ id: 1, starts_at: '2026-11-25T12:00:00', note: 'Porta le torce', session_id: null, status: 'planned', ...o })
const day = (n: number) => screen.getByRole('button', { name: new RegExp(`^${n} `) })

const show = (isGm: boolean, rows: ScheduleRead[] = []) => {
  list.mockResolvedValue(rows)
  return renderWithProviders(<CampaignCalendar campaignId={5} isGm={isGm} sessions={sessions} />)
}

describe('CampaignCalendar', () => {
  it('griglia del mese con settimana da lunedì e frecce', async () => {
    show(false)
    // 1 novembre 2026 è domenica → con lunedì come primo giorno è la 7a cella
    const cells = await screen.findAllByRole('button', { name: /^\d+ / })
    expect(cells).toHaveLength(30)
    const heads = screen.getAllByTestId('weekday').map((e) => e.textContent?.toLowerCase())
    expect(heads[0]).toMatch(/^lun/)
    expect((screen.getByTestId('grid').children[0] as HTMLElement).style.gridColumnStart).toBe('7')
    await userEvent.click(screen.getByRole('button', { name: 'campaign.calendar.next' }))
    expect(screen.getAllByRole('button', { name: /^\d+ / })).toHaveLength(31) // dicembre
    await userEvent.click(screen.getByRole('button', { name: 'campaign.calendar.prev' }))
    await userEvent.click(screen.getByRole('button', { name: 'campaign.calendar.prev' }))
    expect(screen.getAllByRole('button', { name: /^\d+ / })).toHaveLength(31) // ottobre
  })

  it('serata passata marcata e al tocco porta al riepilogo', async () => {
    show(false)
    await screen.findAllByRole('button', { name: /^\d+ / })
    expect(day(4).querySelector('[data-mark=done]')).not.toBeNull()
    await userEvent.click(day(4))
    await userEvent.click(screen.getByRole('button', { name: /campaign\.night_n 1/ }))
    expect(navigateSpy).toHaveBeenCalledWith('/campaign/5/recap/7')
  })

  it('serata passata senza riepilogo non è un link', async () => {
    show(false)
    await screen.findAllByRole('button', { name: /^\d+ / })
    await userEvent.click(day(6))
    expect(screen.queryByRole('button', { name: /campaign\.night_n 2/ })).toBeNull()
    expect(screen.getByText(/campaign\.night_n 2/)).toBeInTheDocument()
  })

  it('serata programmata: segno distinto, ora e nota; giocatore senza azioni', async () => {
    show(false, [row({})])
    await waitFor(() => expect(day(25).querySelector('[data-mark=planned]')).not.toBeNull())
    await userEvent.click(day(25))
    expect(screen.getByText('Porta le torce')).toBeInTheDocument()
    expect(screen.getByText(/\d{2}:\d{2}/)).toBeInTheDocument()
    expect(screen.queryByText('campaign.calendar.schedule')).toBeNull()
    expect(screen.queryByText('campaign.calendar.move')).toBeNull()
    expect(screen.queryByText('campaign.calendar.cancel')).toBeNull()
  })

  it('serata saltata ha l\'etichetta', async () => {
    show(false, [row({ status: 'skipped' })])
    await waitFor(() => expect(day(25).querySelector('[data-mark=skipped]')).not.toBeNull())
    await userEvent.click(day(25))
    expect(screen.getByText('campaign.calendar.skipped')).toBeInTheDocument()
  })

  it('le righe done non raddoppiano il segno delle sessioni', async () => {
    show(false, [row({ id: 2, status: 'done', starts_at: '2026-11-10T12:00:00', session_id: 7 })])
    await screen.findAllByRole('button', { name: /^\d+ / })
    expect(day(10).querySelector('[data-mark]')).toBeNull()
  })

  it('master: Programma serata, Sposta e Annulla', async () => {
    show(true, [row({})])
    expect(await screen.findByRole('button', { name: 'campaign.calendar.schedule' })).toBeInTheDocument()
    await userEvent.click(day(25))
    expect(screen.getByRole('button', { name: 'campaign.calendar.move' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'campaign.calendar.cancel' }))
    remove.mockResolvedValue(undefined)
    await userEvent.click(screen.getByRole('button', { name: 'campaign.calendar.cancel_confirm' }))
    await waitFor(() => expect(remove).toHaveBeenCalledWith(5, 1))
  })

  it('la sheet invia starts_at ISO con offset da data e ora locali', async () => {
    create.mockResolvedValue(row({}))
    show(true)
    await userEvent.click(await screen.findByRole('button', { name: 'campaign.calendar.schedule' }))
    fireEvent.change(document.querySelector('input[type=date]')!, { target: { value: '2026-12-05' } })
    fireEvent.change(document.querySelector('input[type=time]')!, { target: { value: '21:00' } })
    await userEvent.type(document.querySelector('input:not([type=date]):not([type=time])') as HTMLInputElement, 'Cena')
    await userEvent.click(screen.getByRole('button', { name: 'common.save' }))
    await waitFor(() => expect(create).toHaveBeenCalled())
    const [cid, body] = create.mock.calls[0] as [number, { starts_at: string; note: string }]
    expect(cid).toBe(5)
    expect(body.starts_at).toBe(new Date(2026, 11, 5, 21, 0).toISOString())
    expect(body.starts_at).toMatch(/Z$/)
    expect(body.note).toBe('Cena')
  })

  it('422 mostra un messaggio inline', async () => {
    const { ApiError } = await import('@/api/client')
    create.mockRejectedValue(new ApiError(422, 'in the past'))
    show(true)
    await userEvent.click(await screen.findByRole('button', { name: 'campaign.calendar.schedule' }))
    fireEvent.change(document.querySelector('input[type=date]')!, { target: { value: '2026-12-05' } })
    fireEvent.change(document.querySelector('input[type=time]')!, { target: { value: '21:00' } })
    await userEvent.click(screen.getByRole('button', { name: 'common.save' }))
    expect(await screen.findByText('campaign.calendar.err_past')).toBeInTheDocument()
  })

  it('Sposta precompila e usa PATCH', async () => {
    update.mockResolvedValue(row({}))
    show(true, [row({})])
    await screen.findAllByRole('button', { name: /^\d+ / })
    await userEvent.click(day(25))
    await userEvent.click(screen.getByRole('button', { name: 'campaign.calendar.move' }))
    expect((document.querySelector('input[type=date]') as HTMLInputElement).value).toBe('2026-11-25')
    fireEvent.change(document.querySelector('input[type=time]')!, { target: { value: '20:30' } })
    await userEvent.click(screen.getByRole('button', { name: 'common.save' }))
    await waitFor(() => expect(update).toHaveBeenCalled())
    expect(update.mock.calls[0][1]).toBe(1)
    expect(update.mock.calls[0][2].starts_at).toBe(new Date(2026, 10, 25, 20, 30).toISOString())
  })
})
