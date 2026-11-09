import { useTranslation } from 'react-i18next'
import type { SpellcastingInfo } from '@/types'

type Row = NonNullable<SpellcastingInfo['limits']>[number]

/** Limiti per classe: oltre il limite il numero diventa rosso e basta, nessun dato cambia. */
export default function SpellLimits({ limits }: { limits: Row[] }) {
  const { t } = useTranslation()
  const rows = limits
    .map((row) => ({
      row,
      cells: ([
        ['limit_cantrips', row.cantrips_count, row.cantrips_limit],
        ['limit_known', row.known_count, row.known_limit],
        ['limit_prepared', row.prepared_count, row.prepared_limit],
        ['limit_off_school', row.school_outside_count ?? 0, row.school_free_limit],
      ] as const).filter(([, , limit]) => limit != null),
    }))
    .filter(({ cells }) => cells.length > 0)
  if (rows.length === 0) return null

  return (
    <div className="rounded-xl border border-dnd-border bg-dnd-surface-raised px-3 py-2 space-y-1" data-testid="spell-limits">
      {rows.map(({ row, cells }) => (
        <div key={row.class_id} className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          {rows.length > 1 && (
            <span className="font-body text-sm text-dnd-text">
              {t(`dnd.classes.${row.class_name.toLowerCase()}`, { defaultValue: row.class_name })}
            </span>
          )}
          {cells.map(([key, count, limit]) => (
            <span key={key} className="inline-flex items-baseline gap-1.5">
              <span className="font-cinzel text-xs uppercase tracking-widest text-dnd-gold-dim">{t(`character.spells.${key}`)}</span>
              <span className={`font-mono text-xs tabular-nums ${count > limit! ? 'text-dnd-crimson-bright' : 'text-dnd-text'}`}>
                {count}/{limit}
              </span>
            </span>
          ))}
          {!!row.school_names?.length && (
            <span data-testid="school-hint" className="text-xs font-body text-dnd-text-muted">
              {t('character.spells.school_hint', { schools: row.school_names.map((s) => t(`character.spells.schools.${s}`, { defaultValue: s })).join(' / ') })}
            </span>
          )}
        </div>
      ))}
    </div>
  )
}
