/** 13200 → "3h 40m"; sotto l'ora "25m". Uguale in it/en. */
export function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  return h > 0 ? (m > 0 ? `${h}h ${String(m).padStart(2, '0')}m` : `${h}h`) : `${m}m`
}
