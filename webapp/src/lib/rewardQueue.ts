const KEY = 'reward-queue'

export interface Reward {
  message_id: number
  item_id: number
  item_name: string
  item_quantity: number
  char_id: number
  granted_at: string // ISO
}

function readQueue(): Reward[] {
  try {
    const raw = sessionStorage.getItem(KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? (parsed as Reward[]) : []
  } catch (err) {
    console.warn('[rewardQueue] read failed', err)
    return []
  }
}

function writeQueue(q: Reward[]): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(q))
  } catch (err) {
    console.warn('[rewardQueue] write failed', err)
  }
}

export function enqueue(r: Reward): void {
  const q = readQueue()
  // dedup by message_id (in case the same incremental fetch fires twice)
  if (q.some((x) => x.message_id === r.message_id)) return
  q.push(r)
  writeQueue(q)
}

export function peek(): Reward | null {
  const q = readQueue()
  return q.length > 0 ? q[0] : null
}

export function dequeue(): Reward | null {
  const q = readQueue()
  if (q.length === 0) return null
  const head = q[0]
  writeQueue(q.slice(1))
  return head
}

export function clear(): void {
  writeQueue([])
}

export function pruneOlderThan(maxAgeMs: number): void {
  const q = readQueue()
  const now = Date.now()
  const fresh = q.filter((r) => {
    const t = Date.parse(r.granted_at)
    return Number.isFinite(t) && now - t < maxAgeMs
  })
  if (fresh.length !== q.length) writeQueue(fresh)
}
