/**
 * Zustand store for client-side UI state.
 * Server data (character lists, full character) is managed by TanStack Query.
 */

import { create } from 'zustand'
import { getLanguageCode } from '@/auth/telegram'

interface CharacterStore {
  /** Currently selected character id (from URL, set by the router) */
  activeCharId: number | null
  setActiveCharId: (id: number | null) => void

  /** UI language (detected from Telegram user profile) */
  locale: string
  setLocale: (locale: string) => void
}

export const useCharacterStore = create<CharacterStore>((set) => ({
  activeCharId: null,
  setActiveCharId: (id) => set({ activeCharId: id }),

  locale: getLanguageCode().startsWith('it') ? 'it' : 'en',
  setLocale: (locale) => set({ locale }),
}))
