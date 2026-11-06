import { describe, it, expect, vi, afterEach } from 'vitest'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../utils/renderWithProviders'
import SpellDamageSheet from '@/pages/spells/SpellDamageSheet'
import type { Spell, RollDamageResult } from '@/types'

const { rollDamage, useSpell, updateConc } = vi.hoisted(() => ({ rollDamage: vi.fn(), useSpell: vi.fn(), updateConc: vi.fn() }))

vi.mock('@/api/client', () => ({
  api: { spells: { rollDamage, use: useSpell, updateConcentration: updateConc } },
  ApiError: class ApiError extends Error { constructor(public status: number, public detail: unknown) { super('x') } },
}))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
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
    AnimatePresence: (p: { children?: unknown }) => p.children,
  }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/dice/useDiceAnimation', () => ({ useDiceAnimation: () => ({ playAndCollect: () => Promise.resolve([]) }) }))
vi.mock('@/store/diceSettings', () => ({ useDiceSettings: (sel: (s: { animate3d: boolean }) => unknown) => sel({ animate3d: false }) }))
vi.mock('@/hooks/useReducedMotion', () => ({ useReducedMotion: () => true }))
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; children?: unknown }) => (p.open ? React.createElement('div', null, p.children) : null) }
})
vi.mock('@/components/ui/Button', async () => {
  const React = await import('react')
  return { default: (p: { onClick?: () => void; children?: unknown }) => React.createElement('button', { onClick: p.onClick }, p.children) }
})

const result: RollDamageResult = { total: 14, half_damage: 7, breakdown: '2d6+2 = 14', damage_type: 'fire' } as RollDamageResult
const cantrip = { id: 1, name: 'Mano Magica', level: 0, attack_save: 'ATK', is_concentration: false, damage_dice: '1d8' } as Spell
const leveled = { id: 2, name: 'Palla di Fuoco', level: 3, attack_save: 'DEX', is_concentration: false, damage_dice: '8d6' } as Spell

afterEach(() => { rollDamage.mockReset(); useSpell.mockReset(); updateConc.mockReset() })

