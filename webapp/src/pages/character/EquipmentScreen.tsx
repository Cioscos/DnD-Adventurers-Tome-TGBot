import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ImagePlus, Pencil, RotateCcw, Swords } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import PaperDoll from '@/components/character/PaperDoll'
import EquipItemPicker from '@/components/character/EquipItemPicker'
import SlotActionSheet from '@/components/character/SlotActionSheet'
import ItemDetailsModal from '@/components/character/ItemDetailsModal'
import EquipmentStatsFooter from '@/components/character/EquipmentStatsFooter'
import SectionDivider from '@/components/ui/SectionDivider'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'
import { api } from '@/api/client'
import { haptic } from '@/auth/telegram'
import { silhouetteUrl } from '@/lib/silhouette'
import type { CharacterFull, EquipmentSlot, Item } from '@/types'

interface Props {
  char: CharacterFull
}

type SheetState =
  | { kind: 'closed' }
  | { kind: 'picker'; slot: EquipmentSlot }
  | { kind: 'actions'; slot: EquipmentSlot; item: Item }
  | { kind: 'details'; slot: EquipmentSlot; item: Item }

export default function EquipmentScreen({ char }: Props) {
  const { t } = useTranslation()
  const [sheet, setSheet] = useState<SheetState>({ kind: 'closed' })

  const qc = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const [silMenu, setSilMenu] = useState(false)

  const uploadSil = useMutation({
    mutationFn: (file: File) => api.silhouette.upload(char.id, file),
    onSuccess: (updated) => { qc.setQueryData(['character', char.id], updated); haptic.success(); setSilMenu(false) },
    onError: () => haptic.error(),
  })
  const removeSil = useMutation({
    mutationFn: () => api.silhouette.remove(char.id),
    onSuccess: (updated) => { qc.setQueryData(['character', char.id], updated); haptic.success(); setSilMenu(false) },
    onError: () => haptic.error(),
  })

  const onFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) uploadSil.mutate(f)
    e.target.value = ''
  }

  const effectiveUrl = char.has_custom_silhouette ? api.silhouette.fileUrl(char.id) : silhouetteUrl(char)

  const handleSlotTap = (slot: EquipmentSlot, equipped: Item | null) => {
    if (equipped) {
      setSheet({ kind: 'actions', slot, item: equipped })
    } else {
      setSheet({ kind: 'picker', slot })
    }
  }

  return (
    <div className="px-4 pt-2 pb-safe space-y-2">
      <SectionDivider align="center" icon={<Swords size={12} aria-hidden="true" />}>
        {t('character.equipment.equipment', { defaultValue: 'Equipment' })}
      </SectionDivider>

      <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={onFile} />

      <PaperDoll
        items={char.items ?? []}
        onSlotTap={handleSlotTap}
        silhouetteUrl={effectiveUrl}
        silhouetteAction={
          <button
            type="button"
            onClick={() => {
              haptic.light()
              if (char.has_custom_silhouette) setSilMenu(true)
              else fileRef.current?.click()
            }}
            disabled={uploadSil.isPending}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-dnd-surface-raised border border-dnd-gold-dim/60 text-dnd-gold-bright text-[10px] font-cinzel uppercase tracking-widest shadow-parchment-md disabled:opacity-50 active:scale-95"
          >
            {char.has_custom_silhouette ? <Pencil size={12} /> : <ImagePlus size={12} />}
            {uploadSil.isPending ? t('character.equipment.silhouette.uploading') : t('character.equipment.silhouette.upload')}
          </button>
        }
      />

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
          onDetails={(item) => setSheet({ kind: 'details', slot: sheet.slot, item })}
        />
      )}
      {sheet.kind === 'details' && (
        <ItemDetailsModal
          item={sheet.item}
          slot={sheet.slot}
          onClose={() => setSheet({ kind: 'closed' })}
        />
      )}

      <Sheet open={silMenu} onClose={() => setSilMenu(false)} centered title={t('character.equipment.silhouette.upload')}>
        <div className="p-5 space-y-2">
          <Button variant="secondary" fullWidth onClick={() => { setSilMenu(false); fileRef.current?.click() }}>
            {t('character.equipment.silhouette.change')}
          </Button>
          <Button variant="danger" fullWidth icon={<RotateCcw size={16} />} loading={removeSil.isPending} onClick={() => removeSil.mutate()} haptic="warning">
            {t('character.equipment.silhouette.remove')}
          </Button>
        </div>
      </Sheet>
    </div>
  )
}
