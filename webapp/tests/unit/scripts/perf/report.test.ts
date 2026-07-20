import { describe, it, expect } from 'vitest'
// @ts-expect-error — modulo .mjs dell'harness, senza dichiarazioni di tipo
import { renderMarkdown, renderComparison } from '../../../../scripts/perf/lib/report.mjs'

const metrics = (over: object = {}) => ({
  durationMs: 1000,
  longTasks: [{ startMs: 10, durMs: 120, culprit: 'FunctionCall' }],
  buckets: { scriptMs: 200, styleMs: 30, layoutMs: 40, paintMs: 90, compositeMs: 15 },
  frames: { drawn: 30, avgFps: 30, droppedPctEst: 50 },
  fullScreenPaints: 4,
  ...over,
})

const meta = {
  label: 'baseline',
  mode: 'device',
  date: '2026-07-20T10:00:00',
  viewport: { width: 375, height: 667 },
}

describe('renderMarkdown', () => {
  it('produce una tabella con una riga per scenario e il dettaglio long task', () => {
    const md = renderMarkdown(meta, [
      { scenarioId: 'overlay-modal', title: 'Modale generica', metrics: metrics() },
    ])
    expect(md).toContain('# Perf run — baseline')
    expect(md).toContain('| Modale generica | 1 | 120 | 30 | 50 | 4 |')
    expect(md).toContain('| 10 | 120 | FunctionCall |')
  })
})

describe('renderComparison', () => {
  it('mostra i delta per scenario appaiato per id', () => {
    const baseline = {
      meta,
      results: [{ scenarioId: 'overlay-modal', title: 'Modale generica', metrics: metrics() }],
    }
    const current = {
      meta: { ...meta, label: 'after-blur' },
      results: [
        {
          scenarioId: 'overlay-modal',
          title: 'Modale generica',
          metrics: metrics({
            longTasks: [],
            frames: { drawn: 55, avgFps: 55, droppedPctEst: 8.33 },
            fullScreenPaints: 0,
          }),
        },
      ],
    }
    const md = renderComparison(baseline, current)
    expect(md).toContain('baseline → after-blur')
    expect(md).toContain('Modale generica')
    // long task: 1 → 0 ; fps 30 → 55 ; full-screen paint 4 → 0
    expect(md).toContain('| Long task | 1 | 0 |')
    expect(md).toContain('| FPS medi | 30 | 55 |')
    expect(md).toContain('| Paint full-screen | 4 | 0 |')
  })

  it('segnala gli scenari presenti solo in uno dei due run', () => {
    const baseline = { meta, results: [] }
    const current = {
      meta: { ...meta, label: 'after' },
      results: [{ scenarioId: 'nuovo', title: 'Nuovo', metrics: metrics() }],
    }
    expect(renderComparison(baseline, current)).toContain('senza corrispettivo')
  })
})
