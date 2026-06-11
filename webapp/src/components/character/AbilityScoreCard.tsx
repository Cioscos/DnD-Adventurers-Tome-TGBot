import { m } from 'framer-motion'
import { useTranslation } from 'react-i18next'
import { ChevronDown, Pencil } from 'lucide-react'
import { haptic } from '@/auth/telegram'
import { spring } from '@/styles/motion'
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
      {/* Stretched expand button (behind content) — only when there are bonuses to reveal. */}
      {hasBonus && (
        <button
          type="button"
          onClick={() => { haptic.light(); onToggle() }}
          aria-expanded={expanded}
          aria-label={fullName}
          className="absolute inset-0 z-0 rounded-2xl"
        />
      )}

      <div className="relative z-10 pointer-events-none">
        {/* 2-col header: name | pencil. I nomi sono parole singole non spezzabili:
            il corpo scala con la card (clamp) e degrada a ellissi, mai a metà parola. */}
        <div className="grid grid-cols-[minmax(0,1fr)_40px] items-center gap-1">
          <span className="min-w-0 overflow-hidden text-ellipsis whitespace-nowrap text-center text-[clamp(7.5px,2.4vw,11px)] font-cinzel uppercase tracking-[0.04em] leading-tight text-dnd-text opacity-90">
            {fullName}
          </span>
          <m.button
            type="button"
            onClick={() => { haptic.light(); onEdit() }}
            whileTap={{ scale: 0.9 }}
            aria-label={t('common.edit')}
            className="pointer-events-auto justify-self-end flex h-10 w-10 items-center justify-center rounded-full bg-dnd-bg border border-dnd-border text-dnd-gold"
          >
            <Pencil size={14} />
          </m.button>
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
            <m.span
              aria-hidden
              className="mb-1.5 text-dnd-gold-bright"
              animate={{ rotate: expanded ? 180 : 0 }}
              transition={spring.snappy}
            >
              <ChevronDown size={14} />
            </m.span>
          )}
        </div>
      </div>
    </div>
  )
}
