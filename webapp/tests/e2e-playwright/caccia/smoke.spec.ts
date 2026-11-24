import { expect, test, UTENTE } from './fixtures'

// caccia: {"id": "CB-001", "fonte": "CLAUDE.md · API: scheda personaggio salvata nel database", "zona": "flusso:identità-impostazioni", "voce": "persistenza", "copre": ["route:/char/:id"]}
test('il personaggio resta dopo il ricaricamento', async ({ comeUtente, charId }) => {
  const page = await comeUtente(UTENTE)
  await page.goto(`/?dev_user=${UTENTE}#/char/${charId}`)
  await expect(page.getByText('Eroe di prova').first()).toBeVisible()
  await page.reload()
  await expect(page.getByText('Eroe di prova').first()).toBeVisible()
})

// caccia: {"id": "CB-002", "fonte": "CLAUDE.md · API: ownership check", "zona": "flusso:identità-impostazioni", "voce": "permessi", "copre": ["GET /characters/{char_id}"]}
test('un altro utente non vede il personaggio', async ({ comeUtente, charId }) => {
  const page = await comeUtente(9002)
  const risposta = page.waitForResponse((r) => new URL(r.url()).pathname === `/characters/${charId}`)
  await page.goto(`/?dev_user=9002&x=1#/char/${charId}`)
  expect([403, 404]).toContain((await risposta).status())
  await expect(page.getByText('Eroe di prova')).toHaveCount(0)
})
