import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ALL_SLOTS } from '@/lib/equipmentSlots'
import EquipmentSlotCell from './EquipmentSlotCell'
import type { EquipmentSlot, Item } from '@/types'

interface Props {
  items: Item[]
  onSlotTap: (slot: EquipmentSlot, equipped: Item | null) => void
  silhouetteUrl?: string | null
}

const LEFT_SLOTS: EquipmentSlot[] = ['head', 'neck', 'cloak', 'body']
const RIGHT_SLOTS: EquipmentSlot[] = ['hands', 'ring1', 'ring2', 'feet']
const BOTTOM_SLOTS: EquipmentSlot[] = ['ammunition', 'main_hand', 'off_hand']

function findEquipped(items: Item[], slot: EquipmentSlot): Item | null {
  return items.find((i) => i.is_equipped && i.equipment_slot === slot) ?? null
}

export default function PaperDoll({ items, onSlotTap, silhouetteUrl }: Props) {
  const { t } = useTranslation()
  const [imgFailed, setImgFailed] = useState(false)
  void ALL_SLOTS

  const showImage = !!silhouetteUrl && !imgFailed

  return (
    <div
      className="@container relative w-full mx-auto rounded-2xl overflow-hidden p-3 bg-dnd-surface border border-dnd-border-strong"
      style={{
        maxWidth: 420,
        boxShadow: 'var(--shadow-2)',
      }}
      role="region"
      aria-label={t('character.equipment.equipment', { defaultValue: 'Equipment' })}
    >
      <div className="grid grid-cols-[56px_1fr_56px] @max-[340px]:grid-cols-[48px_1fr_48px] gap-2 @max-[340px]:gap-1.5 items-start">
        {/* Left column */}
        <div className="flex flex-col gap-2">
          {LEFT_SLOTS.map((slot) => (
            <EquipmentSlotCell
              key={slot}
              slot={slot}
              equipped={findEquipped(items, slot)}
              onTap={(item) => onSlotTap(slot, item)}
            />
          ))}
        </div>

        {/* Vitruvian silhouette OR class+race+gender PNG */}
        <div className="flex items-center justify-center min-h-[280px]">
          {showImage ? (
            <img
              src={silhouetteUrl as string}
              alt={t('character.equipment.equipment', { defaultValue: 'Equipment' })}
              className="max-h-[320px] w-auto object-contain"
              style={{ filter: 'drop-shadow(0 2px 6px rgba(var(--dnd-shadow-color), 0.45))' }}
              onError={() => setImgFailed(true)}
            />
          ) : (
            <svg
              viewBox="0 0 200 360"
              width="100%"
              height="320"
              className="text-dnd-border-strong"
              style={{ filter: 'drop-shadow(0 2px 6px rgba(var(--dnd-shadow-color), 0.45))' }}
              aria-hidden="true"
            >
              <defs>
                <linearGradient id="paperdoll-body" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--dnd-surface-raised)" />
                  <stop offset="100%" stopColor="var(--dnd-bg)" />
                </linearGradient>
              </defs>
              {/* Head */}
              <ellipse cx="100" cy="40" rx="22" ry="26"
                fill="url(#paperdoll-body)" stroke="currentColor" strokeWidth="1.5" />
              {/* Neck */}
              <path d="M88 62 L88 75 L112 75 L112 62 Z"
                fill="url(#paperdoll-body)" stroke="currentColor" strokeWidth="1.5" />
              {/* Torso */}
              <path d="M65 78 Q62 82 60 95 L55 145 Q58 160 70 165 L130 165 Q142 160 145 145 L140 95 Q138 82 135 78 Z"
                fill="url(#paperdoll-body)" stroke="currentColor" strokeWidth="1.5" />
              {/* Arms */}
              <path d="M62 95 Q40 110 32 150 Q28 180 35 200 L48 200 Q42 180 46 155 Q52 125 70 110 Z"
                fill="url(#paperdoll-body)" stroke="currentColor" strokeWidth="1.5" />
              <path d="M138 95 Q160 110 168 150 Q172 180 165 200 L152 200 Q158 180 154 155 Q148 125 130 110 Z"
                fill="url(#paperdoll-body)" stroke="currentColor" strokeWidth="1.5" />
              {/* Hands */}
              <circle cx="41" cy="208" r="8"
                fill="url(#paperdoll-body)" stroke="currentColor" strokeWidth="1.5" />
              <circle cx="159" cy="208" r="8"
                fill="url(#paperdoll-body)" stroke="currentColor" strokeWidth="1.5" />
              {/* Pelvis + legs */}
              <path d="M70 165 L75 200 L72 270 Q72 290 80 310 L92 310 Q90 280 95 240 L100 200 L105 240 Q110 280 108 310 L120 310 Q128 290 128 270 L125 200 L130 165 Z"
                fill="url(#paperdoll-body)" stroke="currentColor" strokeWidth="1.5" />
              {/* Feet */}
              <ellipse cx="86" cy="320" rx="12" ry="6"
                fill="url(#paperdoll-body)" stroke="currentColor" strokeWidth="1.5" />
              <ellipse cx="114" cy="320" rx="12" ry="6"
                fill="url(#paperdoll-body)" stroke="currentColor" strokeWidth="1.5" />
            </svg>
          )}
        </div>

        {/* Right column */}
        <div className="flex flex-col gap-2">
          {RIGHT_SLOTS.map((slot) => (
            <EquipmentSlotCell
              key={slot}
              slot={slot}
              equipped={findEquipped(items, slot)}
              onTap={(item) => onSlotTap(slot, item)}
            />
          ))}
        </div>
      </div>

      {/* Bottom weapon row */}
      <div className="mt-3 flex justify-center gap-3 @max-[340px]:gap-2">
        {BOTTOM_SLOTS.map((slot) => (
          <EquipmentSlotCell
            key={slot}
            slot={slot}
            size="lg"
            equipped={findEquipped(items, slot)}
            onTap={(item) => onSlotTap(slot, item)}
          />
        ))}
      </div>
    </div>
  )
}
