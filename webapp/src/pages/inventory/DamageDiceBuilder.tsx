import { useTranslation } from 'react-i18next'
import { Minus, Plus } from 'lucide-react'
import { DIE_SIZES, parseDamageDice, serializeDamageDice } from './itemMetadata'

interface DamageDiceBuilderProps {
  /** Notazione canonica, es. "1d8", "2d6+3", "1d6-1". */
  value: string
  onChange: (next: string) => void
  /** Tagli di dado proposti come chip (default: dadi arma 5e). */
  dieSizes?: readonly number[]
  /** Numero massimo di dadi (default 10; le spell arrivano a 12). */
  maxCount?: number
  /** Etichetta del campo (default: label inventario). */
  label?: string
}

const COUNT_MIN = 1
const MOD_MIN = -5
const MOD_MAX = 20

interface StepperProps {
  display: string
  onDec: () => void
  onInc: () => void
  decDisabled?: boolean
  incDisabled?: boolean
}

function Stepper({ display, onDec, onInc, decDisabled, incDisabled }: StepperProps) {
  return (
    <div className="inline-flex items-center rounded-lg bg-dnd-surface border border-dnd-border overflow-hidden">
      <button
        type="button"
        onClick={onDec}
        disabled={decDisabled}
        className="w-11 h-11 flex items-center justify-center text-dnd-gold-bright disabled:opacity-30 active:bg-dnd-surface-raised"
      >
        <Minus size={16} />
      </button>
      <span className="min-w-[44px] text-center text-base font-bold text-dnd-text tabular-nums">
        {display}
      </span>
      <button
        type="button"
        onClick={onInc}
        disabled={incDisabled}
        className="w-11 h-11 flex items-center justify-center text-dnd-gold-bright disabled:opacity-30 active:bg-dnd-surface-raised"
      >
        <Plus size={16} />
      </button>
    </div>
  )
}

export default function DamageDiceBuilder({
  value,
  onChange,
  dieSizes = DIE_SIZES,
  maxCount = 10,
  label,
}: DamageDiceBuilderProps) {
  const { t } = useTranslation()
  const { count, die, mod } = parseDamageDice(value)
  // Fuori-set rispetto ai dadi proposti QUI (non a DIE_SIZES hardcoded):
  // con dieSizes custom (es. spell con d20) il set di riferimento cambia.
  const unknownDie = !dieSizes.includes(die)

  const emit = (c: number, d: number, m: number) => onChange(serializeDamageDice(c, d, m))

  // Mostra il dado fuori-set (es. d20 homebrew) come chip extra, così l'edit non perde dati.
  const dice: number[] = unknownDie ? [...dieSizes, die] : [...dieSizes]

  const fmtMod = (m: number) => (m > 0 ? `+${m}` : m < 0 ? `${m}` : '+0')
  const preview =
    mod === 0
      ? `${count}d${die}`
      : `${count}d${die} ${mod > 0 ? '+' : '−'} ${Math.abs(mod)}`

  return (
    <div>
      <label className="block text-[11px] uppercase tracking-wider mb-2 font-cinzel font-bold text-dnd-gold-dim">
        {label ?? t('character.inventory.damage_dice_label')}
      </label>

      {/* N° dadi */}
      <div className="flex items-center gap-3 mb-3">
        <span className="text-xs text-dnd-text-muted font-body w-20 shrink-0">
          {t('character.inventory.dice_count')}
        </span>
        <Stepper
          display={String(count)}
          onDec={() => emit(Math.max(COUNT_MIN, count - 1), die, mod)}
          onInc={() => emit(Math.min(maxCount, count + 1), die, mod)}
          decDisabled={count <= COUNT_MIN}
          incDisabled={count >= maxCount}
        />
      </div>

      {/* Tipo dado */}
      <div className="flex items-start gap-3 mb-3">
        <span className="text-xs text-dnd-text-muted font-body w-20 shrink-0 mt-2.5">
          {t('character.inventory.die_type')}
        </span>
        <div className="flex flex-wrap gap-2">
          {dice.map((d) => {
            const active = d === die
            return (
              <button
                key={d}
                type="button"
                onClick={() => emit(count, d, mod)}
                className={`min-h-[44px] px-3 rounded-lg text-sm font-bold tabular-nums transition-colors
                  ${active
                    ? 'bg-dnd-gold text-dnd-ink shadow-halo-gold'
                    : 'bg-dnd-surface-raised text-dnd-text border border-dnd-border'}`}
              >
                d{d}
              </button>
            )
          })}
        </div>
      </div>

      {/* Modificatore */}
      <div className="flex items-center gap-3 mb-3">
        <span className="text-xs text-dnd-text-muted font-body w-20 shrink-0">
          {t('character.inventory.modifier')}
        </span>
        <Stepper
          display={fmtMod(mod)}
          onDec={() => emit(count, die, Math.max(MOD_MIN, mod - 1))}
          onInc={() => emit(count, die, Math.min(MOD_MAX, mod + 1))}
          decDisabled={mod <= MOD_MIN}
          incDisabled={mod >= MOD_MAX}
        />
      </div>

      {/* Preview */}
      <div className="rounded-lg bg-dnd-surface border border-dashed border-dnd-gold-dim/50 py-2.5 text-center">
        <span className="text-xl font-bold text-dnd-gold-bright tabular-nums tracking-wide">
          {preview}
        </span>
      </div>
    </div>
  )
}
