import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import InspirationRerollButton from '@/components/InspirationRerollButton'

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

describe('InspirationRerollButton', () => {
  it('renders nothing when inspiration is unavailable', () => {
    const { container } = render(<InspirationRerollButton available={false} onClick={() => {}} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders and fires onClick when available', async () => {
    const onClick = vi.fn()
    render(<InspirationRerollButton available onClick={onClick} />)
    await userEvent.click(screen.getByRole('button'))
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('is disabled while pending', () => {
    render(<InspirationRerollButton available pending onClick={() => {}} />)
    expect(screen.getByRole('button')).toBeDisabled()
  })
})
