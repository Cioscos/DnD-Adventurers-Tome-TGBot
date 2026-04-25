import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type ThemeMode = 'auto' | 'dark' | 'light'

interface ThemeSettingsStore {
  mode: ThemeMode
  setMode: (mode: ThemeMode) => void
}

export const useThemeSettings = create<ThemeSettingsStore>()(
  persist(
    (set) => ({
      mode: 'auto',
      setMode: (mode) => set({ mode }),
    }),
    { name: 'dnd-theme-settings' },
  ),
)
