import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import Identity from '@/pages/Identity'

const { getChar, updateChar } = vi.hoisted(() => ({ getChar: vi.fn(), updateChar: vi.fn() }))

vi.mock('@/api/client', () => ({
  api: { characters: { get: getChar, update: updateChar }, share: { card: vi.fn() } },
}))
vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useParams: () => ({ id: '3' }) }
})
vi.mock('@/components/Layout', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/hooks/useShareMessage', () => ({ useShareMessage: () => vi.fn() }))

const char = {
  id: 3, name: 'Eroe', speed: 30, languages: [], general_proficiencies: [],
  personality: {}, damage_modifiers: {},
  settings: { quick_actions: ['a'], senses: [{ type: 'darkvision', range_ft: 60 }] },
}

describe('Identity senses editor', () => {
  it('saves senses merged into the existing settings', async () => {
    getChar.mockResolvedValue(char)
    updateChar.mockResolvedValue(char)
    renderWithProviders(<Identity />)
    await userEvent.click(await screen.findByRole('button', { name: /Vista pura|Truesight/i }))
    await userEvent.click(await screen.findByRole('button', { name: /Salva ora|Save now/i }))
    await waitFor(() => expect(updateChar).toHaveBeenCalled())
    const settings = updateChar.mock.calls[0][1].settings
    expect(settings.quick_actions).toEqual(['a'])
    expect(settings.senses).toEqual([
      { type: 'darkvision', range_ft: 60 },
      { type: 'truesight', range_ft: 60 },
    ])
  })
})
