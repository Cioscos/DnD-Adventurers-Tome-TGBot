import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { SLOT_PLACEHOLDER_ICON } from '@/lib/equipmentSlots'
import { haptic } from '@/auth/telegram'
import type { EquipmentSlot, Item } from '@/types'

interface Props {
  slot: EquipmentSlot
  equipped: Item | null
  size?: 'md' | 'lg'
  onTap: (equipped: Item | null) => void
}

export default function EquipmentSlotCell({ slot, equipped, size = 'md', onTap }: Props) {
  const { t } = useTranslation()
  const PlaceholderIcon = SLOT_PLACEHOLDER_ICON[slot]
  const dim = size === 'lg' ? 56 : 46
  const slotLabel = t(`character.equipment.slots.${slot}`, { defaultValue: slot })

  return (
    <m.button
      type="button"
      onClick={() => { haptic.light(); onTap(equipped) }}
      whileTap={{ scale: 0.92 }}
      style={{
        width: dim,
        height: dim,
        borderRadius: 6,
        border: equipped
          ? '2px solid var(--dnd-gold-bright, #d4af37)'
          : '2px solid var(--dnd-gold-dim, #826635)',
        background: equipped
          ? 'rgba(212,175,55,0.18)'
          : 'rgba(212,175,55,0.08)',
        boxShadow: equipped ? '0 0 6px rgba(212,175,55,0.35)' : undefined,
      }}
      className="relative flex items-center justify-center"
      aria-label={equipped ? `${slotLabel}: ${equipped.name}` : `${slotLabel} ${t('character.equipment.picker.empty', { defaultValue: 'empty' })}`}
    >
      {equipped ? (
        <span
          className="font-cinzel text-[10px] uppercase tracking-wider text-dnd-gold-bright text-center px-1 truncate"
          style={{ maxWidth: dim - 4 }}
        >
          {equipped.name.slice(0, 3)}
        </span>
      ) : (
        <PlaceholderIcon size={dim * 0.45} className="text-dnd-gold-dim" />
      )}
    </m.button>
  )
}
