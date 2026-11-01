import { useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { haptic } from '@/auth/telegram'
import type { EncounterLive } from '@/types'

/** Toast «tocca a te» quando il puntatore del turno passa al mio PG. */
export function useYourTurnToast(enc: EncounterLive | null | undefined, myUserId: number): void {
  const { t } = useTranslation()
  const prevActiveRef = useRef<number | null>(null)
  useEffect(() => {
    const activeId = enc?.status === 'active' ? enc.active_combatant_id : null
    if (activeId !== null && activeId !== prevActiveRef.current) {
      const active = enc?.combatants.find((c) => c.id === activeId)
      if (active?.kind === 'pc' && active.owner_user_id === myUserId) {
        haptic.success()
        toast.success(t('session.combat.your_turn'), { duration: 3000 })
      }
    }
    prevActiveRef.current = activeId
  }, [enc, myUserId, t])
}
