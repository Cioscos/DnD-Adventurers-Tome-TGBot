import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ChipSelect from '@/components/ui/ChipSelect'

vi.mock('framer-motion', async () => {
  const React = await import('react')
  const MOTION = new Set(['initial', 'animate', 'exit', 'transition', 'variants', 'whileTap', 'whileHover', 'layout'])
  const make = (tag: string) => (props: Record<string, unknown>) => {
    const clean: Record<string, unknown> = {}
    for (const k in props) if (!MOTION.has(k)) clean[k] = props[k]
    return React.createElement(tag, clean)
  }
  // Cache per tag: identità stabile dei componenti, altrimenti ogni re-render
  // smonta/rimonta il sottoalbero (input che perdono focus a metà digitazione).
  const cache: Record<string, unknown> = {}
  return { m: new Proxy({}, { get: (_t: object, tag: string | symbol) => (cache[String(tag)] ??= make(String(tag))) }) }
})

const OPTIONS = [
  { value: 'long_rest', label: 'Riposo lungo' },
  { value: 'short_rest', label: 'Riposo breve' },
  { value: 'manual', label: 'Manuale' },
]

describe('ChipSelect', () => {
  it('renders one radio chip per option and marks the active one', () => {
    render(<ChipSelect label="Recupero" options={OPTIONS} value="short_rest" onChange={() => {}} />)
    expect(screen.getAllByRole('radio')).toHaveLength(3)
    expect(screen.getByRole('radio', { name: 'Riposo breve' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByRole('radio', { name: 'Manuale' })).toHaveAttribute('aria-checked', 'false')
    expect(screen.getByText('Recupero')).toBeInTheDocument()
  })

  it('fires onChange with the option value on tap', async () => {
    const onChange = vi.fn()
    render(<ChipSelect options={OPTIONS} value="manual" onChange={onChange} />)
    await userEvent.click(screen.getByRole('radio', { name: 'Riposo lungo' }))
    expect(onChange).toHaveBeenCalledWith('long_rest')
  })

  it('does not fire onChange when disabled', async () => {
    const onChange = vi.fn()
    render(<ChipSelect options={OPTIONS} value="manual" onChange={onChange} disabled />)
    await userEvent.click(screen.getByRole('radio', { name: 'Riposo lungo' }))
    expect(onChange).not.toHaveBeenCalled()
  })

  it('spans the orphan last chip across the full row in a grid (chip-grid rule)', () => {
    render(<ChipSelect options={OPTIONS} value="manual" onChange={() => {}} columns={2} />)
    expect(screen.getByRole('radio', { name: 'Manuale' })).toHaveClass('col-span-full')
    expect(screen.getByRole('radio', { name: 'Riposo lungo' })).not.toHaveClass('col-span-full')
  })

  it('uses flex-wrap (no grid) when columns is omitted', () => {
    render(<ChipSelect options={OPTIONS} value="manual" onChange={() => {}} />)
    expect(screen.getByRole('radiogroup')).toHaveClass('flex-wrap')
  })
})
