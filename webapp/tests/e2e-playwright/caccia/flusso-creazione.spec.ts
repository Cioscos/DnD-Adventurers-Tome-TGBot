import { expect, test, UTENTE } from './fixtures'

// caccia: {"id": "CB-655", "fonte": "invariante: una richiesta ripetuta non crea due volte (doppio tocco su Crea)", "zona": "flusso:creazione", "voce": "ripetizione", "copre": ["route:/"]}
test('il doppio tocco su Crea crea un solo personaggio', async ({ comeUtente, apiRequest }) => {
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
  await page.getByRole('button', { name: 'Avanti →' }).click() // background facoltativo
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


// caccia: {"id": "CB-1392", "fonte": "invariante: un wizard chiuso senza creare non lascia scelte al successivo (monete al posto dell'equipaggiamento)", "zona": "flusso:creazione", "voce": "annullamento", "copre": ["route:/"]}
test.fail('chiudere il wizard con le monete accese e riaprirlo con la stessa classe le spegne', async ({ comeUtente }) => {
  const page = await comeUtente(UTENTE)
  await page.goto(`/?dev_user=${UTENTE}`)
  const monete = page.getByRole('button', { name: /Monete al posto dell'equipaggiamento/ })
  await page.getByRole('button', { name: 'Nuovo personaggio' }).click()
  await page.getByPlaceholder('Il nome del tuo eroe').fill('Annullato')
  await page.getByRole('button', { name: 'Avanti →' }).click()
  await page.getByRole('button', { name: 'Avanti →' }).click() // background facoltativo
  await page.getByText('Guerriero', { exact: true }).click()
  await page.getByRole('button', { name: 'Atletica' }).click()
  await page.getByRole('button', { name: 'Percezione' }).click()
  await page.getByRole('button', { name: 'Avanti →' }).click() // classe -> specie
  await page.getByRole('button', { name: 'Avanti →' }).click() // specie -> punteggi
  await page.getByText('Salta: lascia tutti a 10').click()
  await monete.click()
  for (let n = 0; n < 5; n++) await page.getByRole('button', { name: 'Indietro' }).click() // fino al nome
  await page.getByRole('button', { name: 'Annulla' }).click()
  await page.getByRole('button', { name: 'Nuovo personaggio' }).click()
  await page.getByPlaceholder('Il nome del tuo eroe').fill('Riaperto')
  await page.getByRole('button', { name: 'Avanti →' }).click()
  await page.getByRole('button', { name: 'Avanti →' }).click()
  await page.getByText('Guerriero', { exact: true }).click()
  await page.getByRole('button', { name: 'Atletica' }).click()
  await page.getByRole('button', { name: 'Percezione' }).click()
  await page.getByRole('button', { name: 'Avanti →' }).click()
  await page.getByRole('button', { name: 'Avanti →' }).click()
  await page.getByText('Salta: lascia tutti a 10').click()
  await expect(monete).toBeVisible()
  await expect(monete).not.toHaveClass(/dnd-gold/)
})
