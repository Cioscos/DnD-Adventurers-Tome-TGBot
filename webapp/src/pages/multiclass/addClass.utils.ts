// Form-model helpers for AddClassForm, kept out of the component module so the
// component file only exports a component (react-refresh/only-export-components).

export const PREDEFINED_CLASSES: Record<string, { hit_die: number; spellcasting_ability: string | null }> = {
  barbarian: { hit_die: 12, spellcasting_ability: null },
  bard:      { hit_die: 8,  spellcasting_ability: 'charisma' },
  cleric:    { hit_die: 8,  spellcasting_ability: 'wisdom' },
  druid:     { hit_die: 8,  spellcasting_ability: 'wisdom' },
  fighter:   { hit_die: 10, spellcasting_ability: null },
  rogue:     { hit_die: 8,  spellcasting_ability: null },
  wizard:    { hit_die: 6,  spellcasting_ability: 'intelligence' },
  monk:      { hit_die: 8,  spellcasting_ability: null },
  paladin:   { hit_die: 10, spellcasting_ability: 'charisma' },
  ranger:    { hit_die: 10, spellcasting_ability: 'wisdom' },
  sorcerer:  { hit_die: 6,  spellcasting_ability: 'charisma' },
  warlock:   { hit_die: 8,  spellcasting_ability: 'charisma' },
}

export const CUSTOM_KEY = '__custom__'

export type ClassForm = {
  class_key: string
  custom_name: string
  level: string
  subclass: string
  hit_die: string
  spellcasting_ability: string
}

export const emptyClass: ClassForm = {
  class_key: '',
  custom_name: '',
  level: '1',
  subclass: '',
  hit_die: '8',
  spellcasting_ability: '',
}

export function resolveClassName(form: ClassForm): string {
  return form.class_key === CUSTOM_KEY ? form.custom_name.trim() : form.class_key
}
