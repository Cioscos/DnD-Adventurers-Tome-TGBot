import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import NoteEditor from '@/pages/notes/NoteEditor'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/components/ui/Input', async () => {
  const React = await import('react')
  return { default: (p: { label?: string; placeholder?: string; value: string; onChange: (v: string) => void }) => React.createElement('input', { 'aria-label': p.label || p.placeholder, placeholder: p.placeholder, value: p.value, onChange: (e: { target: { value: string } }) => p.onChange(e.target.value) }) }
})
vi.mock('@/components/ui/Button', async () => {
  const React = await import('react')
  return { default: (p: { onClick?: () => void; disabled?: boolean; loading?: boolean; children?: unknown }) => React.createElement('button', { onClick: p.onClick, disabled: p.disabled || p.loading }, p.children) }
})
vi.mock('@/components/ui/ChipInput', async () => {
  const React = await import('react')
  return { default: (p: { values: string[] }) => React.createElement('div', { 'data-testid': 'chips' }, (p.values ?? []).join(',')) }
})

describe('NoteEditor', () => {
  it('add mode: title is required before saving, then emits trimmed values', async () => {
    const onSave = vi.fn()
    render(<NoteEditor onSave={onSave} onCancel={() => {}} isPending={false} />)
    const save = screen.getByRole('button', { name: 'common.save' })
    expect(save).toBeDisabled()
    fireEvent.change(screen.getByLabelText('character.notes.title_label'), { target: { value: 'Cripta' } })
    fireEvent.change(screen.getByPlaceholderText('character.notes.body_placeholder'), { target: { value: 'corpo' } })
    expect(save).toBeEnabled()
    await userEvent.click(save)
    expect(onSave).toHaveBeenCalledWith('Cripta', 'corpo', [])
  })

  it('edit mode hides the title input', () => {
    render(<NoteEditor initialNote={{ title: 'T', body: 'B', tags: ['NPC'] }} onSave={() => {}} onCancel={() => {}} isPending={false} />)
    expect(screen.queryByLabelText('character.notes.title_label')).not.toBeInTheDocument()
  })

  it('cancels', async () => {
    const onCancel = vi.fn()
    render(<NoteEditor onSave={() => {}} onCancel={onCancel} isPending={false} />)
    await userEvent.click(screen.getByRole('button', { name: 'common.cancel' }))
    expect(onCancel).toHaveBeenCalledTimes(1)
  })
})
