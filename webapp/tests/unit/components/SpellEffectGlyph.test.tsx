import { describe, it, expect, vi } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import { renderWithProviders } from '../utils/renderWithProviders'
import SpellEffectAsk from '@/components/rules/SpellEffectAsk'
import type { SpellEffectInfo } from '@/types'

vi.mock('@/api/client', () => ({ api: { characters: { sessionAllies: vi.fn(async () => []), allyWeapons: vi.fn(async () => []) } } }))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})

const glyph: SpellEffectInfo = {
  target_kind: 'self', max_targets_by_slot: { '3': 1 },
  choices: [
    { key: 'glyph', label: { it: 'Glifo', en: 'Glyph' }, options: ['explosive', 'spell'] },
    { key: 'damage_type', label: { it: 'Tipo di danno', en: 'Damage type' }, options: ['acid', 'fire'], when: ['glyph', 'explosive'] },
  ],
}

describe('Glyph of Warding choices', () => {
  const open = (onConfirm = vi.fn()) => {
    renderWithProviders(<SpellEffectAsk charId={1} title="Glifo" effect={glyph} slotLevel={3} onConfirm={onConfirm} onClose={vi.fn()} />)
    return onConfirm
  }

  it('does not ask for the damage type of a spell glyph', () => {
    const onConfirm = open()
    expect(screen.queryByText('Tipo di danno')).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('character.spells.effect_glyph_spell'))
    expect(screen.queryByText('Tipo di danno')).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('character.spells.effect_confirm'))
    expect(onConfirm).toHaveBeenCalledWith({ choices: { glyph: 'spell' } })
  })

  it('asks for the type of the explosive runes and drops it if the player switches to the spell glyph', () => {
    const onConfirm = open()
    fireEvent.click(screen.getByText('character.spells.effect_glyph_explosive'))
    expect(screen.getByText('Tipo di danno')).toBeInTheDocument()
    expect(screen.getByText('character.spells.effect_confirm').closest('button')).toBeDisabled()
    fireEvent.click(screen.getByText('character.inventory.damage_types.dmg_fire'))
    fireEvent.click(screen.getByText('character.spells.effect_glyph_spell'))
    fireEvent.click(screen.getByText('character.spells.effect_confirm'))
    expect(onConfirm).toHaveBeenCalledWith({ choices: { glyph: 'spell' } })
  })
})
