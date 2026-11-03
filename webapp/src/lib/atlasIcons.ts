import type { MarkerType } from '@/types'
import {
  Anchor, Beer, Bone, BookOpen, Castle, Church, Compass, Coins, Crown, Eye, Flag, Flame, Gem, Ghost,
  Hammer, House, Key, Landmark, MapPin, Mountain, Moon, Scroll, Ship, Shield, Skull, Sparkles, Store,
  Swords, Tent, TreePine, TriangleAlert, User, Waves, Wheat,
  type LucideIcon,
} from 'lucide-react'

// Keys must stay IDENTICAL to api/services/atlas.py::ICONS (kebab-case lucide names).
export const ATLAS_ICONS: Record<string, LucideIcon> = {
  castle: Castle, skull: Skull, landmark: Landmark, 'triangle-alert': TriangleAlert, user: User, scroll: Scroll,
  beer: Beer, tent: Tent, mountain: Mountain, 'tree-pine': TreePine, waves: Waves, anchor: Anchor, ship: Ship,
  swords: Swords, shield: Shield, crown: Crown, gem: Gem, coins: Coins, key: Key, flame: Flame, moon: Moon,
  ghost: Ghost, bone: Bone, church: Church, house: House, store: Store, flag: Flag, eye: Eye, compass: Compass,
  'map-pin': MapPin, sparkles: Sparkles, wheat: Wheat, hammer: Hammer, 'book-open': BookOpen,
}

// Colour key -> tailwind text class on DESIGN.md tokens (full literals so Tailwind keeps them).
export const ATLAS_COLORS: Record<string, string> = {
  gold: 'text-dnd-gold', crimson: 'text-dnd-crimson', emerald: 'text-dnd-emerald', arcane: 'text-dnd-arcane',
  cobalt: 'text-dnd-cobalt', amber: 'text-dnd-amber', parchment: 'text-dnd-parchment',
}

// Mirror of api/services/atlas.py::BUILTIN_TYPES: key -> [icon, color].
export const BUILTIN_TYPES: Record<string, [string, string]> = {
  city: ['castle', 'gold'],
  dungeon: ['skull', 'arcane'],
  poi: ['landmark', 'cobalt'],
  danger: ['triangle-alert', 'crimson'],
  npc: ['user', 'emerald'],
  quest: ['scroll', 'amber'],
}

export function resolveType(t: MarkerType) {
  return {
    Icon: ATLAS_ICONS[t.icon] ?? MapPin,
    color: ATLAS_COLORS[t.color] ?? ATLAS_COLORS.parchment,
    // builtin: name is the key, translated by the client (atlas.types.<key>); custom: literal name.
    label: (tr: (key: string) => string) => (t.builtin ? tr(`atlas.types.${t.key ?? t.name}`) : t.name),
  }
}
