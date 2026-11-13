import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../utils/renderWithProviders'
import FeatPickerSheet from '@/components/character/FeatPickerSheet'
import FeatOptionsSheet from '@/components/character/FeatOptionsSheet'
import OriginFeatStep from '@/pages/creation/OriginFeatStep'
import type { Ability, CharacterFull } from '@/types'

const { take, complete } = vi.hoisted(() => ({ take: vi.fn(), complete: vi.fn() }))
vi.mock('@/api/client', () => ({ api: { feats: { take, complete } } }))
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; children?: unknown }) => (p.open ? React.createElement('div', null, p.children) : null) }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/lib/srd/catalog', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  const entry = (index: string, it: string, level: number, classes: string[], school = 'evocation', ritual = false) => ({
    index, name: { it, en: it }, level, school, casting_time: { it: '1 azione', en: '1 action' },
    range_ft: 60, range_text: { it: '18 m', en: '60 ft' }, area: null, components: ['V'], duration: { it: 'Istantanea', en: 'Instant' },
    concentration: false, ritual, desc: { it: 'x', en: 'x' }, attack_type: null, save_ability: null,
    damage_dice: null, damage_type: null, higher_levels_dice: null, classes,
  })
  return {
    ...actual,
    loadSpellCatalog: vi.fn(async () => [
      entry('light', 'Luce', 0, ['wizard', 'cleric']), entry('mage-hand', 'Mano Magica', 0, ['wizard']),
      entry('sleep', 'Sonno', 1, ['wizard']), entry('bless', 'Benedizione', 1, ['cleric']),
      entry('command', 'Comando', 1, ['cleric'], 'enchantment'), entry('alarm', 'Allarme', 1, ['wizard'], 'abjuration', true),
      entry('find-familiar', 'Trova famiglio', 1, ['wizard'], 'conjuration', true),
    ]),
  }
})

const char = (cha = 13) => ({
  id: 7, rules_edition: '2024', total_level: 1, classes: [], abilities: [],
  ability_scores: ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma']
    .map((name) => ({ name, value: name === 'charisma' ? cha : 10 })),
  proficiency_bonus: 2, skills: {},
}) as unknown as CharacterFull

beforeEach(() => { take.mockReset(); complete.mockReset() })

describe('FeatPickerSheet (Aggiungi talento)', () => {
  it('asks for the ability of a feat with a +1 and posts it', async () => {
    take.mockResolvedValue({ id: 7 })
    renderWithProviders(<FeatPickerSheet char={char()} open onClose={() => {}} />)
    await userEvent.click(screen.getByText('Attore'))
    expect(screen.getByText('character.feats.add_confirm')).toBeDisabled()
    await userEvent.selectOptions(screen.getByLabelText('character.level_choice.pick_ability'), 'charisma')
    await userEvent.click(screen.getByText('character.feats.add_confirm'))
    await waitFor(() => expect(take).toHaveBeenCalledWith(7, { feat_key: '2024_actor', ability: 'charisma' }))
  })

  it('disables a feat whose prerequisites are not met', () => {
    renderWithProviders(<FeatPickerSheet char={char(12)} open onClose={() => {}} />)
    expect(screen.getByText('Attore').closest('button')).toBeDisabled()
  })
})

describe('FeatOptionsSheet (Completa talento)', () => {
  const skilled = { id: 3, name: 'Abile', feature_key: 'feat.2024_skilled', feat_status: 'incomplete' } as unknown as Ability

  it('Skilled needs three distinct picks', async () => {
    complete.mockResolvedValue({ id: 7 })
    renderWithProviders(<FeatOptionsSheet char={char()} ability={skilled} open onClose={() => {}} />)
    const confirm = screen.getByText('character.feats.complete_confirm')
    await userEvent.click(screen.getByText('character.skills.stealth'))
    await userEvent.click(screen.getByText('character.skills.arcana'))
    expect(confirm).toBeDisabled()
    await userEvent.click(screen.getByText('character.skills.history'))
    await userEvent.click(confirm)
    await waitFor(() => expect(complete).toHaveBeenCalledWith(7, 3, {
      options: { picks: ['stealth', 'arcana', 'history'] }, spells: [] }))
  })

  it('Magic Initiate sends two cantrips and one spell of the chosen list', async () => {
    complete.mockResolvedValue({ id: 7 })
    const mi = { ...skilled, name: 'Iniziato alla magia', feature_key: 'feat.2024_magic_initiate' } as Ability
    renderWithProviders(<FeatOptionsSheet char={char()} ability={mi} open onClose={() => {}} />)
    await userEvent.selectOptions(screen.getByLabelText('character.feats.mi_list'), 'wizard')
    await userEvent.selectOptions(screen.getByLabelText('character.feats.mi_ability'), 'intelligence')
    await userEvent.click(await screen.findByText('Luce'))
    await userEvent.click(screen.getByText('Mano Magica'))
    await userEvent.click(screen.getByText('Sonno'))
    expect(screen.queryByText('Benedizione')).toBeNull()  // non è della lista del Mago
    await userEvent.click(screen.getByText('character.feats.complete_confirm'))
    await waitFor(() => expect(complete).toHaveBeenCalled())
    const [, , body] = complete.mock.calls[0]
    expect(body.options).toEqual({ list: 'wizard', ability: 'intelligence' })
    expect(body.spells.map((s: { srd_index: string; level: number }) => [s.srd_index, s.level]))
      .toEqual([['light', 0], ['mage-hand', 0], ['sleep', 1]])
  })
})

