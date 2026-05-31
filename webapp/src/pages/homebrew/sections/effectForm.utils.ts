import type { Effect, EffectAction } from '@/lib/homebrew/types'

/** Seed Effect for a freshly-picked action — mirrors the backend defaults. */
export function defaultEffect(action: EffectAction): Effect {
  switch (action) {
    case 'roll_dice':
      return { action, notation: '1d6', store_as: 'result' }
    case 'lookup_table':
      return { action, table: '', row: '', col: '', store_as: 'mapped' }
    case 'match':
      return { action, value: '$result', cases: {} }
    case 'if':
      return { action, cond: { path: '', op: 'eq', value: '' }, then: [] }
    case 'set_property':
      return { action, target: 'subject', key: '', value: '' }
    case 'inc_property':
      return { action, target: 'subject', key: '', delta: 1 }
    case 'unequip':
      return { action, target: 'subject' }
    case 'damage_character':
      return { action, amount: 1 }
    case 'heal_character':
      return { action, amount: 1 }
    case 'change_resource':
      return { action, key: '', delta: -1 }
    case 'restore_resource':
      return { action, key: '', amount: 'max' }
    case 'apply_condition':
      return { action, key: '' }
    case 'remove_condition':
      return { action, key: '' }
    case 'apply_modifier_once':
      return { action, target: 'character.ac', delta: 1, label: '' }
    case 'notify':
      return { action, severity: 'info', message: '' }
    case 'add_history':
      return { action, description: '' }
  }
}
