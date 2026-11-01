import { pathToFileURL, fileURLToPath } from 'node:url'
import { parseArgs, promisify } from 'node:util'
import { execFile } from 'node:child_process'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { scenarios } from './scenarios.mjs'

const JANK_MS = 33
const r1 = (n) => Math.round(n * 10) / 10

// ── Funzioni pure (testate in run.test.mjs) ────────────────────────────────

/** Statistiche sugli intervalli fra timestamp rAF consecutivi. */
export function frameStats(timestamps) {
  const d = []
  for (let i = 1; i < timestamps.length; i++) d.push(timestamps[i] - timestamps[i - 1])
  if (d.length === 0) return { frames: 0, p50Ms: 0, p95Ms: 0, maxMs: 0, jankFrames: 0 }
  const s = [...d].sort((a, b) => a - b)
  const pct = (p) => s[Math.ceil(p * s.length) - 1]
  return {
    frames: d.length,
    p50Ms: r1(pct(0.5)),
    p95Ms: r1(pct(0.95)),
    maxMs: r1(s[s.length - 1]),
    jankFrames: d.filter((x) => x > JANK_MS).length,
  }
}

/** Riassume le entry `long-animation-frame`; `null` = API non supportata. */
export function summarizeLoaf(entries) {
  if (!entries) return { supported: false }
  const worst = [...entries]
    .sort((a, b) => b.duration - a.duration)
    .slice(0, 3)
    .map((e) => ({
      durationMs: r1(e.duration),
      blockingMs: r1(e.blockingDuration),
      styleLayoutMs: e.styleAndLayoutStart ? r1(e.startTime + e.duration - e.styleAndLayoutStart) : 0,
      scripts: e.scripts.map((s) => ({ src: s.sourceURL, invoker: s.invoker, durationMs: r1(s.duration) })),
    }))
  return {
    supported: true,
    count: entries.length,
    totalMs: r1(entries.reduce((t, e) => t + e.duration, 0)),
    worst,
  }
}

/** Primo serial adb che espone una WebView in debug. */
export async function pickDevice(serials, hasWebView) {
  for (const s of serials) if (await hasWebView(s)) return s
  throw new Error(
    'Nessuna WebView in debug trovata. Verifica: adb connesso (`adb devices`), ' +
      '"Enable WebView Debug" attivo in Telegram (poi chiudi e riapri Telegram), Mini App aperta.',
  )
}

const loafCells = (l) =>
  l.supported ? `${l.count} | ${l.totalMs}` : 'n/d | n/d'

export function renderReport(meta, results) {
  const lines = [
    `# Perf run — ${meta.label}`,
    '',
    `- **Data:** ${meta.date}`,
    `- **Modalità:** ${meta.mode}`,
    `- **Viewport:** ${meta.viewport.width}×${meta.viewport.height}`,
    '',
    `Frame: intervalli fra requestAnimationFrame durante il gesto. Scatti = frame > ${JANK_MS} ms.`,
    'LoAF: frame bloccati > 50 ms (long-animation-frame), con lo script responsabile.',
    '',
    '| Scenario | Frame | p50 (ms) | p95 (ms) | max (ms) | Scatti | LoAF | LoAF tot (ms) |',
    '|---|---|---|---|---|---|---|---|',
  ]
  for (const r of results) {
    if (r.error) {
      lines.push(`| ${r.title} | ERRORE: ${r.error} | | | | | | |`)
      continue
    }
    const f = r.frames
    lines.push(
      `| ${r.title} | ${f.frames} | ${f.p50Ms} | ${f.p95Ms} | ${f.maxMs} | ${f.jankFrames} | ${loafCells(r.loaf)} |`,
    )
  }
  for (const r of results) {
    if (r.error || !r.loaf.supported || r.loaf.worst.length === 0) continue
    lines.push('', `## ${r.title} — frame bloccati peggiori`, '')
    for (const w of r.loaf.worst) {
      lines.push(`- **${w.durationMs} ms** (bloccante ${w.blockingMs}, stile+layout ${w.styleLayoutMs})`)
      for (const s of w.scripts) lines.push(`  - ${s.durationMs} ms · ${s.invoker} · ${s.src}`)
    }
  }
  return lines.join('\n') + '\n'
}

