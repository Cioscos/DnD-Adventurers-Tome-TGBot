import { describe, it, expect, vi, afterEach } from 'vitest'
import { QueryClient, QueryObserver, onlineManager, type Query } from '@tanstack/react-query'
import { persistQueryClientRestore, type PersistedClient } from '@tanstack/react-query-persist-client'
import { ApiError } from '@/api/client'
import {
  CACHE_MAX_AGE_MS,
  OFFLINE_QUERY_DEFAULTS,
  createPersister,
  isNetworkError,
  shouldPersistQuery,
  storageKeyFor,
} from '@/lib/queryPersist'

const query = (queryKey: unknown[], state: Record<string, unknown> = { status: 'success', data: {} }) =>
  ({ queryKey, state: { dataUpdatedAt: Date.now(), ...state } }) as unknown as Query

const client = (updatedAts: number[]): PersistedClient => ({
  buster: 'test',
  timestamp: Date.now(),
  clientState: {
    mutations: [],
    queries: updatedAts.map((dataUpdatedAt, i) => ({
      queryKey: ['character', i],
      queryHash: `["character",${i}]`,
      state: { status: 'success', data: { id: i }, dataUpdatedAt },
    })),
  } as unknown as PersistedClient['clientState'],
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.useRealTimers()
  localStorage.clear()
})

describe('shouldPersistQuery', () => {
  it.each([[['characters']], [['character', 1]], [['notes', 1]]])('persists %j on success', (key) => {
    expect(shouldPersistQuery(query(key))).toBe(true)
  })

  it.each([
    [['session-me']],
    [['session-live', 1]],
    [['history', 1]],
    [['dice-history', 1]],
    [['homebrew-resources', 1]],
  ])('never persists %j', (key) => {
    expect(shouldPersistQuery(query(key))).toBe(false)
  })

  it('does not persist a failed query that has no data', () => {
    expect(shouldPersistQuery(query(['character', 1], { status: 'error', error: new TypeError('x') }))).toBe(false)
  })

  it.each([404, 403])('discards the cached copy on a %i', (status) => {
    const state = { status: 'error', data: { id: 1 }, error: new ApiError(status, 'gone') }
    expect(shouldPersistQuery(query(['character', 1], state))).toBe(false)
  })

  // Una sessione scaduta (401) o un backend in errore non dicono nulla sui dati.
  it.each([401, 500, 503])('keeps the cached copy on a %i', (status) => {
    const state = { status: 'error', data: { id: 1 }, error: new ApiError(status, 'boom') }
    expect(shouldPersistQuery(query(['character', 1], state))).toBe(true)
  })

  // Da offline ogni salvataggio riscrive l'intera cache: senza questo caso il
  // refetch fallito cancellerebbe la scheda e il ricaricamento dopo non la troverebbe.
  it('keeps the cached copy when a refetch fails for network reasons', () => {
    const state = { status: 'error', data: { id: 1 }, error: new TypeError('Failed to fetch') }
    expect(shouldPersistQuery(query(['character', 1], state))).toBe(true)
  })

  // Il maxAge del persister guarda il timestamp dell'intero client, che ogni
  // salvataggio rinfresca: da solo non farebbe mai scadere una singola query.
  it('stops persisting a successful query older than the maximum age', () => {
    const old = { status: 'success', data: { id: 1 }, dataUpdatedAt: Date.now() - CACHE_MAX_AGE_MS - 1 }
    expect(shouldPersistQuery(query(['character', 1], old))).toBe(false)
  })

  it('stops persisting a failed refetch whose data is older than the maximum age', () => {
    const old = {
      status: 'error',
      data: { id: 1 },
      error: new TypeError('Failed to fetch'),
      dataUpdatedAt: Date.now() - CACHE_MAX_AGE_MS - 1,
    }
    expect(shouldPersistQuery(query(['character', 1], old))).toBe(false)
  })

  it('still persists data just inside the maximum age', () => {
    const recent = { status: 'success', data: { id: 1 }, dataUpdatedAt: Date.now() - CACHE_MAX_AGE_MS + 60_000 }
    expect(shouldPersistQuery(query(['character', 1], recent))).toBe(true)
  })

  it('does not persist other queries even if the refetch failed for network reasons', () => {
    const state = { status: 'error', data: [], error: new TypeError('Failed to fetch') }
    expect(shouldPersistQuery(query(['history', 1], state))).toBe(false)
  })
})

