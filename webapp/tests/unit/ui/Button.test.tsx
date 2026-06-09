import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Button from '@/components/ui/Button'

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

describe('Button', () => {
  it('renders children and fires onClick', async () => {
    const onClick = vi.fn()
    render(<Button onClick={onClick}>Go</Button>)
    await userEvent.click(screen.getByRole('button', { name: 'Go' }))
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('does not fire onClick when disabled, and is disabled while loading', async () => {
    const onClick = vi.fn()
    const { rerender } = render(<Button onClick={onClick} disabled>X</Button>)
    await userEvent.click(screen.getByRole('button'))
    expect(onClick).not.toHaveBeenCalled()
    rerender(<Button onClick={onClick} loading>X</Button>)
    expect(screen.getByRole('button')).toBeDisabled()
  })

  it('triggers the requested haptic kind on click', async () => {
    render(<Button haptic="success">S</Button>)
    await userEvent.click(screen.getByRole('button'))
    expect(hap.success).toHaveBeenCalledTimes(1)
  })

  it('fires no haptic when haptic="none"', async () => {
    render(<Button haptic="none">N</Button>)
    await userEvent.click(screen.getByRole('button'))
    expect(hap.light).not.toHaveBeenCalled()
    expect(hap.success).not.toHaveBeenCalled()
  })
})
