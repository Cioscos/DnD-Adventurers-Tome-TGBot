import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderWithProviders } from '../utils/renderWithProviders'
import RestSheet from '@/components/character/RestSheet'
import QuickActions from '@/components/character/QuickActions'
import { useRest } from '@/hooks/useRest'
import type { CharacterFull } from '@/types'

const { restPreview, spendHitDice } = vi.hoisted(() => ({ restPreview: vi.fn(), spendHitDice: vi.fn() }))

vi.mock('@/api/client', async (orig) => ({
  ...(await orig<typeof import('@/api/client')>()), api: { characters: { restPreview, spendHitDice } },
}))
vi.mock('@/dice/useDiceAnimation', () => ({ useDiceAnimation: () => ({ playAndCollect: vi.fn() }) }))
vi.mock('@/pages/spells/useCastFlow', () => ({ useCastFlow: () => ({ isSpellPending: () => false, beginCast: vi.fn(), dialogs: null }) }))
vi.mock('@/dice/useAnimatedRoll', () => ({ useAnimatedRoll: () => async () => undefined }))
vi.mock('react-i18next', async (orig) => ({
  ...(await orig<typeof import('react-i18next')>()), useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }),
}))
vi.mock('@/components/ui/Sheet', () => ({ default: (p: { open: boolean; children: unknown }) => (p.open ? p.children : null) }))
vi.mock('@/components/ui/ConfirmSheet', () => ({
  default: (p: { open: boolean; body?: unknown }) => (p.open ? <div data-testid="conferma">{p.body as never}</div> : null),
}))

const char = {
  id: 7, rules_edition: '2014', hit_points: 20, current_hit_points: 10,
  settings: { quick_actions: [{ type: 'hit_die', classId: 1 }] },
  classes: [{ id: 1, class_name: 'fighter', level: 3, hit_die: 10, hit_dice_used: 0 }],
} as unknown as CharacterFull

afterEach(() => { vi.clearAllMocks() })

describe('caccia: riposo', () => {
  // caccia: {"id": "CB-008", "fonte": "invariante: una scelta annullata non vale per il riposo dopo", "zona": "flusso:riposo", "voce": "annullamento", "copre": []}
  it('chiudere il riposo breve azzera le scelte', () => {
    const qc = new QueryClient()
    const { result } = renderHook(() => useRest(7, char), {
      wrapper: ({ children }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>,
    })
    act(() => {
      result.current.openShort(); result.current.setInterrupted(true); result.current.setRecovery({ 1: 1 })
      result.current.setArcane({ 1: 1 }); result.current.setRestoration(2); result.current.setMemorize({ out: 1, into: 2 })
      result.current.setResistance('fire'); result.current.setTempAllies([3])
    })
    act(() => result.current.closeShort())
    const r = result.current
    expect([r.shortRestOpen, r.interrupted, r.recovery, r.arcane, r.restoration, r.memorize, r.resistance, r.tempAllies])
      .toEqual([false, false, {}, {}, 0, null, '', []])
  })

  // caccia: {"id": "CB-025", "fonte": "invariante: una scelta annullata non vale per il riposo dopo", "zona": "flusso:riposo", "voce": "annullamento", "copre": []}
  it('annullare il riposo lungo azzera anche resistenza e alleati', () => {
    const qc = new QueryClient()
    const { result } = renderHook(() => useRest(7, char), {
      wrapper: ({ children }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>,
    })
    act(() => { result.current.openLong(); result.current.setResistance('fire'); result.current.setTempAllies([3]) })
    act(() => result.current.cancelLongRest())
    expect([result.current.resistance, result.current.tempAllies]).toEqual(['', []])
  })

  // caccia: {"id": "CB-013", "fonte": "CLAUDE.md · ate_and_drank=false blocca la riduzione nel 2014", "zona": "flusso:riposo", "voce": "interazione", "copre": []}
  it('senza mangiare e bere l\'anteprima del riposo lungo si aggiorna', async () => {
    restPreview.mockImplementation(async (_id: number, _tipo: string, mangiato = true) => ({
      hp_gain: 0, hit_dice_regain: {}, slots: {}, pact_slots: 0, abilities: [], homebrew_resources: [], item_charges: [],
      exhaustion_change: mangiato ? -1 : 0, ends_concentration: false,
    }))
    renderWithProviders(<RestSheet char={char} open onClose={() => {}} />)
    await userEvent.click(screen.getByText('character.quick_actions.rest_long'))
    expect(await screen.findByText('character.rest_preview.exhaustion')).toBeInTheDocument()
    await userEvent.click(screen.getAllByRole('switch').at(-1)!)
    await waitFor(() => expect(screen.queryByText('character.rest_preview.exhaustion')).toBeNull())
    expect(screen.getByText('character.rest_preview.nothing')).toBeInTheDocument()
  })

  // caccia: {"id": "CB-024", "fonte": "invariante: un morto non spende dadi vita; CLAUDE.md · 2024 nessun riposo a 0 PF", "zona": "flusso:riposo", "voce": "edizioni", "copre": []}
  it.each([
    ['morto', { is_dead: true, current_hit_points: 0 }, true],
    ['2024 a 0 PF', { rules_edition: '2024', current_hit_points: 0 }, true],
    ['2014 a 0 PF', { current_hit_points: 0 }, false],
    ['ferito', {}, false],
  ])('azione rapida del dado vita: %s', (_nome, cambio, bloccata) => {
    renderWithProviders(<QuickActions char={{ ...char, ...cambio } as CharacterFull} />)
    const tasto = screen.getByText('d10 · dnd.classes.fighter').closest('button') as HTMLButtonElement
    expect(tasto.disabled).toBe(bloccata)
  })
})
