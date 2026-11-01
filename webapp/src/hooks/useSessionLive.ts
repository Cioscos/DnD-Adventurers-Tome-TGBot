import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'

/** Stato live della sessione, condiviso da SessionRoom e dalla pagina Combattimento. */
export function useSessionLive(sessionId: number) {
  return useQuery({
    queryKey: ['session-live', sessionId],
    queryFn: async () => {
      // last_activity_at è il keep-alive del server: cambia a OGNI poll e
      // nessun componente lo legge. Va scartato prima che il dato entri in
      // cache: così i poll senza novità restano deep-equal, lo structural
      // sharing riusa la stessa reference e la pagina non ri-renderizza
      // a ogni tick da 2.5s.
      const { last_activity_at: keepAlive, ...stable } = await api.sessions.live(sessionId)
      void keepAlive
      return stable
    },
    refetchInterval: (query) => {
      const d = query.state.data
      return d && d.status === 'active' ? 2500 : false
    },
    // Si entra spesso da un'altra pagina con la cache vecchia (es. combattimento
    // iniziato nel frattempo): al mount serve sempre il dato fresco.
    refetchOnMount: 'always',
    enabled: Number.isFinite(sessionId),
  })
}
