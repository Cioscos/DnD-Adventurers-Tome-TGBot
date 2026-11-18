import { afterEach, describe, expect, it, vi } from 'vitest'
import { createDiceWorld, type DiceWorld } from '@/dice/physics/world'
import { createRollSimulation, type RollSimulation } from '@/dice/physics/rollSimulation'

// Playtest L6: tre 20 naturali di fila. Il d20 lo decide questa simulazione e il
// server lo accetta, quindi la distribuzione delle facce va misurata senza UI.

const FRAME = 1 / 60
const ROLLS = 1000

/** Seme fisso: il test è deterministico, niente falsi allarmi a caso. */
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
  // Arena di un telefono 375x667
  dw.walls[0].position.set(-1.453, 0, 0)
  dw.walls[1].position.set(1.453, 0, 0)
  dw.walls[2].position.set(0, 0, -2.122)
  dw.walls[3].position.set(0, 0, 2.122)
  dw.halfX = 1.453
  dw.halfZ = 2.122
  return dw
}

type Drive = (sim: RollSimulation) => void

const normal: Drive = (sim) => {
  for (let f = 0; f < 2000 && sim.phase !== 'settled'; f++) sim.advance(FRAME)
}
/** "Salta animazione": tocco sull'overlay dopo qualche frame. */
const skipped: Drive = (sim) => {
  for (let f = 0; f < 5; f++) sim.advance(FRAME)
  sim.skip()
  normal(sim)
}
/** Finestra in background: requestAnimationFrame si ferma, alla ripresa arriva un delta enorme. */
const background: Drive = (sim) => {
  for (let f = 0; f < 10; f++) sim.advance(FRAME)
  sim.advance(30)
  normal(sim)
}

/** Facce di ROLLS d20, lanciati `perRoll` alla volta (2 = vantaggio/svantaggio). */
function counts(drive: Drive, seed: number, perRoll = 1): number[] {
  seedRandom(seed)
  const dw = arena()
  const faces = new Array(20).fill(0)
  for (let i = 0; i < ROLLS / perRoll; i++) {
    const sim = createRollSimulation(dw, Array.from({ length: perRoll }, () => ({ kind: 'd20' as const, groupIndex: 0 })))
    drive(sim)
    for (const r of sim.results()) faces[r.value - 1]++
    sim.dispose()
  }
  return faces
}

function chiSquare(faces: number[]): number {
  const expected = ROLLS / faces.length
  return faces.reduce((s, o) => s + (o - expected) ** 2 / expected, 0)
}

// 19 gradi di libertà: p=0.001 → 43.8. Soglia larga, il test cerca bias forti.
const CHI2_LIMIT = 43.8

describe('d20 distribution of the physics simulation (L6)', () => {
  afterEach(() => vi.restoreAllMocks())

  it.each([
    ['normal', normal, 11, 1],
    ['skipped', skipped, 22, 1],
    ['background', background, 33, 1],
    ['advantage (two dice)', normal, 44, 2],
  ] as const)('%s rolls are uniform', (name, drive, seed, perRoll) => {
    const faces = counts(drive, seed, perRoll)
    console.info(`[L6] ${name}: chi2=${chiSquare(faces).toFixed(1)} faces=${faces.join(',')}`)
    expect(chiSquare(faces)).toBeLessThan(CHI2_LIMIT)
    // Nessuna faccia (20 compreso) fuori da 50 ± 25 su 1000 tiri.
    for (const n of faces) expect(n).toBeGreaterThan(25)
    for (const n of faces) expect(n).toBeLessThan(75)
  }, 120_000)
})
