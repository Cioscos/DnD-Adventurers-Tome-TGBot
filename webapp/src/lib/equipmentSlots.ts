/**
 * Equipment slot constants and helpers for the paper-doll UI.
 * Mirrors backend `api/services/equipment.py` and must stay in sync.
 */
import { createElement, type ComponentType, type SVGAttributes } from 'react'
import {
  Crown, Gem, Shirt, Shield, HandMetal, Circle, CircleDot, Footprints,
  Sword, Feather,
} from 'lucide-react'
import type { EquipmentSlot, Item } from '@/types'

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

const TWO_HANDED = 'prop_two_handed'

function equippedInSlot(items: Item[], slot: EquipmentSlot): Item | null {
  return items.find((i) => i.is_equipped && i.equipment_slot === slot) ?? null
}

/** True se l'item è un'arma con la proprietà "a due mani". */
export function isTwoHanded(item: Item | null | undefined): boolean {
  if (!item || item.item_type !== 'weapon') return false
  const props = (item.item_metadata as { properties?: unknown } | undefined)?.properties
  return Array.isArray(props) && props.includes(TWO_HANDED)
}

/**
 * Ritorna l'item equipaggiato che andrebbe rimosso per equipaggiare `item`
 * in `slot` (conflitto arma a due mani ⇄ mano secondaria), o null se nessun conflitto.
 */
export function handsConflict(items: Item[], item: Item, slot: EquipmentSlot): Item | null {
  if (slot === 'off_hand') {
    const main = equippedInSlot(items, 'main_hand')
    return isTwoHanded(main) ? main : null
  }
  if (slot === 'main_hand' && isTwoHanded(item)) {
    return equippedInSlot(items, 'off_hand')
  }
  return null
}
