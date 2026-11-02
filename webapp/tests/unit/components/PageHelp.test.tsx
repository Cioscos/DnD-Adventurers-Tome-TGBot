import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

const HELP = { summary: 'Sommario', sections: [{ title: 'Sezione', items: ['voce'] }] }
const { tSpy } = vi.hoisted(() => ({ tSpy: vi.fn() }))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (k: string, o?: { returnObjects?: boolean }) => {
      tSpy(k, o)
      if (o?.returnObjects) return k === 'help.spells' ? HELP : k
      return k === 'help.spells.summary' ? HELP.summary : k
    },
    i18n: { language: 'it' },
  }),
}))
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; children?: unknown }) => (p.open ? React.createElement('div', null, p.children) : null) }
})
vi.mock('@/components/ui/Pressable', async () => {
  const React = await import('react')
  return { default: (p: { onClick?: () => void; 'aria-label'?: string; children?: unknown }) => React.createElement('button', { onClick: p.onClick, 'aria-label': p['aria-label'] }, p.children) }
})

import PageHelp from '@/components/PageHelp'

const objectLookups = () => tSpy.mock.calls.filter(([, o]) => o?.returnObjects).length

describe('PageHelp', () => {
  beforeEach(() => tSpy.mockClear())

  // Perf (S22): t(..., {returnObjects}) costava ~3-4 ms a ogni render della pagina
  // anche a guida chiusa. Si legge l'oggetto solo quando la guida è aperta.
  it('non risolve l\'oggetto della guida finché è chiusa', () => {
    const { rerender } = render(<PageHelp helpKey="spells" title="Incantesimi" />)
    rerender(<PageHelp helpKey="spells" title="Incantesimi" />)
    expect(screen.getByRole('button', { name: 'help.open' })).toBeInTheDocument()
    expect(objectLookups()).toBe(0)
  })

  it('mostra il contenuto quando si apre', async () => {
    render(<PageHelp helpKey="spells" title="Incantesimi" />)
    await userEvent.click(screen.getByRole('button', { name: 'help.open' }))
    expect(screen.getByText('Sommario')).toBeInTheDocument()
    expect(screen.getByText('voce')).toBeInTheDocument()
  })

  it('niente pulsante se la guida non esiste', () => {
    render(<PageHelp helpKey="manca" title="X" />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
