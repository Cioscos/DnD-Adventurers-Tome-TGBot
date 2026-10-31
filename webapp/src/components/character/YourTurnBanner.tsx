import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import Pressable from '@/components/ui/Pressable'
import { GiCrossedSwords } from 'react-icons/gi'
import { api } from '@/api/client'
import { haptic } from '@/auth/telegram'
import { spring } from '@/styles/motion'

/** "È il tuo turno" nella Hero: polling ogni 5 s solo con una sessione attiva. */
export default function YourTurnBanner({ charId }: { charId: number }) {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const { data: session } = useQuery({ queryKey: ['session-me'], queryFn: () => api.sessions.me() })
  const inSession = session?.status === 'active'
  const { data: turn } = useQuery({
    queryKey: ['turn-state', charId],
    queryFn: () => api.characters.turnState(charId),
    enabled: inSession,
    refetchInterval: 5000,
  })
  if (!inSession || !turn?.is_my_turn) return null

  return (
    <Pressable
      onClick={() => { haptic.light(); navigate(`/char/${charId}/turn`) }}
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={spring.drift}
      whileTap={{ scale: 0.98 }}
      aria-label={t('character.turn.banner_cta')}
      className="w-full min-h-11 flex items-center justify-center gap-2 px-3 py-2 rounded-xl
                 bg-dnd-gold/15 border border-dnd-gold/70 shadow-halo-gold text-dnd-gold-bright"
    >
      <GiCrossedSwords size={16} aria-hidden className="shrink-0" />
      <span className="text-sm font-cinzel uppercase tracking-widest font-bold">
        {t('character.turn.banner')}
      </span>
    </Pressable>
  )
}
