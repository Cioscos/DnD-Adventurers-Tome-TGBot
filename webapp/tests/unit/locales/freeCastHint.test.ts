import { describe, it, expect } from 'vitest'
import it_ from '@/locales/it.json'
import en from '@/locales/en.json'

describe('free cast hint (point 36)', () => {
  it('does not promise the action: Bless and the Mantle of Majesty Command use other casting times', () => {
    expect(it_.character.spells.free_cast_hint).not.toMatch(/azione/i)
    expect(en.character.spells.free_cast_hint).not.toMatch(/action/i)
  })
})
