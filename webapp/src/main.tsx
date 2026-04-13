import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import './index.css'
import './i18n'

// Signal Telegram that the Mini App is ready. Reading from window directly
// avoids the stale-capture issue with the module-level `twa` constant in
// telegram.ts (Telegram may inject WebApp after the module is first evaluated).
window.Telegram?.WebApp?.ready()
window.Telegram?.WebApp?.expand()

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>
)
