import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import DamageDiceBuilder from '@/pages/inventory/DamageDiceBuilder'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})

// The count/mod steppers are icon-only buttons (no text); the die chips carry "d{n}".
const iconButtons = () => screen.getAllByRole('button').filter((b) => (b.textContent || '').trim() === '')

describe('DamageDiceBuilder', () => {
  it('parses the notation into count / die / modifier and previews it', () => {
    render(<DamageDiceBuilder value="2d6+3" onChange={() => {}} />)
    expect(screen.getByText('2')).toBeInTheDocument() // count
    expect(screen.getByText('+3')).toBeInTheDocument() // modifier
    expect(screen.getByRole('button', { name: 'd6' })).toHaveClass('bg-dnd-gold') // active die
    expect(screen.getByText('2d6 + 3')).toBeInTheDocument() // preview
  })

  it('selecting a die re-serializes keeping count and modifier (contract with serializeDamageDice)', async () => {
    const onChange = vi.fn()
    render(<DamageDiceBuilder value="2d6+3" onChange={onChange} />)
    await userEvent.click(screen.getByRole('button', { name: 'd8' }))
    expect(onChange).toHaveBeenCalledWith('2d8+3')
  })

  it('incrementing the dice count re-serializes', async () => {
    const onChange = vi.fn()
    render(<DamageDiceBuilder value="2d6+3" onChange={onChange} />)
    await userEvent.click(iconButtons()[1]) // count "+"
    expect(onChange).toHaveBeenCalledWith('3d6+3')
  })

  it('decrementing the modifier re-serializes (positive → smaller positive)', async () => {
    const onChange = vi.fn()
    render(<DamageDiceBuilder value="2d6+3" onChange={onChange} />)
    await userEvent.click(iconButtons()[2]) // modifier "−"
    expect(onChange).toHaveBeenCalledWith('2d6+2')
  })

  it('clamps the count at the minimum of 1 (decrement disabled)', () => {
    render(<DamageDiceBuilder value="1d6" onChange={() => {}} />)
    expect(iconButtons()[0]).toBeDisabled() // count "−"
  })
})
