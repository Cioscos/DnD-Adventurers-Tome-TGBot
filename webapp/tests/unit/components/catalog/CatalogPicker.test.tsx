import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import CatalogPicker from '@/components/catalog/CatalogPicker'
import { spellToForm, type SpellEntry } from '@/lib/srd/catalog'

vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})

describe('CatalogPicker', () => {
  it('searches in both languages and picking yields a prefill with srd_index', async () => {
    const onPick = vi.fn()
    render(<CatalogPicker kind="spells" onPick={onPick} onClose={() => {}} />)
    const box = await screen.findByRole('searchbox')
    await userEvent.type(box, 'palla di fuoco')
    const row = await screen.findByText('Palla di fuoco')
    await userEvent.click(row)
    const entry = onPick.mock.calls[0][0] as SpellEntry
    expect(entry.index).toBe('fireball')
    expect(spellToForm(entry, 'it', 'imperial').srd_index).toBe('fireball')
  })

  it('applies the filters prop', async () => {
    render(<CatalogPicker kind="monsters" onPick={() => {}} onClose={() => {}} filters={(e) => e.index === 'aboleth'} />)
    await waitFor(() => expect(screen.getByText('Aboleth')).toBeInTheDocument())
    expect(screen.getAllByRole('listitem')).toHaveLength(1)
  })
})
