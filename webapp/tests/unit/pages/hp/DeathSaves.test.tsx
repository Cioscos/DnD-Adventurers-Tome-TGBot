import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import DeathSaves from '@/pages/hp/DeathSaves'

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
vi.mock('@/styles/motion', () => ({ spring: new Proxy({}, { get: () => ({}) }) }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/components/ui/Surface', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/ui/Button', async () => {
  const React = await import('react')
  return {
    default: (p: { onClick?: () => void; disabled?: boolean; children?: unknown }) =>
      React.createElement('button', { onClick: p.onClick, disabled: p.disabled }, p.children),
  }
})

type DS = { successes: number; failures: number; stable: boolean }
const ds = (over: Partial<DS> = {}): DS => ({ successes: 0, failures: 0, stable: false, ...over })

describe('DeathSaves', () => {
  it('renders the title, both pip labels and the roll button', () => {
    render(<DeathSaves deathSaves={ds()} onRoll={() => {}} onAction={() => {}} isRolling={false} />)
    expect(screen.getByText('character.death_saves.title')).toBeInTheDocument()
    expect(screen.getByText('character.death_saves.successes')).toBeInTheDocument()
    expect(screen.getByText('character.death_saves.failures')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'character.death_saves.roll' })).toBeInTheDocument()
  })

  it('roll button calls onRoll and is disabled/loading while rolling', async () => {
    const onRoll = vi.fn()
    const { rerender } = render(<DeathSaves deathSaves={ds()} onRoll={onRoll} onAction={() => {}} isRolling={false} />)
    await userEvent.click(screen.getByRole('button', { name: 'character.death_saves.roll' }))
    expect(onRoll).toHaveBeenCalledTimes(1)
    rerender(<DeathSaves deathSaves={ds()} onRoll={onRoll} onAction={() => {}} isRolling />)
    expect(screen.getByRole('button', { name: 'character.death_saves.roll' })).toBeDisabled()
  })

  it.each(['reset', 'success', 'failure', 'stabilize'])(
    'manual override "%s" calls onAction with that action',
    async (action) => {
      const onAction = vi.fn()
      render(<DeathSaves deathSaves={ds()} onRoll={() => {}} onAction={onAction} isRolling={false} />)
      await userEvent.click(screen.getByRole('button', { name: `character.death_saves.${action}` }))
      expect(onAction).toHaveBeenCalledWith(action)
    },
  )

  it('pulses the failures pip group only once failures reach 2 (urgent state)', () => {
    const { container, rerender } = render(
      <DeathSaves deathSaves={ds({ failures: 1 })} onRoll={() => {}} onAction={() => {}} isRolling={false} />,
    )
    expect(container.querySelector('.animate-pulse')).toBeNull()
    rerender(<DeathSaves deathSaves={ds({ failures: 2 })} onRoll={() => {}} onAction={() => {}} isRolling={false} />)
    expect(container.querySelector('.animate-pulse')).not.toBeNull()
  })
})
