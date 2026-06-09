import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import PassiveAbilityDetailModal from '@/pages/abilities/PassiveAbilityDetailModal'
import type { Ability } from '@/types'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; title?: unknown; children?: unknown }) => (p.open ? React.createElement('div', null, React.createElement('h2', null, p.title), p.children) : null) }
})
vi.mock('@/components/ui/Button', async () => {
  const React = await import('react')
  return { default: (p: { onClick?: () => void; children?: unknown }) => React.createElement('button', { onClick: p.onClick }, p.children) }
})

const ability = (over: Partial<Ability> = {}): Ability => ({ id: 1, name: 'Rabbia', description: 'Vantaggio su Forza', ...over } as Ability)

describe('PassiveAbilityDetailModal', () => {
  it('shows the ability name and description', () => {
    render(<PassiveAbilityDetailModal ability={ability()} onClose={() => {}} />)
    expect(screen.getByRole('heading', { name: 'Rabbia' })).toBeInTheDocument()
    expect(screen.getByText('Vantaggio su Forza')).toBeInTheDocument()
  })

  it('falls back to a no-description message when empty', () => {
    render(<PassiveAbilityDetailModal ability={ability({ description: '' })} onClose={() => {}} />)
    expect(screen.getByText('character.abilities.detail.no_description')).toBeInTheDocument()
  })

  it('closes via the close button', async () => {
    const onClose = vi.fn()
    render(<PassiveAbilityDetailModal ability={ability()} onClose={onClose} />)
    await userEvent.click(screen.getByRole('button', { name: 'common.close' }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
