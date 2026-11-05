import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import SpellLimits from '@/pages/spells/SpellLimits'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  const t = (k: string, o?: Record<string, unknown>) => (k.startsWith('dnd.') ? String(o?.defaultValue) : k.split('.').pop()!)
  return { ...actual, useTranslation: () => ({ t, i18n: { language: 'it' } }) }
})

const row = (over: object) => ({
  class_id: 1, class_name: 'bard', cantrips_count: 1, cantrips_limit: 3, known_count: 2, known_limit: 7,
  prepared_count: 0, prepared_limit: null, ...over,
})

describe('SpellLimits', () => {
  it('shows only the limits that apply to the class', () => {
    render(<SpellLimits limits={[row({})]} />)
    expect(screen.getByText('1/3')).toBeInTheDocument()
    expect(screen.getByText('2/7')).toBeInTheDocument()
    expect(screen.queryByText('limit_prepared')).not.toBeInTheDocument()
  })

  it('marks a number above the limit without touching anything', () => {
    render(<SpellLimits limits={[row({ known_limit: null, cantrips_limit: null, prepared_count: 9, prepared_limit: 4 })]} />)
    expect(screen.getByText('9/4').className).toMatch(/crimson/)
  })

  it('renders nothing without limits', () => {
    const { container } = render(<SpellLimits limits={[row({ known_limit: null, cantrips_limit: null })]} />)
    expect(container).toBeEmptyDOMElement()
  })
})
