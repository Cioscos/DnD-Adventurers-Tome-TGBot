import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'
// Inizializza i18next (side-effect import). getLanguageCode ha un fallback
// sicuro a 'it' quando Telegram è assente, quindi non serve lo stub prima.
import '@/i18n'

// Stub minimale di Telegram WebApp letto da api/client.ts (getInitData) e
// auth/telegram.ts, per i test di componenti che chiamano l'API.
;(window as unknown as { Telegram: unknown }).Telegram = {
  WebApp: {
    initData: '',
    initDataUnsafe: { user: { id: 1, language_code: 'it' } },
    ready: () => {},
    expand: () => {},
  },
}

afterEach(() => cleanup())
