import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import './index.css'
import './i18n'

// ─── Diagnostic: capture early state before HashRouter mutates the hash ────
// Stored in window.__tgDebug so TelegramDebugOverlay can read it.
;(window as any).__tgDebug = {
  hash: window.location.hash,         // full hash before HashRouter changes it
  search: window.location.search,
  hasTgProxy: 'TelegramWebviewProxy' in window,
  nativeEvents: [] as Array<{ type: string; data: unknown }>,
}

// Intercept events sent from the native Telegram bridge to the WebView so we
// can see what the native app is (or isn't) delivering.
const wa = window.Telegram?.WebApp
if (wa && typeof wa.receiveEvent === 'function') {
  const orig = wa.receiveEvent.bind(wa)
  wa.receiveEvent = function(type: string, data: unknown) {
    ;(window as any).__tgDebug.nativeEvents.push({ type, data })
    return orig(type, data)
  }
}

// Signal Telegram that the Mini App is ready. For keyboard-button launch
// contexts on some native clients, this triggers async delivery of initData
// via the native bridge. Calling directly on window avoids the stale-capture
// issue with the `twa` module constant.
window.Telegram?.WebApp?.ready()
window.Telegram?.WebApp?.expand()

/**
 * Wait for window.Telegram.WebApp.initData to be non-empty.
 *
 * On some Telegram clients (especially keyboard-button launch), initData
 * arrives asynchronously after ready() via the native bridge postMessage.
 * We poll briefly before mounting React so the first API calls already have
 * a valid header. Falls through after maxWaitMs regardless, allowing the
 * app to render (it will get a 401 if initData never arrives, rather than
 * hanging forever).
 */
async function waitForInitData(maxWaitMs = 2000): Promise<void> {
  const step = 50
  const deadline = Date.now() + maxWaitMs
  while (Date.now() < deadline) {
    if (window.Telegram?.WebApp?.initData) return
    await new Promise(r => setTimeout(r, step))
  }
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
})

waitForInitData().then(() => {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </React.StrictMode>
  )
})
