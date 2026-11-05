import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../utils/renderWithProviders'
import SpellHealingSheet from '@/pages/spells/SpellHealingSheet'
import type { Spell, RollHealingResult } from '@/types'

const { rollHealing, useSpell } = vi.hoisted(() => ({ rollHealing: vi.fn(), useSpell: vi.fn() }))

vi.mock('@/api/client', () => ({ api: { spells: { rollHealing, use: useSpell } } }))
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

const result = { total: 11, breakdown: '1d8=[5] +3 +3 = 11', maximized: false, healed: 0, self_healed: 4, modifier: 3, bonus: 3, rolls: [5], main_rolls: [5], casting_level: 1, main_kind: 'd8' } as RollHealingResult
const cure = { id: 3, name: 'Cura ferite', level: 1, srd_index: 'cure-wounds' } as Spell

afterEach(() => { rollHealing.mockReset(); useSpell.mockReset() })

describe('SpellHealingSheet', () => {
  it('renders nothing without a spell', () => {
    const { container } = renderWithProviders(<SpellHealingSheet charId={7} spell={null} slotLevel={null} onClose={() => {}} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('casts with the slot, asks the server for the healing and shows the total and the self healing', async () => {
    useSpell.mockResolvedValue({ id: 7 })
    rollHealing.mockResolvedValue(result)
    renderWithProviders(<SpellHealingSheet charId={7} spell={cure} slotLevel={2} slotId={21} onClose={() => {}} />)
    await userEvent.click(screen.getByRole('button', { name: /roll_button/ }))
    await waitFor(() => expect(useSpell).toHaveBeenCalledWith(7, 3, expect.objectContaining({ slot_id: 21, slot_level: 2 })))
    await waitFor(() => expect(rollHealing).toHaveBeenCalledWith(7, 3, expect.objectContaining({ casting_level: 2, apply_to_self: false })))
    expect(await screen.findByText('11')).toBeInTheDocument()
    expect(screen.getByText('character.spells.roll_healing.self_healed')).toBeInTheDocument()
  })

  it('sends apply_to_self when the caster is the target', async () => {
    useSpell.mockResolvedValue({ id: 7 })
    rollHealing.mockResolvedValue({ ...result, healed: 11 })
    renderWithProviders(<SpellHealingSheet charId={7} spell={cure} slotLevel={1} onClose={() => {}} />)
    await userEvent.click(screen.getByRole('switch'))
    await userEvent.click(screen.getByRole('button', { name: /roll_button/ }))
    await waitFor(() => expect(rollHealing).toHaveBeenCalledWith(7, 3, expect.objectContaining({ apply_to_self: true })))
  })
})
