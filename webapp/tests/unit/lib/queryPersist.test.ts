import { describe, it, expect, vi, afterEach } from 'vitest'
import type { Query } from '@tanstack/react-query'
import type { PersistedClient } from '@tanstack/react-query-persist-client'
import { ApiError } from '@/api/client'
import {
  CACHE_MAX_AGE_MS,
  createPersister,
  isNetworkError,
  shouldPersistQuery,
  storageKeyFor,
} from '@/lib/queryPersist'

const query = (queryKey: unknown[], state: Record<string, unknown> = { status: 'success', data: {} }) =>
  ({ queryKey, state }) as unknown as Query

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
})
