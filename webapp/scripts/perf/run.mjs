#!/usr/bin/env node
import { parseArgs } from 'node:util'
import { writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import readline from 'node:readline/promises'
import { forwardDevtools } from './lib/adb.mjs'
import { connectDevice, launchLocal } from './lib/session.mjs'
import { startTracing, stopTracing } from './lib/tracing.mjs'
import { analyzeTrace } from './lib/metrics.mjs'
import { createRunDir, writeRun } from './lib/report.mjs'

const RESULTS_ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), 'results')

// Task 4 sposta il registry in scenarios.mjs; qui esiste solo lo smoke.
const SCENARIOS = [
  {
    id: 'smoke',
    title: 'Smoke (verifica harness)',
    instructions: 'Nessuna azione richiesta.',
    auto: async (page) => {
      await page.evaluate(() => window.scrollTo(0, 200))
      await page.waitForTimeout(3000)
    },
  },
]

async function main() {
  const { values } = parseArgs({
    options: {
      mode: { type: 'string', default: 'device' },
      label: { type: 'string', default: 'run' },
      scenario: { type: 'string', multiple: true },
      url: { type: 'string' },
      port: { type: 'string', default: '9222' },
      throttle: { type: 'string', default: '6' },
    },
  })

  const wanted = values.scenario?.length
    ? SCENARIOS.filter((s) => values.scenario.includes(s.id))
    : SCENARIOS
  if (wanted.length === 0) {
    console.error(`Nessuno scenario valido. Disponibili: ${SCENARIOS.map((s) => s.id).join(', ')}`)
    process.exit(1)
  }

  let session
  if (values.mode === 'device') {
    const { socket } = await forwardDevtools({ port: Number(values.port) })
    console.log(`✓ adb forward attivo su ${socket}`)
    session = await connectDevice({ port: Number(values.port) })
  } else {
    session = await launchLocal({ url: values.url, cpuThrottle: Number(values.throttle) })
  }
  console.log(`✓ Collegato a: ${session.page.url()}`)

  const viewport = await session.page.evaluate(() => ({
    width: window.innerWidth,
    height: window.innerHeight,
  }))

  const rl = readline.createInterface({ input: process.stdin, output: process.stdout })
  const dir = await createRunDir(RESULTS_ROOT, values.label)
  const results = []

  for (const s of wanted) {
    console.log(`\n▶ ${s.title}`)
    if (s.auto) {
      const cdp = await startTracing(session.page)
      await s.auto(session.page)
      const events = await stopTracing(cdp)
      results.push(await collect(dir, s, events, viewport))
    } else {
      console.log(`  ${s.instructions}`)
      await rl.question('  INVIO per AVVIARE la registrazione… ')
      const cdp = await startTracing(session.page)
      await rl.question('  Esegui ora il gesto, poi INVIO per FERMARE… ')
      const events = await stopTracing(cdp)
      results.push(await collect(dir, s, events, viewport))
    }
  }

  rl.close()
  const meta = {
    label: values.label,
    mode: values.mode,
    date: new Date().toISOString(),
    viewport,
  }
  await writeRun(dir, meta, results)
  console.log(`\n✓ Report scritto in ${dir}`)
  await session.close()
}

async function collect(dir, scenario, events, viewport) {
  await writeFile(path.join(dir, `${scenario.id}.trace.json`), JSON.stringify(events))
  const metrics = analyzeTrace(events, { viewport })
  console.log(
    `  → long task: ${metrics.longTasks.length}, fps: ${metrics.frames.avgFps}, full-screen paint: ${metrics.fullScreenPaints}`,
  )
  return { scenarioId: scenario.id, title: scenario.title, metrics }
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
