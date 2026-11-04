import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import PendingChoicesBadge from '@/components/character/PendingChoicesBadge'
import type { CharacterFull } from '@/types'

const { resolve } = vi.hoisted(() => ({ resolve: vi.fn() }))
vi.mock('@/api/client', () => ({ api: { choices: { resolve } } }))
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; children?: unknown }) => (p.open ? React.createElement('div', null, p.children) : null) }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})

const opt = (key: string) => ({ key, name: { it: `Nome ${key}`, en: key }, summary: { it: `Testo ${key}`, en: '' } })
const char = {
  id: 7,
  ability_scores: [],
  pending_choices: [{
    id: 'opt1', kind: 'class_option', class_key: 'Stregone', level: 3, created_at: '', group: 'metamagic', count: 2,
    options: [opt('a'), opt('b'), opt('c')],
  }],
} as unknown as CharacterFull

describe('ClassOptionSheet', () => {
  it('requires exactly `count` options and posts them', async () => {
    resolve.mockResolvedValue({ id: 7 })
    renderWithProviders(<PendingChoicesBadge char={char} />)
    await userEvent.click(screen.getByText('character.level_choice.badge'))
    const confirm = screen.getByText('character.level_choice.confirm')
    expect(confirm).toBeDisabled()
    await userEvent.click(screen.getByText('Nome a'))
    expect(confirm).toBeDisabled()
    await userEvent.click(screen.getByText('Nome c'))
    expect(screen.getByText('Nome b').closest('button')).toBeDisabled() // limite raggiunto
    await userEvent.click(confirm)
    await waitFor(() => expect(resolve).toHaveBeenCalledWith(7, 'opt1', { kind: 'class_option', options: ['a', 'c'] }))
  })
})
