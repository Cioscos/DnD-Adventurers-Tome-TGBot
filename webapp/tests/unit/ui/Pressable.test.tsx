import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Pressable from '@/components/ui/Pressable'

const { hap } = vi.hoisted(() => ({
  hap: { light: vi.fn(), medium: vi.fn(), success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}))
vi.mock('@/auth/telegram', () => ({ haptic: hap }))
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

describe('Pressable', () => {
  it('keeps caller className, fires onClick, no haptic by default', async () => {
    const onClick = vi.fn()
    render(<Pressable onClick={onClick} className="row-cls">Riga</Pressable>)
    const btn = screen.getByRole('button', { name: 'Riga' })
    expect(btn).toHaveClass('row-cls')
    await userEvent.click(btn)
    expect(onClick).toHaveBeenCalledTimes(1)
    expect(hap.light).not.toHaveBeenCalled()
  })

  it('pending: disabled, aria-busy, overlay spinner, click ignored', async () => {
    const onClick = vi.fn()
    render(<Pressable onClick={onClick} pending>Riga</Pressable>)
    const btn = screen.getByRole('button')
    expect(btn).toBeDisabled()
    expect(btn).toHaveAttribute('aria-busy', 'true')
    expect(screen.getByRole('status')).toBeInTheDocument()
    await userEvent.click(btn)
    expect(onClick).not.toHaveBeenCalled()
  })

  it('pending + spinner={false}: no spinner overlay rendered', () => {
    render(<Pressable pending spinner={false}>Riga</Pressable>)
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(screen.getByRole('button')).toBeDisabled()
  })

  it('haptic="light" fires the haptic', async () => {
    render(<Pressable haptic="light">X</Pressable>)
    await userEvent.click(screen.getByRole('button'))
    expect(hap.light).toHaveBeenCalledTimes(1)
  })
})
