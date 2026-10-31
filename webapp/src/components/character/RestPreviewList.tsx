import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'

interface Props {
  charId: number
  restType: 'long' | 'short'
}

/** Anteprima di cosa recupera il riposo (GET /rest/preview). Muta solo da lettura. */
export default function RestPreviewList({ charId, restType }: Props) {
  const { t } = useTranslation()
  const { data } = useQuery({
    queryKey: ['rest-preview', charId, restType],
    queryFn: () => api.characters.restPreview(charId, restType),
    gcTime: 0,
  })
  if (!data) return null

  const sum = (r: Record<string, number>) => Object.values(r).reduce((a, b) => a + b, 0)
  const rows: [string, string][] = []
  if (data.hp_gain > 0) rows.push([t('character.rest_preview.hp'), `+${data.hp_gain}`])
  if (sum(data.hit_dice_regain) > 0) rows.push([t('character.rest_preview.hit_dice'), `+${sum(data.hit_dice_regain)}`])
  Object.entries(data.slots).forEach(([lvl, n]) => rows.push([`${t('character.rest_preview.slots')} ${lvl}`, `+${n}`]))
  if (data.pact_slots > 0) rows.push([t('character.rest_preview.pact_slots'), `+${data.pact_slots}`])
  if (data.abilities.length) rows.push([t('character.rest_preview.abilities'), data.abilities.join(', ')])
  if (data.homebrew_resources.length) rows.push([t('character.rest_preview.resources'), data.homebrew_resources.join(', ')])
  data.item_charges.forEach((c) => rows.push([
    c.name,
    c.full ? t('character.rest_preview.charge_full', { count: c.gain ?? 0 }) : `+${c.formula}`,
  ]))
  if (data.exhaustion_change) rows.push([t('character.rest_preview.exhaustion'), String(data.exhaustion_change)])

  return (
    <div className="text-left space-y-1" data-testid="rest-preview">
      <p className="text-xs uppercase tracking-wider text-dnd-text-muted font-body">{t('character.rest_preview.title')}</p>
      {rows.length === 0 && !data.ends_concentration && (
        <p className="text-sm text-dnd-text-muted italic font-body">{t('character.rest_preview.nothing')}</p>
      )}
      {rows.map(([label, value]) => (
        <div key={label} className="flex justify-between gap-3 text-sm font-body">
          <span className="text-dnd-text-muted">{label}</span>
          <span className="text-dnd-text tabular-nums text-right">{value}</span>
        </div>
      ))}
      {data.ends_concentration && (
        <p className="text-sm text-dnd-amber font-body">{t('character.rest_preview.concentration')}</p>
      )}
    </div>
  )
}
