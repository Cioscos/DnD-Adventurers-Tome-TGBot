import { useEffect, useRef } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/client'

/** Turn state polled every 5 s while in a session. A turn/round change may come
 *  with a server-side rounds tick (GM's next-turn), so the cached character is refetched. */
export function useTurnState(charId: number, enabled: boolean) {
  const qc = useQueryClient()
  const query = useQuery({
    queryKey: ['turn-state', charId],
    queryFn: () => api.characters.turnState(charId),
    enabled,
    refetchInterval: 5000,
  })
  const key = query.data ? `${query.data.is_my_turn}:${query.data.round}` : null
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
