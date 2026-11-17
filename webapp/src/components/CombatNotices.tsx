import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { GiSkullCrossedBones } from 'react-icons/gi'
import Pressable from '@/components/ui/Pressable'
import { api } from '@/api/client'
import { haptic } from '@/auth/telegram'
import { useTurnState } from '@/hooks/useTurnState'
import { useCharacterStore } from '@/store/characterStore'

/** Avvisi del combattimento sulle pagine del PG: TS contro la morte a inizio turno (U41)
 *  e fine dello scontro con il ritorno alla serata (U30). */
export default function CombatNotices({ charId }: { charId: number }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const setActiveScreen = useCharacterStore((s) => s.setActiveScreen)
  const { data: char } = useQuery({ queryKey: ['character', charId], queryFn: () => api.characters.get(charId) })
  const { data: session } = useQuery({ queryKey: ['session-me'], queryFn: () => api.sessions.me() })
  const { data: turn } = useTurnState(charId, session?.status === 'active')

  // La serata in cui il PG stava combattendo: quando lo scontro finisce si propone di tornarci.
  const fightingIn = useRef<number | null>(null)
  useEffect(() => {
    if (!turn) return
    if (turn.in_encounter) {
      fightingIn.current = turn.session_id
      return
    }
    const sid = fightingIn.current
    fightingIn.current = null
    if (sid == null) return
    haptic.light()
    toast.info(t('session.combat.ended_toast'), {
      id: 'combat-ended', // montato in più punti: un toast solo
      action: { label: t('session.combat.back_to_session'), onClick: () => navigate(`/session/${sid}`) },
    })
  }, [turn, navigate, t])

  const ds = char?.death_saves
  const dying = !!char && char.current_hit_points === 0 && !ds?.stable && !char.is_dead
  if (!turn?.is_my_turn || !dying) return null
  return (
    <div data-testid="death-save-invite" className="sticky top-0 z-30 w-full bg-dnd-surface-raised">
    <Pressable
      onClick={() => { haptic.light(); setActiveScreen(0); navigate(`/char/${charId}`) }}
      className="w-full min-h-[44px] flex items-center gap-2 px-3 py-2 border-y shadow-parchment-md text-left
                 bg-dnd-crimson/25 border-dnd-crimson/70 text-dnd-crimson-bright"
    >
      <GiSkullCrossedBones size={16} aria-hidden className="shrink-0" />
      <span className="flex-1 min-w-0 text-sm font-display font-bold">{t('character.death_saves.turn_invite')}</span>
    </Pressable>
    </div>
  )
}
