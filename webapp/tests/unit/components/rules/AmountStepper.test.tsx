import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import AmountStepper from '@/components/rules/AmountStepper'

vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (k: string) => k }) }))

describe('AmountStepper', () => {
  it('a large pool (Lay on Hands) also steps by 5, clamped to the bounds (L2)', () => {
    const onChange = vi.fn()
    render(<AmountStepper value={3} min={1} max={25} onChange={onChange} />)
    fireEvent.click(screen.getByLabelText('character.turn.amount_more_big'))
    expect(onChange).toHaveBeenLastCalledWith(8)
    fireEvent.click(screen.getByLabelText('character.turn.amount_less_big'))
    expect(onChange).toHaveBeenLastCalledWith(1)
  })

  it('a small pool keeps only the ±1 buttons', () => {
    render(<AmountStepper value={1} min={1} max={4} onChange={() => {}} />)
    expect(screen.queryByLabelText('character.turn.amount_more_big')).toBeNull()
  })
})
