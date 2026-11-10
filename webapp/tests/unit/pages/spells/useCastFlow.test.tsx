import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient } from '@tanstack/react-query'
import { renderWithProviders } from '../../utils/renderWithProviders'
import { useCastFlow } from '@/pages/spells/useCastFlow'
import { useCastConfirmStore, useEffectPickStore } from '@/lib/rollOptions'
import { ApiError } from '@/api/client'
import i18n from '@/i18n'
import type { CharacterFull, Spell } from '@/types'

const { attack, useSpell, updateConc, toastSuccess, rollDice, castCheck, toastError, toastInfo, sessionAllies } = vi.hoisted(() => ({
  toastInfo: vi.fn(),
  sessionAllies: vi.fn(),
  toastError: vi.fn(),
  castCheck: vi.fn(),
  attack: vi.fn(),
  useSpell: vi.fn(),
  updateConc: vi.fn(),
  toastSuccess: vi.fn(),
  rollDice: vi.fn(),
}))

vi.mock('@/api/client', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, api: { spells: { attack, use: useSpell, updateConcentration: updateConc, castCheck }, characters: { sessionAllies } } }
})
vi.mock('sonner', () => ({ toast: { success: toastSuccess, info: toastInfo, error: toastError, warning: vi.fn() } }))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  const t = (k: string, o?: Record<string, unknown>) =>
    o ? `${k}(${Object.entries(o).map(([a, b]) => `${a}=${String(b)}`).join(',')})` : k
  return { ...actual, useTranslation: () => ({ t, i18n: { language: 'it' } }) }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/dice/useAnimatedRoll', () => ({ useAnimatedRoll: () => rollDice }))
vi.mock('@/hooks/useD20Roll', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useD20Roll: () => async (mode: string) => rollDice('d20', mode === 'normal' ? 1 : 2) }
})
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return {
    default: (p: { open: boolean; title?: string; children?: unknown }) =>
      p.open ? React.createElement('div', { 'data-testid': 'cast-sheet', 'data-title': p.title }, p.children) : null,
  }
})
vi.mock('@/components/ui/ConfirmSheet', async () => {
  const React = await import('react')
  return {
    default: (p: { open: boolean; onConfirm: () => void }) =>
      p.open ? React.createElement('button', { onClick: p.onConfirm }, 'confirm-unprepared') : null,
  }
})
vi.mock('@/pages/spells/CastSpellModal', async () => {
  const React = await import('react')
  return {
    default: (p: { availableSlots: unknown[]; freeOnly?: boolean; canFreeCast?: boolean; onCastFree?: () => void; onCast: (s: { id: number; level: number }) => void; onCastRitual: () => void; onCastKi?: (extra: number) => void }) =>
      React.createElement('div', { 'data-slots': String(p.availableSlots.length), 'data-free-only': String(!!p.freeOnly) },
        p.canFreeCast ? React.createElement('button', { onClick: p.onCastFree }, 'cast-free') : null,
        React.createElement('button', { onClick: () => p.onCast({ id: 1, level: 3 }) }, 'cast-slot-3'),
        React.createElement('button', { onClick: p.onCastRitual }, 'cast-ritual'),
        p.onCastKi ? React.createElement('button', { onClick: () => p.onCastKi?.(1) }, 'cast-ki-1') : null,
      ),
  }
})
vi.mock('@/pages/spells/SpellDamageSheet', async () => {
  const React = await import('react')
  return {
    default: (p: { spell: Spell | null; slotLevel: number | null; kiExtra?: number | null; freeCast?: boolean; slotAlreadyConsumed?: boolean; initialCritical?: boolean; onBack?: () => void }) =>
      p.spell
        ? React.createElement('div', {
            'data-testid': 'damage-sheet',
            'data-slot': String(p.slotLevel),
            'data-ki': String(p.kiExtra ?? 'none'),
            'data-free': String(!!p.freeCast),
            'data-consumed': String(!!p.slotAlreadyConsumed),
            'data-critical': String(!!p.initialCritical),
          }, p.onBack ? React.createElement('button', { onClick: p.onBack }, 'damage-back') : null)
        : null,
  }
})
vi.mock('@/pages/spells/SpellAttackModal', async () => {
  const React = await import('react')
  return {
    default: (p: {
      result: { to_hit_total: number; is_fumble: boolean }
      canRollDamage: boolean
      onRollDamage: () => void
      onInspirationReroll?: () => void
    }) =>
      React.createElement('div', { 'data-testid': 'attack-modal' },
        React.createElement('span', null, `total:${p.result.to_hit_total}`),
        p.canRollDamage ? React.createElement('button', { onClick: p.onRollDamage }, 'roll-damage') : null,
        p.onInspirationReroll ? React.createElement('button', { onClick: p.onInspirationReroll }, 'insp-reroll') : null,
      ),
  }
})

