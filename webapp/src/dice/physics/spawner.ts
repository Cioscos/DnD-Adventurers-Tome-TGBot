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
  const rand = (min: number, max: number) => Math.random() * (max - min) + min
  const lo = PHYSICS.throwLinearMin
  const hi = PHYSICS.throwLinearMax
  body.velocity.set(rand(lo, hi), rand(-0.3, 0.1), rand(lo, hi))
  const a = PHYSICS.throwAngularRange
  body.angularVelocity.set(rand(-a, a), rand(-a, a), rand(-a, a))
  body.quaternion.setFromEuler(rand(0, Math.PI * 2), rand(0, Math.PI * 2), rand(0, Math.PI * 2))
  return body
}

export function computeSpawnPositions(count: number): CANNON.Vec3[] {
  const positions: CANNON.Vec3[] = []
  for (let i = 0; i < count; i++) {
    const angle = count > 1 ? (i / count) * Math.PI * 2 + Math.random() * 0.2 : 0
    const radius = count === 1 ? 0 : count <= 3 ? 0.35 : 0.55
    const x = Math.cos(angle) * radius + (Math.random() - 0.5) * 0.1
    const z = Math.sin(angle) * radius + (Math.random() - 0.5) * 0.1
    const y = 1.6 + Math.random() * 0.4
    positions.push(new CANNON.Vec3(x, y, z))
  }
  return positions
}

export function diceScaleForCount(count: number): number {
  return SIZE_BY_COUNT(count)
}
