import { describe, expect, it } from 'vitest'
import { computeSpawnPositions } from '@/dice/physics/spawner'
import { PHYSICS } from '@/dice/physics/constants'

const DIE_RADIUS = 0.38
const DIAMETER = DIE_RADIUS * 2

describe('computeSpawnPositions', () => {
  const arenas = [
    { halfX: 1.0, halfZ: 2.0 }, // portrait stretto (S22)
    { halfX: 1.3, halfZ: 2.0 }, // landscape/desktop
  ]

  it.each(arenas)('never spawns overlapping dice (halfX=$halfX)', (arena) => {
    for (let trial = 0; trial < 20; trial++) {
      for (let count = 1; count <= 20; count++) {
        const positions = computeSpawnPositions(count, arena)
        expect(positions).toHaveLength(count)
        for (let i = 0; i < count; i++) {
          for (let j = i + 1; j < count; j++) {
            const d = positions[i].distanceTo(positions[j])
            expect(d).toBeGreaterThanOrEqual(DIAMETER - 1e-9)
          }
        }
      }
    }
  })

  it.each(arenas)('stays inside walls, ceiling and floor (halfX=$halfX)', (arena) => {
    for (let trial = 0; trial < 20; trial++) {
      for (const count of [1, 6, 12, 20]) {
        for (const p of computeSpawnPositions(count, arena)) {
          expect(Math.abs(p.x) + DIE_RADIUS).toBeLessThanOrEqual(arena.halfX)
          expect(p.y + DIE_RADIUS).toBeLessThanOrEqual(PHYSICS.ceilingY)
          expect(p.y - DIE_RADIUS).toBeGreaterThan(PHYSICS.floorY)
        }
      }
    }
  })

  it('falls back to a sane arena when none is given', () => {
    const positions = computeSpawnPositions(6)
    for (let i = 0; i < positions.length; i++) {
      for (let j = i + 1; j < positions.length; j++) {
        expect(positions[i].distanceTo(positions[j])).toBeGreaterThanOrEqual(DIAMETER - 1e-9)
      }
      expect(Math.abs(positions[i].x) + DIE_RADIUS).toBeLessThanOrEqual(1.0)
    }
  })
})
