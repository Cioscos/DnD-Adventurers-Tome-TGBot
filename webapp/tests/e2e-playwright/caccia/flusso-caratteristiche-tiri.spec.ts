import { expect, test, UTENTE } from './fixtures'

// caccia: {"id": "CB-993", "fonte": "invariante: la Maestria in uno strumento resta dopo il ricaricamento e sparisce se si toglie dal server", "zona": "flusso:caratteristiche-tiri", "voce": "persistenza", "copre": ["route:/char/:id/skills", "PATCH /characters/{char_id}"]}
test('la Maestria in uno strumento si vede dopo il ricaricamento e cambia col livello', async ({ comeUtente, apiRequest, charId }) => {
  await apiRequest.patch(`/characters/${charId}`, { data: { tool_proficiencies: { thieves_tools: 'expert' } } })
  const page = await comeUtente(UTENTE)
  await page.goto(`/?dev_user=${UTENTE}#/char/${charId}/skills`)
  await expect(page.getByRole('button', { name: /Maestria/ })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('button', { name: /Maestria/ })).toBeVisible()
  await apiRequest.patch(`/characters/${charId}`, { data: { tool_proficiencies: { thieves_tools: true } } })
  await page.reload()
  await expect(page.getByRole('button', { name: /Maestria/ })).toBeHidden()
})
