import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SorcerousRestorationPicker from '@/components/character/SorcerousRestorationPicker'
import type { CharacterFull } from '@/types'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string, o?: Record<string, unknown>) => (o ? `${k}:${JSON.stringify(o)}` : k), i18n: { language: 'it' } }) }
})

const sorcerer = (level: number, uses: number, points: [number, number]) => ({
  id: 3,
  classes: [{ id: 1, class_name: 'sorcerer', level }],
  abilities: [
    { id: 1, feature_key: 'sorcerer.sorcerous_restoration', max_uses: 1, uses },
    { id: 2, feature_key: 'sorcerer.sorcery_points', max_uses: points[1], uses: points[0] },
  ],
}) as unknown as CharacterFull

describe('SorcerousRestorationPicker', () => {
  it('caps the points at half the sorcerer level and at the points actually spent', async () => {
    const onChange = vi.fn()
    const { rerender } = render(<SorcerousRestorationPicker char={sorcerer(11, 1, [3, 11])} value={5} onChange={onChange} />)
    expect(screen.getByText(/sorcerous_restoration_hint.*"max":5/)).toBeInTheDocument()
    expect(screen.getByTestId('sr-plus').querySelector('button')).toBeDisabled()
    await userEvent.click(screen.getByTestId('sr-minus').querySelector('button') as HTMLButtonElement)
    expect(onChange).toHaveBeenCalledWith(4)
    rerender(<SorcerousRestorationPicker char={sorcerer(11, 1, [10, 11])} value={0} onChange={onChange} />)
    expect(screen.getByText(/"max":1/)).toBeInTheDocument()
  })

  it('is hidden without the use, with full points or below the feature level', () => {
    for (const c of [sorcerer(11, 0, [3, 11]), sorcerer(11, 1, [11, 11]), sorcerer(1, 1, [0, 1])]) {
      const { container, unmount } = render(<SorcerousRestorationPicker char={c} value={0} onChange={() => {}} />)
      expect(container).toBeEmptyDOMElement()
      unmount()
    }
  })
})
