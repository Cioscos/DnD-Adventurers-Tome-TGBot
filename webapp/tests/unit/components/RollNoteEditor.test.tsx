import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import RollNoteEditor from '@/components/character/RollNoteEditor'
import type { CharacterFull } from '@/types'

const { update } = vi.hoisted(() => ({ update: vi.fn() }))
vi.mock('@/api/client', () => ({ api: { characters: { update } } }))
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; children?: unknown }) => (p.open ? React.createElement('div', null, p.children) : null) }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})

const baseSettings = {
  quick_actions: ['a', 'b'],
  hero_layout: { order: ['x'] },
  roll_notes: { 'skill.stealth': 'vantaggio al buio', 'save.dexterity': 'old' },
}
const mkChar = (settings = baseSettings) => ({ id: 5, settings }) as unknown as CharacterFull

async function save(text: string | null) {
  await userEvent.click(screen.getByLabelText('character.roll_notes.edit'))
  const input = screen.getByLabelText('character.roll_notes.placeholder')
  if (text !== null) {
    await userEvent.clear(input)
    if (text) await userEvent.type(input, text)
  }
  await userEvent.click(screen.getByText('common.save'))
}

describe('RollNoteEditor', () => {
  it('preserves other settings keys', async () => {
    update.mockResolvedValue({ id: 5 })
    renderWithProviders(<RollNoteEditor char={mkChar()} noteKey="save.wisdom" label="Saggezza" />)
    await save('resistenza magica')
    await waitFor(() => expect(update).toHaveBeenCalled())
    expect(update).toHaveBeenCalledWith(5, {
      settings: {
        quick_actions: ['a', 'b'],
        hero_layout: { order: ['x'] },
        roll_notes: { ...baseSettings.roll_notes, 'save.wisdom': 'resistenza magica' },
      },
    })
  })

  it('empty note removes the key', async () => {
    update.mockClear()
    update.mockResolvedValue({ id: 5 })
    renderWithProviders(<RollNoteEditor char={mkChar()} noteKey="save.dexterity" label="Des" />)
    await save('')
    await waitFor(() => expect(update).toHaveBeenCalled())
    const sent = update.mock.calls[0][1].settings
    expect(sent.roll_notes).toEqual({ 'skill.stealth': 'vantaggio al buio' })
    expect(sent.quick_actions).toEqual(['a', 'b'])
  })
})