const fireBolt = { id: 1, name: 'Dardo di Fuoco', level: 0, attack_save: 'ATK', is_concentration: false, is_ritual: false, damage_dice: '1d10', is_prepared: true } as Spell
const scorching = { id: 2, name: 'Raggio Rovente', level: 2, attack_save: 'atk ', is_concentration: false, is_ritual: false, damage_dice: '2d6', is_prepared: true } as Spell
const light = { id: 3, name: 'Luce', level: 0, attack_save: null, is_concentration: false, is_ritual: false, is_prepared: true } as Spell
const bless = { id: 4, name: 'Benedizione', level: 1, attack_save: null, is_concentration: true, is_ritual: false, is_prepared: true } as Spell
const thunder = { id: 5, name: 'Onda Tonante', level: 1, attack_save: '', is_concentration: false, is_ritual: false, damage_dice: '2d8', is_prepared: true } as Spell

const char = {
  id: 7,
  heroic_inspiration: true,
  spells: [fireBolt, scorching, light, bless, thunder],
  spell_slots: [{ id: 1, level: 3, total: 2, used: 0, available: 2, is_pact: false }],
  spellcasting: { has_preparing_class: false, has_wizard: false, has_ritual_caster: false, casters: [] },
  settings: {},
} as unknown as CharacterFull

const attackResult = (die: number) => ({
  spell_name: 'x', to_hit_die: die, to_hit_bonus: 5, to_hit_total: die + 5,
  is_critical: die === 20, is_fumble: die === 1, caster_class: 'wizard',
  character: { ...char, id: 7 },
})

function Harness({ spell }: { spell: Spell }) {
  const flow = useCastFlow(7, char)
  return (
    <>
      <button onClick={() => flow.beginCast(spell)}>begin</button>
      {flow.elements}
    </>
  )
}

function renderFlow(spell: Spell) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return renderWithProviders(<Harness spell={spell} />, { client })
}

afterEach(() => { vi.clearAllMocks(); castCheck.mockReset() })

