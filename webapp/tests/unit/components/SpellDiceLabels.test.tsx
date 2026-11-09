import { describe, it, expect, vi } from 'vitest'
import { screen, renderHook } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { renderWithProviders } from '../utils/renderWithProviders'
import SpellEffectAsk from '@/components/rules/SpellEffectAsk'
import { useRollNoteLabels } from '@/hooks/useRollNoteLabels'
import itLocale from '@/locales/it.json'
import enLocale from '@/locales/en.json'
import type { SpellEffectInfo } from '@/types'

vi.mock('@/api/client', () => ({ api: { characters: { sessionAllies: vi.fn(async () => []), get: vi.fn() } } }))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string, o?: { defaultValue?: string }) => `${k}|${o?.defaultValue ?? ''}`, i18n: { language: 'it' } }) }
})

const guidance: SpellEffectInfo = {
  target_kind: 'ally', max_targets_by_slot: {},
  choices: [{ key: 'skill', label: { it: 'Abilità', en: 'Skill' }, options: ['acrobatics', 'sleight_of_hand'] }],
}

describe('spell dice labels', () => {
  it('translates the skill options of the Guidance picker instead of showing the slug', () => {
    renderWithProviders(<SpellEffectAsk charId={1} title="Guida" effect={guidance} slotLevel={0} onConfirm={vi.fn()} onClose={vi.fn()} />)
    expect(screen.getByText('character.skills.sleight_of_hand|sleight_of_hand')).toBeInTheDocument()
    expect(screen.queryByText('sleight_of_hand')).not.toBeInTheDocument()
  })

  it('names the spell in the roll notes of a bonus die and of Pass without Trace', () => {
    const { result } = renderHook(() => useRollNoteLabels(1), {
      wrapper: ({ children }) => <QueryClientProvider client={new QueryClient()}><MemoryRouter>{children}</MemoryRouter></QueryClientProvider>,
    })
    expect(result.current(['spell:bless', 'spell:pass_without_trace'])).toEqual([
      'character.roll_notes.spell.bless|bless', 'character.roll_notes.spell.pass_without_trace|pass_without_trace'])
  })

  it('has the spell names in both languages for every dice spell', () => {
    for (const key of ['bless', 'guidance', 'resistance', 'pass_without_trace', 'blade_ward']) {
      expect((itLocale.character.roll_notes as { spell: Record<string, string> }).spell[key]).toBeTruthy()
      expect((enLocale.character.roll_notes as { spell: Record<string, string> }).spell[key]).toBeTruthy()
    }
  })
})
