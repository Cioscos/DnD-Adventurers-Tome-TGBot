import type { EquipmentSlot, Item } from '@/types'

interface Props {
  slot: EquipmentSlot
  equipped: Item | null
  size?: 'md' | 'lg'
  onTap: (equipped: Item | null) => void
}

// Stub implementation — Task 12 fills this in.
export default function EquipmentSlotCell(_props: Props) {
  return null
}
