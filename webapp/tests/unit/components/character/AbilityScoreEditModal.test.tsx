import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import AbilityScoreEditModal from '@/components/character/AbilityScoreEditModal'

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
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; children?: unknown }) => (p.open ? React.createElement('div', null, p.children) : null) }
})
vi.mock('@/components/ui/Input', async () => {
  const React = await import('react')
  return {
    default: (p: { value: string; onChange: (v: string) => void }) =>
      React.createElement('input', { 'data-testid': 'score-input', value: p.value, onChange: (e: { target: { value: string } }) => p.onChange(e.target.value) }),
  }
})
vi.mock('@/components/ui/Button', async () => {
  const React = await import('react')
  return {
    default: (p: { onClick?: () => void; disabled?: boolean; loading?: boolean; children?: unknown }) =>
      React.createElement('button', { onClick: p.onClick, disabled: p.disabled || p.loading }, p.children),
  }
})

describe('AbilityScoreEditModal', () => {
  it('seeds the current value and computes the D&D 5e ability modifier', () => {
    render(<AbilityScoreEditModal open label="DEX" currentValue={14} onClose={() => {}} onSave={() => {}} />)
    expect(screen.getByText('14')).toBeInTheDocument()
    expect(screen.getByText(/\+2/)).toBeInTheDocument() // floor((14-10)/2) = +2
  })

  it('keeps Save disabled until the value actually changes, then saves the new value', async () => {
    const onSave = vi.fn()
    render(<AbilityScoreEditModal open label="DEX" currentValue={14} onClose={() => {}} onSave={onSave} />)
    const save = screen.getByRole('button', { name: 'common.save' })
    expect(save).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: 'character.stats.increase' }))
    expect(screen.getByText('15')).toBeInTheDocument()
    expect(save).toBeEnabled()
    await userEvent.click(save)
    expect(onSave).toHaveBeenCalledWith(15)
  })

  it('cancel closes without saving', async () => {
    const onClose = vi.fn()
    render(<AbilityScoreEditModal open label="DEX" currentValue={14} onClose={onClose} onSave={() => {}} />)
    await userEvent.click(screen.getByRole('button', { name: 'common.cancel' }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('clamps at the bounds (decrement disabled at 1, increment disabled at 30)', () => {
    const { rerender } = render(<AbilityScoreEditModal open label="DEX" currentValue={1} onClose={() => {}} onSave={() => {}} />)
    expect(screen.getByRole('button', { name: 'character.stats.decrease' })).toBeDisabled()
    rerender(<AbilityScoreEditModal open label="DEX" currentValue={30} onClose={() => {}} onSave={() => {}} />)
    expect(screen.getByRole('button', { name: 'character.stats.increase' })).toBeDisabled()
  })
})
