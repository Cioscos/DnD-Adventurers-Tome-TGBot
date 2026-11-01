/**
 * Scenari automatici dell'harness perf. REGOLA: solo lettura — aprire, chiudere,
 * navigare, scorrere. Mai tiri, salvataggi o toggle: gira sui dati reali.
 * Gli sheet si chiudono con Escape (useOverlayDismiss), senza toccare i form.
 *
 * Ogni scenario: { id, title, run(ctx) } con ctx = { page, settle, go(hash), charId(), swipe(dx) }.
 * Le etichette sono it|en: se cambiano in it.json/en.json vanno aggiornate qui.
 */

const HELP = /^(Guida della pagina|Page guide)$/
const HP = /^(Punti Ferita|Hit Points)$/
const ADD_ITEM = /^(Aggiungi oggetto|Add item)$/
const ANIM_MS = 700 // > durata d'ingresso/uscita di Sheet (spring + blur rinviato)

/** Apre lo sheet col pulsante `name` e lo richiude con Escape, `times` volte. */
async function toggleSheet(page, name, times = 5) {
  for (let i = 0; i < times; i++) {
    await page.getByRole('button', { name }).first().click({ timeout: 5000 })
    await page.waitForTimeout(ANIM_MS)
    await page.keyboard.press('Escape')
    await page.waitForTimeout(ANIM_MS)
  }
}

/** Scorre la pagina fino in fondo a passi da 300 px e torna su. */
async function scrollList(page) {
  const max = await page.evaluate(() => document.scrollingElement.scrollHeight - innerHeight)
  for (let y = 0; y < max; y += 300) {
    await page.mouse.wheel(0, 300)
    await page.waitForTimeout(100)
  }
  for (let y = max; y > 0; y -= 300) {
    await page.mouse.wheel(0, -300)
    await page.waitForTimeout(100)
  }
}

// Ogni scenario (tranne idle-home) prepara la pagina con `go` PRIMA del gesto:
// il caricamento finisce nella misura, ma pesa poco rispetto alle ripetizioni.
export const scenarios = [
  {
    id: 'idle-home',
    title: 'Home ferma (5 s)',
    run: async ({ page, go }) => {
      await go('#/')
      await page.waitForTimeout(5000)
    },
  },
  {
    id: 'help-sheet-hub',
    title: 'Guida "?" sull\'hub ×5',
    run: async ({ page, go, charId }) => {
      await go(`#/char/${await charId()}`)
      await toggleSheet(page, HELP)
    },
  },
  {
    id: 'help-sheet-page',
    title: 'Guida "?" su Incantesimi ×5',
    run: async ({ page, go, charId }) => {
      await go(`#/char/${await charId()}/spells`)
      await toggleSheet(page, HELP)
    },
  },
  {
    id: 'hp-sheet-hub',
    title: 'Sheet rapido PF sull\'hub ×5',
    run: async ({ page, go, charId }) => {
      await go(`#/char/${await charId()}`)
      await toggleSheet(page, HP)
    },
  },
  {
    id: 'add-item-sheet',
    title: 'Sheet "Aggiungi oggetto" ×5 (senza salvare)',
    run: async ({ page, go, charId }) => {
      await go(`#/char/${await charId()}/inventory`)
      await toggleSheet(page, ADD_ITEM)
    },
  },
  {
    id: 'hub-swipe',
    title: 'Swipe fra le 3 schermate dell\'hub',
    run: async ({ page, go, charId, swipe }) => {
      await go(`#/char/${await charId()}`)
      const w = await page.evaluate(() => innerWidth)
      for (let round = 0; round < 2; round++) {
        for (const dx of [-0.6 * w, -0.6 * w, 0.6 * w, 0.6 * w]) {
          await swipe(dx)
          await page.waitForTimeout(ANIM_MS)
        }
      }
    },
  },
  {
    id: 'nav',
    title: 'Navigazione hub → 5 pagine',
    run: async ({ page, go, charId }) => {
      const id = await charId()
      for (const sub of ['spells', 'inventory', 'skills', 'hp', 'notes']) {
        await go(`#/char/${id}/${sub}`)
        await page.waitForTimeout(ANIM_MS)
        await go(`#/char/${id}`)
        await page.waitForTimeout(ANIM_MS)
      }
    },
  },
  {
    id: 'scroll-spells',
    title: 'Scroll lista incantesimi',
    run: async ({ page, go, charId }) => {
      await go(`#/char/${await charId()}/spells`)
      await scrollList(page)
    },
  },
  {
    id: 'scroll-inventory',
    title: 'Scroll inventario',
    run: async ({ page, go, charId }) => {
      await go(`#/char/${await charId()}/inventory`)
      await scrollList(page)
    },
  },
]
