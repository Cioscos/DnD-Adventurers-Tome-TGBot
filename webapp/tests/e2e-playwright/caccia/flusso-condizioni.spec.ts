import { expect, test, UTENTE } from './fixtures'

// caccia: {"id": "CB-1303", "fonte": "CLAUDE.md · Durations: le condizioni scadono dopo un numero di round, decrementati da rounds/tick", "zona": "flusso:condizioni", "voce": "persistenza", "copre": ["route:/char/:id/conditions"]}
test('la durata di una condizione scala a ogni «Fine round», resta dopo il ricaricamento e a zero la condizione cade', async ({ comeUtente, apiRequest, charId }) => {
  const r = await apiRequest.patch(`/characters/${charId}/conditions`, { data: { conditions: { blinded: true }, durations: { blinded: 2 } } })
  expect(r.ok()).toBeTruthy()
  const page = await comeUtente(UTENTE)
  await page.goto(`/?dev_user=${UTENTE}#/char/${charId}/conditions`)
  await expect(page.getByText('2 round', { exact: true }).first()).toBeVisible()
  await page.getByRole('button', { name: 'Fine round (−1)' }).click()
  await expect(page.getByText('1 round', { exact: true }).first()).toBeVisible()
  await page.reload()
  await expect(page.getByText('1 round', { exact: true }).first()).toBeVisible()
  await page.getByRole('button', { name: 'Fine round (−1)' }).click()
  await expect(page.getByRole('button', { name: 'Fine round (−1)' })).toHaveCount(0)
  const stato = await (await apiRequest.get(`/characters/${charId}`)).json()
  expect(stato.conditions.blinded).toBeFalsy()
  expect(stato.condition_effects).toEqual([])
})

// caccia: {"id": "CB-1304", "fonte": "invariante: un doppio tocco sul pulsante di conferma non toglie né scrive due volte", "zona": "flusso:condizioni", "voce": "ripetizione", "copre": ["route:/char/:id/conditions"]}
test('doppio tocco su una condizione da accendere lascia una sola riga di storico', async ({ comeUtente, apiRequest, charId }) => {
  const page = await comeUtente(UTENTE)
  await page.goto(`/?dev_user=${UTENTE}#/char/${charId}/conditions`)
  const voce = page.getByRole('button', { name: 'Accecato', exact: true })
  await voce.dblclick()
  await expect.poll(async () => (await (await apiRequest.get(`/characters/${charId}`)).json()).conditions.blinded).toBe(true)
  const storico = await (await apiRequest.get(`/characters/${charId}/history`)).json()
  expect(storico.filter((h: { description: string }) => h.description.includes('Accecato')).length).toBeLessThanOrEqual(1)
})
