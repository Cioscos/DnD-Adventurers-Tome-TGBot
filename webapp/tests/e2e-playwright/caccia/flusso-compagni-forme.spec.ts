import { expect, test, UTENTE } from './fixtures'

// caccia: {"id": "CB-363", "fonte": "invariante: un doppio tocco su Attiva forma spende un solo uso di Forma Selvatica", "zona": "flusso:compagni-forme", "voce": "ripetizione", "copre": ["route:/char/:id/extras"]}
test('il doppio tocco su Attiva forma spende un solo uso', async ({ comeUtente, apiRequest }) => {
  const c = await apiRequest.post('/characters', { data: { name: 'Druido doppio tocco', initial_class: { class_name: 'druid', level: 4 } } })
  expect(c.ok()).toBeTruthy()
  const { id } = await c.json()
  const f = await apiRequest.post(`/characters/${id}/companions`, {
    data: { kind: 'wild_shape', name: 'Lupo', max_hp: 11, armor_class: 13, statblock: { type: 'beast', challenge_rating: 0.25, speed: { walk_ft: 40 }, actions: [] } },
  })
  expect(f.ok()).toBeTruthy()
  const page = await comeUtente(UTENTE)
  await page.goto(`/?dev_user=${UTENTE}#/char/${id}/extras`)
  await page.getByRole('button', { name: /Attiva forma/ }).dblclick()
  await expect(page.getByRole('button', { name: 'Termina forma' })).toBeVisible()
  const pg = await (await apiRequest.get(`/characters/${id}`)).json()
  expect(pg.abilities.find((a: { feature_key: string }) => a.feature_key === 'druid.wild_shape').uses).toBe(1)
  await apiRequest.delete(`/characters/${id}`)
})

// caccia: {"id": "CB-364", "fonte": "invariante: eliminare una forma attiva la chiude e non lascia la scheda del personaggio in forma", "zona": "flusso:compagni-forme", "voce": "annullamento", "copre": ["route:/char/:id/extras"]}
test('eliminare la forma attiva dalla pagina Extra chiude anche la forma sul personaggio', async ({ comeUtente, apiRequest }) => {
  const c = await apiRequest.post('/characters', { data: { name: 'Druido elimina forma', initial_class: { class_name: 'druid', level: 4 } } })
  const { id } = await c.json()
  const f = await apiRequest.post(`/characters/${id}/companions`, {
    data: { kind: 'wild_shape', name: 'Lupo', max_hp: 11, armor_class: 13, statblock: { type: 'beast', challenge_rating: 0.25, speed: { walk_ft: 40 }, actions: [] } },
  })
  const { id: formId } = await f.json()
  expect((await apiRequest.post(`/characters/${id}/companions/${formId}/activate`, { data: {} })).ok()).toBeTruthy()
  const page = await comeUtente(UTENTE)
  await page.goto(`/?dev_user=${UTENTE}#/char/${id}/extras`)
  await page.getByRole('button', { name: 'Elimina' }).click()
  await page.getByRole('button', { name: 'Elimina' }).last().click()
  await expect(page.getByText('Lupo')).toHaveCount(0)
  const pg = await (await apiRequest.get(`/characters/${id}`)).json()
  expect(pg.active_form).toBeNull()
  await apiRequest.delete(`/characters/${id}`)
})
