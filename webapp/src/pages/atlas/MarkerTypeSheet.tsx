import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import Sheet from '@/components/ui/Sheet'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import Pressable from '@/components/ui/Pressable'
import { api } from '@/api/client'
import { ATLAS_COLORS, ATLAS_ICONS } from '@/lib/atlasIcons'
import { useToast } from '@/hooks/useToast'
import type { MarkerType } from '@/types'

interface Props { open: boolean; campaignId: number; onClose: () => void; onCreated: (t: MarkerType) => void }

const LABEL = 'block text-xs uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim'
const cell = (on: boolean) =>
  `flex h-11 w-11 items-center justify-center rounded-xl border ${on ? 'border-dnd-gold bg-dnd-gold/20' : 'border-dnd-border bg-dnd-surface'}`

/** Nuovo tipo di marker: nome, icona dalla libreria curata, colore della palette. */
export default function MarkerTypeSheet({ open, campaignId, onClose, onCreated }: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const [name, setName] = useState('')
  const [icon, setIcon] = useState('map-pin')
  const [color, setColor] = useState('gold')
  useEffect(() => { if (open) { setName(''); setIcon('map-pin'); setColor('gold') } }, [open])

  const create = useMutation({
    mutationFn: () => api.atlas.createType(campaignId, { name: name.trim(), icon, color }),
    onSuccess: (type) => { qc.invalidateQueries({ queryKey: ['atlas-types', campaignId] }); onCreated(type) },
    onError: () => toast.error(t('common.action_failed')),
  })
  const Preview = ATLAS_ICONS[icon]

  return (
    <Sheet open={open} onClose={onClose} title={t('atlas.new_type_title')}>
      <div className="p-5 space-y-4">
        <div className="flex items-end gap-3">
          <Input className="min-w-0 flex-1" label={t('atlas.type_name')} value={name} onChange={(v: string) => setName(v.slice(0, 40))} />
          {/* Anteprima della goccia come apparirà sulla mappa. */}
          <span className={`mb-2 flex h-11 w-11 shrink-0 items-center justify-center ${ATLAS_COLORS[color]}`} aria-hidden>
            <span className="flex h-8 w-8 rotate-45 items-center justify-center rounded-[50%_50%_0_50%] border-2 border-current bg-dnd-surface-raised shadow-parchment-md">
              <Preview size={16} className="-rotate-45" />
            </span>
          </span>
        </div>
        <div>
          <span className={LABEL}>{t('atlas.type_icon')}</span>
          <div className="flex flex-wrap gap-2" role="radiogroup" aria-label={t('atlas.type_icon')}>
            {Object.entries(ATLAS_ICONS).map(([key, Icon]) => (
              <Pressable key={key} role="radio" aria-checked={icon === key} aria-label={key} onClick={() => setIcon(key)} className={cell(icon === key)}>
                <Icon size={20} className={icon === key ? 'text-dnd-gold-bright' : 'text-dnd-text'} />
              </Pressable>
            ))}
          </div>
        </div>
        <div>
          <span className={LABEL}>{t('atlas.type_color')}</span>
          <div className="flex flex-wrap gap-2" role="radiogroup" aria-label={t('atlas.type_color')}>
            {Object.entries(ATLAS_COLORS).map(([key, cls]) => (
              <Pressable key={key} role="radio" aria-checked={color === key} aria-label={key} onClick={() => setColor(key)} className={cell(color === key)}>
                <span className={`h-6 w-6 rounded-full bg-current ${cls}`} />
              </Pressable>
            ))}
          </div>
        </div>
        <div className="flex gap-2 pt-1">
          <Button variant="secondary" fullWidth onClick={onClose}>{t('common.cancel')}</Button>
          <Button fullWidth disabled={!name.trim()} loading={create.isPending} onClick={() => create.mutate()}>{t('atlas.create_type')}</Button>
        </div>
      </div>
    </Sheet>
  )
}
