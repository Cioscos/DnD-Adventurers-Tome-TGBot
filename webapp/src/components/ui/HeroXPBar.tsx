import { m } from 'framer-motion'
import { useTranslation } from 'react-i18next'
import { ChevronsUp } from 'lucide-react'
import { GiPolarStar as Star } from 'react-icons/gi'
import { XP_THRESHOLDS, levelFromXp } from '@/lib/xpThresholds'
import { haptic } from '@/auth/telegram'

interface HeroXPBarProps {
  currentXP: number
  totalClassLevel: number
  onLevelUpReady: () => void
  className?: string
}

export default function HeroXPBar({
  currentXP,
  totalClassLevel,
  onLevelUpReady,
  className = '',
}: HeroXPBarProps) {
  const { t } = useTranslation()

  const xpLevel = levelFromXp(currentXP)
  const prevThreshold = xpLevel > 1 ? XP_THRESHOLDS[xpLevel - 1] : 0
  const nextThreshold: number | null = XP_THRESHOLDS[xpLevel] ?? null
  const levelUpReady = xpLevel > totalClassLevel
  const progressPct = nextThreshold
    ? Math.min(100, Math.max(0, Math.round(((currentXP - prevThreshold) / (nextThreshold - prevThreshold)) * 100)))
    : 100

  const handleLevelUp = () => {
    haptic.medium()
    onLevelUpReady()
  }

  const rightLabel = levelUpReady ? null : (
    nextThreshold !== null
      ? t('character.xp.bar.progress', {
          current: currentXP.toLocaleString(),
          threshold: nextThreshold.toLocaleString(),
        })
      : t('character.xp.bar.max')
  )

  return (
    <div className={`mt-3 ${className}`}>
      <div className="flex items-center justify-between gap-2 mb-1.5 text-xs">
        <span className="inline-flex items-center gap-1 text-dnd-gold-bright font-cinzel font-bold">
          <Star size={12} />
          {t('character.xp.bar.level_label', { level: xpLevel })}
        </span>
        {levelUpReady ? (
          <m.button
            type="button"
            onClick={handleLevelUp}
            whileTap={{ scale: 0.95 }}
            className="inline-flex items-center gap-1 animate-shimmer animate-glow-pulse bg-gradient-to-r from-dnd-gold-deep to-dnd-gold-bright text-black px-2.5 py-0.5 rounded-md text-[10px] font-bold tracking-widest uppercase"
          >
            <ChevronsUp size={12} />
            {t('character.xp.bar.level_up')}
          </m.button>
        ) : (
          <span className="font-mono text-dnd-gold">{rightLabel}</span>
        )}
      </div>
      <div
        className="h-1.5 bg-dnd-surface border border-dnd-border rounded-full overflow-hidden"
        {...(nextThreshold !== null
          ? {
              role: 'progressbar' as const,
              'aria-valuemin': 0,
              'aria-valuemax': nextThreshold,
              'aria-valuenow': currentXP,
              'aria-label': t('character.xp.bar.level_label', { level: xpLevel }),
            }
          : { 'aria-label': t('character.xp.bar.max') })}
      >
        <m.div
          className="h-full bg-gradient-to-r from-dnd-gold-deep to-dnd-gold-bright"
          style={{
            boxShadow: levelUpReady ? '0 0 8px var(--dnd-gold-glow)' : undefined,
          }}
          initial={{ width: 0 }}
          animate={{ width: `${progressPct}%` }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
        />
      </div>
    </div>
  )
}
