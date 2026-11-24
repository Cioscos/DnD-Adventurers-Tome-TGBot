import { expect, test, UTENTE } from './fixtures'

// caccia: {"id": "CB-158", "fonte": "invariante: un doppio tocco su Inizia serata apre una sola sessione", "zona": "flusso:campagna-calendario", "voce": "ripetizione", "copre": ["route:/campaign/:id"]}
test('il doppio tocco su Inizia serata apre una sola serata', async ({ comeUtente, apiRequest }) => {
  const c = await apiRequest.post('/campaigns', { data: { name: 'Campagna doppio tocco' } })
  expect(c.ok()).toBeTruthy()
  const { id } = await c.json()
  const page = await comeUtente(UTENTE)
  await page.goto(`/?dev_user=${UTENTE}#/campaign/${id}`)
  await page.getByRole('button', { name: 'Inizia la sessione' }).dblclick()
  await expect(page).toHaveURL(/#\/session\//)
  const det = await (await apiRequest.get(`/campaigns/${id}`)).json()
  expect(det.sessions).toHaveLength(1)
  await apiRequest.post(`/sessions/${det.active_session_id}/close`)
  await apiRequest.delete(`/campaigns/${id}`)
})


// --- aggiunte del giro del 2026-11-24 (seconda parte) ---
// caccia: {"id": "CB-893", "fonte": "invariante: una serata annullata sparisce subito dal calendario e non torna ricaricando la pagina", "zona": "flusso:campagna-calendario", "voce": "annullamento", "copre": ["route:/campaign/:id"]}
test('annullare una serata la toglie dal calendario subito e dopo il ricaricamento', async ({ comeUtente, apiRequest }) => {
  const c = await apiRequest.post('/campaigns', { data: { name: 'Campagna annulla serata' } })
  expect(c.ok()).toBeTruthy()
  const { id } = await c.json()
  const quando = new Date(Date.now() + 2 * 3600 * 1000).toISOString().slice(0, 19) + 'Z'
  const s = await apiRequest.post(`/campaigns/${id}/schedule`, { data: { starts_at: quando } })
  expect(s.ok()).toBeTruthy()
  const page = await comeUtente(UTENTE)
  await page.goto(`/?dev_user=${UTENTE}#/campaign/${id}`)
  const { giorno, mese } = await page.evaluate((iso) => ({ giorno: new Date(iso).getDate(), mese: new Date(iso).getMonth() }), quando)
  if (mese !== new Date().getMonth()) await page.getByRole('button', { name: 'Mese successivo' }).click()
  await expect(page.locator('[data-mark="planned"]')).toHaveCount(1)
  await page.getByRole('button', { name: new RegExp(`^${giorno} `) }).click()
  await page.getByRole('button', { name: 'Annulla', exact: true }).click()
  await page.getByRole('button', { name: 'Annulla la serata' }).click()
  await expect(page.locator('[data-mark="planned"]')).toHaveCount(0)
  await page.reload()
  await expect(page.getByText('Calendario')).toBeVisible()
  await expect(page.locator('[data-mark="planned"]')).toHaveCount(0)
  expect(await (await apiRequest.get(`/campaigns/${id}/schedule`)).json()).toEqual([])
  await apiRequest.delete(`/campaigns/${id}`)
})
