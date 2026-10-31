import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient } from '@tanstack/react-query'
import { renderWithProviders } from '../../utils/renderWithProviders'
import { useCastFlow } from '@/pages/spells/useCastFlow'
import type { CharacterFull, Spell } from '@/types'

const { attack, useSpell, updateConc, toastSuccess, rollDice } = vi.hoisted(() => ({
  attack: vi.fn(),
  useSpell: vi.fn(),
  updateConc: vi.fn(),
  toastSuccess: vi.fn(),
  rollDice: vi.fn(),
}))

vi.mock('@/api/client', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, api: { spells: { attack, use: useSpell, updateConcentration: updateConc } } }
})
vi.mock('sonner', () => ({ toast: { success: toastSuccess, info: vi.fn(), error: vi.fn() } }))
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
    default: (p: { onCast: (l: number) => void; onCastRitual: () => void }) =>
      React.createElement('div', null,
        React.createElement('button', { onClick: () => p.onCast(3) }, 'cast-slot-3'),
        React.createElement('button', { onClick: p.onCastRitual }, 'cast-ritual'),
      ),
  }
})
vi.mock('@/pages/spells/SpellDamageSheet', async () => {
  const React = await import('react')
  return {
    default: (p: { spell: Spell | null; slotLevel: number | null; slotAlreadyConsumed?: boolean; initialCritical?: boolean }) =>
      p.spell
        ? React.createElement('div', {
            'data-testid': 'damage-sheet',
            'data-slot': String(p.slotLevel),
            'data-consumed': String(!!p.slotAlreadyConsumed),
            'data-critical': String(!!p.initialCritical),
          })
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

afterEach(() => { vi.clearAllMocks() })

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
    await waitFor(() => expect(attack).toHaveBeenCalledWith(7, 2, { slot_level: 3, ritual: false, die: undefined }))
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

  it('keeps the manual critical for spells without a type', async () => {
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

describe('useCastFlow damageless casts', () => {
  it('confirms a damageless cantrip with a toast', async () => {
    renderFlow(light)
    await userEvent.click(screen.getByText('begin'))
    expect(toastSuccess).toHaveBeenCalledWith('character.spells.cast_done(name=Luce)')
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
  })
})
