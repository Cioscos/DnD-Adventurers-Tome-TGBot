// Controllo di layout su telefono, contro il dev server (npm run dev + API locale).
//   npm run check:layout                      → tutte le route del personaggio 4
//   npm run check:layout -- /char/4/currency  → solo le route indicate
// Env: CHAR (id personaggio, default 4), BASE (default http://localhost:5173), SHOTS=dir per gli screenshot.
//      SETUP=file.mjs: modulo con `export default async (route, page, width)` che porta la pagina in uno stato (foglio aperto,
//      esito di un tiro...) prima del controllo. La route può portare una query (`/char/4/hp?stato=x`): il router la ignora.
//
// Segnala ciò che i test jsdom non vedono (nessun layout) e che è sfuggito sul telefono:
//  - SFORA: un elemento esce dal box del genitore (es. "Converti" oltre il bordo a 360px);
//  - ATTACCATI: due comandi di gruppi diversi a meno di 4px (es. tastierino incollato a Spendi/Ricevi);
//  - PICCOLO: area di tocco sotto 44×44 (anche contando ::before e i contenitori che danno il focus);
//  - COPERTO: a fine pagina un comando resta sotto il FAB dei dadi e non si può toccare.
// Gira a 360 e 412px (i telefoni Android più comuni) e in tema scuro (quello di Telegram).
import { chromium } from 'playwright'
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const CHAR = process.env.CHAR ?? '4'
const BASE = process.env.BASE ?? 'http://localhost:5173'
const C = `/char/${CHAR}`
const ALL = ['/', C, ...['hp', 'ac', 'turn', 'extras', 'stats', 'skills', 'saves', 'spells', 'slots',
  'inventory', 'currency', 'abilities', 'class', 'xp', 'conditions', 'history', 'notes', 'maps', 'dice',
  'dice/stats', 'identity', 'settings', 'homebrew', 'homebrew/new'].map((p) => `${C}/${p}`), '/session', '/session/join']
const routes = process.argv.slice(2).length ? process.argv.slice(2) : ALL
const WIDTHS = [360, 412]
const setup = process.env.SETUP ? (await import(pathToFileURL(resolve(process.env.SETUP)).href)).default : null

function audit() {
  const INTERACTIVE = 'button, a[href], [role=button], [role=tab], [role=switch], input:not([type=hidden]), select, textarea'
  // Esclusi: toast (transitori) ed eccezioni dichiarate nel codice con data-layout-ok="motivo".
  // Il FAB dei dadi è fisso e galleggia sopra il contenuto: non è un vicino di layout.
  const skip = (el) => !!el.closest('[data-sonner-toaster], [data-layout-ok], .fixed')
  const visible = (el) => {
    if (skip(el)) return false
    const r = el.getBoundingClientRect(); const cs = getComputedStyle(el)
    return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.opacity !== '0'
  }
  const label = (el) => (el.getAttribute('aria-label') || el.textContent || el.getAttribute('placeholder') || el.tagName)
    .trim().replace(/\s+/g, ' ').slice(0, 30)
  const out = []

  // SFORA: confronto col box del genitore; esclusi posizionati, contenitori a scorrimento e margini negativi voluti.
  for (const el of document.querySelectorAll('main *, header *')) {
    const parent = el.parentElement
    if (!parent || !visible(el)) continue
    const cs = getComputedStyle(el)
    // transform ≠ none: elemento ancora in animazione d'ingresso (le liste a cascata), non un layout rotto.
    if (cs.transform !== 'none' || cs.position === 'absolute' || cs.position === 'fixed' || parseFloat(cs.marginRight) < 0 || parseFloat(cs.marginLeft) < 0) continue
    if (/(auto|scroll)/.test(getComputedStyle(parent).overflowX) || getComputedStyle(parent).display === 'contents') continue
    const r = el.getBoundingClientRect(); const p = parent.getBoundingClientRect()
    const over = Math.max(r.right - p.right, p.left - r.left)
    if (over > 1) out.push(`SFORA +${Math.round(over)}px  <${el.tagName.toLowerCase()}> ${label(el)}`)
  }

  const targets = [...document.querySelectorAll(INTERACTIVE)].filter(visible)
  for (const el of targets) {
    let { width: w, height: h } = el.getBoundingClientRect()
    const b = getComputedStyle(el, '::before')
    if (b.content !== 'none' && b.position === 'absolute') {
      w = Math.max(w, parseFloat(b.minWidth) || 0, parseFloat(b.width) || 0)
      h = Math.max(h, parseFloat(b.minHeight) || 0, parseFloat(b.height) || 0)
    }
    if (el.tagName === 'INPUT' && el.parentElement?.getBoundingClientRect().height >= 44) h = Math.max(h, 44)
    if (el.matches('input[type=checkbox],input[type=radio]') && el.closest('label')) {
      const l = el.closest('label').getBoundingClientRect(); w = Math.max(w, l.width); h = Math.max(h, l.height)
    }
    if (Math.round(w) < 44 || Math.round(h) < 44) out.push(`PICCOLO ${Math.round(w)}x${Math.round(h)}  <${el.tagName.toLowerCase()}> ${label(el)}`)
  }

  // ATTACCATI: comandi con genitori diversi (gruppi diversi) che si sovrappongono su un asse e distano < 4px sull'altro.
  for (let i = 0; i < targets.length; i++) {
    for (let j = i + 1; j < targets.length; j++) {
      const a = targets[i], b = targets[j]
      if (a.parentElement === b.parentElement || a.contains(b) || b.contains(a)) continue
      const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect()
      const overlapX = Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left)
      const overlapY = Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top)
      const gapY = Math.max(rb.top - ra.bottom, ra.top - rb.bottom)
      const gapX = Math.max(rb.left - ra.right, ra.left - rb.right)
      const gap = overlapX > 8 ? gapY : overlapY > 8 ? gapX : Infinity
      if (gap >= 0 && gap < 4) out.push(`ATTACCATI ${Math.round(gap)}px  "${label(a)}" ↔ "${label(b)}"`)
    }
  }
  return [...new Set(out)]
}

