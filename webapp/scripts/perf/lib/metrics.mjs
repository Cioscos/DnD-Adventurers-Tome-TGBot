/**
 * Parser di trace Chrome (array di trace event JSON) → metriche per scenario.
 * Funzione pura, zero I/O.
 *
 * Approssimazioni deliberate (vedi README):
 * - i bucket sommano la durata degli eventi X per nome senza sottrarre i figli
 *   annidati (uno script che contiene un Layout conta in entrambi i bucket);
 * - i frame droppati sono stimati dal rapporto DrawFrame / 60fps.
 */

const LONG_TASK_US = 50_000

const BUCKETS = {
  script: new Set([
    'FunctionCall',
    'EvaluateScript',
    'TimerFire',
    'FireAnimationFrame',
    'EventDispatch',
    'V8.Execute',
  ]),
  style: new Set(['UpdateLayoutTree', 'RecalculateStyles', 'ScheduleStyleRecalculation']),
  layout: new Set(['Layout']),
  paint: new Set(['Paint', 'PaintImage']),
  composite: new Set(['CompositeLayers', 'UpdateLayerTree']),
}

/** pid/tid del main thread del renderer dai metadata `thread_name`. */
function findMainThread(events) {
  const meta = events.find(
    (e) => e.ph === 'M' && e.name === 'thread_name' && e.args?.name === 'CrRendererMain',
  )
  return meta ? { pid: meta.pid, tid: meta.tid } : null
}

const round2 = (n) => Math.round(n * 100) / 100

export function analyzeTrace(events, { viewport } = {}) {
  const x = events.filter((e) => e.ph === 'X' && typeof e.dur === 'number')
  const emptyBuckets = { scriptMs: 0, styleMs: 0, layoutMs: 0, paintMs: 0, compositeMs: 0 }
  if (x.length === 0) {
    return {
      durationMs: 0,
      longTasks: [],
      buckets: emptyBuckets,
      frames: { drawn: 0, avgFps: 0, droppedPctEst: 0 },
      fullScreenPaints: 0,
    }
  }

  const main = findMainThread(events)
  const onMain = main ? x.filter((e) => e.pid === main.pid && e.tid === main.tid) : x

  const t0 = Math.min(...x.map((e) => e.ts))
  const t1 = Math.max(...x.map((e) => e.ts + e.dur))
  const durationMs = (t1 - t0) / 1000

  const longTasks = onMain
    .filter((e) => e.name === 'RunTask' && e.dur >= LONG_TASK_US)
    .map((task) => {
      const children = onMain.filter(
        (c) =>
          c !== task &&
          c.name !== 'RunTask' &&
          c.ts >= task.ts &&
          c.ts + c.dur <= task.ts + task.dur,
      )
      const culprit = [...children].sort((a, b) => b.dur - a.dur)[0]?.name ?? 'unknown'
      return {
        startMs: round2((task.ts - t0) / 1000),
        durMs: round2(task.dur / 1000),
        culprit,
      }
    })
    .sort((a, b) => b.durMs - a.durMs)

  const buckets = {}
  for (const [bucket, names] of Object.entries(BUCKETS)) {
    buckets[`${bucket}Ms`] = round2(
      onMain.filter((e) => names.has(e.name)).reduce((s, e) => s + e.dur, 0) / 1000,
    )
  }

  const drawn = events.filter((e) => e.name === 'DrawFrame').length
  const avgFps = durationMs > 0 ? round2(drawn / (durationMs / 1000)) : 0
  const droppedPctEst = round2(Math.max(0, (1 - avgFps / 60) * 100))

  let fullScreenPaints = 0
  if (viewport?.width && viewport?.height) {
    const vpArea = viewport.width * viewport.height
    for (const e of events) {
      if (e.name !== 'Paint') continue
      const clip = e.args?.data?.clip
      if (!Array.isArray(clip) || clip.length < 6) continue
      const area = Math.abs(clip[2] - clip[0]) * Math.abs(clip[5] - clip[1])
      if (area >= vpArea * 0.9) fullScreenPaints++
    }
  }

  return {
    durationMs: round2(durationMs),
    longTasks,
    buckets,
    frames: { drawn, avgFps, droppedPctEst },
    fullScreenPaints,
  }
}
