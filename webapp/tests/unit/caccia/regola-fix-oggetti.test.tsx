import { describe, expect, it, vi } from 'vitest'
import { renderHook, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import { RollOptionsHost } from '@/components/rules/RollOptionsPrompt'
import { useAttackRoll } from '@/hooks/useWeaponAttackFlow'
import type { RollOption } from '@/api/client'

const { rollOptions, attackUnarmed, turnState } = vi.hoisted(() => ({
  rollOptions: vi.fn(), attackUnarmed: vi.fn(), turnState: vi.fn(),
}))
vi.mock('@/api/client', () => ({
  api: { characters: { rollOptions, turnState }, items: { attackUnarmed } },
  ApiError: class extends Error {},
}))
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; children?: unknown }) => (p.open ? React.createElement('div', null, p.children) : null) }
})
vi.mock('react-i18next', async (orig) => ({
  ...(await orig<typeof import('react-i18next')>()), useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }),
}))
vi.mock('sonner', () => ({ toast: { warning: vi.fn(), error: vi.fn(), success: vi.fn(), info: vi.fn() } }))
vi.mock('@/hooks/useD20Roll', async (orig) => ({ ...(await orig() as object), useD20Roll: () => async () => undefined }))
vi.mock('@/dice/useAnimatedRoll', () => ({ useAnimatedRoll: () => async () => [9] }))

const option = (key: string, label: string, extra: Partial<RollOption>) => ({
  key, phase: 'before', label, source: 'feature:monk', dice: null, bonus: null, mode: null, multiplier: null,
  once_per_turn: false, slot: null, needs: null, requires_input: null, input_options: [], auto_fail: false, cost: null, ...extra,
}) as RollOption

describe('caccia: correzioni del gruppo oggetti', () => {
  // caccia: {"id": "CB-4273", "fonte": "2024 · Monaco · Arti Marziali pag. 101, Raffica di Colpi pag. 102; Glossario · Colpo Senz'Armi · pag. 377", "zona": "regola:2024/monk", "voce": "regola", "copre": ["carta:2024/classes/monk.md#Arti Marziali / Martial Arts (Monaco 1, pag. 101)", "carta:2024/classes/monk.md#Raffica di Colpi / Flurry of Blows (Monaco 2, pag. 102)", "carta:2024/general.md#Unarmed Strike (Colpo Senz'Armi) (pag. 377)", "route:/char/:id/turn"]}
  it('Afferrare o Spingere si può fare con il colpo bonus del monaco, senza contarlo fra gli attacchi dell\'azione', async () => {
    rollOptions.mockResolvedValue([
      option('monk.martial_arts_bonus', 'Arti Marziali: colpo bonus', { slot: 'bonus' }),
      option('feat.vantaggio', 'Vantaggio', { mode: 'advantage' }),  // riguarda il tiro per colpire, che qui non c'è
    ])
    turnState.mockResolvedValue({ attacks_allowed: 1, turn: { attacks_made: 1, action_attacks: 1 } })
    attackUnarmed.mockResolvedValue({ effect: 'shove', save_dc: 13 })
    renderWithProviders(<RollOptionsHost />)
    const { result } = renderHook(() => useAttackRoll())
    const done = result.current.unarmedEffect(1, 'shove')
    await userEvent.click(await screen.findByRole('switch', { name: 'Arti Marziali: colpo bonus' }))
    expect(screen.queryByRole('switch', { name: 'Vantaggio' })).toBeNull()
    await userEvent.click(screen.getByText('character.roll_options.roll'))
    await done
    // l'azione Attacco è finita, ma il colpo bonus non ne fa parte: nessuna conferma «oltre il limite»
    expect(attackUnarmed).toHaveBeenCalledWith(1, false, { options: ['monk.martial_arts_bonus'], option_inputs: {} }, { effect: 'shove' })
  })
})
