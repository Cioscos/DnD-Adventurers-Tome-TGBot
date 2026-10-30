// webapp/src/dice/physics/rollSimulation.ts
import * as CANNON from 'cannon-es'
import * as THREE from 'three'
import type { DetectedResult, DiceKind } from '../types'
import { getDiceGeometry } from '../geometries'
import { faceUp } from './faceDetector'
import { PHYSICS } from './constants'
import { computeSpawnPositions, spawnDiceBody, totalKineticActivity } from './spawner'
import type { DiceWorld } from './world'

type PhysicalKind = Exclude<DiceKind, 'd100'>

export interface SimDieSpec {
  kind: PhysicalKind
  groupIndex: number
}

export interface SimDie extends SimDieSpec {
  body: CANNON.Body
  retries: number
}

export type RollPhase = 'simulating' | 'settled'

export interface RollSimulation {
  readonly dice: SimDie[]
  readonly phase: RollPhase
  /** Avanza di un frame. Il delta è limitato: una pausa della pagina non conta come tempo di lancio. */
  advance(deltaSeconds: number): void
  /** Porta i dadi al risultato in pochi frame, sempre con la fisica vera. */
  skip(): void
  /** Valori delle facce visibili: validi solo a phase 'settled'. */
  results(): DetectedResult[]
  dispose(): void
}

const COS_15 = Math.cos((15 * Math.PI) / 180)
const MAX_RETRIES = 2
const RETRY_PUSH = 2
const RETRY_LIFT = 4.5
const MAX_FRAME_SECONDS = 1 / 15
const SKIP_FRAME_BUDGET_MS = 12
const SKIP_STEPS_PER_BATCH = 8

/** Finestra di controllo della posa: conta il movimento reale, non i picchi di velocità dei contatti. */
const POSE_WINDOW_MS = 300
const POSE_MAX_MOVE = 0.008
const POSE_MAX_ROTATION = 0.02

function quaternionOf(body: CANNON.Body): THREE.Quaternion {
  const q = body.quaternion
  return new THREE.Quaternion(q.x, q.y, q.z, q.w)
}

/**
 * Coppie davvero compenetrate: i centri sono più vicini della somma delle sfere
 * inscritte. Sotto questa distanza due convessi si intersecano per forza; sopra
 * possono semplicemente toccarsi (due d6 affiancati stanno a ~0.44).
 */
export function findOverlappingPairs(
  dice: Array<{ body: CANNON.Body; kind: PhysicalKind }>,
): Array<[number, number]> {
  const pairs: Array<[number, number]> = []
  for (let i = 0; i < dice.length; i++) {
    for (let j = i + 1; j < dice.length; j++) {
      const limit = (getDiceGeometry(dice[i].kind).inradius + getDiceGeometry(dice[j].kind).inradius) * 0.95
      if (dice[i].body.position.distanceTo(dice[j].body.position) < limit) pairs.push([i, j])
    }
  }
  return pairs
}

/** Separa le coppie compenetrate con un impulso lungo la congiungente. */
function separateOverlaps(dice: SimDie[]): boolean {
  const pairs = findOverlappingPairs(dice)
  const dir = new CANNON.Vec3()
  for (const [i, j] of pairs) {
    const a = dice[i].body
    const b = dice[j].body
    b.position.vsub(a.position, dir)
    const dist = dir.length()
    if (dist < 1e-4) dir.set(1, 0, 0)
    else dir.scale(1 / dist, dir)
    a.wakeUp()
    b.wakeUp()
    b.applyImpulse(new CANNON.Vec3(dir.x * 0.6, 0.25, dir.z * 0.6))
    a.applyImpulse(new CANNON.Vec3(-dir.x * 0.6, 0.25, -dir.z * 0.6))
  }
  return pairs.length > 0
}