export function renderComparison(base, cur) {
  const a = base.meta.label
  const b = cur.meta.label
  const lines = [
    `# Confronto: ${a} → ${b}`,
    '',
    `| Scenario | p95 ${a} | p95 ${b} | Scatti ${a} | Scatti ${b} | LoAF tot ${a} | LoAF tot ${b} |`,
    '|---|---|---|---|---|---|---|',
  ]
  const byId = new Map(base.results.map((r) => [r.id, r]))
  const cell = (r, k) => (r.error ? 'ERR' : r.frames[k])
  const loafTot = (r) => (r.error || !r.loaf.supported ? 'n/d' : r.loaf.totalMs)
  for (const c of cur.results) {
    const p = byId.get(c.id)
    if (!p) continue
    lines.push(
      `| ${c.title} | ${cell(p, 'p95Ms')} | ${cell(c, 'p95Ms')} | ${cell(p, 'jankFrames')} | ${cell(c, 'jankFrames')} | ${loafTot(p)} | ${loafTot(c)} |`,
    )
  }
  const curIds = new Set(cur.results.map((r) => r.id))
  for (const r of base.results) if (!curIds.has(r.id)) lines.push(`- ⚠️ \`${r.id}\` solo in ${a}`)
  for (const r of cur.results) if (!byId.has(r.id)) lines.push(`- ⚠️ \`${r.id}\` solo in ${b}`)
  return lines.join('\n') + '\n'
}

// ── Device / sessione ───────────────────────────────────────────────────────

const RESULTS_ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), 'results')
const APP_URL = /cioscos\.github\.io|localhost|127\.0\.0\.1/
const CDP_PORT = 9222
const exec = promisify(execFile)
// Import pigro: i test (vitest) importano solo le funzioni pure senza caricare Playwright.
const chromium = async () => (await import('@playwright/test')).chromium
const adb = async (...args) => (await exec('adb', args)).stdout

async function webviewSockets(serial) {
  const out = await adb('-s', serial, 'shell', 'cat /proc/net/unix')
  return [...new Set(out.match(/webview_devtools_remote_\d+/g) ?? [])]
}

async function connectDevice() {
  const serials = (await adb('devices'))
    .split('\n')
    .slice(1)
    .map((l) => l.trim().split(/\s+/))
    .filter(([, state]) => state === 'device')
    .map(([s]) => s)
  const serial = await pickDevice(serials, async (s) => (await webviewSockets(s)).length > 0)
  const sockets = await webviewSockets(serial)
  // Più WebView in debug: si prova dall'ultima (la più recente) finché una ospita la Mini App.
  for (const socket of sockets.reverse()) {
    await adb('-s', serial, 'forward', `tcp:${CDP_PORT}`, `localabstract:${socket}`)
    const browser = await (await chromium())
      .connectOverCDP(`http://127.0.0.1:${CDP_PORT}`, { timeout: 10_000 })
      .catch(() => null)
    // WebView congelata (telefono bloccato / Telegram in background) o morta: prossimo socket.
    if (!browser) continue
    const page = browser.contexts().flatMap((c) => c.pages()).find((p) => APP_URL.test(p.url()))
    if (page) return { browser, page, label: `${serial} · ${socket}` }
    await browser.close()
  }
  throw new Error(
    'WebView trovata ma non risponde o non ospita la Mini App: sblocca il telefono, ' +
      'tieni la Mini App aperta in primo piano e riprova.',
  )
}

async function launchLocal(url, throttle) {
  if (!url) throw new Error('--mode local richiede --url (es. http://localhost:5173)')
  const browser = await (await chromium()).launch({ channel: 'chrome' }) // Chrome installato: niente download dei browser Playwright
  const context = await browser.newContext({
    viewport: { width: 375, height: 667 },
    isMobile: true,
    hasTouch: true,
    deviceScaleFactor: 2,
  })
  const page = await context.newPage()
  const cdp = await context.newCDPSession(page)
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: throttle })
  await page.goto(url)
  return { browser, page, label: `locale ${url} · CPU ${throttle}x` }
}

// ── Misura ──────────────────────────────────────────────────────────────────

