/**
 * Equipment slot constants and helpers for the paper-doll UI.
 * Mirrors backend `api/services/equipment.py` and must stay in sync.
 */
import type { ComponentType, SVGAttributes } from 'react'
import {
  Crown, Gem, Shirt, Shield, HandMetal, Circle, Footprints,
  Sword, ShieldHalf, Feather,
} from 'lucide-react'
import type { EquipmentSlot } from '@/types'

type IconCmp = ComponentType<SVGAttributes<SVGElement> & { size?: number | string }>

export const ALL_SLOTS: EquipmentSlot[] = [
  'head', 'neck', 'cloak', 'body',
  'hands', 'ring1', 'ring2', 'feet',
  'main_hand', 'off_hand', 'ammunition',
]

/** Lucide icon shown in an empty slot to suggest what it accepts. */
export const SLOT_PLACEHOLDER_ICON: Record<EquipmentSlot, IconCmp> = {
  head: Crown,
  neck: Gem,
  cloak: Shirt,
  body: Shield,
  hands: HandMetal,
  ring1: Circle,
  ring2: Circle,
  feet: Footprints,
  main_hand: Sword,
  off_hand: ShieldHalf,
  ammunition: Feather,
}

/** Allowed slots per item_type. Mirrors EQUIPMENT_SLOT_COMPAT in the backend. */
export const ITEM_TYPE_TO_SLOTS: Record<string, EquipmentSlot[]> = {
  weapon: ['main_hand', 'off_hand'],
  armor: ['body'],
  shield: ['off_hand'],
  accessory: ['neck', 'cloak', 'ring1', 'ring2'],
  gear: ['head', 'hands', 'feet', 'ammunition'],
}

export function slotsAllowedFor(itemType: string): EquipmentSlot[] {
  return ITEM_TYPE_TO_SLOTS[itemType] ?? []
}

export function isSlotAllowed(itemType: string, slot: EquipmentSlot): boolean {
  return slotsAllowedFor(itemType).includes(slot)
}
