import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import AddConditionSheet from '@/pages/session/AddConditionSheet'
import type { CharacterLiveSnapshot, CombatantLive, EncounterLive } from '@/types'

const { applySpy } = vi.hoisted(() => ({ applySpy: vi.fn() }))

vi.mock('@/api/client', () => ({
  api: { sessions: { encounter: { applyCondition: applySpy } } },
  ApiError: class ApiError extends Error {
    constructor(public status: number, public detail: unknown) { super('api error') }
  },
}))
vi.mock('@/components/ui/Sheet', () => ({
  default: ({ open, children }: { open: boolean; children: React.ReactNode }) => (open ? <div>{children}</div> : null),
}))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('sonner', () => ({ toast: { error: vi.fn(), success: vi.fn() } }))

const comb = (over: Partial<CombatantLive>): CombatantLive => ({
  id: 1, kind: 'monster', character_id: null, owner_user_id: null, name: 'Goblin',
  initiative: 10, initiative_die: 8, initiative_mod: 2, sort_order: 10, is_dead: false,
  conditions: {}, current_hp: 7, max_hp: 7, ac: 15, hp_bucket: null, ...over,
})
const goblin = comb({ id: 1, name: 'Goblin' })
const orc = comb({ id: 2, name: 'Orco' })
const hero = comb({ id: 3, kind: 'pc', character_id: 7, name: 'Eroe' })
const encounter = {
  id: 9, mode: 'full', status: 'active', round: 1, active_combatant_id: 3,
  created_at: '', started_at: '', ended_at: null, combatants: [hero, goblin, orc],
} as EncounterLive
const snap = (conc: boolean) => ({ id: 7, name: 'Eroe', is_concentrating: conc }) as CharacterLiveSnapshot

function setup(conc = false) {
  const onClose = vi.fn()
  render(
    <QueryClientProvider client={new QueryClient()}>
      <AddConditionSheet
        sessionId={5} encounter={encounter} target={goblin}
        liveCharacters={[snap(conc)]} onClose={onClose}
      />
    </QueryClientProvider>,
  )
  return { onClose }
}

const user = userEvent.setup()
const pick = async (trigger: string, option: string) => {
  await user.click(screen.getByText(trigger))
  await user.click(screen.getByRole('radio', { name: option }))
}

describe('AddConditionSheet', () => {
  beforeEach(() => { applySpy.mockReset().mockResolvedValue(encounter) })

  it('invia scadenza "fine del prossimo turno della fonte" + TS COS 15 a fine turno', async () => {
    const { onClose } = setup()
    await pick('session.combat.cond.pick', 'character.conditions.poisoned')
    await pick('session.combat.cond.source_none', 'Eroe')
    await user.click(screen.getByRole('radio', { name: 'session.combat.cond.dur_end' }))
    await user.click(screen.getByRole('radio', { name: 'session.combat.cond.of_source' }))
    await user.click(screen.getByRole('radio', { name: 'character.ability.constitution_short' }))
    await user.type(screen.getByRole('textbox'), '15')
    await user.click(screen.getByRole('radio', { name: 'session.combat.cond.save_edge_end' }))
    await user.click(screen.getByRole('button', { name: 'session.combat.cond.submit' }))
    await waitFor(() => expect(applySpy).toHaveBeenCalledWith(5, 1, {
      slug: 'poisoned',
      expiry: { anchor: 'source', edge: 'end', count: 1 },
      save: { ability: 'constitution', dc: 15, edge: 'end' },
      source_combatant_id: 3,
      ends_with_concentration: false,
    }))
    await waitFor(() => expect(onClose).toHaveBeenCalled())
  })

  it('checkbox concentrazione: nascosta con fonte mostro, visibile con PG concentrato', async () => {
    setup(true)
    await pick('session.combat.cond.pick', 'character.conditions.charmed')
    await pick('session.combat.cond.source_none', 'Orco')
    expect(screen.queryByText('session.combat.cond.concentration')).not.toBeInTheDocument()
    await pick('Orco', 'Eroe')
    expect(screen.getByText('session.combat.cond.concentration')).toBeInTheDocument()
  })

  it('errore 422 source_not_concentrating mostrato inline', async () => {
    const { ApiError } = await import('@/api/client')
    applySpy.mockRejectedValue(new ApiError(422, { code: 'source_not_concentrating' }))
    const { onClose } = setup(true)
    await pick('session.combat.cond.pick', 'character.conditions.charmed')
    await pick('session.combat.cond.source_none', 'Eroe')
    await user.click(screen.getByRole('switch'))
    await user.click(screen.getByRole('button', { name: 'session.combat.cond.submit' }))
    expect(await screen.findByText('session.combat.cond.source_not_concentrating')).toBeInTheDocument()
    expect(applySpy.mock.calls[0][2].ends_with_concentration).toBe(true)
    expect(onClose).not.toHaveBeenCalled()
  })

  it('spossatezza: stepper del livello invia value, niente scadenza/TS', async () => {
    setup()
    await pick('session.combat.cond.pick', 'character.conditions.exhaustion_condition')
    expect(screen.queryByText('session.combat.cond.duration')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '+' }))
    await user.click(screen.getByRole('button', { name: 'session.combat.cond.submit' }))
    await waitFor(() => expect(applySpy).toHaveBeenCalledWith(5, 1, { slug: 'exhaustion', value: 2 }))
  })
})
