#!/usr/bin/env node
import { pathToFileURL } from 'node:url'

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

// ── CLI ─────────────────────────────────────────────────────────────────────

async function main() {}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((err) => {
    console.error(err.message ?? err)
    process.exit(1)
  })
}
