import { expect, test, UTENTE } from './fixtures'

// caccia: {"id": "CB-655", "fonte": "invariante: una richiesta ripetuta non crea due volte (doppio tocco su Crea)", "zona": "flusso:creazione", "voce": "ripetizione", "copre": ["route:/"]}
test.fail('il doppio tocco su Crea crea un solo personaggio', async ({ comeUtente, apiRequest }) => {
  const nome = `Doppio tocco ${Date.now()}`
  const page = await comeUtente(UTENTE)
  // la risposta arriva in ritardo: il secondo tocco cade mentre la prima richiesta è ancora in corso
  await page.route('**/characters', async (route) => {
    if (route.request().method() === 'POST') await new Promise((r) => setTimeout(r, 800))
    await route.continue()
  })
  await page.goto(`/?dev_user=${UTENTE}`)
  await page.getByRole('button', { name: 'Nuovo personaggio' }).click()
  await page.getByPlaceholder('Il nome del tuo eroe').fill(nome)
  await page.getByRole('button', { name: 'Avanti →' }).click()
  await page.getByText('Senza classe').click()
  await page.getByRole('button', { name: 'Avanti →' }).click() // classe -> specie
  await page.getByRole('button', { name: 'Avanti →' }).click() // specie -> punteggi
  await page.getByText('Salta: lascia tutti a 10').click()
  await page.getByRole('button', { name: 'Crea', exact: true }).dblclick()
  await expect(page).toHaveURL(/#\/char\/\d+/)
  const lista = await (await apiRequest.get('/characters')).json()
  const trovati = lista.filter((c: { name: string }) => c.name === nome)
  expect(trovati).toHaveLength(1)
  for (const c of trovati) await apiRequest.delete(`/characters/${c.id}`)
})