describe('isNetworkError', () => {
  it('is true for anything that is not an ApiError', () => {
    expect(isNetworkError(new TypeError('Failed to fetch'))).toBe(true)
    expect(isNetworkError(new DOMException('timeout', 'TimeoutError'))).toBe(true)
  })

  it('is false for an ApiError', () => {
    expect(isNetworkError(new ApiError(500, 'boom'))).toBe(false)
  })

  it('still recognises an ApiError restored from storage as a plain object', () => {
    const restored = JSON.parse(JSON.stringify(new ApiError(500, 'boom')))
    expect(isNetworkError(restored)).toBe(false)
    // Un TypeError serializzato diventa {}: resta rete.
    expect(isNetworkError(JSON.parse(JSON.stringify(new TypeError('x'))))).toBe(true)
  })
})

describe('storageKeyFor', () => {
  it('separates users on the same device', () => {
    expect(storageKeyFor(1)).not.toBe(storageKeyFor(2))
  })

  it('uses the expected format', () => {
    expect(storageKeyFor(42)).toBe('dnd-query-cache-42')
    expect(storageKeyFor('42')).toBe('dnd-query-cache-42')
    expect(storageKeyFor(null)).toBe('dnd-query-cache-anon')
  })
})

describe('CACHE_MAX_AGE_MS', () => {
  it('is seven days', () => {
    expect(CACHE_MAX_AGE_MS).toBe(604_800_000)
  })
})

describe('OFFLINE_QUERY_DEFAULTS', () => {
  afterEach(() => { onlineManager.setOnline(true) })

  const setup = (queryFn: () => Promise<unknown>) => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, ...OFFLINE_QUERY_DEFAULTS } } })
    client.mount()
    const unsubscribe = new QueryObserver(client, { queryKey: ['x'], queryFn }).subscribe(() => {})
    return () => { unsubscribe(); client.unmount(); client.clear() }
  }

  const reconnect = () => {
    onlineManager.setOnline(false)
    onlineManager.setOnline(true)
  }

  // networkMode 'always' spegne il refetch alla riconnessione, se non è esplicito.
  it('refetches stale data when the network comes back', async () => {
    const queryFn = vi.fn().mockResolvedValue(1)
    const teardown = setup(queryFn)
    await vi.waitFor(() => expect(queryFn).toHaveBeenCalledTimes(1))
    await new Promise((resolve) => setTimeout(resolve))

    reconnect()
    await vi.waitFor(() => expect(queryFn).toHaveBeenCalledTimes(2))
    teardown()
  })

  // Il caso della stanza di sessione aperta senza dati: senza dati non c'è polling.
  it('refetches a query that failed without data when the network comes back', async () => {
    const queryFn = vi.fn().mockRejectedValueOnce(new TypeError('Failed to fetch')).mockResolvedValue(1)
    const teardown = setup(queryFn)
    await vi.waitFor(() => expect(queryFn).toHaveBeenCalledTimes(1))
    await new Promise((resolve) => setTimeout(resolve))

    reconnect()
    await vi.waitFor(() => expect(queryFn).toHaveBeenCalledTimes(2))
    teardown()
  })

  it('fails instead of pausing while offline', () => {
    expect(OFFLINE_QUERY_DEFAULTS.networkMode).toBe('always')
  })
})

