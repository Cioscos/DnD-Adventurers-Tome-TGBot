import type { CharacterClass, ClassResource } from '@/types'

export interface ResourceMaxDiff {
  classId: number
  resourceId: number
  name: string
  prev: number
  next: number
}

/**
 * Compare class-resource maxes before vs after a class change so we can
 * surface scaled pools (e.g. Lay on Hands 5/5 → 5/10 at lv1→lv2 Paladin)
 * via a toast. Only positive deltas are returned; we don't toast on demotion
 * because a class level-down is a deliberate edit by the user.
 */
export function diffResourceMaxes(
  before: CharacterClass[],
  after: CharacterClass[],
): ResourceMaxDiff[] {
  const out: ResourceMaxDiff[] = []
  const beforeMap = new Map<number, ClassResource>()
  for (const cls of before) {
    for (const r of cls.resources ?? []) beforeMap.set(r.id, r)
  }
  for (const cls of after) {
    for (const r of cls.resources ?? []) {
      const prior = beforeMap.get(r.id)
      if (!prior) continue
      if (r.total > prior.total) {
        out.push({
          classId: cls.id,
          resourceId: r.id,
          name: r.name,
          prev: prior.total,
          next: r.total,
        })
      }
    }
  }
  return out
}
