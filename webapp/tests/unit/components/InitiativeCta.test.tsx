import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import InitiativeCta from '@/pages/session/InitiativeCta'
import type { CombatantLive } from '@/types'

const { rollSpy } = vi.hoisted(() => ({ rollSpy: vi.fn() }))

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/api/client', () => ({
  api: { sessions: { encounter: { rollInitiative: rollSpy } } },
}))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
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

beforeEach(() => rollSpy.mockReset())

describe('InitiativeCta', () => {
  it('mostra il bottone e invia il tiro', async () => {
    rollSpy.mockResolvedValue({})
    renderCta(combatant())
    await userEvent.click(screen.getByText('session.combat.roll_initiative'))
    await waitFor(() => expect(rollSpy).toHaveBeenCalledWith(42, 5, undefined))
  })

  it('già tirata: mostra il riepilogo, niente bottone', () => {
    renderCta(combatant({ initiative: 17, initiative_die: 14 }))
    expect(screen.queryByText('session.combat.roll_initiative')).not.toBeInTheDocument()
    expect(screen.getByText('session.combat.rolled_detail')).toBeInTheDocument()
  })
})
