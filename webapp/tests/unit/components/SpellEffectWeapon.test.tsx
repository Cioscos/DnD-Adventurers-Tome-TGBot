import { describe, it, expect, vi } from 'vitest'
import { screen, fireEvent, waitFor } from '@testing-library/react'
import { renderWithProviders } from '../utils/renderWithProviders'
import SpellEffectAsk from '@/components/rules/SpellEffectAsk'
import { needsEffectAsk } from '@/lib/spellChoice'
import type { SpellEffectInfo } from '@/types'

vi.mock('@/api/client', () => ({
  api: { characters: {
    sessionAllies: vi.fn(async () => [{ id: 2, name: 'Eroe' }]),
    allyWeapons: vi.fn(async (_id: number, ally: number) => (ally === 2 ? [{ id: 7, name: 'Spada lunga' }] : [])),
  } },
}))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})

const magicWeapon: SpellEffectInfo = { target_kind: 'ally', weapon_choice: true, max_targets_by_slot: { '2': 1 }, choices: [] }

describe('needsEffectAsk', () => {
  it('asks for targets, choices or a weapon, but not for self or an aura', () => {
    expect(needsEffectAsk({ target_kind: 'self', choices: [] })).toBe(false)
    expect(needsEffectAsk({ target_kind: 'aura', choices: [] })).toBe(false)
    expect(needsEffectAsk({ target_kind: 'ally', choices: [] })).toBe(true)
    expect(needsEffectAsk({ target_kind: 'aura', choices: [{}] })).toBe(true)
    expect(needsEffectAsk({ target_kind: 'self', choices: [], weapon_choice: true })).toBe(true)
  })
})

describe('weapon choice of Magic Weapon', () => {
  it('after the target it lists the weapons of that target and confirms with the item id', async () => {
    const onConfirm = vi.fn()
    renderWithProviders(<SpellEffectAsk charId={1} title="Arma Magica" effect={magicWeapon} slotLevel={2} onConfirm={onConfirm} onClose={vi.fn()} />)
    fireEvent.click(await screen.findByText('Eroe'))
    await waitFor(() => expect(screen.getByText('Spada lunga')).toBeInTheDocument())
    fireEvent.click(screen.getByText('Spada lunga'))
    expect(onConfirm).toHaveBeenCalledWith({ targets: [2], choices: { item_id: '7' } })
  })
})
