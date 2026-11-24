import { expect, test, UTENTE } from './fixtures'

// caccia: {"id": "CB-467", "fonte": "comportamento dichiarato in CLAUDE.md: lo stato della concentrazione è sul server e sopravvive al ricaricamento", "zona": "flusso:concentrazione", "voce": "persistenza", "copre": ["route:/char/:id/spells"]}
test('la concentrazione avviata dal lancio resta dopo il ricaricamento', async ({ comeUtente, apiRequest, charId }) => {
  await apiRequest.post(`/characters/${charId}/classes`, { data: { class_name: 'bard', level: 5, hit_die: 8 } })
  const sp = await apiRequest.post(`/characters/${charId}/spells`, {
    data: { name: 'Benedizione', level: 1, is_concentration: true, duration: 'Concentration, up to 1 minute', is_prepared: true },
  })
  const { id } = await sp.json()
  const uso = await apiRequest.post(`/characters/${charId}/spells/${id}/use`, { data: { slot_level: 1 } })
  expect(uso.ok()).toBeTruthy()
  const stato = await (await apiRequest.get(`/characters/${charId}`)).json()
  expect(stato.concentrating_spell_id).toBe(id)
  const page = await comeUtente(UTENTE)
  await page.goto(`/?dev_user=${UTENTE}#/char/${charId}/spells`)
  await expect(page.getByRole('button', { name: 'Interrompi concentrazione' }).first()).toBeVisible()
  await page.reload()
  await expect(page.getByRole('button', { name: 'Interrompi concentrazione' }).first()).toBeVisible()
})

// caccia: {"id": "CB-1203", "fonte": "comportamento dichiarato nel codice: l'incantesimo in concentrazione resta visibile nel turno (U15), anche se viene da un oggetto", "zona": "flusso:concentrazione", "voce": "interazione", "copre": ["route:/char/:id/turn"]}
test.fail('la concentrazione da incantesimo di oggetto è visibile nella pagina del turno', async ({ comeUtente, apiRequest, charId }) => {
  const spell = { name: 'Raggio Fantasma', level: 2, charges_cost: 1, is_concentration: true, duration: 'Concentration, up to 1 minute' }
  const it = await apiRequest.post(`/characters/${charId}/items`, {
    data: { name: 'Bacchetta', item_type: 'accessory', item_metadata: { charges: { current: 3, max: 3 }, granted_spells: [spell] } },
  })
  expect(it.ok()).toBeTruthy()
  const items = await (await apiRequest.get(`/characters/${charId}/items`)).json()
  const iid = items.find((i: { name: string }) => i.name === 'Bacchetta').id
  const uso = await apiRequest.post(`/characters/${charId}/items/${iid}/cast`, { data: { spell_index: 0 } })
  expect(uso.ok()).toBeTruthy()
  const page = await comeUtente(UTENTE)
  await page.goto(`/?dev_user=${UTENTE}#/char/${charId}/turn`)
  await expect(page.getByTestId('turn-concentration')).toContainText('Raggio Fantasma')
})
