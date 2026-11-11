import { notifyMutationError } from '@/lib/mutationError'
import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Plus, Trash2 } from 'lucide-react'
import Sheet from '@/components/ui/Sheet'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import ChipSelect from '@/components/ui/ChipSelect'
import SelectSheet from '@/components/ui/SelectSheet'
import MarkerTypeSheet from '@/pages/atlas/MarkerTypeSheet'
import { api } from '@/api/client'
import { resolveType, typeValue, visibilityKey } from '@/lib/atlasIcons'
import type { AtlasMap, AtlasMarker, MarkerVisibility } from '@/types'

interface Props {
  open: boolean
  campaignId: number
  mapId: number
  isGm: boolean
  maps: AtlasMap[]
  /** Nuovo marker: punto scelto col mirino. */
  point: { x: number; y: number } | null
  /** Modifica: il marker esistente (la visibilità si cambia dalla scheda). */
  marker: AtlasMarker | null
  onClose: () => void
  onSaved: () => void
}

/** Form del marker: tipo (base, personalizzati, «+ Nuovo tipo»), nome, descrizione, visibilità, collegamento. */
export default function MarkerFormSheet({ open, campaignId, mapId, isGm, maps, point, marker, onClose, onSaved }: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [type, setType] = useState('b:poi')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [visibility, setVisibility] = useState<MarkerVisibility>('private')
  const [link, setLink] = useState('')
  const [sub, setSub] = useState<null | 'type' | 'deleteType'>(null)

  useEffect(() => {
    if (!open) return
    setType(marker ? typeValue(marker.type) : 'b:poi')
    setName(marker?.name ?? '')
    setDescription(marker?.description ?? '')
    setVisibility('private')
    setLink(marker?.link_map_id != null ? String(marker.link_map_id) : '')
    setSub(null)
  }, [open, marker])

  const typesQ = useQuery({ queryKey: ['atlas-types', campaignId], queryFn: () => api.atlas.types(campaignId), enabled: open })
  const types = typesQ.data ?? []
  const selected = types.find((tp) => typeValue(tp) === type)
  const fail = (e: unknown) => notifyMutationError(e)
  const refreshMarkers = () => qc.invalidateQueries({ queryKey: ['atlas-markers', campaignId] })

  const save = useMutation({
    mutationFn: () => {
      const custom = type.startsWith('c:')
      const common = {
        name: name.trim(),
        description: description.trim(),
        type_key: custom ? null : type.slice(2),
        custom_type_id: custom ? Number(type.slice(2)) : null,
        // Solo il master può collegare una sottomappa: il giocatore non manda mai il campo.
        ...(isGm ? { link_map_id: link ? Number(link) : null } : {}),
      }
      return marker
        ? api.atlas.updateMarker(campaignId, marker.id, common)
        : api.atlas.createMarker(campaignId, mapId, { ...common, x: point!.x, y: point!.y, visibility })
    },
    onSuccess: () => { refreshMarkers(); onSaved() },
    onError: fail,
  })
  const removeType = useMutation({
    mutationFn: () => api.atlas.deleteType(campaignId, selected!.id!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['atlas-types', campaignId] })
      refreshMarkers()
      setType('b:poi')
      setSub(null)
    },
    onError: fail,
  })

  return (
    <>
      <Sheet open={open && sub === null} onClose={onClose} title={t(marker ? 'atlas.edit_marker' : 'atlas.new_marker')}>
        <div className="p-5 space-y-4">
          <div>
            <ChipSelect
              label={t('atlas.type_label')}
              value={type}
              onChange={setType}
              options={types.map((tp) => {
                const { Icon, color, label } = resolveType(tp)
                return { value: typeValue(tp), label: label(t), icon: <Icon size={16} className={color} aria-hidden /> }
              })}
            />
            <div className="mt-2 flex flex-wrap gap-2">
              <Button variant="secondary" size="sm" icon={<Plus size={16} />} onClick={() => setSub('type')}>{t('atlas.new_type')}</Button>
              {selected && !selected.builtin && selected.can_delete && (
                <Button variant="danger" size="sm" icon={<Trash2 size={16} />} onClick={() => setSub('deleteType')}>{t('atlas.delete_type')}</Button>
              )}
            </div>
          </div>
          <Input label={t('atlas.marker_name')} value={name} onChange={(v: string) => setName(v.slice(0, 80))} />
          <div>
            <Input variant="textarea" rows={4} label={t('atlas.marker_description')} value={description} onChange={(v: string) => setDescription(v.slice(0, 2000))} />
            <p className="mt-1 text-right font-mono text-xs tabular-nums text-dnd-text-faint">{description.length}/2000</p>
          </div>
          {!marker && (
            <ChipSelect
              label={t('atlas.visibility')}
              value={visibility}
              onChange={(v) => setVisibility(v as MarkerVisibility)}
              columns={2}
              options={(['private', 'public'] as const).map((v) => ({ value: v, label: t(visibilityKey(isGm, v)) }))}
            />
          )}
          {isGm && (
            <SelectSheet
              label={t('atlas.link_label')}
              value={link}
              onChange={setLink}
              options={[
                { value: '', label: t('atlas.link_none') },
                ...maps.filter((mp) => mp.id !== mapId).map((mp) => ({ value: String(mp.id), label: mp.name })),
              ]}
            />
          )}
          <div className="flex gap-2 pt-1">
            <Button variant="secondary" fullWidth onClick={onClose}>{t('common.cancel')}</Button>
            <Button fullWidth disabled={!name.trim()} loading={save.isPending} onClick={() => save.mutate()}>{t('common.save')}</Button>
          </div>
        </div>
      </Sheet>
      <MarkerTypeSheet
        open={open && sub === 'type'}
        campaignId={campaignId}
        onClose={() => setSub(null)}
        onCreated={(tp) => { setType(typeValue(tp)); setSub(null) }}
      />
      <ConfirmSheet
        open={open && sub === 'deleteType'}
        onClose={() => setSub(null)}
        onConfirm={() => removeType.mutate()}
        title={t('atlas.delete_type_title')}
        body={t('atlas.delete_type_body')}
        confirmLabel={t('common.delete')}
        loading={removeType.isPending}
      />
    </>
  )
}
