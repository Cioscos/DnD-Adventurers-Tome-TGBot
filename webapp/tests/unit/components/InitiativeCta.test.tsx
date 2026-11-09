import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import InitiativeCta from '@/pages/session/InitiativeCta'
import type { CombatantLive } from '@/types'

const { rollSpy, rollOptionsSpy, lastRollSpy, infoSpy, getSpy } = vi.hoisted(() => ({
  rollSpy: vi.fn(), rollOptionsSpy: vi.fn(), lastRollSpy: vi.fn(), infoSpy: vi.fn(), getSpy: vi.fn(),
}))

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/api/client', () => ({
  api: { characters: { rollOptions: rollOptionsSpy, lastRollOptions: lastRollSpy, get: getSpy }, sessions: { encounter: { rollInitiative: rollSpy } } },
}))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn(), info: infoSpy } }))
// animazione 3D disattivata nel test -> die undefined, niente overlay
vi.mock('@/store/diceSettings', () => ({
  useDiceSettings: (sel: (s: { animate3d: boolean }) => unknown) => sel({ animate3d: false }),
}))
vi.mock('@/hooks/useReducedMotion', () => ({ useReducedMotion: () => false }))
vi.mock('@/dice/useDiceAnimation', () => ({
  useDiceAnimation: () => ({ playAndCollect: vi.fn() }),
}))

const combatant = (over: Partial<CombatantLive> = {}): CombatantLive => ({
  id: 5, kind: 'pc', character_id: 7, owner_user_id: 99, name: 'Eroe',
  initiative: null, initiative_die: null, initiative_mod: 3,
  sort_order: null, is_dead: false, conditions: {},
  current_hp: null, max_hp: null, ac: null, hp_bucket: null,
  ...over,
})

function renderCta(c: CombatantLive) {
  const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <InitiativeCta sessionId={42} combatant={c} />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  rollSpy.mockReset()
  rollOptionsSpy.mockReset()
  rollOptionsSpy.mockResolvedValue([])
  lastRollSpy.mockReset()
  infoSpy.mockReset()
  getSpy.mockReset()
  getSpy.mockResolvedValue({ rules_edition: '2014', abilities: [{ feature_key: 'monk.perfect_self', name: 'Perfezione Interiore' }] })
})

describe('InitiativeCta', () => {
  it('mostra il bottone e invia il tiro', async () => {
    rollSpy.mockResolvedValue({})
    renderCta(combatant())
    await userEvent.click(screen.getByText('session.combat.roll_initiative'))
    await waitFor(() => expect(rollSpy).toHaveBeenCalledWith(42, 5, undefined))
  })

  it('dopo il tiro dice il nome del privilegio e che cosa ha fatto (Perfezione Interiore: 4 ki), non la chiave', async () => {
    rollSpy.mockResolvedValue({ initiative_roll: {
      mode_applied: 'normal', notes: ['feature:monk.perfect_self'],
      option_result: { keys: [], effects: [{ it: 'Perfezione Interiore: recuperi 4 punti ki.', en: 'Perfect Self: you regain 4 ki points.' }] },
    } })
    renderCta(combatant())
    await waitFor(() => expect(getSpy).toHaveBeenCalledWith(7))  // la pagina di sessione non ha caricato il personaggio
    await userEvent.click(screen.getByText('session.combat.roll_initiative'))
    await waitFor(() => expect(infoSpy).toHaveBeenCalledWith('Perfezione Interiore · Perfezione Interiore: recuperi 4 punti ki.'))
  })

  it('già tirata: mostra il riepilogo, niente bottone', () => {
    renderCta(combatant({ initiative: 17, initiative_die: 14 }))
    expect(screen.queryByText('session.combat.roll_initiative')).not.toBeInTheDocument()
    expect(screen.getByText('session.combat.rolled_detail')).toBeInTheDocument()
    // Riaperta più tardi: non è il tiro appena fatto, i privilegi non si offrono.
    expect(rollOptionsSpy).not.toHaveBeenCalled()
  })

  it('subito dopo il tiro offre i privilegi usabili a esito noto', async () => {
    rollSpy.mockResolvedValue({})
    rollOptionsSpy.mockResolvedValue([{
      key: 'add', phase: 'after_roll', label: 'Somma?', dice: null, bonus: 3, mode: null, multiplier: null, slot: null,
      once_per_turn: false, auto_fail: false, cost: null, dice_cost: 0, needs: null, after: 'add',
    }])
    lastRollSpy.mockResolvedValue({ total: 20 })
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
    const ui = (c: CombatantLive) => <QueryClientProvider client={qc}><InitiativeCta sessionId={42} combatant={c} /></QueryClientProvider>
    const view = render(ui(combatant()))
    await userEvent.click(screen.getByText('session.combat.roll_initiative'))
    await waitFor(() => expect(rollSpy).toHaveBeenCalled())
    view.rerender(ui(combatant({ initiative: 17, initiative_die: 14 })))
    await userEvent.click(await screen.findByRole('button', { name: /Somma\?/ }))
    await waitFor(() => expect(lastRollSpy).toHaveBeenCalledWith(7, expect.objectContaining({ options: ['add'] })))
  })
})
