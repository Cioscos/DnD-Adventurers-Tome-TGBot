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
