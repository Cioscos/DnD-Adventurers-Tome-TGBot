// webapp/src/dice/physics/spawner.ts
import * as CANNON from 'cannon-es'
import { PHYSICS } from './constants'

export interface SpawnOptions {
  shape: CANNON.ConvexPolyhedron
  material: CANNON.Material
  position: CANNON.Vec3
  scale?: number
  totalCount?: number
}

export interface SleepTuning {
  sleepSpeedLimit: number
  sleepTimeLimit: number
}

const SIZE_BY_COUNT = (n: number) => (n <= 1 ? 0.75 : n <= 3 ? 0.65 : n <= 6 ? 0.55 : 0.48)

const rand = (min: number, max: number) => Math.random() * (max - min) + min

/**
 * Sleep params adattivi: più dadi = criterio meno stretto + tempo più corto.
 * Evita jitter prolungato quando molti body si toccano tra di loro.
 */
export function sleepTuningForCount(count: number): SleepTuning {
  if (count <= 3) return { sleepSpeedLimit: PHYSICS.sleepSpeedLimit, sleepTimeLimit: PHYSICS.sleepTimeLimit }
  if (count <= 8) return { sleepSpeedLimit: 0.1, sleepTimeLimit: 0.45 }
  return { sleepSpeedLimit: 0.2, sleepTimeLimit: 0.3 }
}

export function spawnDiceBody(opts: SpawnOptions): CANNON.Body {
  const tuning = sleepTuningForCount(opts.totalCount ?? 1)
  const body = new CANNON.Body({
    mass: 1,
    shape: opts.shape,
    material: opts.material,
    allowSleep: true,
    sleepSpeedLimit: tuning.sleepSpeedLimit,
    sleepTimeLimit: tuning.sleepTimeLimit,
    linearDamping: PHYSICS.linearDamping,
    angularDamping: PHYSICS.angularDamping,
  })
  body.position.copy(opts.position)

  // direzione: vettore (0,0,-1) ruotato di un cono random intorno all'asse Y
  const coneRad = (PHYSICS.spawnConeDeg * Math.PI) / 180
  const yaw = rand(-coneRad, coneRad)
  const dirX = Math.sin(yaw)
  const dirZ = -Math.cos(yaw)
  const speed = rand(PHYSICS.throwLinearMin, PHYSICS.throwLinearMax)
  body.velocity.set(dirX * speed, rand(-1, 0), dirZ * speed)

  const a = PHYSICS.throwAngularRange
  body.angularVelocity.set(rand(-a, a), rand(-a, a), rand(-a, a))
  body.quaternion.setFromEuler(rand(0, Math.PI * 2), rand(0, Math.PI * 2), rand(0, Math.PI * 2))
  return body
}

/**
 * Layout spawn:
 *  - count <= 6: fila singola su X (come prima).
 *  - count > 6: griglia 2D xz + tier verticali su Y per evitare pile-up iniziale
 *    quando molti dadi spawnano insieme.
 */
export function computeSpawnPositions(count: number): CANNON.Vec3[] {
  const positions: CANNON.Vec3[] = []
  if (count <= 6) {
    for (let i = 0; i < count; i++) {
      const xOffset = (i - (count - 1) / 2) * PHYSICS.spawnXOffsetPerDie
      const x = xOffset + rand(-PHYSICS.spawnXSpread, PHYSICS.spawnXSpread) * 0.3
      const y = PHYSICS.spawnYBase + Math.random() * PHYSICS.spawnYJitter
      const z = PHYSICS.spawnZ + (Math.random() - 0.5) * 0.1
      positions.push(new CANNON.Vec3(x, y, z))
    }
    return positions
  }

  // Griglia 2D + tier Y per N grandi
  const cols = Math.min(6, Math.ceil(Math.sqrt(count)))
  const rows = Math.ceil(count / cols)
  const stepX = PHYSICS.spawnXOffsetPerDie
  const stepZ = 0.35
  const tierStep = 0.6
  for (let i = 0; i < count; i++) {
    const col = i % cols
    const row = Math.floor(i / cols)
    const xOffset = (col - (cols - 1) / 2) * stepX
    const zOffset = (row - (rows - 1) / 2) * stepZ
    const tier = Math.floor(i / cols)
    const x = xOffset + rand(-0.05, 0.05)
    const y = PHYSICS.spawnYBase + tier * tierStep + rand(0, PHYSICS.spawnYJitter)
    const z = PHYSICS.spawnZ + zOffset + rand(-0.05, 0.05)
    positions.push(new CANNON.Vec3(x, y, z))
  }
  return positions
}

export function diceScaleForCount(count: number): number {
  return SIZE_BY_COUNT(count)
}

/**
 * Energia cinetica totale (somma |v| + |ω|) di un set di body.
 * Usata per force-sleep precoce quando il sistema è di fatto fermo
 * ma cannon-es non riconosce sleep (jitter da contatti residui).
 */
export function totalKineticActivity(bodies: CANNON.Body[]): number {
  let total = 0
  for (const b of bodies) {
    total += b.velocity.length() + b.angularVelocity.length() * 0.3
  }
  return total
}
