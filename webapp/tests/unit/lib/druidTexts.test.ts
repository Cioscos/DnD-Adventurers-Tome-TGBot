import { describe, it, expect } from 'vitest'
import it_ from '@/locales/it.json'
import en from '@/locales/en.json'

type Tree = Record<string, unknown>
const at = (tree: unknown, path: string): string =>
  path.split('.').reduce<unknown>((node, key) => (node as Tree)[key], tree) as string

describe('texts of the druid rules', () => {
  it('the cost question of the beast-form materials is answered by the sheet buttons (cast anyway or cancel)', () => {
    for (const tree of [it_, en]) {
      const body = at(tree, 'character.spells.cast_confirm.form_materials_cost_body')
      expect(body).not.toMatch(/\?.*\?/)
      expect(body.trim().endsWith('?')).toBe(true)
      expect(body).toMatch(/(lanciarlo comunque|cast it anyway)/i)
    }
  })

  it('the cantrip pick banner names the list as a parameter, not a feature that grants none in particular', () => {
    expect(at(it_, 'character.spells.pick_cantrip_banner')).toContain('{{list}}')
    expect(at(it_, 'character.spells.pick_cantrip_banner')).not.toMatch(/privilegio/i)
    expect(at(en, 'character.spells.pick_cantrip_banner')).toContain('{{list}}')
    expect(at(en, 'character.spells.pick_cantrip_banner')).not.toMatch(/feature/i)
  })

  it('every new text exists in both languages', () => {
    for (const key of ['character.spells.pick_filter_note', 'character.extras.return_bonus_used', 'character.extras.wild_heal_full']) {
      expect(at(it_, key)).toBeTruthy()
      expect(at(en, key)).toBeTruthy()
    }
  })
})
