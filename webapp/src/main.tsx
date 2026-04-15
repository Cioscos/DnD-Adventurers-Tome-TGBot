import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import './index.css'
import './i18n'

// Signal Telegram that the Mini App is ready
window.Telegram?.WebApp?.ready()
window.Telegram?.WebApp?.expand()

// Theme detection: apply .light class if Telegram reports light mode
function applyTheme() {
  const scheme = window.Telegram?.WebApp?.colorScheme
  document.documentElement.classList.toggle('light', scheme === 'light')
}
applyTheme()

// Listen for live theme changes (user toggles dark/light in Telegram)
window.Telegram?.WebApp?.onEvent?.('themeChanged', applyTheme)

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
