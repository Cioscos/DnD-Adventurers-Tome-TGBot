import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface DiceSettingsStore {
  animate3d: boolean
  setAnimate3d: (value: boolean) => void
}

export const useDiceSettings = create<DiceSettingsStore>()(
  persist(
    (set) => ({
      animate3d: true,
      setAnimate3d: (value) => set({ animate3d: value }),
    }),
    { name: 'dnd-dice-settings' },
  ),
)
