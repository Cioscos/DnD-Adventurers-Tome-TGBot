import { useTranslation } from 'react-i18next'
import type { AbilityScore } from '@/types'

interface Props {
  score: AbilityScore
}

export default function AbilityScoreDetail({ score }: Props) {
  const { t } = useTranslation()

  return (
    <div className="space-y-1 px-1 pb-3 text-sm font-body">
      <p className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim">
        {t('character.ability.sources')}
      </p>
      <div className="flex items-center justify-between text-dnd-text-muted">
        <span>{t('character.ability.breakdown.base')}</span>
        <span className="font-mono tabular-nums">{score.base_value ?? score.value}</span>
      </div>
      {(score.modifiers_applied ?? []).map((mod, idx) => (
        <div key={idx} className="flex items-center justify-between text-dnd-text-muted">
          <span className="flex-1 truncate">{mod.source}</span>
          <span className="ml-2 shrink-0 font-mono tabular-nums">
            {mod.kind === 'relative'
              ? (mod.value >= 0 ? `+${mod.value}` : mod.value)
              : `=${mod.value}`}
          </span>
        </div>
      ))}
      <div className="flex items-center justify-between border-t border-dnd-border/60 pt-1 font-bold text-dnd-gold-bright">
        <span>{t('character.ability.breakdown.effective')}</span>
        <span className="font-mono tabular-nums">{score.value}</span>
      </div>
    </div>
  )
}
