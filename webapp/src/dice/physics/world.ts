// webapp/src/dice/physics/world.ts
import * as CANNON from 'cannon-es'
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
  const contact = new CANNON.ContactMaterial(diceMaterial, floorMaterial, {
    friction: PHYSICS.diceFloorFriction,
    restitution: PHYSICS.diceFloorRestitution,
  })
  world.addContactMaterial(contact)

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
    const wall = new CANNON.Body({ mass: 0, shape: new CANNON.Plane(), material: floorMaterial })
    wall.quaternion.setFromAxisAngle(def.axis, def.angle)
    wall.position.copy(def.pos)
    world.addBody(wall)
    walls.push(wall)
  }

  return { world, diceMaterial, floorMaterial, walls }
}

export function disposeDiceWorld(dw: DiceWorld): void {
  while (dw.world.bodies.length) {
    dw.world.removeBody(dw.world.bodies[0])
  }
}
