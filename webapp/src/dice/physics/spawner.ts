// webapp/src/dice/physics/spawner.ts
import * as CANNON from 'cannon-es'
import { PHYSICS } from './constants'

export interface SpawnOptions {
  shape: CANNON.ConvexPolyhedron
  material: CANNON.Material
  position: CANNON.Vec3
  scale?: number
}

const SIZE_BY_COUNT = (n: number) => (n <= 1 ? 0.75 : n <= 3 ? 0.65 : n <= 6 ? 0.55 : 0.48)

const rand = (min: number, max: number) => Math.random() * (max - min) + min

export function spawnDiceBody(opts: SpawnOptions): CANNON.Body {
  const body = new CANNON.Body({
    mass: 1,
    shape: opts.shape,
    material: opts.material,
    allowSleep: true,
    sleepSpeedLimit: PHYSICS.sleepSpeedLimit,
    sleepTimeLimit: PHYSICS.sleepTimeLimit,
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

export function computeSpawnPositions(count: number): CANNON.Vec3[] {
  const positions: CANNON.Vec3[] = []
  for (let i = 0; i < count; i++) {
    const xOffset = (i - (count - 1) / 2) * PHYSICS.spawnXOffsetPerDie
    const x = xOffset + rand(-PHYSICS.spawnXSpread, PHYSICS.spawnXSpread) * 0.3
    const y = PHYSICS.spawnYBase + Math.random() * PHYSICS.spawnYJitter
    const z = PHYSICS.spawnZ + (Math.random() - 0.5) * 0.1
    positions.push(new CANNON.Vec3(x, y, z))
  }
  return positions
}

export function diceScaleForCount(count: number): number {
  return SIZE_BY_COUNT(count)
}
