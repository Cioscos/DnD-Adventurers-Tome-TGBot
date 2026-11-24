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
