// webapp/src/dice/physics/world.ts
import * as CANNON from 'cannon-es'
import * as THREE from 'three'
import { PHYSICS } from './constants'

export interface DiceWorld {
  world: CANNON.World
  diceMaterial: CANNON.Material
  floorMaterial: CANNON.Material
  walls: CANNON.Body[]
}

const WORLD_HALF = 1.0

export function createDiceWorld(): DiceWorld {
  const world = new CANNON.World({ gravity: PHYSICS.gravity.clone() })
  world.allowSleep = true
  world.defaultContactMaterial.friction = PHYSICS.defaultFriction
  world.defaultContactMaterial.restitution = PHYSICS.defaultRestitution

  const diceMaterial = new CANNON.Material('dice')
  const floorMaterial = new CANNON.Material('floor')
  const floorContact = new CANNON.ContactMaterial(diceMaterial, floorMaterial, {
    friction: PHYSICS.diceFloorFriction,
    restitution: PHYSICS.diceFloorRestitution,
  })
  world.addContactMaterial(floorContact)

  const wallMaterial = new CANNON.Material('wall')
  const wallContact = new CANNON.ContactMaterial(diceMaterial, wallMaterial, {
    friction: 0.05,
    restitution: PHYSICS.wallRestitution,
  })
  world.addContactMaterial(wallContact)

  const floor = new CANNON.Body({
    mass: 0,
    shape: new CANNON.Plane(),
    material: floorMaterial,
  })
  floor.quaternion.setFromAxisAngle(new CANNON.Vec3(1, 0, 0), -Math.PI / 2)
  floor.position.set(0, PHYSICS.floorY, 0)
  world.addBody(floor)

  const wallDefs: Array<{ pos: CANNON.Vec3; axis: CANNON.Vec3; angle: number }> = [
    { pos: new CANNON.Vec3(-WORLD_HALF, 0, 0), axis: new CANNON.Vec3(0, 1, 0), angle: Math.PI / 2 },
    { pos: new CANNON.Vec3(WORLD_HALF, 0, 0), axis: new CANNON.Vec3(0, 1, 0), angle: -Math.PI / 2 },
    { pos: new CANNON.Vec3(0, 0, -WORLD_HALF), axis: new CANNON.Vec3(0, 1, 0), angle: 0 },
    { pos: new CANNON.Vec3(0, 0, WORLD_HALF), axis: new CANNON.Vec3(0, 1, 0), angle: Math.PI },
  ]
  const walls: CANNON.Body[] = []
  for (const def of wallDefs) {
    const wall = new CANNON.Body({ mass: 0, shape: new CANNON.Plane(), material: wallMaterial })
    wall.quaternion.setFromAxisAngle(def.axis, def.angle)
    wall.position.copy(def.pos)
    world.addBody(wall)
    walls.push(wall)
  }

  // soffitto invisibile (impedisce ai dadi di volare via verso l'alto)
  const ceiling = new CANNON.Body({
    mass: 0,
    shape: new CANNON.Plane(),
    material: floorMaterial,
  })
  ceiling.quaternion.setFromAxisAngle(new CANNON.Vec3(1, 0, 0), Math.PI / 2)
  ceiling.position.set(0, PHYSICS.ceilingY, 0)
  world.addBody(ceiling)

  return { world, diceMaterial, floorMaterial, walls }
}

export function disposeDiceWorld(dw: DiceWorld): void {
  while (dw.world.bodies.length) {
    dw.world.removeBody(dw.world.bodies[0])
  }
}

/**
 * Riposiziona i 4 muri della box fisica così che coincidano con i bordi
 * dello schermo proiettati sul piano floor (y = PHYSICS.floorY).
 *
 * Calcola intersezione tra i raggi camera→edge-screen e il piano floor,
 * poi sposta i muri (mantenendo le orientazioni esistenti, [-X, +X, -Z, +Z]).
 */
export function updateWalls(dw: DiceWorld, camera: THREE.PerspectiveCamera, size: { width: number; height: number }): void {
  if (dw.walls.length !== 4) return
  const halfX = computeProjectedHalfExtent(camera, size, 'x')
  const halfZ = computeProjectedHalfExtent(camera, size, 'z')
  // walls order definita in createDiceWorld: [-X, +X, -Z, +Z]
  dw.walls[0].position.set(-halfX, 0, 0)
  dw.walls[1].position.set(halfX, 0, 0)
  dw.walls[2].position.set(0, 0, -halfZ)
  dw.walls[3].position.set(0, 0, halfZ)
}

function computeProjectedHalfExtent(
  camera: THREE.PerspectiveCamera,
  _size: { width: number; height: number },
  axis: 'x' | 'z',
): number {
  // raycast da centro camera verso edge-NDC (±1 sull'asse target), interseca con piano floor
  const ndcEdge = axis === 'x' ? new THREE.Vector3(1, 0, 0.5) : new THREE.Vector3(0, -1, 0.5)
  const worldEdge = ndcEdge.clone().unproject(camera)
  const dir = worldEdge.sub(camera.position).normalize()
  // y = PHYSICS.floorY → t = (floorY - cam.y) / dir.y
  const FLOOR = -0.9
  const t = (FLOOR - camera.position.y) / dir.y
  const hit = camera.position.clone().addScaledVector(dir, t)
  return Math.abs(axis === 'x' ? hit.x : hit.z)
}
