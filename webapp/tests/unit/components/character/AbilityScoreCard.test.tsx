import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import AbilityScoreCard from '@/components/character/AbilityScoreCard'
import type { AbilityScore } from '@/types'

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
    useReducedMotion: () => false,
  }
})
vi.mock('@/styles/motion', () => ({ spring: new Proxy({}, { get: () => ({}) }) }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))

const score = (over: Partial<AbilityScore> = {}): AbilityScore =>
  ({ name: 'dexterity', value: 16, modifier: 3, modifiers_applied: [{ source: 'X', kind: 'relative', value: 2 }], ...over } as AbilityScore)

describe('AbilityScoreCard', () => {
  it('renders the value and signed modifier', () => {
    render(<AbilityScoreCard score={score()} expanded={false} onToggle={() => {}} onEdit={() => {}} />)
    expect(screen.getByText('16')).toBeInTheDocument()
    expect(screen.getByText('+3')).toBeInTheDocument()
  })

  it('the pencil triggers edit', async () => {
    const onEdit = vi.fn()
    render(<AbilityScoreCard score={score()} expanded={false} onToggle={() => {}} onEdit={onEdit} />)
    await userEvent.click(screen.getByRole('button', { name: 'common.edit' }))
    expect(onEdit).toHaveBeenCalledTimes(1)
  })

  it('exposes an expand toggle only when there are bonuses to reveal', async () => {
    const onToggle = vi.fn()
    render(<AbilityScoreCard score={score()} expanded={false} onToggle={onToggle} onEdit={() => {}} />)
    const expand = screen.getByRole('button', { name: 'character.stats.dexterity' })
    expect(expand).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(expand)
    expect(onToggle).toHaveBeenCalledTimes(1)
  })

  it('hides the expand toggle when the score has no modifiers', () => {
    render(<AbilityScoreCard score={score({ modifiers_applied: [] })} expanded={false} onToggle={() => {}} onEdit={() => {}} />)
    expect(screen.queryByRole('button', { name: 'character.stats.dexterity' })).not.toBeInTheDocument()
  })
})
