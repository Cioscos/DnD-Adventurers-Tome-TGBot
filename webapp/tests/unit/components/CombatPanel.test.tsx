import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import CombatPanel from '@/pages/session/CombatPanel'
import type { CombatantLive, EncounterLive, GameSessionLive } from '@/types'

const { toastSpy, hapticSpy } = vi.hoisted(() => ({
  toastSpy: vi.fn(),
  hapticSpy: vi.fn(),
}))

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
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
  api: { sessions: { encounter: new Proxy({}, { get: () => vi.fn().mockResolvedValue({}) }) } },
}))
vi.mock('@/store/diceSettings', () => ({
  useDiceSettings: (sel: (s: { animate3d: boolean }) => unknown) => sel({ animate3d: false }),
}))
vi.mock('@/hooks/useReducedMotion', () => ({ useReducedMotion: () => false }))
vi.mock('@/dice/useDiceAnimation', () => ({
  useDiceAnimation: () => ({ playAndCollect: vi.fn() }),
}))
vi.mock('@/components/ui/ConditionBadge', () => ({ default: () => null }))
vi.mock('@/styles/motion', () => ({ spring: new Proxy({}, { get: () => ({}) }) }))
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
})

describe('CombatPanel', () => {
  it('senza incontro: bottone start solo per il GM', () => {
    const { unmount } = renderPanel(live(null), { amGm: true })
    expect(screen.getByText('session.combat.start_encounter')).toBeInTheDocument()
    unmount()
    renderPanel(live(null), { amGm: false })
    expect(screen.queryByText('session.combat.start_encounter')).not.toBeInTheDocument()
  })

  it('setup, giocatore col proprio PG senza iniziativa: CTA visibile', () => {
    renderPanel(live(encounter({})))
    expect(screen.getByText('session.combat.roll_initiative')).toBeInTheDocument()
  })

  it('setup, GM: controlli aggiungi/avvia visibili', () => {
    renderPanel(live(encounter({})), { amGm: true, myUserId: GM_ID })
    expect(screen.getByText('session.combat.add_monster')).toBeInTheDocument()
    expect(screen.getByText('session.combat.start')).toBeInTheDocument()
  })

  it('attivo: TurnBar con round e nome del combattente attivo', () => {
    const c = combatant({ initiative: 17, sort_order: 10 })
    renderPanel(live(encounter({ status: 'active', round: 2, active_combatant_id: c.id, combatants: [c] })))
    expect(screen.getByText('session.combat.round_label')).toBeInTheDocument()
    expect(screen.getByText('session.combat.turn_of')).toBeInTheDocument()
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
})
