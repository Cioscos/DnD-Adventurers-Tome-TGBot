import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import StubPage from '@/components/StubPage'

vi.mock('react-router-dom', () => ({ useParams: () => ({ id: '7' }) }))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/components/Layout', async () => {
  const React = await import('react')
  return {
    default: (p: { title?: unknown; children?: unknown }) =>
      React.createElement('div', null, React.createElement('h1', null, p.title), p.children),
  }
})
vi.mock('@/components/Card', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})

describe('StubPage', () => {
  it('renders the emoji + title in the layout header and a default in-progress note', () => {
    render(<StubPage titleKey="character.notes.title" emoji="📜" />)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('📜 character.notes.title')
    expect(screen.getByText(/in costruzione/)).toBeInTheDocument()
  })

  it('renders a custom description when provided', () => {
    render(<StubPage titleKey="t" emoji="🛠️" description="Presto disponibile" />)
    expect(screen.getByText('Presto disponibile')).toBeInTheDocument()
  })
})
