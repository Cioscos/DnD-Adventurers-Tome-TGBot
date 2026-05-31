import type { ComponentType } from 'react'
import Skeleton from '@/components/ui/Skeleton'
import ArmorClassSkeleton from './ArmorClassSkeleton'
import HPSkeleton from './HPSkeleton'
import SavingThrowsSkeleton from './SavingThrowsSkeleton'
import SpellsSkeleton from './SpellsSkeleton'
import SpellSlotsSkeleton from './SpellSlotsSkeleton'

/** Generic page skeleton — used when a page has no bespoke skeleton yet. */
export function GenericPageSkeleton() {
  return (
    <div className="space-y-3" aria-hidden>
      <Skeleton.Rect height="160px" />
      <Skeleton.Rect height="80px" delay={80} />
      <Skeleton.Rect height="80px" delay={160} />
    </div>
  )
}

/** Map of sub-page key (see PAGE_GROUPS in useSwipeNavigation) → skeleton. */
const REGISTRY: Record<string, ComponentType> = {
  // combat
  hp: HPSkeleton,
  ac: ArmorClassSkeleton,
  saves: SavingThrowsSkeleton,
  // magic
  spells: SpellsSkeleton,
  slots: SpellSlotsSkeleton,
}

/** Returns the skeleton component for a page key, or the generic fallback. */
export function pageSkeleton(pageKey?: string): ComponentType {
  if (pageKey && REGISTRY[pageKey]) return REGISTRY[pageKey]
  return GenericPageSkeleton
}
