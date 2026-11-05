import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import Pressable from '@/components/ui/Pressable'
import ExpandChevron from '@/components/ui/ExpandChevron'
import DamageTypePicker from '@/components/ui/DamageTypePicker'
import { haptic } from '@/auth/telegram'
import { damageTypeLabel, type DamageModifier, type DamageMultiplier } from '@/lib/damageModifier'

const LABEL_KEYS = {
  none: 'modifier_none', half: 'modifier_half', double: 'modifier_double', half_double: 'modifier_half_double',
  immune: 'modifier_immune',
} as const

interface DamageTypeControlsProps {
  damageType: string
  setDamageType?: (type: string) => void
  /** Override dell'utente; null = segue la proposta del tipo. */
  damageModifier: DamageModifier
  setDamageModifier: (m: DamageModifier) => void
  proposedModifier?: DamageMultiplier
}

/** Tipo di danno opzionale + chip Pieno / ½ / ×2 / Immune. Senza tipo restano i
 *  due toggle ½ / ×2 (override manuale come prima). */
export default function DamageTypeControls({
  damageType, setDamageType, damageModifier, setDamageModifier, proposedModifier,
}: DamageTypeControlsProps) {
  const { t } = useTranslation()
  const effective: DamageModifier = damageModifier ?? (damageType ? proposedModifier ?? null : null)
  const mods: DamageMultiplier[] = damageType
    ? ['none', 'half', 'double', ...(proposedModifier === 'half_double' ? ['half_double' as const] : []), 'immune']
    : ['half', 'double']
  // Chiuso di default: è opzionale e non deve spingere il valore e il pulsante fuori schermo.
  const [open, setOpen] = useState(!!damageType || !!damageModifier)
  const summary = [
    damageType ? damageTypeLabel(t, damageType) : null,
    effective && effective !== 'none' ? t(`character.hp.${LABEL_KEYS[effective]}`) : null,
  ].filter(Boolean).join(' · ')

  return (
    <>
      <Pressable
        onClick={() => { setOpen(!open); haptic.selection() }}
        aria-expanded={open}
        aria-label={t('character.hp.damage_type')}
        className="flex w-full items-center justify-between gap-2 min-h-[44px] px-1 text-left"
      >
        {/* Con una scelta fatta conta il valore: a 360 px etichetta e riepilogo insieme non ci stanno. */}
        {summary
          ? <span className="min-w-0 truncate font-body text-sm text-dnd-cobalt-bright">{summary}</span>
          : <span className="min-w-0 truncate font-cinzel text-xs font-bold uppercase tracking-wider text-dnd-text-muted">{t('character.hp.damage_type')}</span>}
        <ExpandChevron open={open} className="text-dnd-text-muted" />
      </Pressable>
      {open && setDamageType && (
        <DamageTypePicker
          label=""
          value={damageType}
          onChange={(v) => { setDamageType(v); setDamageModifier(null) }}
          valueFormat="spell"
          allowEmpty
          columns={3}
          excludeOther
        />
      )}
      {open && (
      <div className="grid grid-cols-2 gap-2">
        {mods.map((mod) => {
          const on = effective === mod
          return (
            <Pressable
              key={mod}
              onClick={() => { setDamageModifier(on || mod === proposedModifier ? null : mod); haptic.selection() }}
              aria-pressed={on}
              className={`flex items-center justify-center min-h-[44px] rounded-xl border px-2 font-cinzel text-xs uppercase tracking-wider max-xs:tracking-normal whitespace-nowrap transition-colors
                ${on
                  ? '!bg-dnd-cobalt/20 !text-dnd-cobalt-bright !border-dnd-cobalt/60'
                  : 'bg-transparent text-dnd-text-muted border-dnd-border'}`}
            >
              {t(`character.hp.${LABEL_KEYS[mod]}`)}
            </Pressable>
          )
        })}
      </div>
      )}
    </>
  )
}
