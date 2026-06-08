import type { Ability } from '@/types'

export interface ResourceMaxDiff {
  abilityId: number
  name: string
  prev: number
  next: number
}

/**
 * Compare class-feature ability maxes before vs after a class change so we can
 * surface scaled pools (e.g. Lay on Hands 5/5 → 5/10 at lv1→lv2 Paladin) via a
 * toast. Le risorse di classe ora sono Ability (is_class_feature). Only positive
 * deltas are returned; we don't toast on demotion because a class level-down is
 * a deliberate edit by the user.
 */
export function diffResourceMaxes(
  before: Ability[],
  after: Ability[],
): ResourceMaxDiff[] {
  const out: ResourceMaxDiff[] = []
  const beforeMap = new Map<number, Ability>()
  for (const a of before) beforeMap.set(a.id, a)
  for (const a of after) {
    if (!a.is_class_feature) continue
    const prior = beforeMap.get(a.id)
    if (!prior || prior.max_uses == null || a.max_uses == null) continue
    if (a.max_uses > prior.max_uses) {
      out.push({
        abilityId: a.id,
        name: a.name,
        prev: prior.max_uses,
        next: a.max_uses,
      })
    }
  }
  return out
}