/** Installa in pagina il campionatore rAF + observer LoAF (window.__perf). */
function installMeter() {
  const st = { ts: [], loaf: null, on: true }
  const loop = (t) => {
    if (!st.on) return
    st.ts.push(t)
    requestAnimationFrame(loop)
  }
  requestAnimationFrame(loop)
  let obs
  const push = (list) => {
    for (const e of list) {
      st.loaf.push({
        startTime: e.startTime,
        duration: e.duration,
        blockingDuration: e.blockingDuration,
        styleAndLayoutStart: e.styleAndLayoutStart,
        scripts: e.scripts.map((s) => ({ sourceURL: s.sourceURL, invoker: s.invoker, duration: s.duration })),
      })
    }
  }
  if (PerformanceObserver.supportedEntryTypes?.includes('long-animation-frame')) {
    st.loaf = []
    obs = new PerformanceObserver((l) => push(l.getEntries()))
    obs.observe({ type: 'long-animation-frame' })
  }
  st.stop = () => {
    st.on = false
    if (obs) {
      push(obs.takeRecords())
      obs.disconnect()
    }
    return { ts: st.ts, loaf: st.loaf }
  }
  window.__perf = st
}

const TRACE_CATEGORIES = [
  '-*',
  'devtools.timeline',
  'disabled-by-default-devtools.timeline',
  'disabled-by-default-devtools.timeline.frame',
  'blink.user_timing',
]

async function startTrace(page) {
  const cdp = await page.context().newCDPSession(page)
  await cdp.send('Tracing.start', {
    traceConfig: { includedCategories: TRACE_CATEGORIES },
    transferMode: 'ReturnAsStream',
  })
  return cdp
}

/** Ferma la trace e restituisce il JSON grezzo (si apre così com'è in DevTools → Performance). */
async function stopTrace(cdp) {
  try {
    return await readTrace(cdp)
  } finally {
    // Sempre: una sessione lasciata attaccata terrebbe il tracing acceso e romperebbe gli scenari successivi.
    await cdp.detach().catch(() => {})
  }
}

async function readTrace(cdp) {
  const done = new Promise((resolve) => cdp.once('Tracing.tracingComplete', resolve))
  await cdp.send('Tracing.end')
  const { stream } = await done
  const chunks = []
  for (;;) {
    const { data, base64Encoded, eof } = await cdp.send('IO.read', { handle: stream })
    chunks.push(base64Encoded ? Buffer.from(data, 'base64').toString('utf8') : data)
    if (eof) break
  }
  await cdp.send('IO.close', { handle: stream })
  return chunks.join('')
}

