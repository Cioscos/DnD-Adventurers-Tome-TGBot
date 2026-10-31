import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'
import { useTurnState } from '@/hooks/useTurnState'
import type { PendingSave } from '@/types'

/** Pending repeated saves of the character, always kept fresh: turn-state is polled
 *  while in an active session or while the character still carries saves. */
export function usePendingSaves(charId: number): { saves: PendingSave[]; isMyTurn: boolean } {
  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
    enabled: charId > 0,
  })
  const { data: session } = useQuery({ queryKey: ['session-me'], queryFn: () => api.sessions.me() })
  const inSession = session?.status === 'active' && !!session.participants?.some((p) => p.character_id === charId)
  const { data: turn } = useTurnState(charId, charId > 0 && (inSession || (char?.pending_saves?.length ?? 0) > 0))
  return {
    saves: turn?.pending_saves ?? char?.pending_saves ?? [],
    isMyTurn: !!turn?.is_my_turn,
  }
}
