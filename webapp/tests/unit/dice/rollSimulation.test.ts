import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as CANNON from 'cannon-es'
import * as THREE from 'three'
import { createDiceWorld, type DiceWorld } from '@/dice/physics/world'
import { createRollSimulation, findOverlappingPairs, type SimDieSpec } from '@/dice/physics/rollSimulation'
import { getDiceGeometry } from '@/dice/geometries'
import { faceUp } from '@/dice/physics/faceDetector'

const FRAME = 1 / 60

/** Lanci riproducibili: fisica e spawn dipendono solo da Math.random. */
function seedRandom(seed: number) {
  let a = seed >>> 0
  vi.spyOn(Math, 'random').mockImplementation(() => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  })
}

function arena(): DiceWorld {
  const dw = createDiceWorld()
  // Stessa arena di un telefono 375x667
  dw.walls[0].position.set(-1.453, 0, 0)
  dw.walls[1].position.set(1.453, 0, 0)
  dw.walls[2].position.set(0, 0, -2.122)
  dw.walls[3].position.set(0, 0, 2.122)
  dw.halfX = 1.453
  dw.halfZ = 2.122
  return dw
}

const specs = (kind: SimDieSpec['kind'], n: number): SimDieSpec[] =>
  Array.from({ length: n }, () => ({ kind, groupIndex: 0 }))

function settle(sim: ReturnType<typeof createRollSimulation>, maxFrames = 2000) {
  let frames = 0
  while (sim.phase !== 'settled' && frames < maxFrames) {
    sim.advance(FRAME)
    frames++
  }
  return frames
}

function shownValue(body: CANNON.Body, kind: SimDieSpec['kind']): number {
  const q = new THREE.Quaternion(body.quaternion.x, body.quaternion.y, body.quaternion.z, body.quaternion.w)
  return faceUp(getDiceGeometry(kind).faceNormals, q).value
}

describe('createRollSimulation', () => {
  beforeEach(() => seedRandom(1234))
  afterEach(() => vi.restoreAllMocks())

  it('saves exactly the value shown on every die, even in a crowded roll', () => {
    const dw = arena()
    for (let roll = 0; roll < 25; roll++) {
      const sim = createRollSimulation(dw, specs('d20', 12))
      settle(sim)
      expect(sim.phase).toBe('settled')
      const results = sim.results()
      expect(results).toHaveLength(12)
      sim.dice.forEach((d, i) => expect(results[i].value).toBe(shownValue(d.body, 'd20')))
      sim.dispose()
    }
  })

  it('does not wait for the hard timeout when a single die is already still', () => {
    const dw = arena()
    const seconds: number[] = []
    for (let roll = 0; roll < 150; roll++) {
      const sim = createRollSimulation(dw, specs('d20', 1))
      seconds.push(settle(sim) * FRAME)
      sim.dispose()
    }
    seconds.sort((a, b) => a - b)
    expect(seconds[Math.floor(seconds.length * 0.95)]).toBeLessThan(3.5)
  })

  it('never takes more than the total budget, even on the slowest d4 rolls', () => {
    const dw = arena()
    for (let roll = 0; roll < 100; roll++) {
      const sim = createRollSimulation(dw, specs('d4', 1))
      expect(settle(sim) * FRAME).toBeLessThanOrEqual(8.1)
      sim.dispose()
    }
  })

  it('rarely leaves a lone die leaning on a wall', () => {
    const dw = arena()
    let tilted = 0
    const rolls = 200
    for (let roll = 0; roll < rolls; roll++) {
      const sim = createRollSimulation(dw, specs('d4', 1))
      settle(sim)
      const q = sim.dice[0].body.quaternion
      const { dot } = faceUp(
        getDiceGeometry('d4').faceNormals,
        new THREE.Quaternion(q.x, q.y, q.z, q.w),
      )
      if (dot < Math.cos((15 * Math.PI) / 180)) tilted++
      sim.dispose()
    }
    expect(tilted / rolls).toBeLessThan(0.03)
  })

  it('reports each die under its own group', () => {
    const dw = arena()
    const sim = createRollSimulation(dw, [
      { kind: 'd6', groupIndex: 0 },
      { kind: 'd8', groupIndex: 1 },
      { kind: 'd8', groupIndex: 1 },
    ])
    settle(sim)
    expect(sim.results().map((r) => [r.groupIndex, r.kind])).toEqual([
      [0, 'd6'],
      [1, 'd8'],
      [1, 'd8'],
    ])
    sim.dispose()
  })

  it('reaches the result in far fewer frames once skipped, and it is still what is shown', () => {
    const dw = arena()
    const sim = createRollSimulation(dw, specs('d20', 4))
    sim.advance(FRAME)
    sim.skip()
    const frames = settle(sim)
    expect(frames).toBeLessThan(20)
    sim.dice.forEach((d, i) => expect(sim.results()[i].value).toBe(shownValue(d.body, 'd20')))
    sim.dispose()
  })

  it('lets the dice really land when skipped on a slow device', () => {
    // Telefono lento: ogni lettura dell'orologio costa 20 ms, cannon esce dal
    // suo ciclo dopo un solo substep e scarta il tempo residuo.
    let clock = 0
    vi.spyOn(performance, 'now').mockImplementation(() => (clock += 20))
    const dw = arena()
    const sim = createRollSimulation(dw, specs('d6', 4))
    const startedAt = dw.world.time
    sim.skip()
    settle(sim, 20000)
    expect(sim.phase).toBe('settled')
    // Col vecchio conteggio il tetto scattava dopo 1 s esatto di fisica, a dadi in volo.
    expect(dw.world.time - startedAt).toBeGreaterThan(1.05)
    sim.dispose()
  })

  it('does not freeze dice in mid-air after a long pause of the page', () => {
    const dw = arena()
    const sim = createRollSimulation(dw, specs('d20', 1))
    sim.advance(30)
    expect(sim.phase).toBe('simulating')
    expect(sim.dice[0].body.sleepState).not.toBe(CANNON.Body.SLEEPING)
    sim.dispose()
  })

  it('removes its bodies from the world when disposed', () => {
    const dw = arena()
    const before = dw.world.bodies.length
    const sim = createRollSimulation(dw, specs('d6', 3))
    expect(dw.world.bodies.length).toBe(before + 3)
    sim.dispose()
    expect(dw.world.bodies.length).toBe(before)
  })
})

describe('findOverlappingPairs', () => {
  const at = (x: number, kind: SimDieSpec['kind']) => ({
    kind,
    body: new CANNON.Body({ mass: 1, position: new CANNON.Vec3(x, 0, 0) }),
  })

  it('leaves alone two d6 that merely touch', () => {
    expect(findOverlappingPairs([at(0, 'd6'), at(0.5, 'd6')])).toHaveLength(0)
  })

  it('detects two d6 that really interpenetrate', () => {
    expect(findOverlappingPairs([at(0, 'd6'), at(0.3, 'd6')])).toHaveLength(1)
  })

  it('uses the size of each die: the same distance is an overlap for two d20', () => {
    expect(findOverlappingPairs([at(0, 'd20'), at(0.5, 'd20')])).toHaveLength(1)
  })
})
