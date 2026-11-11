import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import PublicStates from '@/components/session/PublicStates'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})

describe('PublicStates', () => {
  it('shows two states with the same key without a duplicate-key warning (62)', () => {
    const warn = vi.spyOn(console, 'error').mockImplementation(() => {})
    const row = (name: string) => ({ key: 'spell:aid', name, rounds_left: null, others: [] })
    render(<PublicStates states={[row('Aid da Alfa'), row('Aid da Beta')]} />)
    expect(screen.getByText('Aid da Alfa')).toBeInTheDocument()
    expect(screen.getByText('Aid da Beta')).toBeInTheDocument()
    expect(warn.mock.calls.some((c) => String(c[0]).includes('same key'))).toBe(false)
    warn.mockRestore()
  })
})
