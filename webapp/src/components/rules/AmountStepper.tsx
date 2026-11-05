import { Minus, Plus } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import Pressable from '@/components/ui/Pressable'

/** Quanti usi spendere di un pool (Imposizione delle Mani): da 1 a `max`. Bersagli da 44 px. */
export default function AmountStepper({ value, max, onChange }: { value: number; max: number; onChange: (n: number) => void }) {
  const { t } = useTranslation()
  const btn = 'w-11 h-11 flex items-center justify-center text-dnd-gold-bright disabled:opacity-30 active:bg-dnd-surface-raised'
  return (
    <div className="flex items-center justify-end gap-3">
      <span className="text-xs text-dnd-text-muted font-body">{t('character.turn.amount_label')}</span>
      <div className="inline-flex items-center rounded-lg bg-dnd-surface border border-dnd-border overflow-hidden">
        <Pressable onClick={() => onChange(Math.max(1, value - 1))} disabled={value <= 1}
          aria-label={t('character.turn.amount_less')} className={btn}>
          <Minus size={16} />
        </Pressable>
        <span data-testid="use-amount" className="min-w-[44px] text-center text-base font-bold text-dnd-text tabular-nums">{value}</span>
        <Pressable onClick={() => onChange(Math.min(max, value + 1))} disabled={value >= max}
          aria-label={t('character.turn.amount_more')} className={btn}>
          <Plus size={16} />
        </Pressable>
      </div>
    </div>
  )
}
