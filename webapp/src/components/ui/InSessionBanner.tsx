import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { ChevronRight } from 'lucide-react'
import { GiCrossedSwords as Swords } from 'react-icons/gi'
import { api } from '@/api/client'
import { haptic } from '@/auth/telegram'
import { spring } from '@/styles/motion'

interface InSessionBannerProps {
  charId: number
}

export default function InSessionBanner({ charId }: InSessionBannerProps) {
  const navigate = useNavigate()
  const { t } = useTranslation()

  const { data: session } = useQuery({
    queryKey: ['session-me'],
    queryFn: () => api.sessions.me(),
  })

  if (!session) return null
  if (session.status !== 'active') return null
  const isMember = session.participants.some(p => p.character_id === charId)
  if (!isMember) return null

  const label = session.title || t('session.active_session_banner')

  return (
    <m.button
      type="button"
      onClick={() => {
        haptic.light()
        navigate(`/session/${session.id}`)
      }}
      initial={{ y: -8, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={spring.drift}
      whileTap={{ scale: 0.98 }}
      className="sticky top-0 z-30 w-full flex items-center gap-2 px-3 py-2
                 bg-gradient-to-r from-dnd-amber/20 via-dnd-gold/15 to-dnd-amber/20
                 border-y border-dnd-amber/60 shadow-parchment-md backdrop-blur-sm"
      aria-label={t('character.inSession.cta')}
    >
      <Swords size={14} className="text-dnd-amber shrink-0" />
      <div className="flex-1 min-w-0 text-left">
        <p className="text-[10px] uppercase tracking-widest font-cinzel text-dnd-amber leading-none">
          {t('character.inSession.label')}
        </p>
        <p className="text-sm font-display font-bold text-dnd-gold-bright truncate leading-tight mt-0.5">
          {label}
        </p>
      </div>
      <ChevronRight size={18} className="text-dnd-gold-bright shrink-0" />
    </m.button>
  )
}
