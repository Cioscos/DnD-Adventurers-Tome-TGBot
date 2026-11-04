import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SpellSlotsSummary from '@/components/character/SpellSlotsSummary'
import type { SpellSlot } from '@/types'

const { navigateSpy } = vi.hoisted(() => ({ navigateSpy: vi.fn() }))

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('react-router-dom', () => ({
  useParams: () => ({ id: '7' }),
  useNavigate: () => navigateSpy,
}))
vi.mock('framer-motion', async () => {
  const React = await import('react')
  const MOTION = new Set(['initial', 'animate', 'exit', 'transition', 'variants', 'whileTap', 'whileHover', 'drag', 'layout'])
  const make = (tag: string) => (props: Record<string, unknown>) => {
    const clean: Record<string, unknown> = {}
    for (const k in props) if (!MOTION.has(k)) clean[k] = props[k]
    return React.createElement(tag, clean)
  }
  return { m: new Proxy({}, { get: (_t: object, tag: string | symbol) => make(String(tag)) }) }
})
vi.mock('@/components/ui/Surface', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))

const slot = (level: number, total: number, available = total): SpellSlot => ({ level, total, available } as unknown as SpellSlot)

afterEach(() => navigateSpy.mockReset())

describe('SpellSlotsSummary', () => {
  it('renders nothing when there are no slots', () => {
    const { container } = render(<SpellSlotsSummary slots={[]} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing when every level has zero slots', () => {
    const { container } = render(<SpellSlotsSummary slots={[slot(1, 0), slot(2, 0)]} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('sums per spell level and shows what is left (Warlock multiclass: two level-1 rows → combined count)', () => {
    const { container } = render(<SpellSlotsSummary slots={[slot(1, 2, 1), slot(1, 1, 1)]} />)
    expect(container.querySelector('.text-dnd-gold-bright')?.textContent).toBe('2')
  })

  it('always shows all nine levels, with what is left in each', () => {
    const { container } = render(<SpellSlotsSummary slots={[slot(2, 3), slot(1, 4, 0), slot(3, 0)]} />)
    const cells = [...container.querySelectorAll('.grid > div')].map((c) => c.textContent)
    expect(cells).toEqual(['10', '23', '3–', '4–', '5–', '6–', '7–', '8–', '9–'])
  })

  it('navigates to the slots page when tapped', async () => {
    render(<SpellSlotsSummary slots={[slot(1, 2)]} />)
    await userEvent.click(screen.getByRole('button'))
    expect(navigateSpy).toHaveBeenCalledWith('/char/7/slots')
  })
})
