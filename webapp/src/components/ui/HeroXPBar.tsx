import { m } from 'framer-motion'
import { useTranslation } from 'react-i18next'
import { ChevronsUp } from 'lucide-react'
import { GiPolarStar as Star } from 'react-icons/gi'
import { XP_THRESHOLDS, levelFromXp } from '@/lib/xpThresholds'

interface HeroXPBarProps {
  currentXP: number
  totalClassLevel: number
  className?: string
  /**
   * When true, suppresses the level-up halo (shimmer/glow).
   * Set by the parent when another higher-priority halo is active
   * on the same screen (e.g. low-HP pulse on HPGauge) to honor the
   * Halo-as-Signal Rule (one halo per screen).
   */
  suppressHalo?: boolean
}

export default function HeroXPBar({
  currentXP,
  totalClassLevel,
  className = '',
  suppressHalo = false,
}: HeroXPBarProps) {
  const { t } = useTranslation()

  const xpLevel = levelFromXp(currentXP)
  // Finding #4: with no classes (total_level 0) the character has no level — show
  // LIV 0 and suppress the LEVEL UP prompt, consistent with "Nessuna classe". The
  // XP-derived level is a pending value with no class to assign it to.
  const hasClasses = totalClassLevel > 0
  const displayLevel = hasClasses ? xpLevel : 0
  const prevThreshold = xpLevel > 1 ? XP_THRESHOLDS[xpLevel - 1] : 0
  const nextThreshold: number | null = XP_THRESHOLDS[xpLevel] ?? null
  const levelUpReady = hasClasses && xpLevel > totalClassLevel
  const progressPct = nextThreshold
    ? Math.min(100, Math.max(0, Math.round(((currentXP - prevThreshold) / (nextThreshold - prevThreshold)) * 100)))
    : 100

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
          {t('character.xp.bar.level_label', { level: displayLevel })}
        </span>
        {levelUpReady ? (
          <span
            className={`inline-flex items-center gap-1 min-h-[44px] px-3 rounded-md text-[10px] font-cinzel font-bold tracking-widest uppercase bg-dnd-gold text-dnd-ink border border-dnd-gold-bright ${suppressHalo ? '' : 'animate-glow-pulse'}`}
          >
            <ChevronsUp size={12} />
            {t('character.xp.bar.level_up')}
          </span>
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
              'aria-label': t('character.xp.bar.level_label', { level: displayLevel }),
            }
          : { 'aria-label': t('character.xp.bar.max') })}
      >
        <m.div
          className="h-full w-full origin-left bg-gradient-to-r from-dnd-gold-deep to-dnd-gold-bright"
          style={{
            boxShadow: levelUpReady && !suppressHalo ? '0 0 8px var(--dnd-gold-glow)' : undefined,
          }}
          initial={{ scaleX: 0 }}
          animate={{ scaleX: progressPct / 100 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        />
      </div>
    </div>
  )
}
