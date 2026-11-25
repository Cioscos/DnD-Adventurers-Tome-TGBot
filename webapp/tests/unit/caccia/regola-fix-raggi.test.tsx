import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient } from '@tanstack/react-query'
import { renderWithProviders } from '../utils/renderWithProviders'
import { useCastFlow } from '@/pages/spells/useCastFlow'
import type { CharacterFull, Spell } from '@/types'

const { attack, rollDamage, rollOptions, turnState, lastRollRefund } = vi.hoisted(() => ({
  attack: vi.fn(), rollDamage: vi.fn(), rollOptions: vi.fn(async () => [] as unknown[]), turnState: vi.fn(), lastRollRefund: vi.fn(async () => ({})),
}))

vi.mock('@/api/client', async (orig) => ({
  ...(await orig<Record<string, unknown>>()),
  api: {
    spells: { attack, rollDamage, castCheck: vi.fn(async () => []) },
    characters: { rollOptions, turnState, lastRollRefund, sessionAllies: vi.fn(async () => []) },
  },
}))
vi.mock('react-i18next', async (orig) => ({
  ...(await orig<typeof import('react-i18next')>()),
  useTranslation: () => ({ t: (k: string, o?: Record<string, unknown>) => (o && 'n' in o ? `${k} ${String(o.n)}/${String(o.total)}` : k), i18n: { language: 'it' } }),
}))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/dice/useAnimatedRoll', () => ({ useAnimatedRoll: () => async () => undefined }))
vi.mock('@/dice/useDiceAnimation', () => ({ useDiceAnimation: () => ({ playAndCollect: vi.fn(async () => []) }) }))
vi.mock('@/hooks/useD20Roll', async (orig) => ({ ...(await orig<Record<string, unknown>>()), useD20Roll: () => async () => undefined }))
vi.mock('@/components/ui/Sheet', () => ({ default: (p: { open: boolean; children?: React.ReactNode }) => (p.open ? <div>{p.children}</div> : null) }))

const blast = { id: 1, name: 'Deflagrazione Occulta', level: 0, attack_save: 'ATK', damage_dice: '1d10', is_prepared: true, rays: 2 } as Spell
const char = { id: 7, rules_edition: '2024', spells: [blast], spell_slots: [], spellcasting: null, settings: {}, classes: [] } as unknown as CharacterFull
const colpo = (die: number, ray: number) => ({
  spell_name: blast.name, to_hit_die: die, to_hit_bonus: 5, to_hit_total: die + 5, is_critical: die === 20, is_fumble: die === 1,
  caster_class: 'warlock', character: char, ray, rays: 2,
})
const danno = { rolls: [7], total: 7, half_damage: 3, damage_type: 'force', breakdown: '', casting_level: 0, is_critical: false, main_kind: 'd10', main_rolls: [7], extra_kind: null, extra_rolls: [] }

function Banco() {
  const flow = useCastFlow(7, char)
  return <><button onClick={() => flow.beginCast(blast)}>lancia</button>{flow.elements}</>
}

const monta = () => {
  turnState.mockResolvedValue({ in_encounter: false, turn: { last_roll: { refundable: { x: [] } } } })
  renderWithProviders(<Banco />, { client: new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }) })
  return userEvent.setup({ pointerEventsCheck: 0 })  // i fogli entrano con un'animazione che jsdom non completa
}

afterEach(() => { vi.clearAllMocks(); rollOptions.mockResolvedValue([]) })

describe('caccia: raggi della Deflagrazione Occulta', () => {
  // caccia: {"id": "CB-4689", "fonte": "decisione D-037 (tests/caccia/decisioni.md): un tiro per colpire e un danno per raggio; 2014 · pag. 229; 2024 · pag. 267", "zona": "regola:2024/incantesimi-D-F", "voce": "interazione", "copre": ["carta:2014/spells.md#Deflagrazione Occulta", "carta:2024/spells.md#Esplosione occulta", "POST /characters/{char_id}/spells/{spell_id}/attack"]}
  it('dopo il danno di un raggio si tira il seguente, senza un nuovo lancio', async () => {
    attack.mockResolvedValueOnce(colpo(20, 1)).mockResolvedValueOnce(colpo(9, 2))
    rollDamage.mockResolvedValue(danno)
    const user = monta()
    await user.click(screen.getByText('lancia'))
    expect(await screen.findByText(/ray_of 1\/2/)).toBeInTheDocument()
    await user.click(screen.getByText('character.spells.attack_roll_damage'))
    await user.click(await screen.findByText('character.spells.roll_damage.roll_button'))
    await waitFor(() => expect(rollDamage).toHaveBeenCalledWith(7, 1, expect.objectContaining({ is_critical: true })))
    await user.click(await screen.findByText('character.spells.roll_damage.close'))
    expect(screen.queryByText('character.spells.attack_roll_damage')).toBeNull()  // il danno di questo raggio è già tirato
    await user.click(await screen.findByRole('button', { name: 'character.spells.next_ray 2/2' }))
    expect(await screen.findByText(/ray_of 2\/2/)).toBeInTheDocument()
    expect(attack).toHaveBeenLastCalledWith(7, 1, expect.objectContaining({ ray: true }))
    expect(attack.mock.calls[0][2]).not.toHaveProperty('ray')
    expect(screen.queryByRole('button', { name: /next_ray/ })).toBeNull()
    expect(lastRollRefund).not.toHaveBeenCalled()
  })

  // caccia: {"id": "CB-4690", "fonte": "decisione D-037 (tests/caccia/decisioni.md): ogni raggio colpisce o manca da solo; 2014 · pag. 229; 2024 · pag. 267", "zona": "regola:2024/incantesimi-D-F", "voce": "interazione", "copre": ["carta:2024/spells.md#Esplosione occulta", "POST /characters/{char_id}/last-roll/refund"]}
  it('un raggio mancato passa al seguente e rimborsa ciò che si paga solo se il tiro riesce', async () => {
    attack.mockResolvedValueOnce(colpo(4, 1)).mockResolvedValueOnce(colpo(12, 2))
    const user = monta()
    await user.click(screen.getByText('lancia'))
    await user.click(await screen.findByRole('button', { name: 'character.spells.next_ray_missed 2/2' }))
    expect(await screen.findByText(/ray_of 2\/2/)).toBeInTheDocument()
    expect(lastRollRefund).toHaveBeenCalledWith(7)
    expect(rollDamage).not.toHaveBeenCalled()
  })
})
