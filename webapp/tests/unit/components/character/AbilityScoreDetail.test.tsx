import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import AbilityScoreDetail from '@/components/character/AbilityScoreDetail'
import type { AbilityScore } from '@/types'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})

const score = (over: Partial<AbilityScore> = {}): AbilityScore =>
  ({ name: 'strength', value: 17, base_value: 15, modifier: 3, modifiers_applied: [], ...over } as AbilityScore)

describe('AbilityScoreDetail', () => {
  it('shows the base value and the effective value', () => {
    render(<AbilityScoreDetail score={score()} />)
    expect(screen.getByText('15')).toBeInTheDocument() // base
    expect(screen.getByText('17')).toBeInTheDocument() // effective
  })

  it('renders a relative modifier with a signed value', () => {
    render(<AbilityScoreDetail score={score({ modifiers_applied: [{ source: 'Gauntlets', kind: 'relative', value: 2 }] })} />)
    expect(screen.getByText('Gauntlets')).toBeInTheDocument()
    expect(screen.getByText('+2')).toBeInTheDocument()
  })

  it('renders an absolute modifier with an = prefix', () => {
    render(<AbilityScoreDetail score={score({ modifiers_applied: [{ source: 'Belt', kind: 'absolute', value: 19 }] })} />)
    expect(screen.getByText('=19')).toBeInTheDocument()
  })

  it('falls back to value when base_value is missing', () => {
    render(<AbilityScoreDetail score={score({ base_value: undefined, value: 12 })} />)
    expect(screen.getAllByText('12').length).toBeGreaterThan(0)
  })
})
