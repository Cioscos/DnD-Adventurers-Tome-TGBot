import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { m, useReducedMotion } from 'framer-motion'
import { SLOT_PLACEHOLDER_ICON, equippedItemIcon } from '@/lib/equipmentSlots'
import { haptic } from '@/auth/telegram'
import type { EquipmentSlot, Item } from '@/types'

interface Props {
  slot: EquipmentSlot
  equipped: Item | null
  size?: 'md' | 'lg'
  onTap: (equipped: Item | null) => void
}

const EQUIP_HALO_MS = 900

export default function EquipmentSlotCell({ slot, equipped, size = 'md', onTap }: Props) {
  const { t } = useTranslation()
  const reduced = useReducedMotion()
  const PlaceholderIcon = SLOT_PLACEHOLDER_ICON[slot]
  const dim = size === 'lg' ? 56 : 46
  const slotLabel = t(`character.equipment.slots.${slot}`, { defaultValue: slot })
  const initial = equipped?.name?.trim()?.[0]?.toUpperCase() ?? ''
  const Icon = equipped ? equippedItemIcon(equipped, slot) : null

  const prevIdRef = useRef<number | null>(equipped?.id ?? null)
  const [halo, setHalo] = useState(false)

  useEffect(() => {
    const next = equipped?.id ?? null
    if (next != null && next !== prevIdRef.current) {
      if (!reduced) {
        setHalo(true)
        const t = setTimeout(() => setHalo(false), EQUIP_HALO_MS)
        prevIdRef.current = next
        return () => clearTimeout(t)
      }
    }
    prevIdRef.current = next
  }, [equipped?.id, reduced])

  return (
    <m.button
      type="button"
      onClick={() => { haptic.light(); onTap(equipped) }}
      whileTap={reduced ? undefined : { scale: 0.97 }}
      animate={halo ? {
        boxShadow: [
          '0 0 0 0 rgba(240, 201, 112, 0)',
          '0 0 0 3px rgba(240, 201, 112, 0.55), 0 0 18px rgba(212, 168, 71, 0.55)',
          '0 0 0 0 rgba(240, 201, 112, 0)',
        ],
      } : { boxShadow: '0 0 0 0 rgba(240, 201, 112, 0)' }}
      transition={halo ? { duration: EQUIP_HALO_MS / 1000, ease: 'easeOut' } : { duration: 0 }}
      style={{
        width: dim,
        height: dim,
        borderRadius: 8,
        borderWidth: equipped ? 2 : 1,
        borderStyle: 'solid',
        borderColor: equipped
          ? 'var(--dnd-gold-bright)'
          : 'var(--dnd-border)',
        background: equipped
          ? 'rgba(240, 201, 112, 0.10)'
          : 'transparent',
      }}
      className="relative flex items-center justify-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-dnd-gold focus-visible:ring-offset-2 focus-visible:ring-offset-dnd-bg"
      aria-label={equipped ? `${slotLabel}: ${equipped.name}` : `${slotLabel} ${t('character.equipment.picker.empty', { defaultValue: 'empty' })}`}
      title={equipped ? equipped.name : slotLabel}
    >
      {equipped ? (
        <m.span
          layoutId={`equip-icon-${equipped.id}`}
          aria-hidden="true"
          className="text-dnd-gold-bright leading-none flex items-center justify-center"
        >
          {Icon
            ? <Icon size={size === 'lg' ? 22 : 18} />
            : <span className="font-cinzel font-bold" style={{ fontSize: size === 'lg' ? 22 : 18 }}>{initial}</span>}
        </m.span>
      ) : (
        <PlaceholderIcon
          aria-hidden="true"
          size={Math.round(dim * 0.42)}
          className="text-dnd-text-faint"
        />
      )}
    </m.button>
  )
}
