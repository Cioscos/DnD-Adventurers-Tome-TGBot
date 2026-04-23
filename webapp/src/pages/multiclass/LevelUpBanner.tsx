import { m } from 'framer-motion'
import { useTranslation } from 'react-i18next'
import { Sparkles } from 'lucide-react'
import { spring } from '@/styles/motion'
import { haptic } from '@/auth/telegram'

interface LevelUpBannerProps {
  onOpen: () => void
  className?: string
}

export default function LevelUpBanner({ onOpen, className = '' }: LevelUpBannerProps) {
  const { t } = useTranslation()

  const handleClick = () => {
    haptic.medium()
    onOpen()
  }

  return (
    <m.button
      type="button"
      onClick={handleClick}
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={spring.elastic}
      whileTap={{ scale: 0.97 }}
      aria-label={t('character.xp.level_up_available')}
      className={`w-full rounded-2xl bg-gradient-gold border border-dnd-gold text-dnd-ink
                  px-4 py-3 text-sm font-cinzel uppercase tracking-wider
                  flex items-center justify-center gap-2 shadow-parchment-lg
                  hover:brightness-110 transition ${className}`}
    >
      <Sparkles size={16} className="animate-shimmer" />
      {t('character.xp.level_up_available')}
    </m.button>
  )
}
