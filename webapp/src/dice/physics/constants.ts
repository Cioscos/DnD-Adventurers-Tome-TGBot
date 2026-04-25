// webapp/src/dice/physics/constants.ts
import * as CANNON from 'cannon-es'

export const PHYSICS = {
  gravity: new CANNON.Vec3(0, -32, 0),
  floorY: -0.9,
  ceilingY: 5,
  defaultFriction: 0.4,
  defaultRestitution: 0.25,
  diceFloorFriction: 0.4,
  diceFloorRestitution: 0.55,
  wallRestitution: 0.7,
  sleepSpeedLimit: 0.05,
  sleepTimeLimit: 0.6,
  linearDamping: 0.1,
  angularDamping: 0.1,
  throwLinearMin: 4,
  throwLinearMax: 7,
  throwAngularRange: 25,
  simulationHardTimeoutMs: 5000,
  spawnConeDeg: 20,
  spawnYBase: 3.5,
  spawnYJitter: 0.4,
  spawnZ: 1.0,
  spawnXSpread: 0.3,
  spawnXOffsetPerDie: 0.3,
} as const
