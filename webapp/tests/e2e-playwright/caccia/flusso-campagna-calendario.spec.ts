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
