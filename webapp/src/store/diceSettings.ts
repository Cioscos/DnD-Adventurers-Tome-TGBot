import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface DiceSettingsStore {
  animate3d: boolean
  packId: string
  setAnimate3d: (value: boolean) => void
  setPackId: (id: string) => void
}

export const useDiceSettings = create<DiceSettingsStore>()(
  persist(
    (set) => ({
      animate3d: true,
      packId: 'default',
      setAnimate3d: (value) => set({ animate3d: value }),
      setPackId: (id) => set({ packId: id }),
    }),
    { name: 'dnd-dice-settings' },
  ),
)
