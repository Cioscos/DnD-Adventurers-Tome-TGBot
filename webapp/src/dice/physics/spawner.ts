// webapp/src/dice/physics/spawner.ts
import * as CANNON from 'cannon-es'
import { PHYSICS } from './constants'

export interface SpawnOptions {
  shape: CANNON.ConvexPolyhedron
  material: CANNON.Material
  position: CANNON.Vec3
  totalCount?: number
}

export interface SleepTuning {
  sleepSpeedLimit: number
  sleepTimeLimit: number
}

export interface SpawnArena {
  halfX: number
  halfZ: number
}

/** Mezzo dado (circumradius 0.38) + margine dai muri. */
const ARENA_MARGIN = 0.43

const rand = (min: number, max: number) => Math.random() * (max - min) + min

/**
 * Sleep params adattivi: più dadi = criterio meno stretto + tempo più corto.
 * Evita jitter prolungato quando molti body si toccano tra di loro.
 */
export function sleepTuningForCount(count: number): SleepTuning {
  if (count <= 3) return { sleepSpeedLimit: PHYSICS.sleepSpeedLimit, sleepTimeLimit: 0.45 }
  if (count <= 8) return { sleepSpeedLimit: 0.3, sleepTimeLimit: PHYSICS.sleepTimeLimit }
  return { sleepSpeedLimit: 0.4, sleepTimeLimit: 0.3 }
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
 * Layout spawn: griglia colonne×righe (passo spawnStep > diametro dado) con
 * tier verticali DISCENDENTI quando una griglia non basta. Nessuna coppia di
 * dadi nasce mai a distanza < diametro (0.76) — la compenetrazione alla
 * nascita era la causa principale degli incastri con 5-6 dadi.
 */
export function computeSpawnPositions(count: number, arena?: SpawnArena): CANNON.Vec3[] {
  const step = PHYSICS.spawnStep
  const halfX = arena?.halfX ?? 1.0
  // Colonne che stanno dentro i muri: (cols-1)/2*step ≤ halfX − margine.
  const cols = Math.max(1, Math.min(3, Math.floor(((halfX - ARENA_MARGIN) * 2) / step) + 1))
  const rowsPerTier = 3
  const perTier = cols * rowsPerTier

  const positions: CANNON.Vec3[] = []
  for (let i = 0; i < count; i++) {
    const tier = Math.floor(i / perTier)
    const slot = i % perTier
    const col = slot % cols
    const row = Math.floor(slot / cols)
    // jitter xz piccolo (±0.02): la varietà visiva la danno già velocità e
    // rotazioni random; un jitter ampio rimangerebbe il margine anti-overlap.
    const x = (col - (cols - 1) / 2) * step + rand(-0.02, 0.02)
    const z = PHYSICS.spawnZ - row * step + rand(-0.02, 0.02)
    const y = PHYSICS.spawnYBase - tier * PHYSICS.tierStepY + rand(0, PHYSICS.spawnYJitter)
    positions.push(new CANNON.Vec3(x, Math.max(y, PHYSICS.floorY + 0.5), z))
  }
  return positions
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
