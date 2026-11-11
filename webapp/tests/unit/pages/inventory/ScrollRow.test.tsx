import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ScrollRow } from '@/pages/inventory/InventoryItem'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})

describe('ScrollRow (punto 45)', () => {
  it('two scrolls open together keep distinct ids, each label bound to its own select', async () => {
    const first = vi.fn(), second = vi.fn()
    render(<><ScrollRow onScroll={first} /><ScrollRow onScroll={second} /></>)
    const selects = screen.getAllByRole('combobox')
    expect(new Set(selects.map((s) => s.id)).size).toBe(2)
    const labels = screen.getAllByText('character.inventory.magic.scroll_level')
    expect(labels.map((l) => l.getAttribute('for'))).toEqual(selects.map((s) => s.id))
    await userEvent.selectOptions(selects[1], '3')
    await userEvent.click(screen.getAllByText('character.inventory.magic.scroll_cast')[1])
    expect(second).toHaveBeenCalledWith(3)
    expect(first).not.toHaveBeenCalled()
  })
})
