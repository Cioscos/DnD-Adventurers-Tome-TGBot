import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import PendingChoicesBadge from '@/components/character/PendingChoicesBadge'
import { ReplaceOptionSheet } from '@/components/rules/ClassOptionSheet'
import type { CharacterFull } from '@/types'

const { resolve } = vi.hoisted(() => ({ resolve: vi.fn() }))
const { classOptions, replaceOption } = vi.hoisted(() => ({ classOptions: vi.fn(), replaceOption: vi.fn() }))
const { navigate } = vi.hoisted(() => ({ navigate: vi.fn() }))
vi.mock('react-router-dom', async (orig) => ({ ...((await orig()) as Record<string, unknown>), useNavigate: () => navigate }))
vi.mock('@/api/client', () => ({ api: { choices: { resolve, classOptions, replaceOption } } }))
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

  it('sends a spell pick (Magical Secrets) to the spells page instead of a list of options', async () => {
    const picking = {
      id: 7, ability_scores: [],
      pending_choices: [{
        id: 'sec1', kind: 'class_option', class_key: 'Bardo', level: 10, created_at: '', group: 'magical_secrets', count: 2,
        options: [], spell_pick: { free: false, max_level: 5 },
      }],
    } as unknown as CharacterFull
    navigate.mockClear()
    renderWithProviders(<PendingChoicesBadge char={picking} />)
    await userEvent.click(screen.getByText('character.level_choice.badge'))
    expect(navigate).toHaveBeenCalledWith('/char/7/spells?pick=sec1')
    expect(screen.queryByText('character.level_choice.confirm')).not.toBeInTheDocument()
  })

  it('replaces a chosen option with an available one', async () => {
    classOptions.mockResolvedValue({ replaceable: true, chosen: [opt('a')], available: [opt('z')] })
    replaceOption.mockResolvedValue({ id: 7 })
    renderWithProviders(<ReplaceOptionSheet char={char} classId={3} group="metamagic" open onClose={() => {}} />)
    const confirm = screen.getByText('character.level_choice.confirm')
    await userEvent.click(await screen.findByText('Nome a'))
    expect(confirm).toBeDisabled()
    await userEvent.click(screen.getByText('Nome z'))
    await userEvent.click(confirm)
    await waitFor(() => expect(replaceOption).toHaveBeenCalledWith(7, 3, { group: 'metamagic', old_key: 'a', new_key: 'z' }))
  })
})
