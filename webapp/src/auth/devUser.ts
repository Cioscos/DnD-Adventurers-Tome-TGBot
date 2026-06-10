/**
 * Dev-only multi-user impersonation.
 *
 * Opening the app with `?dev_user=<id>` (query string, before the HashRouter
 * hash: http://localhost:5173/?dev_user=222#/...) marks the current browser
 * tab as that user. The id is persisted in sessionStorage so each tab keeps
 * its own identity across navigation — two tabs become two distinct users,
 * which is required to test game sessions locally (GM + player).
 *
 * The backend honors the X-Dev-User-Id header only when DEV_USER_ID is set,
 * and the whole module is dead code in production builds (import.meta.env.DEV).
 */

const STORAGE_KEY = 'dev_user_id'

let cached: string | null | undefined

export function getDevUserId(): string | null {
  if (!import.meta.env.DEV) return null
  if (cached !== undefined) return cached

  const fromUrl = new URLSearchParams(window.location.search).get('dev_user')
  if (fromUrl && /^\d+$/.test(fromUrl)) {
    sessionStorage.setItem(STORAGE_KEY, fromUrl)
    cached = fromUrl
  } else {
    cached = sessionStorage.getItem(STORAGE_KEY)
  }
  return cached
}
