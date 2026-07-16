import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import IconButton from '@/components/ui/IconButton'

const { hap } = vi.hoisted(() => ({
  hap: { light: vi.fn(), medium: vi.fn(), success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}))
vi.mock('@/auth/telegram', () => ({ haptic: hap }))
vi.mock('@/styles/motion', () => ({ spring: new Proxy({}, { get: () => ({}) }) }))
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

beforeEach(() => Object.values(hap).forEach((f) => f.mockClear()))

describe('IconButton', () => {
  it('renders the icon and fires onClick with light haptic by default', async () => {
    const onClick = vi.fn()
    render(<IconButton icon={<svg data-testid="ico" />} onClick={onClick} aria-label="del" />)
    await userEvent.click(screen.getByRole('button', { name: 'del' }))
    expect(onClick).toHaveBeenCalledTimes(1)
    expect(hap.light).toHaveBeenCalledTimes(1)
    expect(screen.getByTestId('ico')).toBeInTheDocument()
  })

  it('while loading: disabled, spinner replaces icon, onClick ignored', async () => {
    const onClick = vi.fn()
    render(<IconButton icon={<svg data-testid="ico" />} onClick={onClick} loading aria-label="del" />)
    const btn = screen.getByRole('button')
    expect(btn).toBeDisabled()
    expect(btn).toHaveAttribute('aria-busy', 'true')
    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(screen.queryByTestId('ico')).not.toBeInTheDocument()
    await userEvent.click(btn)
    expect(onClick).not.toHaveBeenCalled()
  })

  it('haptic="none" fires no haptic', async () => {
    render(<IconButton icon={<span />} haptic="none" aria-label="x" />)
    await userEvent.click(screen.getByRole('button'))
    expect(hap.light).not.toHaveBeenCalled()
  })
})
