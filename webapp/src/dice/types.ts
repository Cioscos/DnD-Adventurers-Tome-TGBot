export type DiceKind = 'd4' | 'd6' | 'd8' | 'd10' | 'd12' | 'd20' | 'd100'

export type DiceTint = 'normal' | 'crit' | 'fumble' | 'arcane' | 'ember'

export interface DiceGroup {
  kind: DiceKind
  results: number[]
  tint?: DiceTint
  label?: string
}

export interface DicePlayRequest {
  groups: DiceGroup[]
  interGroupMs?: number
}

export interface DiceAnimationApi {
  play: (req: DicePlayRequest) => Promise<void>
  isPlaying: boolean
}
