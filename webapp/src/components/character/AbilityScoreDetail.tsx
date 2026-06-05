import { useTranslation } from 'react-i18next'
import type { AbilityScore } from '@/types'

interface Props {
  score: AbilityScore
}

export default function AbilityScoreDetail({ score }: Props) {
  const { t } = useTranslation()
  const fullName = t(`character.stats.${score.name}`, { defaultValue: score.name })

  return (
    <div className="rounded-xl border border-dnd-gold-dim bg-dnd-surface-raised px-4 py-3">
      <p className="mb-2 text-[9px] font-cinzel uppercase tracking-widest text-dnd-gold-bright">
        {fullName} · {t('character.ability.sources')}
      </p>
      <div className="flex items-center justify-between text-[11px] text-dnd-text-faint">
        <span>{t('character.ability.breakdown.base')}</span>
        <span className="font-mono">{score.base_value ?? score.value}</span>
      </div>
      {(score.modifiers_applied ?? []).map((mod, idx) => (
        <div key={idx} className="flex items-center justify-between text-[11px] text-dnd-gold-dim">
          <span className="flex-1 truncate">{mod.source}</span>
          <span className="ml-2 shrink-0 font-mono">
            {mod.kind === 'relative'
              ? (mod.value >= 0 ? `+${mod.value}` : mod.value)
              : `=${mod.value}`}
          </span>
        </div>
      ))}
      <div className="mt-1 flex items-center justify-between border-t border-dnd-border/60 pt-1.5 text-[11px] font-bold text-dnd-gold-bright">
        <span>{t('character.ability.breakdown.effective')}</span>
        <span className="font-mono">{score.value}</span>
      </div>
    </div>
  )
}
