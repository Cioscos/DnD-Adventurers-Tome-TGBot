import { describe, it, expect } from 'vitest'
import { newBoxParent, roundLb, containerPath, containerTree, isContainer } from '@/lib/containers'
import type { Item } from '@/types'

const c = (id: number, container_id: number | null = null): Item => ({
  id, name: `C${id}`, weight: 1, quantity: 1, item_type: 'gear', is_equipped: false,
  container_id, item_metadata: { container: { capacity_lb: null, counts_weight: true, quick_access: false, coins: {} } },
})
const plain = (id: number, container_id: number | null = null): Item => ({
  id, name: `I${id}`, weight: 1, quantity: 1, item_type: 'gear', is_equipped: false, container_id,
})

// 1 > 2 > 3 ; 4 alla radice; 5 dentro 4
const items = [c(3, 2), c(1), plain(9, 1), c(2, 1), c(4), c(5, 4)]

describe('containers lib', () => {
  it('isContainer', () => {
    expect(isContainer(c(1))).toBe(true)
    expect(isContainer(plain(9))).toBe(false)
  })
  it('containerPath dalla radice', () => {
    expect(containerPath(items, 3).map((i) => i.id)).toEqual([1, 2, 3])
    expect(containerPath(items, null)).toEqual([])
    expect(containerPath(items, 99)).toEqual([])
  })
  it('containerTree in profondità per id', () => {
    expect(containerTree(items).map((n) => [n.item.id, n.depth])).toEqual([
      [1, 0], [2, 1], [3, 2], [4, 0], [5, 1],
    ])
  })
  it('newBoxParent: mai dentro ciò che si sposta', () => {
    expect(newBoxParent(items, 3, [3])).toBe(2) // spostando il contenitore aperto: nel suo padre
    expect(newBoxParent(items, 3, [2])).toBe(1) // spostando un antenato
    expect(newBoxParent(items, 1, [1])).toBeNull() // dalla radice
    expect(newBoxParent(items, 3, [9])).toBe(3) // oggetto qualsiasi: resta nel livello
    expect(newBoxParent(items, null, [4])).toBeNull()
  })
  it('roundLb', () => {
    expect(roundLb(0.1 + 0.2)).toBe(0.3)
  })
})
