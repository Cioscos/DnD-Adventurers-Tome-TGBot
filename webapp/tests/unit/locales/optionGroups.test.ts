import { describe, it, expect } from 'vitest'
import it_ from '@/locales/it.json'
import en from '@/locales/en.json'

// I gruppi di scelta del Barbaro 2024 (Task 31, I6): /class non deve mostrare la chiave grezza.
describe('level choice group labels', () => {
  it.each(['aspect_of_the_wilds', 'primal_knowledge'])('%s has an it and en label', (group) => {
    const groups = (l: typeof it_) => (l.character.level_choice as { groups: Record<string, string> }).groups
    expect(groups(it_)[group]).toBeTruthy()
    expect(groups(en as typeof it_)[group]).toBeTruthy()
  })
})
