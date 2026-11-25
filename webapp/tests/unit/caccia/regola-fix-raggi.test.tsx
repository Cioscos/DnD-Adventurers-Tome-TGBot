import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient } from '@tanstack/react-query'
import { renderWithProviders } from '../utils/renderWithProviders'
import { useCastFlow } from '@/pages/spells/useCastFlow'
import { usePromptStore } from '@/lib/rollOptions'
import type { CharacterFull, Spell } from '@/types'

const { attack, rollDamage, rollOptions, turnState, lastRollRefund, lastRollOptions } = vi.hoisted(() => ({
  lastRollOptions: vi.fn(),
  attack: vi.fn(), rollDamage: vi.fn(), rollOptions: vi.fn(async () => [] as unknown[]), turnState: vi.fn(), lastRollRefund: vi.fn(async () => ({})),
}))

vi.mock('@/api/client', async (orig) => ({
  ...(await orig<Record<string, unknown>>()),
  api: {
    spells: { attack, rollDamage, castCheck: vi.fn(async () => []) },
    characters: { rollOptions, turnState, lastRollRefund, lastRollOptions, sessionAllies: vi.fn(async () => []) },
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

function Banco({ pg = char }: { pg?: CharacterFull }) {
  const flow = useCastFlow(7, pg)
  return <><button onClick={() => flow.beginCast(blast)}>lancia</button>{flow.elements}</>
}

const monta = (pg = char) => {
  turnState.mockResolvedValue({ in_encounter: false, turn: { last_roll: { refundable: { x: [] } } } })
  renderWithProviders(<Banco pg={pg} />, { client: new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }) })
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

  // caccia: {"id": "CB-4692", "fonte": "2024 · Warlock · Deflagrazione Respingente · pag. 157 (colpendo si può spingere); 2014 · pag. 118; per ogni raggio: decisione D-037 (tests/caccia/decisioni.md)", "zona": "regola:2024/warlock", "voce": "interazione", "copre": ["carta:2014/classes/warlock.md#Deflagrazione Respingente / Repelling Blast (Suppliche Occulte, trucchetto deflagrazione occulta, pag. 118)", "POST /characters/{char_id}/spells/{spell_id}/roll_damage"]}
  it('dopo il colpo si chiedono le opzioni del colpo: vanno col primo danno, il «Mancato» passa al raggio seguente', async () => {
    const spinta = { key: 'warlock.repelling_blast', phase: 'after_hit', label: 'Respingente', needs: null, input_options: [], preselected: false, multiplier: null, cost: null }
    const precisione = { ...spinta, key: 'fighter.maneuver_precision', phase: 'after_roll', after: 'add' }
    rollOptions.mockResolvedValue([spinta, precisione])
    attack.mockResolvedValueOnce(colpo(15, 1)).mockResolvedValueOnce(colpo(12, 2))
    rollDamage.mockResolvedValue(danno)
    const user = monta()
    await user.click(screen.getByText('lancia'))
    await user.click(await screen.findByText('character.spells.attack_roll_damage'))
    await waitFor(() => expect(usePromptStore.getState().request).not.toBeNull())
    const richiesta = usePromptStore.getState().request!
    expect([richiesta.phase, richiesta.options.map((o) => o.key), richiesta.afterRoll]).toEqual(['after_hit', [spinta.key], []])
    richiesta.answer({ options: [spinta.key], option_inputs: {} })
    await user.click(await screen.findByText('character.spells.roll_damage.roll_button'))
    await waitFor(() => expect(rollDamage).toHaveBeenCalledWith(7, 1, expect.objectContaining({ hit_options: [spinta.key] })))
    await user.click(await screen.findByText('character.spells.roll_damage.reroll'))
    await user.click(await screen.findByText('character.spells.roll_damage.roll_button'))
    await waitFor(() => expect(rollDamage).toHaveBeenCalledTimes(2))
    expect(rollDamage.mock.calls[1][2]).not.toHaveProperty('hit_options')  // già pagata
    await user.click(await screen.findByText('character.spells.roll_damage.close'))
    await user.click(await screen.findByRole('button', { name: 'character.spells.next_ray 2/2' }))
    await user.click(await screen.findByText('character.spells.attack_roll_damage'))
    await waitFor(() => expect(usePromptStore.getState().request).not.toBeNull())
    usePromptStore.getState().request!.answer({ options: [], option_inputs: {}, outcome: 'miss' })
    await waitFor(() => expect(screen.queryByText(/ray_of/)).toBeNull())  // ultimo raggio mancato: il lancio è finito
    expect(rollDamage).toHaveBeenCalledTimes(2)
  })

  // caccia: {"id": "CB-4879", "fonte": "decisione D-048 (tests/caccia/decisioni.md): il rilancio con Ispirazione tiene le opzioni confermate sul primo tiro", "zona": "regola:2024/generali", "voce": "interazione", "copre": ["POST /characters/{char_id}/spells/{spell_id}/attack", "POST /characters/{char_id}/last-roll/options"]}
  it('dopo il rilancio con Ispirazione il d4 di Benedizione già sommato non si somma di nuovo', async () => {
    rollOptions.mockResolvedValue([{ key: 'bless', phase: 'after_roll', after: 'add', label: 'Benedizione', needs: null, input_options: [], preselected: true, multiplier: null, cost: null }])
    lastRollOptions.mockResolvedValue({ die: 4, dice: [4], mode: 'normal', bonus: 5, total: 12, notes: [], is_critical: false, is_fumble: false })
    attack.mockResolvedValueOnce({ ...colpo(4, 1), cast_option_result: { keys: ['x'], effects: [{ it: 'effetto del lancio', en: 'cast effect' }] } })
      .mockResolvedValueOnce({ ...colpo(14, 1), to_hit_bonus: 8, to_hit_total: 22 })
    const user = monta({ ...char, heroic_inspiration: true } as CharacterFull)
    await user.click(screen.getByText('lancia'))
    expect(await screen.findByText('12')).toBeInTheDocument()
    await user.click(await screen.findByRole('button', { name: /character.inspiration/ }))
    expect(await screen.findByText('22')).toBeInTheDocument()
    expect(attack).toHaveBeenLastCalledWith(7, 1, expect.objectContaining({ with_inspiration: true }))
    await waitFor(() => expect(turnState).toHaveBeenCalled())
    expect(lastRollOptions).toHaveBeenCalledTimes(1)
    expect(screen.getByText('effetto del lancio')).toBeInTheDocument()
  })
})
