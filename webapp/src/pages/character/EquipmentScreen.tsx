import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Swords } from 'lucide-react'
import PaperDoll from '@/components/character/PaperDoll'
import EquipItemPicker from '@/components/character/EquipItemPicker'
import SlotActionSheet from '@/components/character/SlotActionSheet'
import EquipmentStatsFooter from '@/components/character/EquipmentStatsFooter'
import SectionDivider from '@/components/ui/SectionDivider'
import { silhouetteUrl } from '@/lib/silhouette'
import type { CharacterFull, EquipmentSlot, Item } from '@/types'

interface Props {
  char: CharacterFull
}

type SheetState =
  | { kind: 'closed' }
  | { kind: 'picker'; slot: EquipmentSlot }
  | { kind: 'actions'; slot: EquipmentSlot; item: Item }

export default function EquipmentScreen({ char }: Props) {
  const { t } = useTranslation()
  const [sheet, setSheet] = useState<SheetState>({ kind: 'closed' })

  const handleSlotTap = (slot: EquipmentSlot, equipped: Item | null) => {
    if (equipped) {
      setSheet({ kind: 'actions', slot, item: equipped })
    } else {
      setSheet({ kind: 'picker', slot })
    }
  }

  const sUrl = silhouetteUrl(char)

  return (
    <div className="px-4 pt-2 pb-safe space-y-2">
      <SectionDivider align="center" icon={<Swords size={12} aria-hidden="true" />}>
        {t('character.equipment.equipment', { defaultValue: 'Equipment' })}
      </SectionDivider>

      <PaperDoll items={char.items ?? []} onSlotTap={handleSlotTap} silhouetteUrl={sUrl} />

      <EquipmentStatsFooter char={char} />

      {sheet.kind === 'picker' && (
        <EquipItemPicker
          charId={char.id}
          slot={sheet.slot}
          items={char.items ?? []}
          onClose={() => setSheet({ kind: 'closed' })}
        />
      )}
      {sheet.kind === 'actions' && (
        <SlotActionSheet
          charId={char.id}
          slot={sheet.slot}
          item={sheet.item}
          onClose={() => setSheet({ kind: 'closed' })}
          onReplace={() => setSheet({ kind: 'picker', slot: sheet.slot })}
          onDetails={(_item) => {
            setSheet({ kind: 'closed' })
          }}
        />
      )}
    </div>
  )
}
