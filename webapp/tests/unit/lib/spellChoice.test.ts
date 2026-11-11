import { describe, expect, it } from 'vitest'
import itJson from '@/locales/it.json'
import { optionLabel } from '@/lib/spellChoice'

// Le chiavi come le risolve i18next: percorso a punti dentro il JSON italiano
const t = (key: string, o?: Record<string, unknown>) => (key.split('.').reduce<unknown>((n, k) => (n as Record<string, unknown> | undefined)?.[k], itJson) as string | undefined) ?? (o?.defaultValue as string)

describe('optionLabel', () => {
  it('names the damage type of the weapon-damage choice of Shillelagh 2024', () => {
    expect(optionLabel(t, 'weapon_damage', 'force')).toBe('Forza')
    expect(optionLabel(t, 'weapon_damage', 'normal')).toBe("Quello dell'arma")
  })

  it('names the damage type of the upcast choice and keeps the older keys', () => {
    expect(optionLabel(t, 'upcast_type', 'radiant')).toBe(itJson.character.inventory.damage_types.dmg_radiant)
    expect(optionLabel(t, 'damage_type', 'fire')).toBe(itJson.character.inventory.damage_types.dmg_fire)
    expect(optionLabel(t, 'ability', 'wisdom')).toBe(itJson.common.abilities.wisdom)
  })
})
