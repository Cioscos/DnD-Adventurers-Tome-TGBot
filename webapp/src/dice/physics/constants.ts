// webapp/src/dice/physics/constants.ts
import * as CANNON from 'cannon-es'

export const PHYSICS = {
  gravity: new CANNON.Vec3(0, -16, 0),
  floorY: -0.9,
  ceilingY: 5,
  defaultFriction: 0.45,
  defaultRestitution: 0.25,
  diceFloorFriction: 0.5,
  diceFloorRestitution: 0.3,
  wallRestitution: 0.3,
  sleepSpeedLimit: 0.18,
  sleepTimeLimit: 0.35,
  linearDamping: 0.15,
  angularDamping: 0.18,
  throwLinearMin: -0.5,
  throwLinearMax: 0.5,
  throwAngularRange: 6,
  simulationHardTimeoutMs: 2400,
} as const
