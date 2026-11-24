import { defineConfig } from '@playwright/test'

// 4173 è l'unica origine ammessa dal CORS oltre al dev server dell'utente (5173).
export default defineConfig({
  testDir: './tests/e2e-playwright/caccia',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 30_000,
  reporter: 'list',
  use: { baseURL: 'http://localhost:4173', viewport: { width: 412, height: 900 } },
  webServer: [
    { command: 'node tests/e2e-playwright/caccia/avvia-api.mjs', url: 'http://127.0.0.1:8020/health', reuseExistingServer: false },
    {
      command: 'npx vite --port 4173 --strictPort --host localhost',
      url: 'http://localhost:4173/',
      reuseExistingServer: false,
      env: { VITE_API_BASE_URL: 'http://127.0.0.1:8020' },
    },
  ],
})
