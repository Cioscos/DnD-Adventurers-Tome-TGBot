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
  return { ...actual, useTranslation: () => ({ t: (k: string, o?: { name?: string }) => (o?.name ? `${k}:${o.name}` : k), i18n: { language: 'it' } }) }
})

const mkChar = (pending = true) => ({
  id: 7,
  ability_scores: [
    { name: 'strength', value: 19 }, { name: 'dexterity', value: 14 },
  ],
  pending_choices: pending ? [{ id: 'abc', kind: 'asi', class_key: 'Guerriero', level: 4, created_at: '' }] : [],
}) as unknown as CharacterFull

describe('PendingChoicesBadge / ResolveChoiceSheet', () => {
  it('renders nothing without pending choices', () => {
    const { container } = renderWithProviders(<PendingChoicesBadge char={mkChar(false)} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('caps scores at 20 and posts +1/+1', async () => {
    resolve.mockResolvedValue({ id: 7 })
    renderWithProviders(<PendingChoicesBadge char={mkChar()} />)
    await userEvent.click(screen.getByText('character.level_choice.badge'))
    const incStr = 'character.level_choice.increase:common.abilities.strength'
    await userEvent.click(screen.getByLabelText(incStr))
    // STR 19 -> 20: a second point on STR is blocked by the cap
    expect(screen.getByLabelText(incStr)).toBeDisabled()
    await userEvent.click(screen.getByLabelText('character.level_choice.increase:common.abilities.dexterity'))
    await userEvent.click(screen.getByText('character.level_choice.confirm'))
    await waitFor(() => expect(resolve).toHaveBeenCalledWith(7, 'abc', {
      kind: 'asi', increases: { strength: 1, dexterity: 1 },
    }))
  })

  it('disables feats already taken', async () => {
    const char = { ...mkChar(), abilities: [{ feature_key: 'feat.alert' }] } as unknown as CharacterFull
    renderWithProviders(<PendingChoicesBadge char={char} />)
    await userEvent.click(screen.getByText('character.level_choice.badge'))
    await userEvent.click(screen.getByText('character.level_choice.feat'))
    expect(screen.getByText('character.level_choice.feats.alert.name').closest('button')).toBeDisabled()
    expect(screen.getByText('character.level_choice.feats.tough.name').closest('button')).not.toBeDisabled()
  })

  it('posts a feat with its ability choice', async () => {
    resolve.mockResolvedValue({ id: 7 })
    renderWithProviders(<PendingChoicesBadge char={mkChar()} />)
    await userEvent.click(screen.getByText('character.level_choice.badge'))
    await userEvent.click(screen.getByText('character.level_choice.feat'))
    await userEvent.click(screen.getByText('character.level_choice.feats.observant.name'))
    expect(screen.getByText('character.level_choice.confirm')).toBeDisabled()
    await userEvent.selectOptions(screen.getByLabelText('character.level_choice.pick_ability'), 'wisdom')
    await userEvent.click(screen.getByText('character.level_choice.confirm'))
    await waitFor(() => expect(resolve).toHaveBeenLastCalledWith(7, 'abc', {
      kind: 'feat', feat_key: 'observant', ability: 'wisdom',
    }))
  })
})
