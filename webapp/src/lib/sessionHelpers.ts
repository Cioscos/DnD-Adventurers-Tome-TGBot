/** Pure helpers for session screens. */

export type SessionRole = 'gm' | 'player' | 'none'

export interface SessionParticipant {
  user_id: number
  role?: 'gm' | 'player' | string
}

export interface ActiveSessionShape {
  gm_user_id?: number | null
  participants?: SessionParticipant[]
}

export function getMyRole(active: ActiveSessionShape | null | undefined, myUserId: number | null | undefined): SessionRole {
  if (!active || !myUserId) return 'none'
  if (active.gm_user_id === myUserId) return 'gm'
  if (active.participants?.some((p) => p.user_id === myUserId)) return 'player'
  return 'none'
}

/** Format a session uptime ("Xh Ym") from a created_at ISO string. */
export function formatUptime(createdAtIso: string | Date, now: Date = new Date()): string {
  const start = createdAtIso instanceof Date ? createdAtIso : new Date(createdAtIso)
  const ms = Math.max(0, now.getTime() - start.getTime())
  const totalMin = Math.floor(ms / 60_000)
  const h = Math.floor(totalMin / 60)
  const m = totalMin % 60
  if (h <= 0) return `${m}m`
  return `${h}h ${m}m`
}
