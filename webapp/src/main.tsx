import React from 'react'
import ReactDOM from 'react-dom/client'
import { MutationCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { LazyMotion, domMax } from 'framer-motion'
import App from './App'
import AppErrorBoundary from './components/AppErrorBoundary'
import Toast from './components/ui/Toast'
import {
  showHomebrewNotifications,
  type NotificationLike,
} from './components/homebrew/HomebrewNotification'
import { initTheme } from './theme/applyTheme'
import { getStartParam } from './auth/telegram'
import { parseStartParam } from './lib/startParam'
import './index.css'
import './i18n'

// Signal Telegram that the Mini App is ready
window.Telegram?.WebApp?.ready()
window.Telegram?.WebApp?.expand()

// Telegram deep-link (t.me/<bot>?startapp=join_XXX): risolvilo PRIMA che React e
// HashRouter montino. Al lancio Telegram scrive i suoi dati nel fragment
// (#tgWebAppData=…&tgWebAppStartParam=join_XXX); HashRouter lo interpreterebbe
// come rotta sconosciuta e la route catch-all `*` rimbalzerebbe su '/'
// (CharacterSelect), sovrascrivendo qualsiasi redirect fatto via effetto in-app.
// Riscrivendo qui il fragment, il router parte direttamente sulla pagina di join.
// Sicuro: l'initData per l'auth è letto dall'oggetto WebApp dell'SDK, non dal
// fragment dell'URL, quindi rimuovere tgWebAppData dall'hash non rompe l'auth.
const startAction = parseStartParam(getStartParam())
if (startAction?.kind === 'join') {
  window.location.hash = `/session/join?code=${startAction.code}`
}

// Lock the app frame against Telegram's native vertical-swipe gesture (Bot API
// 7.7+). Without this, a fast vertical scroll inside our own scroll containers
// gets partially captured by Telegram and drags the whole webview up — in
// fullscreen this slides the top bar underneath the floating native controls
// (Close / chevron / ⋮), losing its safe-area padding. With it, only the inner
// content scrolls and the header stays pinned. Closing is still possible via the
// always-visible Close control. No-op on clients < Bot API 7.7.
window.Telegram?.WebApp?.disableVerticalSwipes?.()

// Theme system: read user preference from store, follow Telegram in auto mode
initTheme()

// Sync --tg-vh with viewport stable height (updated when keyboard opens/closes)
function syncViewportHeight() {
  const tg = window.Telegram?.WebApp
  const h = tg?.viewportStableHeight ?? tg?.viewportHeight ?? window.innerHeight
  document.documentElement.style.setProperty('--tg-vh', `${h}px`)
}
syncViewportHeight()
// Update --tg-vh only on the STABLE frame. During the minimize→restore
// animation Telegram fires viewportChanged repeatedly with transient heights;
// applying each one makes the root container (height: var(--tg-vh)) thrash → flicker.
window.Telegram?.WebApp?.onEvent?.('viewportChanged', (e?: { isStateStable?: boolean }) => {
  if (e && e.isStateStable === false) return
  syncViewportHeight()
})
window.addEventListener('resize', syncViewportHeight)

// Telegram fullscreen mode (Bot API 8.0+): the native controls (Close pill,
// chevron, ⋮ menu) float OVER the Mini App instead of living in a dedicated
// header bar. env(safe-area-inset-top) only covers the device notch, NOT the
// band the Telegram controls occupy — so without this the app header ends up
// underneath them. We normalize both inset objects into our own CSS vars,
// consumed by .pt-safe / .px-safe / .pb-safe (see index.css). Falls back to 0
// outside Telegram or on clients < Bot API 8.0.
function syncSafeAreas() {
  const tg = window.Telegram?.WebApp
  const root = document.documentElement.style
  const set = (prefix: string, inset?: { top: number; bottom: number; left: number; right: number }) => {
    root.setProperty(`${prefix}-top`, `${inset?.top ?? 0}px`)
    root.setProperty(`${prefix}-bottom`, `${inset?.bottom ?? 0}px`)
    root.setProperty(`${prefix}-left`, `${inset?.left ?? 0}px`)
    root.setProperty(`${prefix}-right`, `${inset?.right ?? 0}px`)
  }
  set('--tg-safe', tg?.safeAreaInset)
  set('--tg-content', tg?.contentSafeAreaInset)
}
function syncFullscreenClass() {
  const tg = window.Telegram?.WebApp
  document.body.classList.toggle('tg-fullscreen', !!tg?.isFullscreen)
}
syncSafeAreas()
syncFullscreenClass()
window.Telegram?.WebApp?.onEvent?.('safeAreaChanged', syncSafeAreas)
window.Telegram?.WebApp?.onEvent?.('contentSafeAreaChanged', syncSafeAreas)
window.Telegram?.WebApp?.onEvent?.('fullscreenChanged', () => {
  syncFullscreenClass()
  syncSafeAreas()
})

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
  // Global surface for homebrew rule notifications: any mutation whose
  // response body carries a `homebrew_notifications` array gets piped
  // through the sonner toast system. Single wiring point — no per-page
  // mutation needs to opt in.
  mutationCache: new MutationCache({
    onSuccess: (data) => {
      if (!data || typeof data !== 'object') return
      if (!('homebrew_notifications' in data)) return
      const list = (data as { homebrew_notifications?: unknown }).homebrew_notifications
      if (!Array.isArray(list) || list.length === 0) return
      showHomebrewNotifications(list as NotificationLike[])
    },
  }),
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AppErrorBoundary>
      <LazyMotion features={domMax} strict>
        <QueryClientProvider client={queryClient}>
          <App />
          <Toast />
        </QueryClientProvider>
      </LazyMotion>
    </AppErrorBoundary>
  </React.StrictMode>
)
