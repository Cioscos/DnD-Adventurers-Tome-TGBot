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
 * Format a feet-based length using the current unit system.
 * D&D 5e tradition: 5 ft = 1.5 m (one grid square). We round metric to one decimal
 * and strip the trailing ".0" so common values render cleanly (30 ft → 9 m).
 */
export function formatLength(valueFeet: number, system: UnitSystem): string {
  if (system === 'metric') {
    const m = valueFeet * 0.3048
    const rounded = Math.round(m * 10) / 10
    const display = Number.isInteger(rounded) ? String(rounded) : String(rounded.toFixed(1))
    return `${display.replace(/\.0$/, '')} m`
  }
  return `${valueFeet} ft`
}

export function oppositeSystem(system: UnitSystem): UnitSystem {
  return system === 'imperial' ? 'metric' : 'imperial'
}
