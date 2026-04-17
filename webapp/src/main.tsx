import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { LazyMotion, domAnimation } from 'framer-motion'
import App from './App'
import Toast from './components/ui/Toast'
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

// Sync --tg-vh with viewport stable height (updated when keyboard opens/closes)
function syncViewportHeight() {
  const tg = window.Telegram?.WebApp
  const h = tg?.viewportStableHeight ?? tg?.viewportHeight ?? window.innerHeight
  document.documentElement.style.setProperty('--tg-vh', `${h}px`)
}
syncViewportHeight()
window.Telegram?.WebApp?.onEvent?.('viewportChanged', syncViewportHeight)
window.addEventListener('resize', syncViewportHeight)

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
    <LazyMotion features={domAnimation} strict>
      <QueryClientProvider client={queryClient}>
        <App />
        <Toast />
      </QueryClientProvider>
    </LazyMotion>
  </React.StrictMode>
)
