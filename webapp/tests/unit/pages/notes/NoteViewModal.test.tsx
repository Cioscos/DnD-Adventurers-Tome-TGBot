import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import NoteViewModal from '@/pages/notes/NoteViewModal'
import type { Note } from '@/types'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; title?: unknown; children?: unknown }) => (p.open ? React.createElement('div', null, React.createElement('h2', null, p.title), p.children) : null) }
})
vi.mock('@/components/ui/Button', async () => {
  const React = await import('react')
  return { default: (p: { onClick?: () => void; children?: unknown }) => React.createElement('button', { onClick: p.onClick }, p.children) }
})

const note = { title: 'La Cripta', body: 'Testo *enfasi*', tags: ['Lore', 'NPC'] } as Note

describe('NoteViewModal', () => {
  it('renders nothing when no note is selected', () => {
    const { container } = render(<NoteViewModal note={null} onClose={() => {}} onEdit={() => {}} onDelete={() => {}} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('shows the note title, tags and inline-markdown body', () => {
    render(<NoteViewModal note={note} onClose={() => {}} onEdit={() => {}} onDelete={() => {}} />)
    expect(screen.getByRole('heading', { name: 'La Cripta' })).toBeInTheDocument()
    expect(screen.getByText('Lore')).toBeInTheDocument()
    expect(screen.getByText('enfasi').tagName).toBe('EM')
  })

  it('wires edit / delete / close', async () => {
    const onEdit = vi.fn(); const onDelete = vi.fn(); const onClose = vi.fn()
    render(<NoteViewModal note={note} onClose={onClose} onEdit={onEdit} onDelete={onDelete} />)
    await userEvent.click(screen.getByRole('button', { name: 'common.edit' }))
    expect(onEdit).toHaveBeenCalledWith('La Cripta', 'Testo *enfasi*', ['Lore', 'NPC'])
    await userEvent.click(screen.getByRole('button', { name: 'common.delete' }))
    expect(onDelete).toHaveBeenCalledWith('La Cripta')
    await userEvent.click(screen.getByRole('button', { name: 'common.close' }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
