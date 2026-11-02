import type { ContainerMeta, Item } from '@/types'

export function containerMeta(item: Item): ContainerMeta | null {
  return (item.item_metadata?.container as ContainerMeta | undefined) ?? null
}

export const isContainer = (item: Item): boolean => containerMeta(item) !== null

/** Contenitori antenati + quello indicato, dalla radice. Vuoto per null/sconosciuto. */
export function containerPath(items: Item[], containerId: number | null): Item[] {
  const byId = new Map(items.map((i) => [i.id, i]))
  const path: Item[] = []
  let cur = containerId == null ? undefined : byId.get(containerId)
  while (cur && isContainer(cur) && !path.includes(cur)) {
    path.unshift(cur)
    cur = cur.container_id == null ? undefined : byId.get(cur.container_id)
  }
  return containerId != null && path.at(-1)?.id !== containerId ? [] : path
}

/** Alberi di contenitori in profondità, ordinati per id. */
export function containerTree(items: Item[]): { item: Item; depth: number }[] {
  const boxes = items.filter(isContainer).sort((a, b) => a.id - b.id)
  const out: { item: Item; depth: number }[] = []
  const visit = (parent: number | null, depth: number) => {
    for (const b of boxes) {
      if ((b.container_id ?? null) !== parent) continue
      out.push({ item: b, depth })
      visit(b.id, depth + 1)
    }
  }
  visit(null, 0)
  return out
}
