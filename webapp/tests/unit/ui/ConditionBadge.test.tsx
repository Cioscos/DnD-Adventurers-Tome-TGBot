import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import ConditionBadge from '@/components/ui/ConditionBadge'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/lib/conditions', async () => {
  const React = await import('react')
  return {
    CONDITION_ICONS: new Proxy({}, { get: () => () => React.createElement('span', { 'data-testid': 'cond-icon' }) }),
    formatCondition: (key: string, value: unknown) => (value && value !== true ? `${key} (${value})` : key),
  }
})
vi.mock('@/components/ui/Tooltip', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement(React.Fragment, null, p.children) }
})

describe('ConditionBadge', () => {
  it('labels the badge with the formatted condition', () => {
    render(<ConditionBadge conditionKey="poisoned" value={true} />)
    expect(screen.getByRole('button', { name: 'poisoned' })).toBeInTheDocument()
  })

  it('includes the value in the label when the condition is graded', () => {
    render(<ConditionBadge conditionKey="exhaustion" value={3} />)
    expect(screen.getByRole('button', { name: 'exhaustion (3)' })).toBeInTheDocument()
  })

  it('renders the condition icon', () => {
    render(<ConditionBadge conditionKey="prone" value={true} />)
    expect(screen.getByTestId('cond-icon')).toBeInTheDocument()
  })
})
