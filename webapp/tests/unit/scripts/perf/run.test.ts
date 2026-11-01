import { test } from 'vitest'
import assert from 'node:assert/strict'
// @ts-expect-error — modulo .mjs dell'harness, senza dichiarazioni di tipo
import { frameStats, summarizeLoaf, pickDevice, renderReport, renderComparison } from '../../../../scripts/perf/run.mjs'

test('frameStats: intervalli fra rAF, scatti > 33 ms', () => {
  const s = frameStats([0, 16, 32, 100])
  assert.equal(s.frames, 3)
  assert.equal(s.maxMs, 68)
  assert.equal(s.jankFrames, 1)
  assert.equal(s.p50Ms, 16)
})

test('frameStats: meno di 2 campioni → tutto 0', () => {
  assert.deepEqual(frameStats([5]), { frames: 0, p50Ms: 0, p95Ms: 0, maxMs: 0, jankFrames: 0 })
})

const loaf = (startTime, duration) => ({
  startTime,
  duration,
  blockingDuration: duration - 50,
  styleAndLayoutStart: startTime + duration - 10,
  scripts: [{ sourceURL: 'app.js', invoker: 'onclick', duration: duration - 20 }],
})

test('summarizeLoaf: null = API non supportata', () => {
  assert.equal(summarizeLoaf(null).supported, false)
})

test('summarizeLoaf: i 3 peggiori in ordine decrescente', () => {
  const s = summarizeLoaf([loaf(0, 60), loaf(100, 200), loaf(400, 80), loaf(600, 120)])
  assert.equal(s.supported, true)
  assert.equal(s.count, 4)
  assert.equal(s.totalMs, 460)
  assert.deepEqual(s.worst.map((w) => w.durationMs), [200, 120, 80])
  assert.equal(s.worst[0].styleLayoutMs, 10)
  assert.equal(s.worst[0].blockingMs, 150)
  assert.deepEqual(s.worst[0].scripts, [{ src: 'app.js', invoker: 'onclick', durationMs: 180 }])
})

test('pickDevice: sceglie il device con la WebView', async () => {
  assert.equal(await pickDevice(['A', 'B'], async (s) => s === 'B'), 'B')
})

test('pickDevice: nessuna WebView → errore chiaro', async () => {
  await assert.rejects(pickDevice(['A'], async () => false), /WebView/)
})

const ok = (id, p95) => ({
  id,
  title: id,
  frames: { frames: 10, p50Ms: 8, p95Ms: p95, maxMs: 40, jankFrames: 1 },
  loaf: { supported: true, count: 1, totalMs: 70, worst: [] },
})
const meta = { label: 'a', mode: 'device', date: '2026-11-01', viewport: { width: 360, height: 780 } }

test('renderReport: scenario fallito e LoAF non supportato', () => {
  const md = renderReport(meta, [
    { id: 'x', title: 'X', error: 'boom' },
    { ...ok('y', 20), loaf: { supported: false } },
  ])
  assert.match(md, /ERRORE: boom/)
  assert.match(md, /n\/d/)
})

test('renderComparison: p95 di entrambi e id mancanti', () => {
  const md = renderComparison(
    { meta: { label: 'base' }, results: [ok('s1', 20), ok('gone', 5)] },
    { meta: { label: 'cur' }, results: [ok('s1', 12), ok('new', 5)] },
  )
  assert.match(md, /20/)
  assert.match(md, /12/)
  assert.match(md, /gone/)
  assert.match(md, /new/)
})
