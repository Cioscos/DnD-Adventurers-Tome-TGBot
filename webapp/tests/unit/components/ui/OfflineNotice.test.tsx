import { describe, it, expect, vi, afterEach } from 'vitest'
import { act, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import OfflineNotice from '@/components/ui/OfflineNotice'
import { ApiError } from '@/api/client'

const { lang } = vi.hoisted(() => ({ lang: { value: 'it' } }))

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return {
    ...actual,
    useTranslation: () => ({
      t: (k: string, o?: { time?: string }) => `${k}|${o?.time ?? ''}`,
      i18n: { language: lang.value },
    }),
  }
})

// Oggi all'ora indicata, nel fuso del test.
const todayAt = (hours = 14, minutes = 5) => {
  const d = new Date()
  d.setHours(hours, minutes, 0, 0)
  return d.getTime()
}

const base = {
  data: { id: 1 },
  dataUpdatedAt: todayAt(),
  failureReason: null,
  error: null,
  isFetching: false,
  isRefetchError: false,
}

afterEach(() => { lang.value = 'it' })

describe('OfflineNotice', () => {
  it('shows the time of the cached data after a network failure', () => {
    render(<OfflineNotice query={{ ...base, isRefetchError: true, error: new TypeError('Failed to fetch') }} />)
    expect(screen.getByText('common.offline_data_from|14:05')).toBeInTheDocument()
  })

  // La cache dura 7 giorni: un orario nudo farebbe sembrare di oggi i dati di ieri.
  it('includes the date when the data is not from today', () => {
    const old = new Date(2026, 0, 2, 14, 5).getTime()
    render(<OfflineNotice query={{ ...base, dataUpdatedAt: old, isRefetchError: true, error: new TypeError('x') }} />)
    expect(screen.getByText(/common\.offline_data_from\|.*02.*01.*14:05/)).toBeInTheDocument()
  })

  it('uses 24-hour HH:mm in English too', () => {
    lang.value = 'en'
    render(<OfflineNotice query={{ ...base, isRefetchError: true, error: new TypeError('x') }} />)
    expect(screen.getByText('common.offline_data_from|14:05')).toBeInTheDocument()
  })

  // hour12: false può dare 24:05 su alcuni motori, hourCycle no.
  it('asks for the h23 cycle instead of hour12', () => {
    const spy = vi.spyOn(Date.prototype, 'toLocaleString')
    render(<OfflineNotice query={{ ...base, isRefetchError: true, error: new TypeError('x') }} />)
    const options = spy.mock.calls[0][1]
    expect(options?.hourCycle).toBe('h23')
    expect(options).not.toHaveProperty('hour12')
    spy.mockRestore()
  })

  it('writes midnight as 00, not 24, in English', () => {
    lang.value = 'en'
    render(<OfflineNotice query={{ ...base, dataUpdatedAt: todayAt(0, 5), isRefetchError: true, error: new TypeError('x') }} />)
    expect(screen.getByText('common.offline_data_from|00:05')).toBeInTheDocument()
  })

  it.each([500, 401])('shows the neutral text on an ApiError %i', (status) => {
    render(<OfflineNotice query={{ ...base, isRefetchError: true, error: new ApiError(status, 'boom') }} />)
    expect(screen.getByText('common.stale_data_from|14:05')).toBeInTheDocument()
    expect(screen.queryByText(/offline_data_from/)).not.toBeInTheDocument()
  })

  it('keeps the neutral text for an ApiError restored from storage', () => {
    const restored = JSON.parse(JSON.stringify(new ApiError(500, 'boom')))
    render(<OfflineNotice query={{ ...base, isRefetchError: true, error: restored }} />)
    expect(screen.getByText('common.stale_data_from|14:05')).toBeInTheDocument()
  })

  it('is hidden without an error', () => {
    const { container } = render(<OfflineNotice query={base} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('is hidden when there is nothing cached', () => {
    const { container } = render(<OfflineNotice query={{ ...base, data: undefined, error: new TypeError('x') }} />)
    expect(container).toBeEmptyDOMElement()
  })

  // Con la rete giù i tentativi durano secondi: i dati vecchi non devono
  // sembrare aggiornati finché React Query non si arrende.
  it('already shows while retries are failing, before the query turns into an error', () => {
    render(<OfflineNotice query={{ ...base, isFetching: true, failureReason: new TypeError('Failed to fetch') }} />)
    expect(screen.getByText('common.offline_data_from|14:05')).toBeInTheDocument()
  })

  it('ignores a leftover failureReason when no fetch is running', () => {
    const { container } = render(<OfflineNotice query={{ ...base, failureReason: new TypeError('x') }} />)
    expect(container).toBeEmptyDOMElement()
  })

  // setQueryData azzera `error` ma non `failureReason`: dopo un salvataggio riuscito
  // l'avviso diceva "offline" su dati appena scritti.
  it('disappears when a save lands on the cache after a failed refetch', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    client.setQueryData(['character', 1], { id: 1, name: 'prima' })
    const Harness = () => {
      const query = useQuery({
        queryKey: ['character', 1],
        queryFn: () => Promise.reject(new TypeError('Failed to fetch')),
      })
      return <OfflineNotice query={query} />
    }
    render(<QueryClientProvider client={client}><Harness /></QueryClientProvider>)
    expect(await screen.findByText(/common\.offline_data_from/)).toBeInTheDocument()
    expect(client.getQueryState(['character', 1])?.fetchFailureReason).toBeTruthy()

    act(() => { client.setQueryData(['character', 1], { id: 1, name: 'dopo' }) })

    await waitFor(() => expect(screen.queryByText(/common\.offline_data_from/)).not.toBeInTheDocument())
    expect(client.getQueryState(['character', 1])?.fetchFailureReason).toBeTruthy()
  })
})