describe('useCastFlow attack spells', () => {
  it('rolls the d20 for an attack spell and shows the total', async () => {
    rollDice.mockResolvedValue([14])
    attack.mockResolvedValue(attackResult(14))
    renderFlow(fireBolt)
    await userEvent.click(screen.getByText('begin'))
    await waitFor(() => expect(attack).toHaveBeenCalledWith(7, 1, expect.objectContaining({ die: 14, ritual: false })))
    expect(rollDice).toHaveBeenCalledWith('d20', 1)
    expect(await screen.findByText('total:19')).toBeInTheDocument()
    expect(screen.queryByTestId('damage-sheet')).toBeNull()
  })

  it('rolls after the slot choice for a levelled attack spell', async () => {
    rollDice.mockResolvedValue(undefined)
    attack.mockResolvedValue(attackResult(9))
    renderFlow(scorching)
    await userEvent.click(screen.getByText('begin'))
    expect(attack).not.toHaveBeenCalled()
    await userEvent.click(screen.getByText('cast-slot-3'))
    await waitFor(() => expect(attack).toHaveBeenCalledWith(7, 2, expect.objectContaining({ slot_id: 1, slot_level: 3, ritual: false })))
    expect(useSpell).not.toHaveBeenCalled()
    expect(await screen.findByText('total:14')).toBeInTheDocument()
  })

  it('opens the damage sheet with critical on after a natural 20', async () => {
    rollDice.mockResolvedValue([20])
    attack.mockResolvedValue(attackResult(20))
    renderFlow(scorching)
    await userEvent.click(screen.getByText('begin'))
    await userEvent.click(screen.getByText('cast-slot-3'))
    await userEvent.click(await screen.findByText('roll-damage'))
    const sheet = await screen.findByTestId('damage-sheet')
    expect(sheet.dataset.critical).toBe('true')
    expect(sheet.dataset.consumed).toBe('true')
    expect(sheet.dataset.slot).toBe('3')
    expect(screen.queryByTestId('attack-modal')).toBeNull()
  })

  it('offers no damage after a natural 1', async () => {
    rollDice.mockResolvedValue([1])
    attack.mockResolvedValue(attackResult(1))
    renderFlow(fireBolt)
    await userEvent.click(screen.getByText('begin'))
    expect(await screen.findByText('total:6')).toBeInTheDocument()
    expect(screen.queryByText('roll-damage')).toBeNull()
  })

  it('still offers the damage after a natural 1 when the twinned second target did not fumble', async () => {
    rollDice.mockResolvedValue([1])
    attack.mockResolvedValue({ ...attackResult(1), twinned_attack: { die: 18, dice: [18], mode: 'normal', total: 23, is_critical: false, is_fumble: false } })
    renderFlow(fireBolt)
    await userEvent.click(screen.getByText('begin'))
    expect(await screen.findByText('total:6')).toBeInTheDocument()
    expect(screen.getByText('roll-damage')).toBeInTheDocument()
  })

  it('offers no damage when both twinned targets roll a natural 1', async () => {
    rollDice.mockResolvedValue([1])
    attack.mockResolvedValue({ ...attackResult(1), twinned_attack: { die: 1, dice: [1], mode: 'normal', total: 6, is_critical: false, is_fumble: true } })
    renderFlow(fireBolt)
    await userEvent.click(screen.getByText('begin'))
    expect(await screen.findByText('total:6')).toBeInTheDocument()
    expect(screen.queryByText('roll-damage')).toBeNull()
  })

  it('rerolls with inspiration without a slot', async () => {
    rollDice.mockResolvedValueOnce([4]).mockResolvedValueOnce([17])
    attack.mockResolvedValueOnce(attackResult(4)).mockResolvedValueOnce(attackResult(17))
    renderFlow(scorching)
    await userEvent.click(screen.getByText('begin'))
    await userEvent.click(screen.getByText('cast-slot-3'))
    await userEvent.click(await screen.findByText('insp-reroll'))
    await waitFor(() => expect(attack).toHaveBeenLastCalledWith(7, 2, { slot_level: null, ritual: false, die: 17, with_inspiration: true }))
    expect(await screen.findByText('total:22')).toBeInTheDocument()
  })

  it('rolls damage without a critical for spells without a type', async () => {
    renderFlow(thunder)
    await userEvent.click(screen.getByText('begin'))
    await userEvent.click(screen.getByText('cast-slot-3'))
    const sheet = await screen.findByTestId('damage-sheet')
    expect(sheet.dataset.consumed).toBe('false')
    expect(sheet.dataset.critical).toBe('false')
    expect(attack).not.toHaveBeenCalled()
    expect(rollDice).not.toHaveBeenCalled()
  })
})

