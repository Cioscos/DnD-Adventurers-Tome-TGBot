import { type ReactNode, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ALL_SLOTS, isTwoHanded } from '@/lib/equipmentSlots'
import EquipmentSlotCell from './EquipmentSlotCell'
import WandererSilhouette from './WandererSilhouette'
import type { EquipmentSlot, Item } from '@/types'

interface Props {
  items: Item[]
  onSlotTap: (slot: EquipmentSlot, equipped: Item | null) => void
  silhouetteUrl?: string | null
  /** Affordance opzionale resa centro-alto sopra la silhouette (upload/menu). */
  silhouetteAction?: ReactNode
}

const LEFT_SLOTS: EquipmentSlot[] = ['head', 'neck', 'cloak', 'body']
const RIGHT_SLOTS: EquipmentSlot[] = ['hands', 'ring1', 'ring2', 'feet']
const BOTTOM_SLOTS: EquipmentSlot[] = ['ammunition', 'main_hand', 'off_hand']

function findEquipped(items: Item[], slot: EquipmentSlot): Item | null {
  return items.find((i) => i.is_equipped && i.equipment_slot === slot) ?? null
}

export default function PaperDoll({ items, onSlotTap, silhouetteUrl, silhouetteAction }: Props) {
  const { t } = useTranslation()
  const [imgFailed, setImgFailed] = useState(false)
  void ALL_SLOTS

  const showImage = !!silhouetteUrl && !imgFailed

  const mainHandItem = findEquipped(items, 'main_hand')
  const offHandItem = findEquipped(items, 'off_hand')
  const hideOffHand = isTwoHanded(mainHandItem) && offHandItem === null
  const bottomSlots = BOTTOM_SLOTS.filter((s) => !(s === 'off_hand' && hideOffHand))

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

        {/* Viandante di ripiego OR class+race+gender PNG */}
        <div className="flex flex-col items-center justify-center gap-1.5 min-h-[280px]">
          {silhouetteAction && (
            <div className="shrink-0">{silhouetteAction}</div>
          )}
          {showImage ? (
            <img
              src={silhouetteUrl as string}
              alt={t('character.equipment.equipment', { defaultValue: 'Equipment' })}
              className="max-h-[320px] w-auto object-contain"
              // PNG da ~700 KB: decodifica fuori dal main thread (lo swiper
              // monta questo schermo mentre l'utente è ancora sulla Hero).
              decoding="async"
              style={{ filter: 'drop-shadow(0 2px 6px rgba(var(--dnd-shadow-color), 0.45))' }}
              onError={() => setImgFailed(true)}
            />
          ) : (
            <WandererSilhouette />
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
        {bottomSlots.map((slot) => (
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
