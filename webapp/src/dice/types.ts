export type DiceKind = 'd4' | 'd6' | 'd8' | 'd10' | 'd12' | 'd20' | 'd100'

export type DiceTint = 'normal' | 'crit' | 'fumble' | 'arcane' | 'ember'

export interface DiceGroup {
  kind: DiceKind
  /** Opzionale: se presente, attivava lo snap legacy (rimosso). Ora ignorato. */
  results?: number[]
  /** Numero di body fisici da spawnare quando results è assente. Default: 1. */
  count?: number
  tint?: DiceTint
  label?: string
}

export interface DicePlayRequest {
  groups: DiceGroup[]
  interGroupMs?: number
}

export interface DetectedResult {
  groupIndex: number
  kind: Exclude<DiceKind, 'd100'>
  value: number
}

export interface PlayCollectGroup {
  kind: DiceKind
  tint?: DiceTint
  count: number
}

export interface DiceAnimationApi {
  play: (req: DicePlayRequest) => Promise<void>
  playAndCollect: (groups: PlayCollectGroup[]) => Promise<DetectedResult[]>
  isPlaying: boolean
}
