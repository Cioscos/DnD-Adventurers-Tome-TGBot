import { Minus, Plus } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import Pressable from '@/components/ui/Pressable'

/** Passo grande per le riserve ampie (Imposizione delle Mani: 5 per livello), oltre al ±1. */
const BIG_STEP = 5

/** Quanti usi spendere di un pool (Imposizione delle Mani): da `min` (1 se manca) a `max`. Bersagli da 44 px. */
export default function AmountStepper({ value, max, min = 1, label, onChange }: {
  value: number; max: number; min?: number; label?: string; onChange: (n: number) => void
}) {
  const { t } = useTranslation()
  const btn = 'w-11 h-11 flex items-center justify-center text-dnd-gold-bright disabled:opacity-30 active:bg-dnd-surface-raised'
  const big = max - min > BIG_STEP
  const set = (n: number) => onChange(Math.min(max, Math.max(min, n)))
  return (
    <div className="flex flex-wrap items-center justify-end gap-x-3 gap-y-1">
      <span className="text-xs text-dnd-text-muted font-body">{label ?? t('character.turn.amount_label')}</span>
      <div className="inline-flex items-center rounded-lg bg-dnd-surface border border-dnd-border overflow-hidden">
        {big && (
          <Pressable onClick={() => set(value - BIG_STEP)} disabled={value <= min}
            aria-label={t('character.turn.amount_less_big', { n: BIG_STEP })} className={`${btn} font-mono text-sm font-bold`}>
            −{BIG_STEP}
          </Pressable>
        )}
        <Pressable onClick={() => set(value - 1)} disabled={value <= min}
          aria-label={t('character.turn.amount_less')} className={btn}>
          <Minus size={16} />
        </Pressable>
        <span data-testid="use-amount" className="min-w-[44px] text-center text-base font-bold text-dnd-text tabular-nums">{value}</span>
        <Pressable onClick={() => set(value + 1)} disabled={value >= max}
          aria-label={t('character.turn.amount_more')} className={btn}>
          <Plus size={16} />
        </Pressable>
        {big && (
          <Pressable onClick={() => set(value + BIG_STEP)} disabled={value >= max}
            aria-label={t('character.turn.amount_more_big', { n: BIG_STEP })} className={`${btn} font-mono text-sm font-bold`}>
            +{BIG_STEP}
          </Pressable>
        )}
      </div>
    </div>
  )
}
