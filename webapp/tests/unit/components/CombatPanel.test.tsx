import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import CombatPanel from '@/pages/session/CombatPanel'
import type { CombatantLive, EncounterLive, GameSessionLive } from '@/types'

const { toastSpy, hapticSpy, nextTurnSpy, turnStateSpy, navigateSpy } = vi.hoisted(() => ({
  navigateSpy: vi.fn(),
  toastSpy: vi.fn(),
  hapticSpy: vi.fn(),
  nextTurnSpy: vi.fn(),
  turnStateSpy: vi.fn(),
}))

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useNavigate: () => navigateSpy }
})
vi.mock('sonner', () => ({ toast: { success: toastSpy, error: vi.fn() } }))
vi.mock('@/auth/telegram', () => ({
  haptic: new Proxy({}, { get: () => hapticSpy }),
  telegramConfirm: (_m: string, cb: (ok: boolean) => void) => cb(true),
}))
vi.mock('@/api/client', () => ({
  ApiError: class ApiError extends Error {
    constructor(public status: number, public detail: unknown) { super('api error') }
  },
  api: {
    sessions: {
      encounter: new Proxy({}, {
        get: (_t, k) => (k === 'nextTurn' ? nextTurnSpy : vi.fn().mockResolvedValue({})),
      }),
    },
    characters: { turnState: turnStateSpy },
  },
}))
vi.mock('@/components/SaveRollSheet', () => ({
  default: ({ saves }: { saves: { id: number }[] }) => <div data-testid="save-roll-sheet">{saves.length}</div>,
}))
vi.mock('@/store/diceSettings', () => ({
  useDiceSettings: (sel: (s: { animate3d: boolean }) => unknown) => sel({ animate3d: false }),
}))
vi.mock('@/hooks/useReducedMotion', () => ({ useReducedMotion: () => false }))
vi.mock('@/dice/useDiceAnimation', () => ({
  useDiceAnimation: () => ({ playAndCollect: vi.fn() }),
}))
vi.mock('@/components/ui/ConditionBadge', () => ({ default: () => null }))
vi.mock('@/styles/motion', () => ({ spring: new Proxy({}, { get: () => ({}) }), ease: { inkSpread: [0, 0, 1, 1] } }))
vi.mock('framer-motion', async () => {
  const React = await import('react')
  const MOTION = new Set(['initial', 'animate', 'exit', 'transition', 'variants', 'whileTap', 'whileHover', 'drag', 'layout'])
  const make = (tag: string) => (props: Record<string, unknown>) => {
    const clean: Record<string, unknown> = {}
    for (const k in props) if (!MOTION.has(k)) clean[k] = props[k]
    return React.createElement(tag, clean)
  }
  return {
    m: new Proxy({}, { get: (_t: object, tag: string | symbol) => make(String(tag)) }),
    AnimatePresence: ({ children }: { children?: React.ReactNode }) => children,
    // Sheet usa il drag-to-dismiss dal giro r2.
    useDragControls: () => ({ start: () => {} }),
    useReducedMotion: () => true,
  }
})

const MY_ID = 99
const GM_ID = 1

const combatant = (over: Partial<CombatantLive>): CombatantLive => ({
  id: 1, kind: 'pc', character_id: 7, owner_user_id: MY_ID, name: 'Eroe',
  initiative: null, initiative_die: null, initiative_mod: 3,
  sort_order: null, is_dead: false, conditions: {},
  current_hp: null, max_hp: null, ac: null, hp_bucket: null,
  ...over,
})

const encounter = (over: Partial<EncounterLive>): EncounterLive => ({
  id: 1, mode: 'full', status: 'setup', round: 1, active_combatant_id: null,
  created_at: '2026-06-09T10:00:00', started_at: null, ended_at: null,
  combatants: [combatant({})],
  ...over,
})

const live = (enc: EncounterLive | null): GameSessionLive => ({
  id: 42, code: 'ABC123', gm_user_id: GM_ID, gm_display_name: 'GM',
  status: 'active', title: null, created_at: '', last_activity_at: '',
  closed_at: null, participants: [], live_characters: [], encounter: enc,
})

function renderPanel(l: GameSessionLive, opts: { amGm?: boolean; myUserId?: number } = {}) {
  const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <CombatPanel
        live={l}
        sessionId={42}
        amGm={opts.amGm ?? false}
        myUserId={opts.myUserId ?? MY_ID}
      />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  toastSpy.mockReset()
  hapticSpy.mockReset()
  nextTurnSpy.mockReset().mockResolvedValue({})
  turnStateSpy.mockReset().mockResolvedValue({ pending_saves: [] })
  navigateSpy.mockReset()
})

