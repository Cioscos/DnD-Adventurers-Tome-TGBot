import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'

const sumLongMs = (m) => Math.round(m.longTasks.reduce((s, t) => s + t.durMs, 0) * 100) / 100

export function renderMarkdown(meta, results) {
  const lines = [
    `# Perf run — ${meta.label}`,
    '',
    `- **Data:** ${meta.date}`,
    `- **Modalità:** ${meta.mode}`,
    `- **Viewport:** ${meta.viewport.width}×${meta.viewport.height}`,
    '',
    '| Scenario | Long task | Long task tot (ms) | FPS medi | Dropped est. (%) | Paint full-screen | Script (ms) | Layout (ms) | Paint (ms) |',
    '|---|---|---|---|---|---|---|---|---|',
  ]
  for (const r of results) {
    const m = r.metrics
    lines.push(
      `| ${r.title} | ${m.longTasks.length} | ${sumLongMs(m)} | ${m.frames.avgFps} | ${m.frames.droppedPctEst} | ${m.fullScreenPaints} | ${m.buckets.scriptMs} | ${m.buckets.layoutMs} | ${m.buckets.paintMs} |`,
    )
  }
  for (const r of results) {
    if (r.metrics.longTasks.length === 0) continue
    lines.push('', `## ${r.title} — long task`, '', '| inizio (ms) | durata (ms) | causa |', '|---|---|---|')
    for (const t of r.metrics.longTasks) {
      lines.push(`| ${t.startMs} | ${t.durMs} | ${t.culprit} |`)
    }
  }
  return lines.join('\n') + '\n'
}

export function renderComparison(baseline, current) {
  const lines = [`# Confronto: ${baseline.meta.label} → ${current.meta.label}`, '']
  const baseById = new Map(baseline.results.map((r) => [r.scenarioId, r]))
  const seen = new Set()
  for (const cur of current.results) {
    seen.add(cur.scenarioId)
    const base = baseById.get(cur.scenarioId)
    if (!base) {
      lines.push(`- ⚠️ Scenario \`${cur.scenarioId}\` senza corrispettivo nella baseline`)
      continue
    }
    const b = base.metrics
    const c = cur.metrics
    lines.push(
      `## ${cur.title}`,
      '',
      `| Metrica | ${baseline.meta.label} | ${current.meta.label} |`,
      '|---|---|---|',
      `| Long task | ${b.longTasks.length} | ${c.longTasks.length} |`,
      `| Long task tot (ms) | ${sumLongMs(b)} | ${sumLongMs(c)} |`,
      `| FPS medi | ${b.frames.avgFps} | ${c.frames.avgFps} |`,
      `| Dropped est. (%) | ${b.frames.droppedPctEst} | ${c.frames.droppedPctEst} |`,
      `| Paint full-screen | ${b.fullScreenPaints} | ${c.fullScreenPaints} |`,
      '',
    )
  }
  for (const base of baseline.results) {
    if (!seen.has(base.scenarioId)) {
      lines.push(`- ⚠️ Scenario \`${base.scenarioId}\` senza corrispettivo nel run corrente`)
    }
  }
  return lines.join('\n') + '\n'
}

export async function createRunDir(resultsRoot, label) {
  const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
  const dir = path.join(resultsRoot, `${label}-${stamp}`)
  await mkdir(dir, { recursive: true })
  return dir
}

export async function writeRun(dir, meta, results) {
  await writeFile(path.join(dir, 'run.json'), JSON.stringify({ meta, results }, null, 2))
  await writeFile(path.join(dir, 'report.md'), renderMarkdown(meta, results))
}
