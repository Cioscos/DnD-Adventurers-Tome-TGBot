import { useTranslation } from 'react-i18next'
import { Pencil } from 'lucide-react'
import { haptic } from '@/auth/telegram'
import ExpandChevron from '@/components/ui/ExpandChevron'
import Pressable from '@/components/ui/Pressable'
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
  const goldInk = hasBonus ? 'text-dnd-gold-bright' : 'text-dnd-text'

  return (
    <div
      className={`relative rounded-2xl border bg-dnd-surface-raised p-3 transition-colors
                  ${expanded ? 'border-dnd-gold-dim' : 'border-dnd-border-strong'}`}
    >
      {/* Stretched button (behind content): tutta la card è tappabile — espande i
          bonus se ce ne sono, altrimenti apre la modifica come la matita. */}
      <Pressable
        type="button"
        onClick={() => { haptic.light(); if (hasBonus) onToggle(); else onEdit() }}
        aria-expanded={hasBonus ? expanded : undefined}
        aria-label={hasBonus ? fullName : `${t('common.edit')} ${fullName}`}
        className="absolute inset-0 z-0 rounded-2xl"
      />

      <div className="relative z-10 pointer-events-none">
        {/* 2-col header: name | pencil. I nomi sono parole singole non spezzabili e il
            corpo resta a 12 px: senza spaziatura e con la matita verso il bordo della card
            ci stanno per intero, sotto degradano a ellissi, mai a metà parola. */}
        <div className="-mr-2 grid grid-cols-[minmax(0,1fr)_40px] items-center gap-1">
          <span className="min-w-0 overflow-hidden text-ellipsis whitespace-nowrap text-center text-xs font-cinzel uppercase tracking-normal leading-tight text-dnd-text opacity-90">
            {/* Sotto 375px COSTITUZIONE/INTELLIGENZA non stanno accanto alla matita: sigla */}
            <span className="max-xs:hidden">{fullName}</span>
            <span className="xs:hidden">{t(`character.ability.${score.name}_short`, { defaultValue: fullName })}</span>
          </span>
          <Pressable
            type="button"
            onClick={() => { haptic.light(); onEdit() }}
            whileTap={{ scale: 0.9 }}
            aria-label={t('common.edit')}
            className="hit-44 pointer-events-auto justify-self-end flex h-10 w-10 items-center justify-center rounded-full bg-dnd-bg border border-dnd-border text-dnd-gold"
          >
            <Pencil size={14} />
          </Pressable>
        </div>

        {/* value + modifier (+ inline chevron when expandable) — same height with/without bonus */}
        <div className="mt-2 flex items-end justify-center gap-2">
          <span
            className={`text-4xl font-mono font-bold leading-none tabular-nums ${goldInk}`}
            style={{ textShadow: '0 2px 6px rgba(13,10,8,0.5)' }}
          >
            {score.value}
          </span>
          <span className={`mb-1 px-2 py-0.5 rounded-full bg-[rgba(13,10,8,0.25)] text-base font-mono font-bold tabular-nums ${goldInk}`}>
            {modStr}
          </span>
          {hasBonus && (
            <ExpandChevron open={expanded} className="mb-1.5 text-dnd-gold-bright" />
          )}
        </div>
      </div>
    </div>
  )
}
