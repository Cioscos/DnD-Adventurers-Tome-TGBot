import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import RollNotes from '@/components/rules/RollNotes'
import type { OptionResult, TargetEffect } from '@/api/client'

const { preview, applyEffect, success } = vi.hoisted(() => ({ preview: vi.fn(), applyEffect: vi.fn(), success: vi.fn() }))
vi.mock('@/api/client', () => ({
  api: { characters: { targetEffectPreview: preview, targetEffectApply: applyEffect } },
}))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ success, error: vi.fn(), warning: vi.fn() }) }))
vi.mock('@/hooks/useRollNoteLabels', () => ({ useRollNoteLabels: () => (n: string[]) => n }))
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; children?: unknown }) => (p.open ? React.createElement('div', null, p.children) : null) }
})
vi.mock('react-i18next', async (orig) => ({
  ...(await orig() as object),
  useTranslation: () => ({ t: (k: string, o?: { dc?: number }) => (o?.dc ? `${k}:${o.dc}` : k), i18n: { language: 'it' } }),
}))

const topple: TargetEffect = {
  condition: 'prone', save_ability: 'constitution', save_dc: 13, rounds: null, ends_at: null, on_failure_only: true, damage_dice: null,
}
const opts: OptionResult = { keys: ['mastery_topple'], extra_rolls: [], extra_total: 0, bonus: 0, multiplier: 1, spent: [], targets: ['mastery_topple'] }

beforeEach(() => vi.clearAllMocks())

describe('TargetEffectSheet', () => {
  it('shows the save and applies the effect to the chosen combatant', async () => {
    preview.mockResolvedValue({ result: topple, combatants: [{ id: 5, name: 'Goblin 1', kind: 'monster' }] })
    applyEffect.mockResolvedValue({ applied: true, result: topple, target_name: 'Goblin 1', pending_save_id: 9 })
    renderWithProviders(<RollNotes charId={3} optionResult={opts} />)
    await userEvent.click(screen.getByText('character.target_effect.open'))
    expect(await screen.findByText('character.target_effect.save:13')).toBeInTheDocument()
    await userEvent.click(screen.getByText('Goblin 1'))
    await waitFor(() => expect(applyEffect).toHaveBeenCalledWith(3, 'mastery_topple', 5))
    await waitFor(() => expect(success).toHaveBeenCalled())
  })

  it('only shows the outcome without an encounter', async () => {
    preview.mockResolvedValue({ result: topple, combatants: [] })
    renderWithProviders(<RollNotes charId={3} optionResult={opts} />)
    await userEvent.click(screen.getByText('character.target_effect.open'))
    expect(await screen.findByText('character.target_effect.no_encounter')).toBeInTheDocument()
    expect(applyEffect).not.toHaveBeenCalled()
  })

  it('offers nothing when the roll has no target effects', () => {
    renderWithProviders(<RollNotes charId={3} optionResult={{ ...opts, targets: [] }} />)
    expect(screen.queryByText('character.target_effect.open')).toBeNull()
  })
})