describe('useCastFlow single cast sheet', () => {
  it('moves from slot to damage inside one sheet and goes back to the slots', async () => {
    renderFlow(thunder)
    await userEvent.click(screen.getByText('begin'))
    expect(screen.getByTestId('cast-sheet').dataset.title).toBe('character.spells.cast_slot_title')

    await userEvent.click(screen.getByText('cast-slot-3'))
    expect(screen.getAllByTestId('cast-sheet')).toHaveLength(1)
    expect(screen.getByTestId('cast-sheet').dataset.title).toBe('character.spells.roll_damage.title(name=Onda Tonante)')
    expect(await screen.findByTestId('damage-sheet')).toBeInTheDocument()

    await userEvent.click(screen.getByText('damage-back'))
    expect(await screen.findByText('cast-slot-3')).toBeInTheDocument()
    expect(screen.queryByTestId('damage-sheet')).not.toBeInTheDocument()
  })
})

describe('useCastFlow damageless casts', () => {
  it('confirms a damageless cantrip with a toast, through the server', async () => {
    useSpell.mockResolvedValue(char)
    renderFlow(light)
    await userEvent.click(screen.getByText('begin'))
    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith('character.spells.cast_done(name=Luce)'))
    expect(useSpell).toHaveBeenCalledWith(7, 3, expect.objectContaining({ as_ritual: false }))
  })

  it('confirms a damageless levelled spell with slot and concentration', async () => {
    useSpell.mockResolvedValue(char)
    updateConc.mockResolvedValue(char)
    renderFlow(bless)
    await userEvent.click(screen.getByText('begin'))
    await userEvent.click(screen.getByText('cast-slot-3'))
    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith(
      'character.spells.cast_done(name=Benedizione)'
      + 'character.spells.cast_done_slot(level=3)'
      + 'character.spells.cast_done_concentration',
    ))
    expect(useSpell).toHaveBeenCalledWith(7, 4, expect.objectContaining({ slot_id: 1, slot_level: 3 }))
    // Il lancio avvia la concentrazione col contatore: un secondo PATCH lo azzerava (§19 n. 10).
    expect(updateConc).not.toHaveBeenCalled()
  })

  it('a spell granted at will is cast at once without a slot (Thousand Forms)', async () => {
    useSpell.mockResolvedValue(char)
    renderFlow({ ...bless, id: 8, name: 'Alterare se stessi', level: 2, srd_index: 'alter-self', at_will: true } as Spell)
    await userEvent.click(screen.getByText('begin'))
    await waitFor(() => expect(useSpell).toHaveBeenCalledWith(7, 8, expect.objectContaining({
      free_cast: true, slot_level: null, as_ritual: false })))
    expect(screen.queryByText('cast-slot-3')).toBeNull()  // nessuna scelta dello slot
  })

  it('a ki cast without dice is sent at once with the extra ki and no slot', async () => {
    useSpell.mockResolvedValue(char)
    const darkness = { id: 9, name: 'Oscurità', level: 2, srd_index: 'darkness', is_concentration: true, is_ritual: false, is_prepared: true,
      ki_cast: { cost: 2, max_extra: 1, ki_left: 4, feature_key: 'monk.shadow_arts' } } as Spell
    renderFlow(darkness)
    await userEvent.click(screen.getByText('begin'))
    await userEvent.click(await screen.findByText('cast-ki-1'))
    await waitFor(() => expect(useSpell).toHaveBeenCalledWith(7, 9, expect.objectContaining({
      ki: true, ki_extra: 1, slot_level: null, as_ritual: false })))
  })

  it('a ki cast with damage dice waits for the first roll, at the level the extra ki reach', async () => {
    const burning = { id: 10, name: 'Mani brucianti', level: 1, srd_index: 'burning-hands', damage_dice: '3d6', is_concentration: false,
      is_ritual: false, is_prepared: true, ki_cast: { cost: 2, max_extra: 2, ki_left: 5, feature_key: 'monk.discipline_sweeping_cinder_strike' } } as Spell
    renderFlow(burning)
    await userEvent.click(screen.getByText('begin'))
    await userEvent.click(await screen.findByText('cast-ki-1'))
    const sheet = await screen.findByTestId('damage-sheet')
    expect(sheet).toHaveAttribute('data-ki', '1')
    expect(sheet).toHaveAttribute('data-slot', '2')  // 1° livello + 1 ki in più
    expect(useSpell).not.toHaveBeenCalled()
  })

  it('an Arcanum Mistico has no slots to choose and is cast free', async () => {
    useSpell.mockResolvedValue(char)
    renderFlow({ ...bless, id: 11, name: 'Passo planare', level: 7, pact_cast: { kind: 'arcanum', feature_key: 'warlock.mystic_arcanum_7', pact_only: false, uses_left: 1 } } as Spell)
    await userEvent.click(screen.getByText('begin'))
    expect(await screen.findByTestId('cast-sheet')).toBeInTheDocument()
    expect(document.querySelector('[data-free-only="true"]')).not.toBeNull()
    await userEvent.click(screen.getByText('cast-free'))
    await waitFor(() => expect(useSpell).toHaveBeenCalledWith(7, 11, expect.objectContaining({ free_cast: true, slot_level: null, as_ritual: false })))
  })

  it('an Arcanum with damage dice waits for the first roll in the damage sheet, free of a slot', async () => {
    const circle = { ...thunder, id: 12, name: 'Cerchio della morte', level: 6, damage_dice: '8d6',
      pact_cast: { kind: 'arcanum', feature_key: 'warlock.mystic_arcanum_6', pact_only: false, uses_left: 1 } } as Spell
    renderFlow(circle)
    await userEvent.click(screen.getByText('begin'))
    await userEvent.click(await screen.findByText('cast-free'))
    const sheet = await screen.findByTestId('damage-sheet')
    expect(sheet).toHaveAttribute('data-free', 'true')
    expect(sheet).toHaveAttribute('data-slot', '6')
    expect(useSpell).not.toHaveBeenCalled()
  })

  it('an Arcanum already used is not offered as a free cast', async () => {
    renderFlow({ ...bless, id: 13, level: 6, pact_cast: { kind: 'arcanum', feature_key: 'warlock.mystic_arcanum_6', pact_only: false, uses_left: 0 } } as Spell)
    await userEvent.click(screen.getByText('begin'))
    await screen.findByTestId('cast-sheet')
    expect(screen.queryByText('cast-free')).toBeNull()
  })

  it('a once-per-rest invocation offers only the Pact slots', async () => {
    const mixed = { ...char, spell_slots: [
      { id: 1, level: 3, total: 2, used: 0, available: 2, is_pact: false },
      { id: 2, level: 3, total: 1, used: 0, available: 1, is_pact: true }] } as unknown as CharacterFull
    const slow = { ...bless, id: 14, name: 'Lentezza', level: 3, pact_cast: { kind: 'invocation', feature_key: 'warlock.mire_the_mind', pact_only: true, uses_left: 1 } } as Spell
    function PactHarness() {
      const flow = useCastFlow(7, mixed)
      return (<><button onClick={() => flow.beginCast(slow)}>begin</button>{flow.elements}</>)
    }
    renderWithProviders(<PactHarness />, { client: new QueryClient() })
    await userEvent.click(screen.getByText('begin'))
    await screen.findByTestId('cast-sheet')
    expect(document.querySelector('[data-slots="1"]')).not.toBeNull()
  })

  it('a spell that is not at will still asks for the slot', async () => {
    renderFlow(bless)
    await userEvent.click(screen.getByText('begin'))
    expect(await screen.findByText('cast-slot-3')).toBeInTheDocument()
    expect(useSpell).not.toHaveBeenCalled()
  })

  it('a refused confirmation casts nothing and shows no error', async () => {
    castCheck.mockResolvedValue(['armor'])
    renderFlow(bless)
    await userEvent.click(screen.getByText('begin'))
    await userEvent.click(screen.getByText('cast-slot-3'))
    await waitFor(() => expect(useCastConfirmStore.getState().request?.code).toBe('armor'))
    useCastConfirmStore.getState().request!.answer(false)
    await waitFor(() => expect(useCastConfirmStore.getState().request).toBeNull())
    expect(useSpell).not.toHaveBeenCalled()
    expect(toastError).not.toHaveBeenCalled()
  })

  it('sends what the player confirmed', async () => {
    castCheck.mockResolvedValue(['one_slot_per_turn'])
    useSpell.mockResolvedValue(char)
    renderFlow(bless)
    await userEvent.click(screen.getByText('begin'))
    await userEvent.click(screen.getByText('cast-slot-3'))
    await waitFor(() => expect(useCastConfirmStore.getState().request?.code).toBe('one_slot_per_turn'))
    useCastConfirmStore.getState().request!.answer(true)
    await waitFor(() => expect(useSpell).toHaveBeenCalledWith(7, 4, expect.objectContaining({ confirm: ['one_slot_per_turn'] })))
  })
})

