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

/** Peso che l'oggetto porta nel contenitore che lo ospita (con `quantity` opzionale per spostamenti parziali). */
/** Dove creare un contenitore nuovo da cui poi spostare `movingIds`: mai dentro ciò che si sposta
 *  (né in un suo discendente), quindi sopra il più alto contenitore spostato del percorso corrente. */
export function newBoxParent(items: Item[], containerId: number | null, movingIds: number[]): number | null {
  const path = containerPath(items, containerId)
  const i = path.findIndex((c) => movingIds.includes(c.id))
  return i < 0 ? containerId : (path[i - 1]?.id ?? null)
}

/** Lb con 2 decimali: niente 0.30000000000000004 da conversioni di unità. */
export const roundLb = (n: number): number => Math.round(n * 100) / 100

export function movedWeight(item: Item, quantity: number = item.quantity): number {
  const inside = containerMeta(item)?.counts_weight ? (item.container_stats?.contents_weight ?? 0) : 0
  return item.weight * quantity + inside
}

export type ContainerFormValue = Omit<ContainerMeta, 'coins'> & Partial<Pick<ContainerMeta, 'coins'>>

export const PRESETS = [
  { key: 'backpack', capacity_lb: 30, weight: 5, quick_access: false },
  { key: 'sack', capacity_lb: 30, weight: 0.5, quick_access: false },
  { key: 'pouch', capacity_lb: 6, weight: 1, quick_access: false },
  { key: 'quiver', capacity_lb: null, weight: 1, quick_access: true },
  { key: 'chest', capacity_lb: 300, weight: 25, quick_access: false },
] as const

export const defaultContainer: ContainerFormValue = { capacity_lb: null, counts_weight: true, quick_access: false }
