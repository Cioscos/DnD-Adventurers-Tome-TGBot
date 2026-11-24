import { test as base, expect, type APIRequestContext, type Page } from '@playwright/test'

export const API = 'http://127.0.0.1:8020'
export const UTENTE = 9001

export const test = base.extend<{
  apiRequest: APIRequestContext
  charId: number
  /** Una pagina nuova, in un contesto separato, come quell'utente: `goto('/#/char/1')` mantiene l'identità. */
  comeUtente(id: number): Promise<Page>
}>({
  apiRequest: async ({ playwright }, use) => {
    const ctx = await playwright.request.newContext({ baseURL: API, extraHTTPHeaders: { 'X-Dev-User-Id': String(UTENTE) } })
    await use(ctx)
    await ctx.dispose()
  },
  charId: async ({ apiRequest }, use) => {
    const r = await apiRequest.post('/characters', { data: { name: 'Eroe di prova' } })
    expect(r.ok(), `POST /characters: ${r.status()}`).toBeTruthy()
    const { id } = await r.json()
    await use(id)
    await apiRequest.delete(`/characters/${id}`)
  },
  comeUtente: async ({ browser, baseURL }, use) => {
    const contesti: { close(): Promise<void> }[] = []
    await use(async (id) => {
      const contesto = await browser.newContext({ baseURL, viewport: { width: 412, height: 900 } })
      contesti.push(contesto)
      const page = await contesto.newPage()
      await page.goto(`/?dev_user=${id}`)
      return page
    })
    for (const c of contesti) await c.close()
  },
})

export { expect }
