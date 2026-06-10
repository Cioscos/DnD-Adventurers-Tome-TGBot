import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SelectSheet from '@/components/ui/SelectSheet'

vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return {
    default: (p: { open: boolean; title?: unknown; zClassName?: string; children?: unknown }) =>
      p.open
        ? React.createElement('div', { 'data-testid': 'sheet', 'data-z': p.zClassName },
            React.createElement('h2', null, p.title), p.children)
        : null,
  }
})

const OPTIONS = [
  { value: 'barbarian', label: 'Barbaro' },
  { value: 'wizard', label: 'Mago' },
  { value: 'cleric', label: 'Chierico' },
]

describe('SelectSheet', () => {
  it('shows the placeholder when no value is selected', () => {
    render(<SelectSheet label="Classe" options={OPTIONS} value="" onChange={() => {}} placeholder="Seleziona…" />)
    expect(screen.getByRole('button', { name: /Seleziona…/ })).toBeInTheDocument()
    expect(screen.queryByTestId('sheet')).not.toBeInTheDocument()
  })

  it('shows the selected option label on the trigger', () => {
    render(<SelectSheet label="Classe" options={OPTIONS} value="wizard" onChange={() => {}} />)
    expect(screen.getByRole('button', { name: /Mago/ })).toBeInTheDocument()
  })

  it('opens the sheet on tap and lists every option, checking the active one', async () => {
    render(<SelectSheet label="Classe" options={OPTIONS} value="wizard" onChange={() => {}} />)
    await userEvent.click(screen.getByRole('button', { name: /Mago/ }))
    expect(screen.getByTestId('sheet')).toBeInTheDocument()
    expect(screen.getAllByRole('radio')).toHaveLength(3)
    expect(screen.getByRole('radio', { name: /Mago/ })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByRole('radio', { name: /Barbaro/ })).toHaveAttribute('aria-checked', 'false')
  })

  it('fires onChange and closes when an option is picked', async () => {
    const onChange = vi.fn()
    render(<SelectSheet label="Classe" options={OPTIONS} value="" onChange={onChange} placeholder="Seleziona…" />)
    await userEvent.click(screen.getByRole('button', { name: /Seleziona…/ }))
    await userEvent.click(screen.getByRole('radio', { name: /Chierico/ }))
    expect(onChange).toHaveBeenCalledWith('cleric')
    expect(screen.queryByTestId('sheet')).not.toBeInTheDocument()
  })

  it('does not open when disabled', async () => {
    render(<SelectSheet label="Classe" options={OPTIONS} value="" onChange={() => {}} disabled />)
    await userEvent.click(screen.getByRole('button'))
    expect(screen.queryByTestId('sheet')).not.toBeInTheDocument()
  })

  it('raises the nested sheet z-index via zClassName (default z-[60])', async () => {
    render(<SelectSheet label="Classe" options={OPTIONS} value="" onChange={() => {}} />)
    await userEvent.click(screen.getByRole('button'))
    expect(screen.getByTestId('sheet')).toHaveAttribute('data-z', 'z-[60]')
  })
})
