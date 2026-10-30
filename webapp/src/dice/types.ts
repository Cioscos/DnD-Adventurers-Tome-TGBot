export type DiceKind = 'd4' | 'd6' | 'd8' | 'd10' | 'd12' | 'd20' | 'd100'

export type DiceTint = 'normal' | 'crit' | 'fumble' | 'arcane' | 'ember'

export interface DiceGroup {
  kind: DiceKind
  /** Quanti tiri: ogni d100 è una coppia di d10 fisici. Default: 1. */
  count?: number
  tint?: DiceTint
}

export interface DetectedResult {
  groupIndex: number
  kind: Exclude<DiceKind, 'd100'>
  value: number
}

export interface PlayCollectGroup {
  kind: DiceKind
  tint?: DiceTint
  /** Quanti tiri: ogni d100 è una coppia di d10 fisici. */
  count: number
}

export interface DiceAnimationApi {
  /**
   * Anima il tiro e restituisce sempre tutti i dadi richiesti, nell'ordine dei
   * gruppi: quelli che non si possono animare (scena non disponibile, oltre il
   * tetto per tiro) sono generati in locale.
   */
  playAndCollect: (groups: PlayCollectGroup[]) => Promise<DetectedResult[]>
  isPlaying: boolean
}
