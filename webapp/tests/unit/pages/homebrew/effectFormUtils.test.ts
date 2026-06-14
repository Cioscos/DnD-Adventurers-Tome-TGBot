import { describe, it, expect } from 'vitest'
import {
  ACTION_EVENT_ALLOWLIST,
  isActionAllowedForEvent,
} from '@/pages/homebrew/sections/effectForm.utils'

describe('isActionAllowedForEvent (D1: apply_modifier_once)', () => {
  it('allows apply_modifier_once only on level_up', () => {
    expect(isActionAllowedForEvent('apply_modifier_once', 'level_up')).toBe(true)
    expect(isActionAllowedForEvent('apply_modifier_once', 'turn_started')).toBe(false)
    expect(isActionAllowedForEvent('apply_modifier_once', 'manual_trigger')).toBe(false)
    expect(isActionAllowedForEvent('apply_modifier_once', 'attack_rolled')).toBe(false)
  })

  it('does not block when the parent trigger event is unknown (undefined)', () => {
    // EffectFormModal validation is the safety net; the picker is the primary gate.
    expect(isActionAllowedForEvent('apply_modifier_once', undefined)).toBe(true)
  })

  it('leaves unrestricted actions allowed on any event', () => {
    expect(isActionAllowedForEvent('notify', 'turn_started')).toBe(true)
    expect(isActionAllowedForEvent('damage_character', 'manual_trigger')).toBe(true)
    expect(isActionAllowedForEvent('change_resource', 'turn_started')).toBe(true)
    expect(isActionAllowedForEvent('roll_dice', undefined)).toBe(true)
  })

  it('restricts only apply_modifier_once in the allowlist', () => {
    expect(Object.keys(ACTION_EVENT_ALLOWLIST)).toEqual(['apply_modifier_once'])
  })
})
