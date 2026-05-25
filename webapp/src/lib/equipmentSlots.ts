/**
 * Equipment slot constants and helpers for the paper-doll UI.
 * Mirrors backend `api/services/equipment.py` and must stay in sync.
 */
import { createElement, type ComponentType, type SVGAttributes } from 'react'
import {
  Crown, Gem, Shirt, Shield, HandMetal, Circle, CircleDot, Footprints,
  Sword, Feather,
} from 'lucide-react'
import type { EquipmentSlot } from '@/types'

type IconCmp = ComponentType<SVGAttributes<SVGElement> & { size?: number | string }>

/** Triangular cape/mantle outline — placeholder for the cloak slot. */
const CloakIcon: IconCmp = ({ size = 24, ...props }) =>
  createElement(
    'svg',
    {
      ...props,
      width: size,
      height: size,
      viewBox: '0 0 24 24',
      fill: 'none',
      stroke: 'currentColor',
      strokeWidth: 2,
      strokeLinecap: 'round',
      strokeLinejoin: 'round',
    },
    createElement('path', { d: 'M9 3 h6' }),
    createElement('path', { d: 'M9 3 L4 20 Q12 22 20 20 L15 3' }),
    createElement('path', { d: 'M12 5 L12 21' }),
  )

export const ALL_SLOTS: EquipmentSlot[] = [
  'head', 'neck', 'cloak', 'body',
  'hands', 'ring1', 'ring2', 'feet',
  'main_hand', 'off_hand', 'ammunition',
]

/** Lucide icon shown in an empty slot to suggest what it accepts. */
export const SLOT_PLACEHOLDER_ICON: Record<EquipmentSlot, IconCmp> = {
  head: Crown,
  neck: Gem,
  cloak: CloakIcon,
  body: Shirt,
  hands: HandMetal,
  ring1: Circle,
  ring2: CircleDot,
  feet: Footprints,
  main_hand: Sword,
  off_hand: Shield,
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
