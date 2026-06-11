import { ReactElement } from 'react'
import { render } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'

/**
 * Render helper for components that depend on TanStack Query and/or the Router.
 * Pure-function/lib units do not need this — import the function directly.
 */
export function renderWithProviders(ui: ReactElement, { route = '/' } = {}) {
  // retryDelay 0: i componenti che impostano una propria politica `retry`
  // (es. il guard 404 di Layout/CharacterMain) esauriscono i tentativi
  // subito invece di pagare il backoff esponenziale (~7s) nel test.
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, retryDelay: 0 } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  )
}
