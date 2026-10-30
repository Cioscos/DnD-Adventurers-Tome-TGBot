import type { Query } from '@tanstack/react-query'
import { createSyncStoragePersister } from '@tanstack/query-sync-storage-persister'
import { removeOldestQuery, type Persister } from '@tanstack/react-query-persist-client'
import { ApiError } from '@/api/client'

/** Durata massima della cache locale: 7 giorni. Anche `gcTime` delle query salvate
 *  deve valere almeno questo, altrimenti il ripristino le scarta. */
export const CACHE_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000

// Solo ciò che serve a consultare la scheda: sessioni, cronologia, dadi e homebrew
// cambiano troppo o non servono al tavolo senza rete.
const PERSISTED_ROOTS: readonly unknown[] = ['characters', 'character', 'notes']

/** `request()` lancia `ApiError` solo se il server ha risposto: tutto il resto è rete
 *  (fetch fallito, timeout). Un `ApiError` ripristinato dalla cache è un oggetto
 *  semplice, ma conserva `status`: resta una risposta del server. */
export function isNetworkError(err: unknown): boolean {
  if (err instanceof ApiError) return false
  return typeof (err as { status?: unknown } | null | undefined)?.status !== 'number'
}

export function shouldPersistQuery(query: Query): boolean {
  if (!PERSISTED_ROOTS.includes(query.queryKey[0])) return false
  const { status, data, error } = query.state
  if (status === 'success') return true
  // Ogni salvataggio riscrive l'intera cache: un refetch fallito porta la query in
  // `error`, e scartarla qui cancellerebbe la copia che si sta mostrando, lasciando
  // vuoto il ricaricamento successivo. Vale per la rete e per 401/5xx, che non dicono
  // nulla sui dati. Solo 404/403 sconfessano la copia, che va persa.
  if (status !== 'error' || data === undefined) return false
  return !(error instanceof ApiError && (error.status === 404 || error.status === 403))
}

/** Una cache per utente: stesso dispositivo, account diversi, dati separati. */
export function storageKeyFor(userId: string | number | null): string {
  return `dnd-query-cache-${userId ?? 'anon'}`
}

// In lettura un localStorage inaccessibile (WebView senza storage, permessi negati)
// si comporta da vuoto. `setItem` invece deve lanciare: il persister cattura
// l'errore e solo così scatta `removeOldestQuery` a quota esaurita.
const guardedStorage = {
  getItem(key: string): string | null {
    try {
      return window.localStorage.getItem(key)
    } catch {
      return null
    }
  },
  setItem(key: string, value: string): void {
    window.localStorage.setItem(key, value)
  },
  removeItem(key: string): void {
    try {
      window.localStorage.removeItem(key)
    } catch {
      /* niente da pulire se lo storage non è raggiungibile */
    }
  },
}

export function createPersister(userId: string | number | null): Persister {
  return createSyncStoragePersister({
    storage: guardedStorage,
    key: storageKeyFor(userId),
    retry: removeOldestQuery,
  })
}
