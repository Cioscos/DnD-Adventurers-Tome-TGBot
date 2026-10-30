import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import OfflineNotice from '@/components/ui/OfflineNotice'
import { ApiError } from '@/api/client'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return {
    ...actual,
    useTranslation: () => ({
      t: (k: string, o?: { time?: string }) => `${k}|${o?.time ?? ''}`,
      i18n: { language: 'it' },
    }),
  }
})

// Le 14:05 di oggi, nel fuso del test.
const todayAt = () => {
  const d = new Date()
  d.setHours(14, 5, 0, 0)
  return d.getTime()
}

const base = { data: { id: 1 }, dataUpdatedAt: todayAt(), failureReason: null, error: null, isRefetchError: false }

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

  it('is hidden on an ApiError 500', () => {
    const { container } = render(<OfflineNotice query={{ ...base, isRefetchError: true, error: new ApiError(500, 'boom') }} />)
    expect(container).toBeEmptyDOMElement()
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
    render(<OfflineNotice query={{ ...base, failureReason: new TypeError('Failed to fetch') }} />)
    expect(screen.getByText('common.offline_data_from|14:05')).toBeInTheDocument()
  })
})
