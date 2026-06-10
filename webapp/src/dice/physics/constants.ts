// webapp/src/dice/physics/constants.ts
import * as CANNON from 'cannon-es'

export const PHYSICS = {
  gravity: new CANNON.Vec3(0, -32, 0),
  floorY: -0.9,
  ceilingY: 5,
  // Substep fisso + accumulator (world.step a 3 argomenti): la sim resta in
  // tempo reale su display 60/120 Hz e la penetrazione per step si dimezza.
  fixedTimeStep: 1 / 120,
  maxSubSteps: 5,
  solverIterations: 14,
  solverTolerance: 1e-3,
  defaultFriction: 0.4,
  // cannon-es applica la restituzione anche ai contatti a riposo (nessuna
  // soglia di velocità): valori alti iniettano energia → micro-rimbalzi.
  defaultRestitution: 0.15,
  diceFloorFriction: 0.4,
  diceFloorRestitution: 0.3,
  wallFriction: 0.2,
  wallRestitution: 0.35,
  sleepSpeedLimit: 0.25,
  sleepTimeLimit: 0.4,
  linearDamping: 0.12,
  angularDamping: 0.2,
  throwLinearMin: 4,
  throwLinearMax: 7,
  throwAngularRange: 25,
  simulationHardTimeoutMs: 5000,
  spawnConeDeg: 20,
  spawnYBase: 3.5,
  spawnYJitter: 0.15,
  spawnZ: 1.0,
  // Passo griglia spawn: 0.8 − 2×jitter(0.02) = 0.76 = diametro dado
  // (2 × TARGET_CIRCUMRADIUS): i dadi non devono MAI nascere compenetrati.
  spawnStep: 0.8,
  // Tier verticali DISCENDENTI; col jitter (≤0.15) il gap resta > diametro.
  tierStepY: 0.95,
} as const
