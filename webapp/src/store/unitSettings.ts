import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type UnitSystem = 'imperial' | 'metric'

interface UnitSettingsStore {
  system: UnitSystem
  setSystem: (system: UnitSystem) => void
}

export const useUnitSettings = create<UnitSettingsStore>()(
  persist(
    (set) => ({
      system: 'imperial',
      setSystem: (system) => set({ system }),
    }),
    { name: 'dnd-unit-settings' },
  ),
)

/**
 * D&D 5e grid conversion: 5 ft = 1.5 m (one grid square), i.e. 1 ft = 0.3 m.
 * We deliberately use the tabletop grid factor (not the real-world 0.3048) so
 * round-trips stay clean: 30 ft ⇄ 9 m, 60 ft ⇄ 18 m, 5 ft ⇄ 1.5 m.
 */
const FT_TO_M = 0.3

/** Unit suffix to show next to an input/value for the given system. */
export function unitLabel(system: UnitSystem): 'ft' | 'm' {
  return system === 'metric' ? 'm' : 'ft'
}

/**
 * Convert a canonical feet value into the numeric value to show in the chosen
 * unit (metric rounded to one decimal). Use for input fields / editable values.
 */
export function feetToDisplay(valueFeet: number, system: UnitSystem): number {
  if (system === 'metric') return Math.round(valueFeet * FT_TO_M * 10) / 10
  return valueFeet
}

/**
 * Convert a value entered in the chosen unit back into canonical feet (rounded
 * to the nearest integer foot, since the DB stores speed as an int).
 */
export function displayToFeet(displayValue: number, system: UnitSystem): number {
  if (system === 'metric') return Math.round(displayValue / FT_TO_M)
  return Math.round(displayValue)
}

/**
 * Format a feet-based length using the current unit system. We round metric to
 * one decimal and strip the trailing ".0" so common values render cleanly
 * (30 ft → 9 m).
 */
export function formatLength(valueFeet: number, system: UnitSystem): string {
  if (system === 'metric') {
    const rounded = feetToDisplay(valueFeet, system)
    const display = Number.isInteger(rounded) ? String(rounded) : String(rounded.toFixed(1))
    return `${display.replace(/\.0$/, '')} m`
  }
  return `${valueFeet} ft`
}

export function oppositeSystem(system: UnitSystem): UnitSystem {
  return system === 'imperial' ? 'metric' : 'imperial'
}
