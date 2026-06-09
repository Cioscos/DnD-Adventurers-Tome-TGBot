import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import HitDiceModal from '@/pages/hp/HitDiceModal'
import type { CharacterClass } from '@/types'

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
  return { m: new Proxy({}, { get: (_t: object, tag: string | symbol) => make(String(tag)) }) }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return {
    default: (p: { title?: unknown; children?: unknown }) =>
      React.createElement('div', { 'data-testid': 'sheet' }, React.createElement('div', null, p.title), p.children),
  }
})
vi.mock('@/components/ui/Button', async () => {
  const React = await import('react')
  return {
    default: (p: { onClick?: () => void; disabled?: boolean; children?: unknown }) =>
      React.createElement('button', { onClick: p.onClick, disabled: p.disabled }, p.children),
  }
})

const classes = [{ id: 1, class_name: 'fighter', hit_die: 10, level: 5 }] as unknown as CharacterClass[]

// The stepper +/- are icon-only buttons (no text) → identify them as the empty-text buttons.
const stepperButtons = () => screen.getAllByRole('button').filter((b) => (b.textContent || '').trim() === '')

describe('HitDiceModal', () => {
  it('renders an empty state when the character has no classes', () => {
    render(
      <HitDiceModal classes={[]} onSpend={() => {}} onConfirmRest={() => {}} onClose={() => {}} isPending={false} />,
    )
    expect(screen.getByText('common.none')).toBeInTheDocument()
  })

  it('lists each class with its hit-die size', () => {
    render(
      <HitDiceModal classes={classes} onSpend={() => {}} onConfirmRest={() => {}} onClose={() => {}} isPending={false} />,
    )
    expect(screen.getByText('fighter')).toBeInTheDocument()
    expect(screen.getByText('d10')).toBeInTheDocument()
  })

  it('keeps the roll button disabled at 0 dice, then spends the chosen count for that class', async () => {
    const onSpend = vi.fn()
    render(
      <HitDiceModal classes={classes} onSpend={onSpend} onConfirmRest={() => {}} onClose={() => {}} isPending={false} />,
    )
    expect(screen.getByRole('button', { name: 'Roll' })).toBeDisabled()

    // stepperButtons()[1] is the "+" button (after the "−" at index 0).
    await userEvent.click(stepperButtons()[1])
    await userEvent.click(stepperButtons()[1])
    expect(screen.getByText('2')).toBeInTheDocument()

    const roll = screen.getByRole('button', { name: 'Roll' })
    expect(roll).toBeEnabled()
    await userEvent.click(roll)
    expect(onSpend).toHaveBeenCalledWith(1, 2)
  })

  it('decrementing never goes below zero', async () => {
    render(
      <HitDiceModal classes={classes} onSpend={() => {}} onConfirmRest={() => {}} onClose={() => {}} isPending={false} />,
    )
    await userEvent.click(stepperButtons()[0]) // "−" at 0 → clamps to 0
    expect(screen.getByText('0')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Roll' })).toBeDisabled()
  })

  it('confirm-rest and cancel call their respective callbacks', async () => {
    const onConfirmRest = vi.fn()
    const onClose = vi.fn()
    render(
      <HitDiceModal
        classes={classes}
        onSpend={() => {}}
        onConfirmRest={onConfirmRest}
        onClose={onClose}
        isPending={false}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: 'character.hp.confirm_rest' }))
    expect(onConfirmRest).toHaveBeenCalledTimes(1)
    await userEvent.click(screen.getByRole('button', { name: 'common.cancel' }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
