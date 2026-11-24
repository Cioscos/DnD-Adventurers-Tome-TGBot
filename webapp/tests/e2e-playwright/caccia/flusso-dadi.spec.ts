import { expect, test, UTENTE } from './fixtures'

// caccia: {"id": "CB-1489", "fonte": "invariante: un doppio tocco sul tiro di iniziativa registra un solo tiro", "zona": "flusso:dadi", "voce": "ripetizione", "copre": ["route:/char/:id/dice"]}
test('il doppio tocco su Tira Iniziativa registra un solo tiro', async ({ comeUtente, apiRequest, charId }) => {
  const page = await comeUtente(UTENTE)
  await page.goto(`/?dev_user=${UTENTE}#/char/${charId}/dice`)
  await page.getByRole('button', { name: 'Tira Iniziativa' }).dblclick()
  // l'animazione 3D del browser senza GPU può durare più dei 5 s predefiniti
  await expect.poll(async () => (await (await apiRequest.get(`/characters/${charId}/dice/history`)).json()).length, { timeout: 20_000 }).toBeGreaterThan(0)
  await page.waitForTimeout(1500)
  expect((await (await apiRequest.get(`/characters/${charId}/dice/history`)).json()).length).toBe(1)
})

// caccia: {"id": "CB-1490", "fonte": "invariante: dopo lo svuotamento la pagina dei dadi resta vuota anche dopo il ricaricamento", "zona": "flusso:dadi", "voce": "persistenza", "copre": ["route:/char/:id/dice"]}
test('lo storico svuotato dalla pagina dei dadi resta vuoto dopo il ricaricamento', async ({ comeUtente, apiRequest, charId }) => {
  await apiRequest.post(`/characters/${charId}/dice/result`, { data: { rolls: [{ kind: 'd6', value: 4 }] } })
  const page = await comeUtente(UTENTE)
  await page.goto(`/?dev_user=${UTENTE}#/char/${charId}/dice`)
  await page.getByRole('button', { name: 'Cancella cronologia' }).click()
  await page.getByRole('button', { name: 'Conferma' }).click()
  await expect(page.getByRole('button', { name: 'Cancella cronologia' })).toBeHidden()
  await page.reload()
  await expect(page.getByRole('button', { name: 'Tira Iniziativa' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Cancella cronologia' })).toBeHidden()
})
