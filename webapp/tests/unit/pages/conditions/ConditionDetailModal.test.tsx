import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ConditionDetailModal from '@/pages/conditions/ConditionDetailModal'
import itLocale from '@/locales/it.json'
import enLocale from '@/locales/en.json'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return {
    ...actual,
    useTranslation: () => ({
      t: (k: string, opts?: { returnObjects?: boolean; context?: string }) =>
        opts?.returnObjects ? ['Svantaggio alle prove', 'Velocità dimezzata'] : opts?.context ? `${k}:${opts.context}` : k,
      i18n: { language: 'it' },
    }),
  }
})
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; title?: unknown; children?: unknown }) => (p.open ? React.createElement('div', null, React.createElement('h2', null, p.title), p.children) : null) }
})
vi.mock('@/components/ui/Button', async () => {
  const React = await import('react')
  return { default: (p: { onClick?: () => void; children?: unknown }) => React.createElement('button', { onClick: p.onClick }, p.children) }
})

describe('ConditionDetailModal', () => {
  it('shows the condition title + description and closes', async () => {
    const onClose = vi.fn()
    render(<ConditionDetailModal condKey="poisoned" onClose={onClose} />)
    expect(screen.getByRole('heading', { name: 'character.conditions.poisoned' })).toBeInTheDocument()
    expect(screen.getByText('character.conditions.desc.poisoned')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'common.close' }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('renders the exhaustion level ladder for the exhaustion condition', () => {
    render(<ConditionDetailModal condKey="exhaustion" exhaustionLevel={2} onClose={() => {}} />)
    expect(screen.getByText('Svantaggio alle prove')).toBeInTheDocument()
    expect(screen.getByText('Velocità dimezzata')).toBeInTheDocument()
  })

  it('asks for the texts of the character edition', () => {
    render(<ConditionDetailModal condKey="stunned" edition="2024" onClose={() => {}} />)
    expect(screen.getByText('character.conditions.desc.stunned:2024')).toBeInTheDocument()
  })

  it('2024 has its own exhaustion ladder and fine print in both locales', () => {
    for (const loc of [itLocale, enLocale]) {
      const { conditions } = loc.character
      expect(conditions.desc.exhaustion_levels_2024).toHaveLength(6)
      expect(conditions.exhaustion_condition_2024).toBeTruthy()
      expect(conditions.desc.stunned_2024).toBeTruthy()
    }
    expect(itLocale.character.conditions.exhaustion_condition).toBe('Indebolimento')
    expect(itLocale.character.conditions.exhaustion_condition_2024).toBe('Esaurimento')
  })
})
