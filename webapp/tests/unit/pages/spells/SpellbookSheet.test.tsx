import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import SpellbookSheet from '@/pages/spells/SpellbookSheet'
import { bookModes } from '@/lib/spellbook'
import type { Spell } from '@/types'

const { spellbookCost, copyToBook, toastSuccess, toastError } = vi.hoisted(() => ({
  spellbookCost: vi.fn(), copyToBook: vi.fn(), toastSuccess: vi.fn(), toastError: vi.fn(),
}))

vi.mock('@/api/client', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, api: { spells: { spellbookCost, copyToBook } } }
})
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ success: toastSuccess, error: toastError }) }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/lib/mutationError', async (orig) => ({ ...(await orig<typeof import('@/lib/mutationError')>()), notifyMutationError: vi.fn() }))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string, o?: Record<string, unknown>) => (o ? `${k}:${JSON.stringify(o)}` : k), i18n: { language: 'it' } }) }
})
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; children?: unknown }) => (p.open ? React.createElement('div', null, p.children) : null) }
})

const spell = (over: Partial<Spell> = {}) => ({
  id: 5, name: 'Scudo', level: 1, school: 'abjuration', is_prepared: false, is_concentration: false, is_ritual: false, is_pinned: false,
  in_spellbook: false, in_backup: false, has_book: true, ...over,
}) as Spell

function setup(s: Spell) {
  const onClose = vi.fn()
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(<QueryClientProvider client={qc}><SpellbookSheet charId={7} spell={s} open onClose={onClose} /></QueryClientProvider>)
  return { onClose }
}

afterEach(() => vi.clearAllMocks())

describe('bookModes', () => {
  it('offers the copy outside the book, the backup inside, and the rewrite for a prepared spell', () => {
    expect(bookModes(spell())).toEqual(['copy'])
    expect(bookModes(spell({ is_prepared: true }))).toEqual(['copy', 'retranscribe'])
    expect(bookModes(spell({ in_spellbook: true }))).toEqual(['backup'])
    expect(bookModes(spell({ in_spellbook: true, in_backup: true }))).toEqual([])
  })
})

describe('SpellbookSheet', () => {
  it('shows the server cost and pays the copy', async () => {
    spellbookCost.mockResolvedValue({ hours: 1, gold: 25, halved: true })
    copyToBook.mockResolvedValue({ id: 7 })
    const { onClose } = setup(spell())
    await waitFor(() => expect(screen.getByTestId('book-cost')).toHaveTextContent('"gold":25'))
    expect(spellbookCost).toHaveBeenCalledWith(7, 1, 'abjuration', 'copy')
    await userEvent.click(screen.getByText('character.spells.book.confirm'))
    await waitFor(() => expect(copyToBook).toHaveBeenCalledWith(7, 5, 'copy'))
    await waitFor(() => expect(onClose).toHaveBeenCalled())
  })

  it('names the missing gold instead of a generic error', async () => {
    const { ApiError } = await import('@/api/client')
    spellbookCost.mockResolvedValue({ hours: 2, gold: 50, halved: false })
    copyToBook.mockRejectedValue(new ApiError(409, 'insufficient_funds'))
    setup(spell())
    await waitFor(() => expect(screen.getByTestId('book-cost')).toHaveTextContent('"gold":50'))
    await userEvent.click(screen.getByText('character.spells.book.confirm'))
    await waitFor(() => expect(toastError).toHaveBeenCalledWith('character.spells.insufficient_funds'))
  })

  it('lets a prepared spell choose between copy and rewrite', async () => {
    spellbookCost.mockResolvedValue({ hours: 2, gold: 50, halved: false })
    setup(spell({ is_prepared: true }))
    await userEvent.click(screen.getByText('character.spells.book.mode_retranscribe'))
    await waitFor(() => expect(spellbookCost).toHaveBeenCalledWith(7, 1, 'abjuration', 'retranscribe'))
  })
})