describe('useCastFlow spell effects', () => {
  const shield = {
    id: 8, name: 'Scudo della Fede', level: 1, attack_save: null, is_concentration: true, is_ritual: false, is_prepared: true,
    effect: { target_kind: 'ally', max_targets_by_slot: { '3': 1 }, choices: [] },
  } as unknown as Spell
  const aid = {
    id: 9, name: 'Aiuto', level: 2, attack_save: null, is_concentration: false, is_ritual: false, is_prepared: true,
    effect: { target_kind: 'allies', max_targets_by_slot: { '3': 3 }, choices: [] },
  } as unknown as Spell

  it('asks for a target and sends it with the cast', async () => {
    sessionAllies.mockResolvedValue([{ id: 21, name: 'Eroe' }])
    useSpell.mockResolvedValue({ ...char, spell_effects: { applied: [{ id: 21, name: 'Eroe' }] } })
    castCheck.mockResolvedValue([])
    renderFlow(shield)
    await userEvent.click(screen.getByText('begin'))
    await userEvent.click(screen.getByText('cast-slot-3'))
    expect(useSpell).not.toHaveBeenCalled()
    await userEvent.click(await screen.findByText('Eroe'))
    await waitFor(() => expect(useSpell).toHaveBeenCalledWith(7, 8, expect.objectContaining({ slot_level: 3, targets: [21] })))
    // punto 82: un solo toast, con a chi è andato l'effetto come descrizione
    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith(expect.any(String), { description: 'character.spells.effect_applied(name=Scudo della Fede,targets=Eroe)' }))
    expect(toastSuccess).toHaveBeenCalledTimes(1)
  })

  it('does not name the caster in full when the effect lands on him (point 82)', async () => {
    sessionAllies.mockResolvedValue([{ id: 21, name: 'Eroe' }])
    useSpell.mockResolvedValue({ ...char, spell_effects: { applied: [{ id: 7, name: 'Fratello Bartolomeo' }, { id: 21, name: 'Eroe' }] } })
    castCheck.mockResolvedValue([])
    renderFlow(shield)
    await userEvent.click(screen.getByText('begin'))
    await userEvent.click(screen.getByText('cast-slot-3'))
    await userEvent.click(await screen.findByText('Eroe'))
    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith(expect.any(String), {
      description: 'character.spells.effect_applied(name=Scudo della Fede,targets=character.spells.effect_self, Eroe)' }))
  })

  it('lets the caster pick himself and shows the GM text outside an evening', async () => {
    sessionAllies.mockResolvedValue([])
    useSpell.mockResolvedValue({ ...char, spell_effects: { applied: [], text: { it: 'Lo applica il GM', en: 'GM applies it' } } })
    castCheck.mockResolvedValue([])
    renderFlow(shield)
    await userEvent.click(screen.getByText('begin'))
    await userEvent.click(screen.getByText('cast-slot-3'))
    await userEvent.click(await screen.findByText('character.turn.removal_self'))
    await waitFor(() => expect(useSpell).toHaveBeenCalledWith(7, 8, expect.objectContaining({ targets: [7] })))
    await waitFor(() => expect(toastInfo).toHaveBeenCalledWith('Lo applica il GM'))
  })

  it('picks several targets up to the slot limit', async () => {
    sessionAllies.mockResolvedValue([{ id: 21, name: 'Eroe' }, { id: 22, name: 'Maga' }])
    useSpell.mockResolvedValue(char)
    castCheck.mockResolvedValue([])
    renderFlow(aid)
    await userEvent.click(screen.getByText('begin'))
    await userEvent.click(screen.getByText('cast-slot-3'))
    await userEvent.click(await screen.findByText('Eroe'))
    await userEvent.click(screen.getByText('Maga'))
    await userEvent.click(screen.getByText('character.turn.ally_confirm(n=2)'))
    await waitFor(() => expect(useSpell).toHaveBeenCalledWith(7, 9, expect.objectContaining({ targets: [21, 22] })))
  })

  it('asks for the target also on a ritual', async () => {
    sessionAllies.mockResolvedValue([{ id: 21, name: 'Eroe' }])
    useSpell.mockResolvedValue(char)
    castCheck.mockResolvedValue([])
    renderFlow({ ...shield, is_ritual: true } as Spell)
    await userEvent.click(screen.getByText('begin'))
    await userEvent.click(screen.getByText('cast-ritual'))
    expect(useSpell).not.toHaveBeenCalled()
    await userEvent.click(await screen.findByText('Eroe'))
    await waitFor(() => expect(useSpell).toHaveBeenCalledWith(7, 8, expect.objectContaining({ as_ritual: true, targets: [21] })))
  })

  it('asks for the target before the damage sheet of a spell with dice and an effect', async () => {
    sessionAllies.mockResolvedValue([{ id: 21, name: 'Eroe' }])
    castCheck.mockResolvedValue([])
    renderFlow({ ...shield, damage_dice: '1d4' } as Spell)
    await userEvent.click(screen.getByText('begin'))
    await userEvent.click(screen.getByText('cast-slot-3'))
    expect(screen.queryByTestId('damage-sheet')).toBeNull()
    await userEvent.click(await screen.findByText('Eroe'))
    expect(await screen.findByTestId('damage-sheet')).toBeInTheDocument()
    expect(useEffectPickStore.getState().picked[8]).toEqual({ targets: [21], choices: undefined })
  })

  it.each(['invalid_target', 'target_dead', 'invalid_choice'])('shows a dedicated toast for %s', async (code) => {
    sessionAllies.mockResolvedValue([{ id: 21, name: 'Eroe' }])
    useSpell.mockRejectedValue(new ApiError(422, { code }))
    castCheck.mockResolvedValue([])
    renderFlow(shield)
    await userEvent.click(screen.getByText('begin'))
    await userEvent.click(screen.getByText('cast-slot-3'))
    await userEvent.click(await screen.findByText('Eroe'))
    await waitFor(() => expect(toastError).toHaveBeenCalledWith(i18n.t(`character.spells.roll_damage.cast_errors.${code}`)))
  })

  it('does not throw away the ticked targets when another creature is tapped', async () => {
    sessionAllies.mockResolvedValue([{ id: 21, name: 'Eroe' }, { id: 22, name: 'Maga' }])
    castCheck.mockResolvedValue([])
    renderFlow(aid)
    await userEvent.click(screen.getByText('begin'))
    await userEvent.click(screen.getByText('cast-slot-3'))
    await userEvent.click(await screen.findByText('Eroe'))
    await userEvent.click(screen.getByText('character.turn.ally_other'))
    expect(useSpell).not.toHaveBeenCalled()
    expect(screen.getByText('character.turn.ally_confirm(n=1)')).toBeInTheDocument()
  })
})
