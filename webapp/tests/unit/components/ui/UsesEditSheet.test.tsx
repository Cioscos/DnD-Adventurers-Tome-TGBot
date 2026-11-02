import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import UsesEditSheet from '@/components/ui/UsesEditSheet'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; children?: unknown }) => (p.open ? React.createElement('div', null, p.children) : null) }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))

// Campo precompilato: bisognava cancellare il valore attuale prima di scrivere.
describe('UsesEditSheet', () => {
  it('parte vuoto col valore attuale come suggerimento; Salva attivo solo dopo aver scritto', async () => {
    const onSave = vi.fn()
    render(<UsesEditSheet open title="Usi" value={3} max={5} onSave={onSave} onClose={() => {}} isPending={false} />)
    const input = screen.getByRole('textbox')
    expect(input).toHaveValue('')
    expect(input).toHaveAttribute('placeholder', '3')
    const save = screen.getByRole('button', { name: 'common.save' })
    expect(save).toBeDisabled()
    await userEvent.type(input, '1')
    await userEvent.click(save)
    expect(onSave).toHaveBeenCalledWith(1)
  })
})