describe('SpellDamageSheet', () => {
  it('renders nothing without a spell', () => {
    const { container } = renderWithProviders(<SpellDamageSheet charId={7} spell={null} slotLevel={null} onClose={() => {}} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('a cantrip roll posts to rollDamage and shows the total (no slot consumed)', async () => {
    rollDamage.mockResolvedValue(result)
    useSpell.mockResolvedValue({ id: 7 })
    renderWithProviders(<SpellDamageSheet charId={7} spell={cantrip} slotLevel={null} onClose={() => {}} />)
    await userEvent.click(screen.getByRole('button', { name: /roll_button/ }))
    await waitFor(() => expect(rollDamage).toHaveBeenCalledWith(7, 1, expect.objectContaining({ casting_level: 0, is_critical: false })))
    expect(useSpell).toHaveBeenCalledTimes(1)  // il lancio passa dal server: conferme e opzioni, nessuno slot
    expect(useSpell.mock.calls[0][2].slot_id).toBeUndefined()
    expect(await screen.findByText('14')).toBeInTheDocument()
  })

  it('a leveled spell consumes the slot (api.spells.use) on the first roll', async () => {
    useSpell.mockResolvedValue({ id: 7 })
    rollDamage.mockResolvedValue(result)
    const concentrating = { ...leveled, is_concentration: true }
    renderWithProviders(<SpellDamageSheet charId={7} spell={concentrating} slotLevel={3} slotId={21} onClose={() => {}} />)
    await userEvent.click(screen.getByRole('button', { name: /roll_button/ }))
    await waitFor(() => expect(useSpell).toHaveBeenCalledWith(7, 2, expect.objectContaining({ slot_id: 21, slot_level: 3 })))
    await waitFor(() => expect(rollDamage).toHaveBeenCalled())
    expect(updateConc).not.toHaveBeenCalled()  // il contatore dei round resta quello del lancio
  })

  it('shows the second damage part before the roll, and the dice typed by hand do not replace it', async () => {
    rollDamage.mockResolvedValue(result)
    useSpell.mockResolvedValue({ id: 7 })
    const strike = { ...leveled, damage_dice: '4d6', extra_damage_dice: '4d6', extra_damage_type: 'radiant' } as Spell
    renderWithProviders(<SpellDamageSheet charId={7} spell={strike} slotLevel={5} onClose={() => {}} />)
    expect(screen.getByText(/character.spells.roll_damage.second_part/)).toBeInTheDocument()
    // il mock di framer-motion rimonta l'Input a ogni render: si scrive con un solo evento
    fireEvent.change(screen.getByPlaceholderText('character.spells.roll_damage.extra_dice_placeholder'), { target: { value: '1d4' } })
    await userEvent.click(screen.getByRole('button', { name: /roll_button/ }))
    await waitFor(() => expect(rollDamage).toHaveBeenCalledWith(7, 2, expect.objectContaining({ extra_dice: '1d4' })))
  })

  it('lets the player choose the type of a second part that has two (radiant or necrotic)', async () => {
    rollDamage.mockResolvedValue(result)
    useSpell.mockResolvedValue({ id: 7 })
    const wave = { ...leveled, damage_dice: '5d6', damage_type: 'thunder', extra_damage_dice: '5d6', extra_damage_type: 'radiant|necrotic' } as Spell
    renderWithProviders(<SpellDamageSheet charId={7} spell={wave} slotLevel={5} onClose={() => {}} />)
    await userEvent.click(screen.getByText('character.inventory.damage_types.dmg_necrotic'))
    await userEvent.click(screen.getByRole('button', { name: /roll_button/ }))
    await waitFor(() => expect(rollDamage).toHaveBeenCalledWith(7, 2, expect.objectContaining({ extra_damage_type: 'necrotic' })))
  })

  it('names each group of dice by its damage type in the result', async () => {
    rollDamage.mockResolvedValue({ ...result, parts: [
      { label: 'main', type: 'fire', kind: 'd6', rolls: [1, 2] }, { label: 'second', type: 'radiant', kind: 'd6', rolls: [3, 4] }] })
    useSpell.mockResolvedValue({ id: 7 })
    renderWithProviders(<SpellDamageSheet charId={7} spell={leveled} slotLevel={5} onClose={() => {}} />)
    await userEvent.click(screen.getByRole('button', { name: /roll_button/ }))
    expect(await screen.findByText(/dmg_radiant/)).toBeInTheDocument()
    expect(screen.getByText(/dmg_fire/)).toBeInTheDocument()
  })

  it('says the dice cannot be rolled, in plain words, when the spell is cast but its damage is not computable', async () => {
    useSpell.mockResolvedValue({ id: 7, damage_unrollable: true })
    renderWithProviders(<SpellDamageSheet charId={7} spell={leveled} slotLevel={3} slotId={21} onClose={() => {}} />)
    await userEvent.click(screen.getByRole('button', { name: /roll_button/ }))
    expect(await screen.findByText('character.spells.roll_damage.unrollable')).toBeInTheDocument()
    expect(rollDamage).not.toHaveBeenCalled()
  })

  it('says it too when the server refuses the dice after an attack roll', async () => {
    const { ApiError } = await import('@/api/client')
    rollDamage.mockRejectedValue(new ApiError(422, { code: 'bad_damage_dice' }))
    renderWithProviders(<SpellDamageSheet charId={7} spell={leveled} slotLevel={3} slotAlreadyConsumed onClose={() => {}} />)
    await userEvent.click(screen.getByRole('button', { name: /roll_button/ }))
    expect(await screen.findByText('character.spells.roll_damage.unrollable')).toBeInTheDocument()
  })

  it('shows what the damage did to the caster, written by the server in the option result (Overchannel)', async () => {
    rollDamage.mockResolvedValue({ ...result, option_result: {
      keys: ['wizard.overchannel'], extra_rolls: [], extra_total: 0, bonus: 0, multiplier: 1, spent: [], targets: [],
      effects: [{ it: 'Subisci 24 danni necrotici', en: 'You take 24 necrotic damage' }] } })
    useSpell.mockResolvedValue({ id: 7 })
    renderWithProviders(<SpellDamageSheet charId={7} spell={cantrip} slotLevel={null} onClose={() => {}} />)
    await userEvent.click(screen.getByRole('button', { name: /roll_button/ }))
    expect(await screen.findByText('Subisci 24 danni necrotici')).toBeInTheDocument()
  })

  it('a save spell shows the half-damage cell in the result', async () => {
    rollDamage.mockResolvedValue(result)
    renderWithProviders(<SpellDamageSheet charId={7} spell={leveled} slotLevel={3} onClose={() => {}} />)
    useSpell.mockResolvedValue({ id: 7 })
    await userEvent.click(screen.getByRole('button', { name: /roll_button/ }))
    expect(await screen.findByText('character.spells.roll_damage.half_damage')).toBeInTheDocument()
    expect(screen.getByText('7')).toBeInTheDocument()
  })

  it('does not consume the slot again after the attack roll', async () => {
    rollDamage.mockResolvedValue(result)
    const ray = { ...leveled, attack_save: 'ATK', is_concentration: true }
    renderWithProviders(<SpellDamageSheet charId={7} spell={ray} slotLevel={3} slotAlreadyConsumed onClose={() => {}} />)
    await userEvent.click(screen.getByRole('button', { name: /roll_button/ }))
    await waitFor(() => expect(rollDamage).toHaveBeenCalledWith(7, 2, expect.objectContaining({ casting_level: 3 })))
    expect(useSpell).not.toHaveBeenCalled()
    expect(updateConc).not.toHaveBeenCalled()
  })

  it('rolls a critical after a natural 20 and says so, with no manual switch', async () => {
    rollDamage.mockResolvedValue(result)
    renderWithProviders(<SpellDamageSheet charId={7} spell={cantrip} slotLevel={0} slotAlreadyConsumed initialCritical onClose={() => {}} />)
    expect(screen.queryByRole('switch')).not.toBeInTheDocument()
    expect(screen.getByText('character.spells.roll_damage.critical')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /roll_button/ }))
    await waitFor(() => expect(rollDamage).toHaveBeenCalledWith(7, 1, expect.objectContaining({ is_critical: true })))
  })

  it('never offers a critical without the attack roll', () => {
    renderWithProviders(<SpellDamageSheet charId={7} spell={cantrip} slotLevel={0} onClose={() => {}} />)
    expect(screen.queryByRole('switch')).not.toBeInTheDocument()
    expect(screen.queryByText('character.spells.roll_damage.critical')).not.toBeInTheDocument()
  })

  it('goes back to the slot step before rolling', async () => {
    const onBack = vi.fn()
    renderWithProviders(<SpellDamageSheet charId={7} spell={cantrip} slotLevel={0} onClose={() => {}} onBack={onBack} />)
    await userEvent.click(screen.getByRole('button', { name: 'common.back' }))
    expect(onBack).toHaveBeenCalledTimes(1)
  })
})
