import { describe, it, expect } from 'vitest'
// @ts-expect-error — modulo .mjs dell'harness, senza dichiarazioni di tipo
import { analyzeTrace } from '../../../../scripts/perf/lib/metrics.mjs'

const PID = 1
const TID = 10

const threadMeta = {
  ph: 'M',
  name: 'thread_name',
  pid: PID,
  tid: TID,
  args: { name: 'CrRendererMain' },
}

// Evento "X" (complete) sul main thread. ts/dur in microsecondi.
const ev = (name: string, ts: number, dur: number, extra: object = {}) => ({
  ph: 'X',
  name,
  ts,
  dur,
  pid: PID,
  tid: TID,
  ...extra,
})

describe('analyzeTrace', () => {
  it('trace vuota → metriche a zero', () => {
    const r = analyzeTrace([threadMeta])
    expect(r.durationMs).toBe(0)
    expect(r.longTasks).toEqual([])
    expect(r.fullScreenPaints).toBe(0)
  })

  it('rileva un long task >50ms con attribuzione al figlio più lungo', () => {
    const events = [
      threadMeta,
      ev('RunTask', 0, 80_000),
      ev('FunctionCall', 1_000, 60_000),
      ev('Layout', 62_000, 10_000),
    ]
    const r = analyzeTrace(events)
    expect(r.longTasks).toHaveLength(1)
    expect(r.longTasks[0].durMs).toBe(80)
    expect(r.longTasks[0].culprit).toBe('FunctionCall')
  })

  it('ignora i task sotto i 50ms', () => {
    const r = analyzeTrace([threadMeta, ev('RunTask', 0, 49_000)])
    expect(r.longTasks).toEqual([])
  })

  it('somma i bucket per categoria', () => {
    const events = [
      threadMeta,
      ev('FunctionCall', 0, 10_000),
      ev('EvaluateScript', 20_000, 5_000),
      ev('Layout', 30_000, 7_000),
      ev('Paint', 40_000, 3_000),
      ev('UpdateLayoutTree', 50_000, 2_000),
      ev('CompositeLayers', 60_000, 1_000),
    ]
    const r = analyzeTrace(events)
    expect(r.buckets.scriptMs).toBe(15)
    expect(r.buckets.layoutMs).toBe(7)
    expect(r.buckets.paintMs).toBe(3)
    expect(r.buckets.styleMs).toBe(2)
    expect(r.buckets.compositeMs).toBe(1)
  })

  it('calcola FPS medi dai DrawFrame sulla durata della trace', () => {
    // finestra di 1 secondo (1_000_000 µs) con 30 DrawFrame → 30 fps, ~50% dropped
    const events: object[] = [threadMeta, ev('RunTask', 0, 1_000_000)]
    for (let i = 0; i < 30; i++) {
      events.push({ ph: 'I', name: 'DrawFrame', ts: i * 33_000, pid: PID, tid: 20 })
    }
    const r = analyzeTrace(events)
    expect(r.frames.drawn).toBe(30)
    expect(r.frames.avgFps).toBe(30)
    expect(r.frames.droppedPctEst).toBe(50)
  })

  it('conta i paint full-screen (clip ≥90% viewport)', () => {
    const clipFull = [0, 0, 375, 0, 375, 667, 0, 667]
    const clipSmall = [0, 0, 100, 0, 100, 100, 0, 100]
    const events = [
      threadMeta,
      ev('RunTask', 0, 100_000),
      ev('Paint', 1_000, 2_000, { args: { data: { clip: clipFull } } }),
      ev('Paint', 5_000, 2_000, { args: { data: { clip: clipSmall } } }),
    ]
    const r = analyzeTrace(events, { viewport: { width: 375, height: 667 } })
    expect(r.fullScreenPaints).toBe(1)
  })

  it('senza viewport non conta i full-screen paint', () => {
    const clipFull = [0, 0, 375, 0, 375, 667, 0, 667]
    const events = [
      threadMeta,
      ev('Paint', 1_000, 2_000, { args: { data: { clip: clipFull } } }),
    ]
    expect(analyzeTrace(events).fullScreenPaints).toBe(0)
  })

  it('regge trace da centinaia di migliaia di eventi senza stack overflow', () => {
    // Simula traccia grande (es. animazione 3D dadi) con 300_000 eventi
    const events = [threadMeta, ev('RunTask', 0, 3_000_000_000)]
    for (let i = 0; i < 300_000; i++) {
      events.push(ev('FunctionCall', i * 10, 5))
    }
    const r = analyzeTrace(events)
    expect(r.durationMs).toBe(3000000)
    expect(r.longTasks).toHaveLength(1)
    expect(r.frames.drawn).toBe(0)
  })
})