describe('CombatPanel', () => {
  it('setup, giocatore col proprio PG senza iniziativa: CTA visibile', () => {
    renderPanel(live(encounter({})))
    expect(screen.getByText('session.combat.roll_initiative')).toBeInTheDocument()
  })

  it('setup, GM: «Avvia» nel dock e aggiungi mostro nel menu ⋯', () => {
    renderPanel(live(encounter({})), { amGm: true, myUserId: GM_ID })
    expect(screen.getByText('session.combat.start')).toBeInTheDocument()
    expect(screen.queryByText('session.combat.add_monster')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'session.combat.menu' }))
    expect(screen.getByText('session.combat.add_monster')).toBeInTheDocument()
    expect(screen.getByText('session.combat.sync_pcs')).toBeInTheDocument()
    expect(screen.queryByText('session.combat.end')).not.toBeInTheDocument()
  })

  it('attivo: mostra il round e il nastro', () => {
    const c = combatant({ initiative: 17, sort_order: 10 })
    renderPanel(live(encounter({ status: 'active', round: 2, active_combatant_id: c.id, combatants: [c] })))
    expect(screen.getByText('session.combat.round_label')).toBeInTheDocument()
    expect(screen.getByTestId('round-ribbon')).toBeInTheDocument()
  })

  describe('vista combattimento', () => {
    const me = combatant({ id: 1, initiative: 15, sort_order: 20 })
    const goblin = combatant({
      id: 2, kind: 'monster', character_id: null, owner_user_id: null,
      name: 'Goblin', initiative: 17, sort_order: 10, max_hp: 7, current_hp: 7, ac: 15,
    })
    const ally = combatant({ id: 3, character_id: 8, owner_user_id: 50, name: 'Elara', initiative: 12, sort_order: 30 })
    const active = (activeId: number, combatants = [goblin, me, ally]) =>
      live(encounter({ status: 'active', active_combatant_id: activeId, combatants }))

    it('giocatore: «Apri il mio turno» porta alla pagina Turno del suo PG', () => {
      renderPanel(active(2))
      const card = screen.getByTestId('my-combatant-card')
      expect(card).toHaveTextContent('session.combat.turns_until_mine')
      fireEvent.click(screen.getByText('session.combat.open_my_turn'))
      expect(navigateSpy).toHaveBeenCalledWith('/char/7/turn')
    })

    it('giocatore: «Termina turno» solo durante il proprio turno', () => {
      const { unmount } = renderPanel(active(2))
      expect(screen.queryByText('session.combat.end_my_turn')).not.toBeInTheDocument()
      unmount()
      renderPanel(active(1))
      expect(screen.getByText('session.combat.end_my_turn')).toBeInTheDocument()
    })

    it('giocatore con il secondo turno dei Riflessi da Furfante: la sua scheda è quella del PG, anche se la riga viene prima', () => {
      // Il secondo turno è una riga a parte, senza `character_id`: «Termina turno» e «Apri il mio turno» restano del PG.
      const extra = combatant({ id: 9, character_id: null, name: 'Eroe (Riflessi da Furfante)', initiative: 5, sort_order: 5 })
      renderPanel(active(9, [extra, goblin, me, ally]))
      expect(screen.getByText('session.combat.end_my_turn')).toBeInTheDocument()
      fireEvent.click(screen.getByText('session.combat.open_my_turn'))
      expect(navigateSpy).toHaveBeenCalledWith('/char/7/turn')
    })

    it('giocatore senza PG nel combattimento: niente card, nastro e tracciato sì', () => {
      renderPanel(active(2, [goblin, ally]))
      expect(screen.queryByTestId('my-combatant-card')).not.toBeInTheDocument()
      expect(screen.getByTestId('round-ribbon')).toBeInTheDocument()
      expect(screen.getAllByTestId('combatant-row')).toHaveLength(2)
    })

    it('GM: menu ⋯ con aggiungi mostro, sincronizza e termina', () => {
      renderPanel(active(2), { amGm: true, myUserId: GM_ID })
      fireEvent.click(screen.getByRole('button', { name: 'session.combat.menu' }))
      expect(screen.getByText('session.combat.add_monster')).toBeInTheDocument()
      expect(screen.getByText('session.combat.sync_pcs')).toBeInTheDocument()
      expect(screen.getByText('session.combat.end')).toBeInTheDocument()
    })

    it('GM: la card di chi agisce non ha bottoni e il dock ha «Turno successivo»', () => {
      renderPanel(active(2), { amGm: true, myUserId: GM_ID })
      const card = screen.getByTestId('active-combatant-card')
      expect(card).toHaveTextContent('Goblin')
      expect(card.querySelectorAll('button')).toHaveLength(0)
      expect(screen.getByText('session.combat.next_turn')).toBeInTheDocument()
    })

    it('GM: nel tracciato la riga di chi agisce resta compatta (i dettagli sono nella card)', () => {
      renderPanel(active(2), { amGm: true, myUserId: GM_ID })
      const tracked = screen.getAllByTestId('combatant-row').filter((r) => !r.closest('[data-testid="active-combatant-card"]'))
      const activeRow = tracked.find((r) => r.dataset.active === 'true')!
      expect(activeRow.querySelector('[data-testid="hp-bar"]')).toBeNull()
    })

    it('giocatore: la riga di chi agisce è espansa', () => {
      renderPanel(active(2, [{ ...goblin, hp_bucket: 'healthy' }, me, ally]))
      const activeRow = screen.getAllByTestId('combatant-row').find((r) => r.dataset.active === 'true')!
      expect(activeRow.querySelector('[data-testid="hp-bucket-bar"]')).not.toBeNull()
    })

    it("scorre solo la lista d'iniziativa: blocco in alto e barra in basso restano fermi", () => {
      renderPanel(active(2), { amGm: true, myUserId: GM_ID })
      const list = screen.getByTestId('combat-scroll')
      expect(list.className).toContain('overflow-y-auto')
      screen.getAllByTestId('combatant-row')
        .filter((r) => !r.closest('[data-testid="active-combatant-card"]'))
        .forEach((r) => expect(list).toContainElement(r))
      const top = screen.getByTestId('combat-topbar')
      expect(top).toContainElement(screen.getByText('session.combat.round_label'))
      expect(top).toContainElement(screen.getByRole('button', { name: 'session.combat.menu' }))
      expect(top).toContainElement(screen.getByTestId('round-ribbon'))
      expect(top).toContainElement(screen.getByTestId('active-combatant-card'))
      const dock = screen.getByTestId('combat-dock')
      expect(dock).toContainElement(screen.getByText('session.combat.next_turn'))
      expect(list).not.toContainElement(dock)
    })

    it('i morti sono elencati dopo i vivi', () => {
      const deadGob = { ...goblin, is_dead: true }
      renderPanel(active(1, [deadGob, me, ally]))
      const rows = screen.getAllByTestId('combatant-row')
      expect(rows.map((r) => r.dataset.dead)).toEqual(['false', 'false', 'true'])
    })
  })

  it('toast «tocca a te» quando il turno passa al mio PG', () => {
    const me = combatant({ id: 1, initiative: 17, sort_order: 10 })
    const goblin = combatant({
      id: 2, kind: 'monster', character_id: null, owner_user_id: null,
      name: 'Goblin', initiative: 12, sort_order: 20,
    })
    const base = encounter({ status: 'active', combatants: [me, goblin] })
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
    const panel = (activeId: number) => (
      <QueryClientProvider client={qc}>
        <CombatPanel
          live={live({ ...base, active_combatant_id: activeId })}
          sessionId={42}
          amGm={false}
          myUserId={MY_ID}
        />
      </QueryClientProvider>
    )
    // turno del goblin: nessun toast
    const { rerender } = render(panel(2))
    expect(toastSpy).not.toHaveBeenCalled()
    // il turno passa al mio PG (id 1) -> toast
    rerender(panel(1))
    expect(toastSpy).toHaveBeenCalledWith('session.combat.your_turn', expect.anything())
  })

  describe('TS a fine turno', () => {
    const me = combatant({ id: 1, initiative: 17, sort_order: 10 })
    const snap = {
      id: 7, name: 'Eroe', class_summary: '', total_level: 5, hit_points: 22,
      current_hit_points: 22, temp_hp: 0, ac: 10, heroic_inspiration: false,
      hp_bucket: null, armor_category: null,
      condition_effects: [{
        slug: 'prone', save_ability: 'constitution', save_dc: 13, save_edge: 'end' as const,
        ends_with_concentration: false, applied_by_gm: true,
      }],
    }
    const myTurn = () => ({
      ...live(encounter({ status: 'active', active_combatant_id: 1, combatants: [me] })),
      live_characters: [snap],
    })

    it('durante il mio turno mostra il promemoria del TS', () => {
      renderPanel(myTurn())
      expect(screen.getByTestId('end-turn-save-hint')).toHaveTextContent('session.combat.end_turn_save_hint')
    })

    it('«Termina turno» passa il turno e apre subito il TS appena nato', async () => {
      turnStateSpy.mockResolvedValue({
        pending_saves: [{ id: 3, slug: 'prone', ability: 'constitution', dc: 13, status: 'pending', created_at: '' }],
      })
      // Come nell'app: staleTime globale e turn-state già in cache dal polling, senza TS.
      const qc = new QueryClient({ defaultOptions: { queries: { staleTime: 30_000 }, mutations: { retry: false } } })
      qc.setQueryData(['turn-state', 7], { pending_saves: [] })
      render(
        <QueryClientProvider client={qc}>
          <CombatPanel live={myTurn()} sessionId={42} amGm={false} myUserId={MY_ID} />
        </QueryClientProvider>,
      )
      fireEvent.click(screen.getByText('session.combat.end_my_turn'))
      expect(await screen.findByTestId('save-roll-sheet')).toHaveTextContent('1')
      expect(nextTurnSpy).toHaveBeenCalledWith(42)
      expect(turnStateSpy).toHaveBeenCalledWith(7)
    })

    it('senza TS nati il turno passa e nessuna scheda si apre', async () => {
      renderPanel(myTurn())
      fireEvent.click(screen.getByText('session.combat.end_my_turn'))
      await waitFor(() => expect(turnStateSpy).toHaveBeenCalled())
      expect(screen.queryByTestId('save-roll-sheet')).not.toBeInTheDocument()
    })
  })
})
