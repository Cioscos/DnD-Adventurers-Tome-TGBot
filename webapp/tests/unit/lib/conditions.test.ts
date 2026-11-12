import { describe, it, expect, vi } from 'vitest'
import type { TFunction } from 'i18next'
import { CONDITION_ICONS, conditionLabel, formatCondition, incapacitatedMessageKey } from '@/lib/conditions'

// The 14 standard 5e conditions + exhaustion that the hero chips and the
// /conditions page render. Kept here as an explicit contract: if the lookup
// loses (or renames) one, this list stops matching.
const STANDARD_CONDITIONS = [
  'blinded', 'charmed', 'deafened', 'frightened', 'grappled', 'incapacitated',
  'invisible', 'paralyzed', 'petrified', 'poisoned', 'prone', 'restrained',
  'stunned', 'unconscious', 'exhaustion',
]

describe('CONDITION_ICONS', () => {
  it('maps every standard condition (14 + exhaustion) to an icon component', () => {
    for (const key of STANDARD_CONDITIONS) {
      expect(CONDITION_ICONS[key]).toBeTypeOf('function')
    }
    expect(Object.keys(CONDITION_ICONS)).toHaveLength(STANDARD_CONDITIONS.length)
  })
})

describe('formatCondition', () => {
  it('renders a non-exhaustion condition by its slug key', () => {
    const t = vi.fn((key: string) => key) as unknown as TFunction
    expect(formatCondition('poisoned', true, t)).toBe('character.conditions.poisoned')
    expect(t).toHaveBeenCalledWith('character.conditions.poisoned')
  })

  it('renders exhaustion with its level when the value is a positive number', () => {
    const t = vi.fn(
      (key: string, opts?: { level: number }) => (opts ? `${key}:${opts.level}` : key),
    ) as unknown as TFunction
    expect(formatCondition('exhaustion', 3, t)).toBe('character.conditions.exhaustion:3')
    expect(t).toHaveBeenCalledWith('character.conditions.exhaustion', { level: 3 })
  })

  it('renders exhaustion without a level when the value is 0 or not a number', () => {
    const t = vi.fn((key: string) => key) as unknown as TFunction
    expect(formatCondition('exhaustion', 0, t)).toBe('character.conditions.exhaustion')
    expect(formatCondition('exhaustion', true, t)).toBe('character.conditions.exhaustion')
    expect(t).toHaveBeenCalledWith('character.conditions.exhaustion')
    // Never forwards the { level } option on the no-level branch.
    expect(t).not.toHaveBeenCalledWith('character.conditions.exhaustion', expect.anything())
  })
})

describe('conditionLabel', () => {
  const t = ((key: string, opts?: { defaultValue?: string }) => (key.endsWith('.thoughts_read') ? 'Pensieri letti' : opts?.defaultValue ?? key)) as unknown as TFunction

  it('names a catalog custom condition by its translated label, never by the key', () => {
    expect(conditionLabel('custom:thoughts_read', t)).toBe('Pensieri letti')
    expect(conditionLabel('custom:Sanguinamento', t)).toBe('Sanguinamento')  // scritta dal giocatore: il suo nome, senza prefisso
  })

  it('names a standard condition through the conditions dictionary', () => {
    expect(conditionLabel('charmed', t)).toBe('charmed')
  })
})

describe('incapacitatedMessageKey', () => {
  it('Haste lethargy (no_actions) says "cannot move or act", 2024 / conditions say incapacitated', () => {
    expect(incapacitatedMessageKey({ active_states: [{ data: { no_actions: true } }] })).toBe('character.turn.no_actions')
    expect(incapacitatedMessageKey({ active_states: [{ data: { drops_concentration: true } }] })).toBe('character.turn.incapacitated')
    expect(incapacitatedMessageKey({})).toBe('character.turn.incapacitated')
    expect(incapacitatedMessageKey({ computed: { surprised: true }, active_states: [{ data: { no_actions: true } }] })).toBe('character.turn.surprised')
  })
})