describe('FeatOptionsSheet — talenti 2024 con scelte (PR 2)', () => {
  const row = (name: string, key: string) =>
    ({ id: 4, name, feature_key: `feat.2024_${key}`, feat_status: 'incomplete' }) as unknown as Ability
  const confirm = () => screen.getByText('character.feats.complete_confirm')

  it('Keen Mind offers only the five knowledge skills and sends one', async () => {
    complete.mockResolvedValue({ id: 7 })
    renderWithProviders(<FeatOptionsSheet char={char()} ability={row('Mente acuta', 'keen_mind')} open onClose={() => {}} />)
    expect(screen.queryByText('character.skills.athletics')).toBeNull()
    await userEvent.click(screen.getByText('character.skills.nature'))
    await userEvent.click(confirm())
    await waitFor(() => expect(complete).toHaveBeenCalledWith(7, 4, { options: { skill: 'nature' }, spells: [] }))
  })

  it('Keen Mind hides skills that already have Expertise', () => {
    const expert = { ...char(), skills: { arcana: 'expert' } } as unknown as CharacterFull
    renderWithProviders(<FeatOptionsSheet char={expert} ability={row('Mente acuta', 'keen_mind')} open onClose={() => {}} />)
    expect(screen.queryByText('character.skills.arcana')).toBeNull()
    expect(screen.getByText('character.skills.history')).toBeInTheDocument()
  })

  it('Elemental Adept sends the damage type', async () => {
    complete.mockResolvedValue({ id: 7 })
    renderWithProviders(<FeatOptionsSheet char={char()} ability={row('Adepto elementale', 'elemental_adept')} open onClose={() => {}} />)
    expect(screen.queryByText('character.inventory.damage_types.dmg_necrotic')).toBeNull()
    await userEvent.click(screen.getByText('character.inventory.damage_types.dmg_fire'))
    await userEvent.click(confirm())
    await waitFor(() => expect(complete).toHaveBeenCalledWith(7, 4, { options: { damage_type: 'fire' }, spells: [] }))
  })

  it('Fey-Touched offers only 1st-level divination or enchantment spells', async () => {
    complete.mockResolvedValue({ id: 7 })
    renderWithProviders(<FeatOptionsSheet char={char()} ability={row('Toccato dalle fate', 'fey_touched')} open onClose={() => {}} />)
    await userEvent.click(await screen.findByText('Comando'))
    expect(screen.queryByText('Sonno')).toBeNull()
    await userEvent.click(confirm())
    await waitFor(() => expect(complete).toHaveBeenCalled())
    const [, , body] = complete.mock.calls[0]
    expect(body.options).toEqual({})
    expect(body.spells.map((s: { srd_index: string }) => s.srd_index)).toEqual(['command'])
  })

  it('Ritual Caster asks for as many rituals as the proficiency bonus', async () => {
    complete.mockResolvedValue({ id: 7 })
    renderWithProviders(<FeatOptionsSheet char={char()} ability={row('Incantatore rituale', 'ritual_caster')} open onClose={() => {}} />)
    await userEvent.click(await screen.findByText('Allarme'))
    expect(confirm()).toBeDisabled()
    expect(screen.queryByText('Sonno')).toBeNull()
    await userEvent.click(screen.getByText('Trova famiglio'))
    await userEvent.click(confirm())
    await waitFor(() => expect(complete).toHaveBeenCalled())
    expect(complete.mock.calls[0][2].spells.map((s: { srd_index: string }) => s.srd_index)).toEqual(['alarm', 'find-familiar'])
  })

  it('Boon of Energy Resistance needs two types', async () => {
    complete.mockResolvedValue({ id: 7 })
    renderWithProviders(<FeatOptionsSheet char={char()} ability={row('Dono', 'boon_energy_resistance')} open onClose={() => {}} />)
    await userEvent.click(screen.getByText('character.inventory.damage_types.dmg_fire'))
    expect(confirm()).toBeDisabled()
    await userEvent.click(screen.getByText('character.inventory.damage_types.dmg_cold'))
    await userEvent.click(confirm())
    await waitFor(() => expect(complete).toHaveBeenCalledWith(7, 4, { options: { damage_types: ['fire', 'cold'] }, spells: [] }))
  })

  it('Weapon Master sends one weapon', async () => {
    complete.mockResolvedValue({ id: 7 })
    renderWithProviders(<FeatOptionsSheet char={char()} ability={row("Maestro d'armi", 'weapon_master')} open onClose={() => {}} />)
    await userEvent.selectOptions(screen.getByLabelText('character.feats.weapon'), 'mace')
    await userEvent.click(confirm())
    await waitFor(() => expect(complete).toHaveBeenCalledWith(7, 4, { options: { weapon_mastery: ['mace'] }, spells: [] }))
  })
})

describe('OriginFeatStep', () => {
  it('offers only origin feats and can be skipped', async () => {
    const onChange = vi.fn()
    renderWithProviders(<OriginFeatStep value={null} onChange={onChange} />)
    expect(screen.getByText('Robusto')).toBeInTheDocument()
    expect(screen.queryByText('Attore')).toBeNull()
    await userEvent.click(screen.getByText('Robusto'))
    expect(onChange).toHaveBeenLastCalledWith('2024_tough')
    await userEvent.click(screen.getByText('character.feats.origin_skip'))
    expect(onChange).toHaveBeenLastCalledWith(null)
  })
})
