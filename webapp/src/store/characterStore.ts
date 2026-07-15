/**
 * Zustand store for client-side UI state.
 * Server data (character lists, full character) is managed by TanStack Query.
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { getLanguageCode } from '@/auth/telegram'

export type CharacterScreen = 0 | 1 | 2

interface CharacterStore {
  /** Currently selected character id (from URL, set by the router) */
  activeCharId: number | null
  setActiveCharId: (id: number | null) => void

  /** Ultimo PG aperto — persistito, preselezione per gli import condivisi */
  lastCharId: number | null

  /** Active screen index in the 3-screen swiper (0=Hero, 1=Equipment, 2=Menu) */
  activeScreen: CharacterScreen
  setActiveScreen: (idx: CharacterScreen) => void

  /** UI language (detected from Telegram user profile) */
  locale: string
  setLocale: (locale: string) => void
}

export const useCharacterStore = create<CharacterStore>()(
  persist(
    (set, get) => ({
      activeCharId: null,
      setActiveCharId: (id) => {
        if (get().activeCharId !== id) {
          set({ activeCharId: id, activeScreen: 0 })
        } else {
          set({ activeCharId: id })
        }
        if (id !== null) set({ lastCharId: id })
      },

      lastCharId: null,

      activeScreen: 0,
      setActiveScreen: (idx) => set({ activeScreen: idx }),

      locale: getLanguageCode().startsWith('it') ? 'it' : 'en',
      setLocale: (locale) => set({ locale }),
    }),
    {
      name: 'dnd-character-store',
      // Persisti SOLO lastCharId: il resto è stato effimero di sessione
      partialize: (s) => ({ lastCharId: s.lastCharId }),
    },
  ),
)
