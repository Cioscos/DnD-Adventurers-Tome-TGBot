import { useTranslation } from 'react-i18next'
import { Pencil } from 'lucide-react'
import { haptic } from '@/auth/telegram'
import ExpandChevron from '@/components/ui/ExpandChevron'
import Pressable from '@/components/ui/Pressable'
import { LEDGER_LABEL } from '@/styles/ledger'
import type { AbilityScore } from '@/types'

interface Props {
  score: AbilityScore
  expanded: boolean
  onToggle: () => void
  onEdit: () => void
}

export default function AbilityScoreCard({ score, expanded, onToggle, onEdit }: Props) {
  const { t } = useTranslation()
  const hasBonus = (score.modifiers_applied?.length ?? 0) > 0
  const fullName = t(`character.stats.${score.name}`, { defaultValue: score.name })
  const modStr = `${score.modifier >= 0 ? '+' : ''}${score.modifier}`
  const ink = hasBonus ? 'text-dnd-gold-bright' : 'text-dnd-text'

  return (
    <div className="relative flex min-h-[56px] items-center gap-3 pl-1">
      {/* Tutta la riga è tappabile: espande i bonus se ce ne sono, altrimenti apre la modifica. */}
      <Pressable
        type="button"
        onClick={() => { haptic.light(); if (hasBonus) onToggle(); else onEdit() }}
        aria-expanded={hasBonus ? expanded : undefined}
        aria-label={hasBonus ? fullName : `${t('common.edit')} ${fullName}`}
        className="absolute inset-x-0 inset-y-0.5 z-0 hover:bg-dnd-surface/60 transition-colors"
      />
      <span className={`pointer-events-none relative flex-1 ${LEDGER_LABEL}`}>{fullName}</span>
      {hasBonus && <ExpandChevron open={expanded} className="pointer-events-none relative text-dnd-gold-bright" />}
      {/* Il modificatore è il numero che si tira: guida lui, il punteggio accompagna. */}
      <span className="pointer-events-none relative w-7 text-right font-mono text-sm tabular-nums text-dnd-text-muted">{score.value}</span>
      <span className={`pointer-events-none relative w-11 text-right font-mono text-2xl font-bold tabular-nums leading-none ${ink}`}>{modStr}</span>
      <Pressable
        type="button"
        onClick={() => { haptic.light(); onEdit() }}
        whileTap={{ scale: 0.9 }}
        aria-label={t('common.edit')}
        className="relative z-10 flex h-11 w-11 shrink-0 items-center justify-center text-dnd-gold"
      >
        <Pencil size={15} />
      </Pressable>
    </div>
  )
}
