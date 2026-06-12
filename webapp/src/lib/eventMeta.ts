import {
  GiHeartPlus, GiNightSleep, GiCheckedShield, GiCrossedSwords, GiCutDiamond,
  GiSparkles, GiKnapsack, GiTwoCoins, GiLightningTrio, GiSkullCrossedBones,
  GiArcheryTarget, GiShieldEchoes, GiPotionBall,
  GiPerspectiveDiceSixFacesRandom, GiPin, GiAura,
} from 'react-icons/gi'
import type { IconType } from 'react-icons'

export interface EventMeta {
  icon: IconType
  tone: string
}

export const EVENT_META: Record<string, EventMeta> = {
  hp_change:          { icon: GiHeartPlus,      tone: 'text-dnd-crimson-bright bg-dnd-surface-raised border-dnd-crimson' },
  rest:               { icon: GiNightSleep,     tone: 'text-dnd-cobalt-bright bg-dnd-surface-raised border-dnd-cobalt' },
  ac_change:          { icon: GiCheckedShield,  tone: 'text-dnd-gold-bright bg-dnd-surface-raised border-dnd-gold' },
  level_change:       { icon: GiCrossedSwords,  tone: 'text-dnd-amber bg-dnd-surface-raised border-dnd-amber' },
  spell_slot_change:  { icon: GiCutDiamond,     tone: 'text-dnd-arcane-bright bg-dnd-surface-raised border-dnd-arcane' },
  spell_change:       { icon: GiSparkles,       tone: 'text-dnd-arcane-bright bg-dnd-surface-raised border-dnd-arcane' },
  bag_change:         { icon: GiKnapsack,       tone: 'text-dnd-gold-bright bg-dnd-surface-raised border-dnd-gold' },
  currency_change:    { icon: GiTwoCoins,       tone: 'text-dnd-amber bg-dnd-surface-raised border-dnd-amber' },
  ability_change:     { icon: GiLightningTrio,  tone: 'text-dnd-amber bg-dnd-surface-raised border-dnd-amber' },
  death_save:         { icon: GiSkullCrossedBones, tone: 'text-dnd-crimson-bright bg-dnd-surface-raised border-dnd-crimson' },
  condition_change:   { icon: GiAura,           tone: 'text-dnd-crimson-bright bg-dnd-surface-raised border-dnd-crimson' },
  attack_roll:        { icon: GiCrossedSwords,  tone: 'text-dnd-crimson-bright bg-dnd-surface-raised border-dnd-crimson' },
  skill_roll:         { icon: GiArcheryTarget,  tone: 'text-dnd-cobalt-bright bg-dnd-surface-raised border-dnd-cobalt' },
  saving_throw:       { icon: GiShieldEchoes,   tone: 'text-dnd-cobalt-bright bg-dnd-surface-raised border-dnd-cobalt' },
  concentration_save: { icon: GiPotionBall,     tone: 'text-dnd-arcane-bright bg-dnd-surface-raised border-dnd-arcane' },
  hit_dice:           { icon: GiPerspectiveDiceSixFacesRandom, tone: 'text-dnd-emerald-bright bg-dnd-surface-raised border-dnd-emerald' },
  dice_roll:          { icon: GiPerspectiveDiceSixFacesRandom, tone: 'text-dnd-gold-bright bg-dnd-surface-raised border-dnd-gold' },
  other:              { icon: GiPin,            tone: 'text-dnd-text-muted bg-dnd-surface-raised border-dnd-border' },
}
