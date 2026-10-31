import { create } from 'zustand'
import { DEFAULT_WEAPON_CHOICE, type WeaponChoice } from '@/lib/weaponOptions'

/** In-memory per-weapon pre-attack choice, shared by Actions, Inventory and Quick Actions. */
interface WeaponChoiceStore {
  choices: Record<number, WeaponChoice>
  setChoice: (itemId: number, c: WeaponChoice) => void
}

export const useWeaponChoices = create<WeaponChoiceStore>((set) => ({
  choices: {},
  setChoice: (itemId, c) => set((s) => ({ choices: { ...s.choices, [itemId]: c } })),
}))

export const choiceOf = (choices: Record<number, WeaponChoice>, itemId: number): WeaponChoice =>
  choices[itemId] ?? DEFAULT_WEAPON_CHOICE