describe('createPersister', () => {
  it('createPersister works when localStorage throws', async () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('denied') })
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('denied') })
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => { throw new Error('denied') })
    vi.useFakeTimers()
    const persister = createPersister(1)

    await expect(Promise.resolve(persister.persistClient(client([1])))).resolves.toBeUndefined()
    expect(() => vi.runAllTimers()).not.toThrow()
    await expect(Promise.resolve(persister.restoreClient())).resolves.toBeUndefined()
    await expect(Promise.resolve(persister.removeClient())).resolves.toBeUndefined()
  })

  it('round-trips a client under the per-user key', async () => {
    vi.useFakeTimers()
    const persister = createPersister(7)
    persister.persistClient(client([1]))
    vi.runAllTimers()

    expect(localStorage.getItem('dnd-query-cache-7')).not.toBeNull()
    const restored = await persister.restoreClient()
    expect(restored?.clientState.queries).toHaveLength(1)
    expect(await createPersister(8).restoreClient()).toBeUndefined()
  })

  // removeOldestQuery scatta solo se setItem propaga l'errore di quota.
  it('drops the oldest query when storage quota is exceeded', async () => {
    const realSet = Storage.prototype.setItem
    let calls = 0
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (this: Storage, k: string, v: string) {
      calls += 1
      if (calls === 1) throw new DOMException('full', 'QuotaExceededError')
      realSet.call(this, k, v)
    })
    vi.useFakeTimers()
    const persister = createPersister(7)
    persister.persistClient(client([200, 100]))
    vi.runAllTimers()

    const restored = await persister.restoreClient()
    expect(restored?.clientState.queries.map((q) => q.state.dataUpdatedAt)).toEqual([200])
  })

  describe('identical saves', () => {
    // Come un salvataggio vero: timestamp e dehydratedAt cambiano sempre.
    const save = (persister: ReturnType<typeof createPersister>, data: unknown = { id: 1 }) => {
      const now = Date.now()
      persister.persistClient({
        buster: 'test',
        timestamp: now,
        clientState: {
          mutations: [],
          queries: [{
            dehydratedAt: now,
            queryKey: ['character', 1],
            queryHash: '["character",1]',
            state: { status: 'success', data, dataUpdatedAt: 100 },
          }],
        },
      } as unknown as PersistedClient)
      vi.advanceTimersByTime(1000)
    }

    const spySetItem = () => vi.spyOn(Storage.prototype, 'setItem')

    it('skips the write when only the save timestamps differ', () => {
      vi.useFakeTimers()
      const setItem = spySetItem()
      const persister = createPersister(7)
      save(persister)
      save(persister)
      save(persister)
      expect(setItem).toHaveBeenCalledTimes(1)
    })

    it('writes again when the data changes', () => {
      vi.useFakeTimers()
      const setItem = spySetItem()
      const persister = createPersister(7)
      save(persister, { id: 1 })
      save(persister, { id: 2 })
      expect(setItem).toHaveBeenCalledTimes(2)
    })

    // Il confronto non può basarsi sul testo: anche i dati possono avere un campo così.
    it('writes again when a data field named timestamp changes', () => {
      vi.useFakeTimers()
      const setItem = spySetItem()
      const persister = createPersister(7)
      save(persister, { timestamp: 1, dehydratedAt: 1 })
      save(persister, { timestamp: 2, dehydratedAt: 2 })
      expect(setItem).toHaveBeenCalledTimes(2)
    })

    it('writes again after the client was removed', () => {
      vi.useFakeTimers()
      const persister = createPersister(7)
      save(persister)
      persister.removeClient()
      save(persister)
      expect(localStorage.getItem('dnd-query-cache-7')).not.toBeNull()
    })

    it('does not treat a failed write as written', () => {
      vi.useFakeTimers()
      const realSet = Storage.prototype.setItem
      let fail = true
      const setItem = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (this: Storage, k: string, v: string) {
        if (fail) throw new DOMException('denied', 'SecurityError')
        realSet.call(this, k, v)
      })
      const persister = createPersister(7)
      save(persister)
      fail = false
      setItem.mockClear()
      save(persister)
      expect(setItem).toHaveBeenCalledTimes(1)
      expect(localStorage.getItem('dnd-query-cache-7')).not.toBeNull()
    })

    // Una stanza di sessione lunga: gli eventi continuano, i dati salvati no. Il timestamp
    // resta fermo all'ultima scrittura, che non è mai precedente all'ultimo aggiornamento
    // dei dati: la cache scade quando scadono loro, non prima.
    it('keeps the cache restorable through a long unchanged session', async () => {
      vi.useFakeTimers()
      const persister = createPersister(7)
      const start = Date.now()
      save(persister)
      vi.setSystemTime(start + CACHE_MAX_AGE_MS - 60_000)
      save(persister)

      const qc = new QueryClient()
      await persistQueryClientRestore({ queryClient: qc, persister, maxAge: CACHE_MAX_AGE_MS, buster: 'test' })
      expect(qc.getQueryData(['character', 1])).toEqual({ id: 1 })
      qc.clear()

      vi.setSystemTime(start + CACHE_MAX_AGE_MS + 60_000)
      const late = new QueryClient()
      await persistQueryClientRestore({ queryClient: late, persister, maxAge: CACHE_MAX_AGE_MS, buster: 'test' })
      expect(late.getQueryData(['character', 1])).toBeUndefined()
      late.clear()
    })
  })
})
