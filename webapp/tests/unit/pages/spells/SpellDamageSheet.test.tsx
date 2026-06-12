import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../utils/renderWithProviders'
import SpellDamageSheet from '@/pages/spells/SpellDamageSheet'
import type { Spell, RollDamageResult } from '@/types'

const { rollDamage, useSpell, updateConc } = vi.hoisted(() => ({ rollDamage: vi.fn(), useSpell: vi.fn(), updateConc: vi.fn() }))

vi.mock('@/api/client', () => ({ api: { spells: { rollDamage, use: useSpell, updateConcentration: updateConc } } }))
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
    renderWithProviders(<SpellDamageSheet charId={7} spell={cantrip} slotLevel={null} onClose={() => {}} />)
    await userEvent.click(screen.getByRole('button', { name: /roll_button/ }))
    await waitFor(() => expect(rollDamage).toHaveBeenCalledWith(7, 1, expect.objectContaining({ casting_level: 0, is_critical: false })))
    expect(useSpell).not.toHaveBeenCalled()
    expect(await screen.findByText('14')).toBeInTheDocument()
  })

  it('a leveled spell consumes the slot (api.spells.use) on the first roll', async () => {
    useSpell.mockResolvedValue({ id: 7 })
    rollDamage.mockResolvedValue(result)
    renderWithProviders(<SpellDamageSheet charId={7} spell={leveled} slotLevel={3} onClose={() => {}} />)
    await userEvent.click(screen.getByRole('button', { name: /roll_button/ }))
    await waitFor(() => expect(useSpell).toHaveBeenCalledWith(7, 2, 3))
    await waitFor(() => expect(rollDamage).toHaveBeenCalled())
  })

  it('a save spell shows the half-damage cell in the result', async () => {
    rollDamage.mockResolvedValue(result)
    renderWithProviders(<SpellDamageSheet charId={7} spell={leveled} slotLevel={3} onClose={() => {}} />)
    useSpell.mockResolvedValue({ id: 7 })
    await userEvent.click(screen.getByRole('button', { name: /roll_button/ }))
    expect(await screen.findByText('character.spells.roll_damage.half_damage')).toBeInTheDocument()
    expect(screen.getByText('7')).toBeInTheDocument()
  })
})
