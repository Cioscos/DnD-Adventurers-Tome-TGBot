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

  it('shows the Eldritch Knight limit for spells outside the two schools, and the schools', () => {
    render(<SpellLimits limits={[row({ class_name: 'fighter', known_limit: 4, known_count: 4, school_names: ['abjuration', 'evocation'],
                                         school_free_limit: 1, school_outside_count: 2 })]} />)
    expect(screen.getByText('limit_off_school')).toBeInTheDocument()
    expect(screen.getByText('2/1').className).toMatch(/crimson/)
    expect(screen.getByTestId('school-hint')).toBeInTheDocument()
  })

  it('shows no school limit for a class without one', () => {
    render(<SpellLimits limits={[row({})]} />)
    expect(screen.queryByText('limit_off_school')).not.toBeInTheDocument()
    expect(screen.queryByTestId('school-hint')).not.toBeInTheDocument()
  })

  it('renders nothing without limits', () => {
    const { container } = render(<SpellLimits limits={[row({ known_limit: null, cantrips_limit: null })]} />)
    expect(container).toBeEmptyDOMElement()
  })
})