export function createRollSimulation(dw: DiceWorld, specs: SimDieSpec[]): RollSimulation {
  const world = dw.world
  const positions = computeSpawnPositions(specs.length, dw)
  const dice: SimDie[] = specs.map((spec, i) => {
    const body = spawnDiceBody({
      shape: getDiceGeometry(spec.kind).shape,
      material: dw.diceMaterial,
      position: positions[i],
      totalCount: specs.length,
    })
    world.addBody(body)
    return { ...spec, body, retries: 0 }
  })

  const n = dice.length
  // Soglia per body, scala con numero dadi (più dadi = soglia più tollerante).
  const lowEnergyLimit = (n <= 3 ? 0.08 : n <= 8 ? 0.18 : 0.35) * n
  const lowEnergyTimeoutMs = n <= 3 ? 700 : 500

  let phase: RollPhase = 'simulating'
  let skipping = false
  let phaseMs = 0
  let totalMs = 0
  let lowEnergyMs = 0
  let poseMs = 0
  let repairUsed = false
  let pose = dice.map((d) => ({ position: d.body.position.clone(), quaternion: quaternionOf(d.body) }))

  const poseIsStill = (): boolean => {
    let still = true
    pose = dice.map((d, i) => {
      const quaternion = quaternionOf(d.body)
      if (
        d.body.position.distanceTo(pose[i].position) > POSE_MAX_MOVE ||
        quaternion.angleTo(pose[i].quaternion) > POSE_MAX_ROTATION
      ) {
        still = false
      }
      return { position: d.body.position.clone(), quaternion }
    })
    return still
  }

  const resetWatchers = () => {
    phaseMs = 0
    lowEnergyMs = 0
    poseMs = 0
    pose = dice.map((d) => ({ position: d.body.position.clone(), quaternion: quaternionOf(d.body) }))
  }

  /**
   * Rilegge TUTTI i dadi a ogni passaggio: un dado ritentato può urtarne uno già
   * fermo, quindi il valore si fissa solo quando nessuno deve più muoversi.
   */
  const readOrRetry = () => {
    let needRetry = false
    const canRetry = totalMs < PHYSICS.retryBudgetMs
    for (const d of dice) {
      const { dot } = faceUp(getDiceGeometry(d.kind).faceNormals, quaternionOf(d.body))
      if (dot >= COS_15 || d.retries >= MAX_RETRIES || !canRetry) continue
      // ambiguo (dado in pendenza, tipicamente appoggiato a un muro): spinta verso
      // il centro arena + lift, abbastanza da staccarlo e farlo ricadere piatto
      d.body.wakeUp()
      const px = d.body.position.x
      const pz = d.body.position.z
      const len = Math.hypot(px, pz) || 1
      d.body.applyImpulse(new CANNON.Vec3((-px / len) * RETRY_PUSH, RETRY_LIFT, (-pz / len) * RETRY_PUSH))
      d.body.angularVelocity.set(
        (Math.random() - 0.5) * 4,
        (Math.random() - 0.5) * 4,
        (Math.random() - 0.5) * 4,
      )
      d.retries += 1
      needRetry = true
    }
    if (needRetry) resetWatchers()
    else phase = 'settled'
  }

  const checkStop = (elapsedMs: number) => {
    phaseMs += elapsedMs
    totalMs += elapsedMs
    poseMs += elapsedMs

    const allSleeping = dice.every((d) => d.body.sleepState === CANNON.Body.SLEEPING)
    const timedOut = phaseMs > PHYSICS.simulationHardTimeoutMs || totalMs > PHYSICS.totalBudgetMs

    const activity = totalKineticActivity(dice.map((d) => d.body))
    lowEnergyMs = activity < lowEnergyLimit ? lowEnergyMs + elapsedMs : 0
    let stalled = lowEnergyMs >= lowEnergyTimeoutMs
    if (poseMs >= POSE_WINDOW_MS) {
      poseMs = 0
      if (poseIsStill()) stalled = true
    }

    if (!allSleeping && !timedOut && !stalled) return

    // Pila ferma ma ancora sovrapposta? Un solo tentativo di separazione
    // prima di congelare i dadi compenetrati.
    if (stalled && !timedOut && !repairUsed) {
      repairUsed = true
      if (separateOverlaps(dice)) {
        resetWatchers()
        return
      }
    }
    if (timedOut || stalled) for (const d of dice) d.body.sleep()
    readOrRetry()
  }

  // I timer contano il tempo fisico davvero simulato: cannon può fermarsi prima
  // dei substep richiesti su un dispositivo lento, e scarta il tempo residuo.
  const stepAndCheck = (seconds: number, maxSubSteps: number) => {
    const before = world.time
    world.step(PHYSICS.fixedTimeStep, seconds, maxSubSteps)
    checkStop((world.time - before) * 1000)
  }

  return {
    dice,
    get phase() {
      return phase
    },
    advance(deltaSeconds) {
      if (phase === 'settled') return
      if (skipping) {
        const started = performance.now()
        const batchSeconds = PHYSICS.fixedTimeStep * SKIP_STEPS_PER_BATCH
        do {
          stepAndCheck(batchSeconds, SKIP_STEPS_PER_BATCH)
        } while (phase === 'simulating' && performance.now() - started < SKIP_FRAME_BUDGET_MS)
        return
      }
      const seconds = Math.min(deltaSeconds, MAX_FRAME_SECONDS)
      // Substep fissi + accumulator: tempo reale anche a 120 Hz e penetrazione
      // per step dimezzata.
      stepAndCheck(seconds, PHYSICS.maxSubSteps)
    },
    skip() {
      skipping = true
    },
    results() {
      return dice.map((d) => ({
        groupIndex: d.groupIndex,
        kind: d.kind,
        value: faceUp(getDiceGeometry(d.kind).faceNormals, quaternionOf(d.body)).value,
      }))
    },
    dispose() {
      for (const d of dice) world.removeBody(d.body)
    },
  }
}
