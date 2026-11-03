import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'
import type { SessionParticipant } from '@/types'

/** Compagni a cui `charId` può dare qualcosa: serve una sessione attiva in cui il PG gioca e un altro giocatore con PG. */
export function useTradePartners(charId: number): { sessionId: number; partners: SessionParticipant[]; stash: boolean } | null {
  const { data: session } = useQuery({
    queryKey: ['session-me'],
    queryFn: () => api.sessions.me(),
    refetchInterval: (q) => (q.state.data?.status === 'active' ? 10_000 : false),
  })
  if (!session || session.status !== 'active') return null
  const players = (session.participants ?? []).filter((p) => p.role === 'player')
  if (!players.some((p) => p.character_id === charId)) return null
  const partners = players.filter((p) => p.character_id != null && p.character_id !== charId)
  const stash = session.campaign_id != null // in campagna il deposito è sempre un destinatario
  return partners.length > 0 || stash ? { sessionId: session.id, partners, stash } : null
}
