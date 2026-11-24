import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '../utils/renderWithProviders'
import DiceStats from '@/pages/DiceStats'
import Dice from '@/pages/Dice'
import History from '@/pages/History'
import DicePoolResultModal from '@/components/DicePoolResultModal'
import userEvent from '@testing-library/user-event'
import { formatRelative, formatAbsolute } from '@/lib/relativeTime'

const { stats, diceHistory, getChar, getHistory, rollMock, postToChat, tg, toastFn } = vi.hoisted(() => ({
  stats: vi.fn(), diceHistory: vi.fn(), getChar: vi.fn(), getHistory: vi.fn(), rollMock: vi.fn(), postToChat: vi.fn(),
  tg: { dentro: false },
  toastFn: { error: vi.fn(), warning: vi.fn(), info: vi.fn(), success: vi.fn(), base: vi.fn() },
}))

vi.mock('@/api/client', () => ({ api: { dice: { stats, resetStats: vi.fn(), history: diceHistory, initiative: vi.fn(), postToChat }, characters: { get: getChar }, history: { get: getHistory, clear: vi.fn() } } }))
vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useParams: () => ({ id: '7' }) }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }), isInsideTelegram: () => tg.dentro, getLanguageCode: () => 'it' }))
vi.mock('@/store/characterStore', () => ({ useCharacterStore: (sel: (s: { locale: string }) => unknown) => sel({ locale: 'it' }) }))
vi.mock('@/dice/useRollAndPersist', () => ({ useRollAndPersist: () => ({ roll: rollMock, isPending: false }) }))
vi.mock('sonner', () => ({
  toast: Object.assign((...a: unknown[]) => toastFn.base(...a), { error: toastFn.error, warning: toastFn.warning, info: toastFn.info, success: toastFn.success }),
  Toaster: () => null,
}))
vi.mock('@/dice/useDiceAnimation', () => ({ useDiceAnimation: () => ({ playAndCollect: vi.fn() }) }))
vi.mock('@/dice/preload', () => ({ schedulePreloadDiceScene: () => {} }))
vi.mock('@/hooks/useD20Roll', () => ({ useD20Roll: () => async () => undefined, d20Arg: () => undefined }))
vi.mock('@/components/Layout', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/ui/ConfirmSheet', () => ({ default: () => null }))
vi.mock('@/components/ScrollArea', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})

const tzOriginale = process.env.TZ
afterEach(() => {
  stats.mockReset()
  diceHistory.mockReset()
  getChar.mockReset()
  getHistory.mockReset()
  rollMock.mockReset()
  postToChat.mockReset()
  Object.values(toastFn).forEach((f) => f.mockReset())
  tg.dentro = false
  if (tzOriginale === undefined) delete process.env.TZ
  else process.env.TZ = tzOriginale
})