/** Helper passati agli scenari. Solo lettura: niente che modifichi i dati. */
function makeCtx(page) {
  // Set e non contatore: le richieste partite prima dell'aggancio lo manderebbero sotto zero.
  const inflight = new Set()
  let cachedId = ''
  page.on('request', (r) => inflight.add(r))
  page.on('requestfinished', (r) => inflight.delete(r))
  page.on('requestfailed', (r) => inflight.delete(r))

  const settle = async (quietMs = 500, maxMs = 5000) => {
    const end = Date.now() + maxMs
    let quietSince = Date.now()
    while (Date.now() < end) {
      if (inflight.size > 0) quietSince = Date.now()
      else if (Date.now() - quietSince >= quietMs) return
      await page.waitForTimeout(50)
    }
  }

  return {
    page,
    settle,
    go: async (hash) => {
      await page.evaluate((h) => (location.hash = h), hash)
      await settle()
    },
    charId: async () => {
      if (cachedId) return cachedId
      const id = await page.evaluate(() => {
        const m = location.hash.match(/#\/char\/(\d+)/)
        if (m) return m[1]
        try {
          return String(JSON.parse(localStorage.getItem('dnd-character-store')).state.lastCharId ?? '')
        } catch {
          return ''
        }
      })
      if (!id) throw new Error('Nessun personaggio: apri un personaggio nella Mini App e riprova.')
      return (cachedId = id)
    },
    swipe: async (dx) => {
      const cdp = await page.context().newCDPSession(page)
      const { w, h } = await page.evaluate(() => ({ w: innerWidth, h: innerHeight }))
      const x0 = w / 2 - dx / 2
      const y = h / 2
      const touch = (type, x) =>
        cdp.send('Input.dispatchTouchEvent', { type, touchPoints: type === 'touchEnd' ? [] : [{ x, y }] })
      await touch('touchStart', x0)
      for (let i = 1; i <= 10; i++) {
        await touch('touchMove', x0 + (dx * i) / 10)
        await page.waitForTimeout(16)
      }
      await touch('touchEnd', x0 + dx)
      await cdp.detach()
    },
  }
}

async function measure(dir, ctx, scenario) {
  const { page } = ctx
  const base = { id: scenario.id, title: scenario.title }
  let cdp
  let error
  try {
    cdp = await startTrace(page)
    await page.evaluate(installMeter)
    await scenario.run(ctx)
  } catch (err) {
    error = err
  }
  // Misuratore fermato PRIMA della trace: chiuderla (stream via adb) blocca il renderer e sporcherebbe i frame.
  const data = await page.evaluate(() => window.__perf?.stop()).catch(() => null)
  if (cdp) {
    try {
      await writeFile(path.join(dir, `${scenario.id}.trace.json`), await stopTrace(cdp))
    } catch (err) {
      error ??= new Error(`trace: ${err.message ?? err}`)
    }
  }
  if (error || !data) {
    return { ...base, error: String(error?.message ?? error ?? 'misuratore assente').split('\n')[0] }
  }
  return { ...base, frames: frameStats(data.ts), loaf: summarizeLoaf(data.loaf) }
}

// ── CLI ─────────────────────────────────────────────────────────────────────

async function main() {
  const { values, positionals } = parseArgs({
    options: {
      mode: { type: 'string', default: 'device' },
      label: { type: 'string', default: 'run' },
      scenario: { type: 'string', multiple: true },
      url: { type: 'string' },
      throttle: { type: 'string', default: '6' },
      compare: { type: 'boolean', default: false },
    },
    allowPositionals: true,
  })

  if (values.compare) {
    const [a, b] = positionals
    if (!a || !b) throw new Error('Uso: node scripts/perf/run.mjs --compare <dirBase> <dirCorrente>')
    const load = async (d) => JSON.parse(await readFile(path.join(d, 'run.json'), 'utf8'))
    const md = renderComparison(await load(a), await load(b))
    await writeFile(path.join(b, 'comparison.md'), md)
    console.log(md)
    return
  }

  const wanted = values.scenario?.length ? scenarios.filter((s) => values.scenario.includes(s.id)) : scenarios
  if (wanted.length === 0) throw new Error(`Nessuno scenario valido. Disponibili: ${scenarios.map((s) => s.id).join(', ')}`)

  const session =
    values.mode === 'local' ? await launchLocal(values.url, Number(values.throttle)) : await connectDevice()
  const { page } = session
  console.log(`✓ Collegato: ${session.label}\n  ${page.url()}`)

  const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
  const dir = path.join(RESULTS_ROOT, `${values.label}-${stamp}`)
  await mkdir(dir, { recursive: true })
  const viewport = await page.evaluate(() => ({ width: innerWidth, height: innerHeight }))
  const meta = { label: values.label, mode: values.mode, date: new Date().toISOString(), viewport }
  const results = []
  const ctx = makeCtx(page)
  // Id letto PRIMA degli scenari: idle-home naviga in home e l'URL lo perderebbe.
  await ctx.settle(1000, 15_000) // primo caricamento (dev server + CPU 6x è lento)
  await ctx.charId().catch(() => {})

  try {
    for (const s of wanted) {
      process.stdout.write(`▶ ${s.title}… `)
      const r = await measure(dir, ctx, s)
      results.push(r)
      console.log(r.error ? `ERRORE: ${r.error}` : `p95 ${r.frames.p95Ms} ms, scatti ${r.frames.jankFrames}`)
    }
  } finally {
    await writeFile(path.join(dir, 'run.json'), JSON.stringify({ meta, results }, null, 2))
    await writeFile(path.join(dir, 'report.md'), renderReport(meta, results))
    console.log(`\n✓ Report: ${path.join(dir, 'report.md')}`)
    // Device: close() stacca solo il CDP, la WebView resta aperta.
    await session.browser.close()
  }
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((err) => {
    console.error(err.message ?? err)
    process.exit(1)
  })
}
