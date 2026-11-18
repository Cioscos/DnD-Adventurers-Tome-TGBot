import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { loadCatalog } from '@/lib/srd/catalog'
import { damageTypeLabel } from '@/lib/damageModifier'
import { weaponPreviewText, weaponRangeFt } from '@/lib/weaponOptions'
import { formatLength, useUnitSettings } from '@/store/unitSettings'

type WeaponItem = Parameters<typeof weaponPreviewText>[0] & { name?: string }

/** PA1: «+7 · 1d8+4 · Perforazione · Gittata 45 m» sotto l'arma nel Turno. La gittata viene dal catalogo SRD. */
export default function WeaponPreviewLine({ item }: { item: WeaponItem }) {
  const { t } = useTranslation()
  const system = useUnitSettings((s) => s.system)
  const meta = item.item_metadata ?? {}
  const canHaveRange = meta.weapon_type === 'ranged' || (Array.isArray(meta.properties) && meta.properties.includes('prop_thrown'))
  const { data: catalog } = useQuery({
    queryKey: ['srd-catalog', 'equipment'], queryFn: () => loadCatalog('equipment'), enabled: canHaveRange, staleTime: Infinity,
  })
  const range = catalog ? weaponRangeFt(item, catalog) : null
  const preview = weaponPreviewText(item)
  const text = [
    preview,
    preview && typeof meta.damage_type === 'string' && meta.damage_type ? damageTypeLabel(t, meta.damage_type) : null,
    range ? t('character.turn.weapon_range', { range: formatLength(range, system) }) : null,
  ].filter(Boolean).join(' · ')
  return text ? <p className="text-xs font-mono tabular-nums text-dnd-text-muted">{text}</p> : null
}