describe('caccia: dadi', () => {
  // caccia: {"id": "CB-755", "fonte": "invariante: il numero dei tiri conta solo dadi, non il totale di una prova", "zona": "flusso:dadi", "voce": "normale", "copre": ["route:/char/:id/dice/stats"]}
  it('le statistiche contano i dadi e calcolano la media di faccia', async () => {
    stats.mockResolvedValue({ stats: { d6: { '2': 1, '6': 3 }, d20: { '1': 2, '20': 1 }, d20_total: { '57': 1 } } })
    renderWithProviders(<DiceStats />)
    expect(await screen.findByText('5.0')).toBeInTheDocument()
    expect(screen.getByText('7')).toBeInTheDocument()
  })

  // caccia: {"id": "CB-756", "fonte": "invariante: un orario UTC dell'API si mostra nell'ora locale di chi guarda", "zona": "flusso:dadi", "voce": "normale", "copre": ["route:/char/:id/history", "route:/char/:id/dice"]}
  it("l'orario di un evento scritto dall'API in UTC si mostra nell'ora locale", () => {
    process.env.TZ = 'Europe/Rome' // fissa il fuso: Node lo rispetta a runtime su Windows e Linux, e lo ripristina afterEach
    expect(new Date(2026, 10, 24, 12).getTimezoneOffset()).toBe(-60)
    const ora = formatRelative('2026-11-24T09:00:00', {
      locale: 'it', todayLabel: 'Oggi', yesterdayLabel: 'Ieri', now: new Date('2026-11-24T09:30:00Z'),
    })
    expect(ora).toBe('Oggi 10:00')
  })

  // caccia: {"id": "CB-1483", "fonte": "invariante: i dadi elencati accanto al totale tornano come somma", "zona": "flusso:dadi", "voce": "normale", "copre": ["route:/char/:id/dice"]}
  it.fails("nello storico un 4d6kh3 non elenca il dado scartato accanto al totale", async () => {
    getChar.mockResolvedValue({ id: 7, name: 'Eroe', ability_scores: [] })
    diceHistory.mockResolvedValue([{ notation: '4d6kh3', rolls: [3, 4, 5, 1], total: 12, timestamp: '2026-11-24T09:00:00', source: 'manual', label: null }])
    renderWithProviders(<Dice />)
    const elenco = await screen.findByText(/^\[[\d+]+\]$/)
    const somma = (elenco.textContent ?? '').match(/\d+/g)!.reduce((s, n) => s + Number(n), 0)
    expect(somma).toBe(12)
  })

  // caccia: {"id": "CB-1484", "fonte": "invariante: un orario UTC dell'API si mostra nell'ora locale anche nel suggerimento con la data esatta", "zona": "flusso:dadi", "voce": "normale", "copre": ["route:/char/:id/history"]}
  it("la data esatta di un evento scritto dall'API in UTC è nell'ora locale", () => {
    process.env.TZ = 'Europe/Rome'
    expect(formatAbsolute('2026-11-24T09:00:00', 'it')).toContain('10:00')
  })

  // caccia: {"id": "CB-1485", "fonte": "invariante: il giorno di un evento è quello locale di chi guarda, anche a cavallo della mezzanotte", "zona": "flusso:dadi", "voce": "limiti", "copre": ["route:/char/:id/history"]}
  it("un evento UTC di prima di mezzanotte ma dopo mezzanotte locale è di oggi", () => {
    process.env.TZ = 'Europe/Rome'
    const base = { locale: 'it' as const, todayLabel: 'Oggi', yesterdayLabel: 'Ieri', now: new Date('2026-11-24T10:00:00Z') }
    expect(formatRelative('2026-11-23T23:30:00', base)).toBe('Oggi 00:30')
    expect(formatRelative('2026-11-23T22:30:00', base)).toBe('Ieri 23:30')
  })

  // caccia: {"id": "CB-1486", "fonte": "invariante: la ricerca nella cronologia ignora maiuscole e spazi attorno", "zona": "flusso:dadi", "voce": "limiti", "copre": ["route:/char/:id/history"]}
  it("la ricerca nella cronologia trova le voci con maiuscole, accenti e spazi attorno", async () => {
    getHistory.mockResolvedValue([
      { id: 2, timestamp: '2026-11-24T09:00:00', event_type: 'dice_roll', description: 'Iniziativa: 🎲 d20: 14' },
      { id: 1, timestamp: '2026-11-24T08:00:00', event_type: 'other', description: 'Salvezza è fallita' },
    ])
    renderWithProviders(<History />)
    const campo = await screen.findByPlaceholderText('character.history.search_placeholder')
    await userEvent.type(campo, '  INIZIATIVA ')
    expect(screen.getByText(/Iniziativa: /)).toBeInTheDocument()
    expect(screen.queryByText(/Salvezza/)).not.toBeInTheDocument()
    await userEvent.clear(campo)
    await userEvent.type(campo, 'È FALLITA')
    expect(screen.getByText(/Salvezza/)).toBeInTheDocument()
    expect(screen.queryByText(/Iniziativa: /)).not.toBeInTheDocument()
  })

  // caccia: {"id": "CB-1487", "fonte": "invariante: le statistiche mostrano i trofei dei naturali e i dadi in ordine di facce", "zona": "flusso:dadi", "voce": "normale", "copre": ["route:/char/:id/dice/stats"]}
  it("le statistiche mostrano naturali 20 e 1 e ordinano i dadi per facce", async () => {
    stats.mockResolvedValue({ stats: { d20: { '1': 2, '20': 5 }, d4: { '4': 1 }, d12: { '12': 1 } } })
    renderWithProviders(<DiceStats />)
    const nat20 = await screen.findByText('character.dice_stats.nat20')
    expect(nat20.nextElementSibling).toHaveTextContent('5')
    expect(screen.getByText('character.dice_stats.nat1').nextElementSibling).toHaveTextContent('2')
    const nomi = ['d4', 'd12', 'd20'].map((k) => screen.getByText(k))
    nomi.slice(1).forEach((el, i) => expect(nomi[i].compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy())
  })

  // caccia: {"id": "CB-1488", "fonte": "invariante: un fetch fallito non è nessun tiro registrato", "zona": "flusso:dadi", "voce": "contratto", "copre": ["route:/char/:id/dice/stats"]}
  it("se le statistiche non si caricano non dice che non ci sono tiri", async () => {
    stats.mockRejectedValue(new TypeError('Failed to fetch'))
    renderWithProviders(<DiceStats />)
    expect(await screen.findByText('common.offline_unavailable')).toBeInTheDocument()
    expect(screen.queryByText('character.dice_stats.empty_title')).not.toBeInTheDocument()
  })

  // caccia: {"id": "CB-1494", "fonte": "invariante: nessun elenco di dadi sommato non dà il totale (stessa causa di CB-1483)", "zona": "flusso:dadi", "voce": "normale", "copre": ["route:/char/:id/dice"]}
  it.fails("nello storico un d100 non elenca i due d10 accanto al percentile", async () => {
    getChar.mockResolvedValue({ id: 7, name: 'Eroe', ability_scores: [] })
    diceHistory.mockResolvedValue([{ notation: '1d100', rolls: [4, 7], total: 47, timestamp: '2026-11-24T09:00:00', source: 'manual', label: null }])
    renderWithProviders(<Dice />)
    await screen.findByText('1d100')
    const elenco = screen.queryByText(/^\[[\d+]+\]$/)
    if (elenco) expect((elenco.textContent ?? '').match(/\d+/g)!.reduce((s, n) => s + Number(n), 0)).toBe(47)
  })

  // caccia: {"id": "CB-1495", "fonte": "invariante: nessun elenco di dadi sommato non dà il totale (stessa causa di CB-1483)", "zona": "flusso:dadi", "voce": "normale", "copre": ["route:/char/:id/dice"]}
  it.fails("il pannello del risultato di un d100 non elenca i due d10 accanto al percentile", async () => {
    getChar.mockResolvedValue({ id: 7, name: 'Eroe', ability_scores: [] })
    diceHistory.mockResolvedValue([])
    rollMock.mockResolvedValue([{ kind: 'd100', notation: '1d100', rolls: [4, 7], total: 47 }])
    renderWithProviders(<Dice />)
    await userEvent.click(await screen.findByText('d100'))
    await screen.findByText('47')
    const elenco = screen.queryByText(/^\[[\d +]+\]$/)
    if (elenco) expect((elenco.textContent ?? '').match(/\d+/g)!.reduce((s, n) => s + Number(n), 0)).toBe(47)
  })

  // caccia: {"id": "CB-1496", "fonte": "invariante: nessun elenco di dadi sommato non dà il totale (stessa causa di CB-1483)", "zona": "flusso:dadi", "voce": "normale", "copre": ["route:/char/:id/dice"]}
  it.fails("la finestra del risultato di un d100 non elenca i due d10 accanto al percentile", async () => {
    renderWithProviders(<DicePoolResultModal charId={7} initialResults={[{ kind: 'd100', notation: '1d100', rolls: [4, 7], total: 47 }]} inspirationAvailable={false} onClose={() => {}} />)
    await screen.findByText('47')
    const elenco = screen.queryByText(/^\[[\d+]+\]$/)
    if (elenco) expect((elenco.textContent ?? '').match(/\d+/g)!.reduce((s, n) => s + Number(n), 0)).toBe(47)
  })

  // caccia: {"id": "CB-1497", "fonte": "invariante: un invio fallito non resta in silenzio", "zona": "flusso:dadi", "voce": "ripetizione", "copre": ["POST /characters/{char_id}/dice/post-to-chat", "route:/char/:id/dice"]}
  it.fails("se «Manda al bot» fallisce compare un avviso", async () => {
    tg.dentro = true
    getChar.mockResolvedValue({ id: 7, name: 'Eroe', ability_scores: [] })
    diceHistory.mockResolvedValue([])
    rollMock.mockResolvedValue([{ kind: 'd6', notation: '2d6', rolls: [3, 5], total: 8 }])
    postToChat.mockRejectedValue(new Error('502'))
    renderWithProviders(<Dice />)
    await userEvent.click(await screen.findByText('2d6'))
    await userEvent.click(await screen.findByText('character.dice.send_to_bot'))
    await vi.waitFor(() => expect(postToChat).toHaveBeenCalledTimes(1))
    await vi.waitFor(() => expect(toastFn.error.mock.calls.length + toastFn.warning.mock.calls.length).toBeGreaterThan(0), { timeout: 800 })
  })
})