// COPERTO: il FAB dei dadi galleggia sulle liste e copre per forza qualcosa durante lo
// scorrimento; è un difetto solo se a fine pagina un comando resta sotto e non si può più toccare.
async function coveredAtEnd(page) {
  await page.evaluate(() => {
    // Inset come in Telegram a schermo intero: il FAB si alza di tanto, e fuori da Telegram varrebbe 0.
    document.documentElement.style.setProperty('--tg-content-bottom', '74px')
    for (const el of document.querySelectorAll('*')) {
      if (/(auto|scroll)/.test(getComputedStyle(el).overflowY) && el.scrollHeight > el.clientHeight) el.scrollTop = el.scrollHeight
    }
  })
  await page.waitForTimeout(300)
  return page.evaluate(() => {
    const fab = document.querySelector('.bottom-safe-fab')?.getBoundingClientRect()
    if (!fab) return []
    const out = []
    for (const el of document.querySelectorAll('button, a[href], [role=button], [role=tab], [role=switch], input:not([type=hidden]), select, textarea')) {
      if (el.closest('.fixed, .bottom-safe-fab, [data-sonner-toaster], [data-layout-ok]')) continue
      const r = el.getBoundingClientRect()
      if (r.width === 0 || r.height === 0) continue
      const x = Math.min(r.right, fab.right) - Math.max(r.left, fab.left)
      const y = Math.min(r.bottom, fab.bottom) - Math.max(r.top, fab.top)
      if (x > 8 && y > 8) out.push(`COPERTO ${Math.round(y)}px  "${(el.getAttribute('aria-label') || el.textContent || el.tagName).trim().replace(/\s+/g, ' ').slice(0, 30)}"`)
    }
    return out
  })
}

// Le altre due schermate dell'hub non hanno una route: ci si arriva col gesto.
async function swipeLeft(page, width) {
  await page.mouse.move(width - 20, 400)
  await page.mouse.down()
  await page.mouse.move(20, 400, { steps: 8 })
  await page.mouse.up()
  await page.waitForTimeout(600)
}

const browser = await chromium.launch({ channel: 'chrome' })
let problems = 0
for (const width of WIDTHS) {
  const ctx = await browser.newContext({ viewport: { width, height: 800 }, hasTouch: true, isMobile: true })
  const page = await ctx.newPage()
  for (const r of routes) {
    await page.goto(`${BASE}/#${r}`)
    await page.evaluate(() => document.documentElement.classList.remove('light'))
    await page.waitForTimeout(1500)
    if (setup) await setup(r, page, width)
    const found = await page.evaluate(audit)
    if (process.env.SHOTS) await page.screenshot({ path: `${process.env.SHOTS}/${width}${r.replace(/[/?=&]/g, '_')}.png`, fullPage: true })
    found.push(...await coveredAtEnd(page))
    if (r === C) {
      for (const screen of ['equipaggiamento', 'menu']) {
        await swipeLeft(page, width)
        found.push(...(await coveredAtEnd(page)).map((f) => `${f} (hub: ${screen})`))
      }
    }
    if (!found.length) continue
    problems += found.length
    console.log(`\n## ${width}px ${r}`)
    for (const f of found) console.log('  ' + f)
  }
  await ctx.close()
}
await browser.close()
console.log(problems ? `\n${problems} segnalazioni` : 'Nessuna segnalazione')
process.exitCode = problems ? 1 : 0
