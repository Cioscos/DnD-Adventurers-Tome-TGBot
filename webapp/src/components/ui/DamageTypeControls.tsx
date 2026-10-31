import { useTranslation } from 'react-i18next'
import Pressable from '@/components/ui/Pressable'
import DamageTypePicker from '@/components/ui/DamageTypePicker'
import { haptic } from '@/auth/telegram'
import type { DamageModifier, DamageMultiplier } from '@/lib/damageModifier'

const LABEL_KEYS = {
  none: 'modifier_none', half: 'modifier_half', double: 'modifier_double', immune: 'modifier_immune',
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
  const mods: DamageMultiplier[] = damageType ? ['none', 'half', 'double', 'immune'] : ['half', 'double']

  return (
    <>
      {setDamageType && (
        <DamageTypePicker
          label={t('character.hp.damage_type')}
          value={damageType}
          onChange={(v) => { setDamageType(v); setDamageModifier(null) }}
          valueFormat="spell"
          allowEmpty
          columns={3}
          excludeOther
        />
      )}
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
    </>
  )
}
