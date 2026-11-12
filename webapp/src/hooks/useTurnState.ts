import { useEffect, useRef } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/client'

/** Turn state polled every 5 s only while `live` (an active evening; default: whenever enabled). Outside an
 *  evening the page reads it once and mutations invalidate it. A turn/round change may come
 *  with a server-side rounds tick (GM's next-turn), and `effects_sig` changes when an ally's effect
 *  lands (active states, AC, HP), so the cached character is refetched. */
export function useTurnState(charId: number, enabled: boolean, live: boolean = enabled) {
  const qc = useQueryClient()
  const query = useQuery({
    queryKey: ['turn-state', charId],
    queryFn: () => api.characters.turnState(charId),
    enabled,
    refetchInterval: live ? 5000 : false,
  })
  const key = query.data ? `${query.data.is_my_turn}:${query.data.round}:${query.data.effects_sig ?? ''}` : null
  const lastKey = useRef<string | null>(null)
  useEffect(() => {
    if (key === null) return
    if (lastKey.current !== null && lastKey.current !== key) {
      qc.invalidateQueries({ queryKey: ['character', charId] })
    }
    lastKey.current = key
  }, [key, charId, qc])
  return query
}
