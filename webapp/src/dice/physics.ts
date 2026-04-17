import * as CANNON from 'cannon-es'
import * as THREE from 'three'

export interface DiceWorld {
  world: CANNON.World
  diceMaterial: CANNON.Material
  floorMaterial: CANNON.Material
}

const WORLD_HALF = 1.0
const WORLD_FLOOR_Y = -0.9

export function createDiceWorld(): DiceWorld {
  const world = new CANNON.World({ gravity: new CANNON.Vec3(0, -16, 0) })
  world.allowSleep = true
  world.defaultContactMaterial.friction = 0.45
  world.defaultContactMaterial.restitution = 0.25

  const diceMaterial = new CANNON.Material('dice')
  const floorMaterial = new CANNON.Material('floor')
  const contact = new CANNON.ContactMaterial(diceMaterial, floorMaterial, {
    friction: 0.5,
    restitution: 0.3,
  })
  world.addContactMaterial(contact)

  const floor = new CANNON.Body({
    mass: 0,
    shape: new CANNON.Plane(),
    material: floorMaterial,
  })
  floor.quaternion.setFromAxisAngle(new CANNON.Vec3(1, 0, 0), -Math.PI / 2)
  floor.position.set(0, WORLD_FLOOR_Y, 0)
  world.addBody(floor)

  const wallDefs: Array<{ pos: CANNON.Vec3; axis: CANNON.Vec3; angle: number }> = [
    { pos: new CANNON.Vec3(-WORLD_HALF, 0, 0), axis: new CANNON.Vec3(0, 1, 0), angle: Math.PI / 2 },
    { pos: new CANNON.Vec3(WORLD_HALF, 0, 0), axis: new CANNON.Vec3(0, 1, 0), angle: -Math.PI / 2 },
    { pos: new CANNON.Vec3(0, 0, -WORLD_HALF), axis: new CANNON.Vec3(0, 1, 0), angle: 0 },
    { pos: new CANNON.Vec3(0, 0, WORLD_HALF), axis: new CANNON.Vec3(0, 1, 0), angle: Math.PI },
  ]
  for (const def of wallDefs) {
    const wall = new CANNON.Body({ mass: 0, shape: new CANNON.Plane(), material: floorMaterial })
    wall.quaternion.setFromAxisAngle(def.axis, def.angle)
    wall.position.copy(def.pos)
    world.addBody(wall)
  }

  return { world, diceMaterial, floorMaterial }
}

export function disposeDiceWorld(dw: DiceWorld): void {
  while (dw.world.bodies.length) {
    dw.world.removeBody(dw.world.bodies[0])
  }
}

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
    sleepSpeedLimit: 0.18,
    sleepTimeLimit: 0.35,
    linearDamping: 0.15,
    angularDamping: 0.18,
  })
  body.position.copy(opts.position)
  const rand = (min: number, max: number) => Math.random() * (max - min) + min
  body.velocity.set(rand(-0.5, 0.5), rand(-0.3, 0.1), rand(-0.5, 0.5))
  body.angularVelocity.set(rand(-6, 6), rand(-6, 6), rand(-6, 6))
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

/** Find which face value is currently pointing toward `worldTarget` for a body with given quaternion. */
export function faceUp(
  faceNormals: Record<number, THREE.Vector3>,
  bodyQuat: THREE.Quaternion,
  worldTarget: THREE.Vector3 = new THREE.Vector3(0, 1, 0),
): number {
  const tmp = new THREE.Vector3()
  let bestValue = Number(Object.keys(faceNormals)[0])
  let bestDot = -Infinity
  for (const [value, normal] of Object.entries(faceNormals)) {
    tmp.copy(normal).applyQuaternion(bodyQuat)
    const dot = tmp.dot(worldTarget)
    if (dot > bestDot) {
      bestDot = dot
      bestValue = Number(value)
    }
  }
  return bestValue
}

/**
 * Build the body quaternion that aligns `targetFace` normal to `worldTarget`.
 * Default worldTarget is world +Y; pass a camera-facing direction to present the face to the camera.
 */
export function quaternionForFace(
  faceNormals: Record<number, THREE.Vector3>,
  targetFace: number,
  currentQuat: THREE.Quaternion,
  worldTarget: THREE.Vector3 = new THREE.Vector3(0, 1, 0),
): THREE.Quaternion {
  const targetNormal = faceNormals[targetFace]
  if (!targetNormal) return currentQuat.clone()
  const currentTargetWorld = targetNormal.clone().applyQuaternion(currentQuat).normalize()
  const desired = worldTarget.clone().normalize()
  const correction = new THREE.Quaternion().setFromUnitVectors(currentTargetWorld, desired)
  return correction.multiply(currentQuat)
}
