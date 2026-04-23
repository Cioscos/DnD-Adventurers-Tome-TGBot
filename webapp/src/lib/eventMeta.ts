import {
  Heart, Moon, Shield, Swords, Gem, Sparkles, Backpack,
  Coins, Zap, Skull, CircleDot, Pin, Target, ShieldAlert,
  FlaskConical, Dices,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

export interface EventMeta {
  icon: LucideIcon
  tone: string
}

export const EVENT_META: Record<string, EventMeta> = {
  hp_change:          { icon: Heart,        tone: 'text-[var(--dnd-crimson-bright)] bg-dnd-surface-raised border-[var(--dnd-crimson)]' },
  rest:               { icon: Moon,         tone: 'text-[var(--dnd-cobalt-bright)] bg-dnd-surface-raised border-[var(--dnd-cobalt)]' },
  ac_change:          { icon: Shield,       tone: 'text-dnd-gold-bright bg-dnd-surface-raised border-dnd-gold' },
  level_change:       { icon: Swords,       tone: 'text-[var(--dnd-amber)] bg-dnd-surface-raised border-[var(--dnd-amber)]' },
  spell_slot_change:  { icon: Gem,          tone: 'text-dnd-arcane-bright bg-dnd-surface-raised border-[var(--dnd-arcane)]' },
  spell_change:       { icon: Sparkles,     tone: 'text-dnd-arcane-bright bg-dnd-surface-raised border-[var(--dnd-arcane)]' },
  bag_change:         { icon: Backpack,     tone: 'text-dnd-gold-bright bg-dnd-surface-raised border-dnd-gold' },
  currency_change:    { icon: Coins,        tone: 'text-[var(--dnd-amber)] bg-dnd-surface-raised border-[var(--dnd-amber)]' },
  ability_change:     { icon: Zap,          tone: 'text-[var(--dnd-amber)] bg-dnd-surface-raised border-[var(--dnd-amber)]' },
  death_save:         { icon: Skull,        tone: 'text-[var(--dnd-crimson-bright)] bg-dnd-surface-raised border-[var(--dnd-crimson)]' },
  condition_change:   { icon: CircleDot,    tone: 'text-[var(--dnd-crimson-bright)] bg-dnd-surface-raised border-[var(--dnd-crimson)]' },
  attack_roll:        { icon: Swords,       tone: 'text-[var(--dnd-crimson-bright)] bg-dnd-surface-raised border-[var(--dnd-crimson)]' },
  skill_roll:         { icon: Target,       tone: 'text-[var(--dnd-cobalt-bright)] bg-dnd-surface-raised border-[var(--dnd-cobalt)]' },
  saving_throw:       { icon: ShieldAlert,  tone: 'text-[var(--dnd-cobalt-bright)] bg-dnd-surface-raised border-[var(--dnd-cobalt)]' },
  concentration_save: { icon: FlaskConical, tone: 'text-dnd-arcane-bright bg-dnd-surface-raised border-[var(--dnd-arcane)]' },
  hit_dice:           { icon: Dices,        tone: 'text-[var(--dnd-emerald-bright)] bg-dnd-surface-raised border-[var(--dnd-emerald)]' },
  other:              { icon: Pin,          tone: 'text-dnd-text-muted bg-dnd-surface-raised border-dnd-border' },
}
