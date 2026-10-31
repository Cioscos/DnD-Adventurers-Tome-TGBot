import { useTranslation } from 'react-i18next'
import FilterChip from '@/components/ui/FilterChip'

interface Props {
  /** Round residui da assegnare; null = nessuna durata ("fino a fine"). */
  value: number | null
  onChange: (rounds: number | null) => void
}

/** Campo numerico + scorciatoie per la durata in round di una condizione. */
export default function DurationInput({ value, onChange }: Props) {
  const { t } = useTranslation()
  return (
    <div className="flex flex-wrap items-center gap-2">
      <label className="text-xs text-dnd-text-muted font-body" htmlFor="duration-rounds">
        {t('character.conditions.duration.label')}
      </label>
      <input
        id="duration-rounds"
        type="number"
        inputMode="numeric"
        min={1}
        max={9999}
        value={value ?? ''}
        aria-label={t('character.conditions.duration.input_aria')}
        onChange={(e) => {
          const n = parseInt(e.target.value, 10)
          onChange(Number.isFinite(n) && n > 0 ? Math.min(n, 9999) : null)
        }}
        className="w-20 min-h-11 px-2 rounded-lg bg-dnd-surface border border-dnd-border text-dnd-text font-mono tabular-nums text-center"
      />
      <FilterChip
        label={t('character.conditions.duration.one_round')}
        selected={value === 1}
        onToggle={() => onChange(1)}
      />
      <FilterChip
        label={t('character.conditions.duration.one_minute')}
        selected={value === 10}
        onToggle={() => onChange(10)}
      />
      <FilterChip
        label={t('character.conditions.duration.until_end')}
        selected={value === null}
        onToggle={() => onChange(null)}
      />
    </div>
  )
}
