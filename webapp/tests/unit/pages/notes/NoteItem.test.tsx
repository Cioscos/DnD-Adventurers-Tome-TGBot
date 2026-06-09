import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import NoteItem from '@/pages/notes/NoteItem'
import type { Note } from '@/types'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/store/characterStore', () => ({ useCharacterStore: (sel: (s: { locale: string }) => unknown) => sel({ locale: 'it' }) }))
vi.mock('@/lib/relativeTime', () => ({ formatRelative: () => '5 min fa', formatAbsolute: () => '1 gennaio' }))
vi.mock('@/components/Card', async () => {
  const React = await import('react')
  return { default: (p: { onClick?: () => void; children?: unknown }) => React.createElement('div', { onClick: p.onClick }, p.children) }
})

const note = (over: Partial<Note> = {}): Note =>
  ({ title: 'La Cripta', body: 'Testo **importante**', tags: ['Lore'], is_voice: false, updated_at: '2026-06-01T10:00:00Z', ...over } as Note)

describe('NoteItem', () => {
  it('renders a text note with title, tags and inline-markdown body', () => {
    render(<NoteItem note={note()} onDelete={() => {}} />)
    expect(screen.getByText('La Cripta')).toBeInTheDocument()
    expect(screen.getByText('Lore')).toBeInTheDocument()
    expect(screen.getByText('importante').tagName).toBe('STRONG')
  })

  it('wires edit / delete / view callbacks', async () => {
    const onEdit = vi.fn(); const onDelete = vi.fn(); const onView = vi.fn()
    render(<NoteItem note={note()} onEdit={onEdit} onDelete={onDelete} onView={onView} />)
    await userEvent.click(screen.getByRole('button', { name: 'common.edit' }))
    expect(onEdit).toHaveBeenCalledWith('La Cripta', 'Testo **importante**', ['Lore'])
    await userEvent.click(screen.getByRole('button', { name: 'common.delete' }))
    expect(onDelete).toHaveBeenCalledWith('La Cripta')
    await userEvent.click(screen.getByText('La Cripta'))
    expect(onView).toHaveBeenCalledTimes(1)
  })

  it('renders a voice note with an audio player', () => {
    const voice = note({ is_voice: true, body: '[VOICE:data/voice_notes/7/abc.webm]', tags: [] })
    const { container } = render(<NoteItem note={voice} onDelete={() => {}} voiceUrl={(f) => `https://x/${f}`} />)
    const audio = container.querySelector('audio')
    expect(audio).not.toBeNull()
    expect(audio).toHaveAttribute('src', 'https://x/abc.webm')
  })
})
