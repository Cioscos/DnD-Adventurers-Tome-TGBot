# 3D Dice Revamp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trasformare il sistema dadi 3D in fisica naturale "stile D&D Beyond" (risultato letto dalla geometria), con lanci più forti e bordi-schermo come muri, supporto a texture pack UV-mapped (PBR opzionale, fallback a default), nuova API `POST /dice/result`, fallback non-3D via `crypto.getRandomValues`, e FAB nascosto sulla pagina settings.

**Architecture:** Tutto il lavoro vive nella webapp (`webapp/src/dice/`) salvo il cambio API in `api/routers/dice.py`. La fisica `cannon-es` viene retunata e estratta in moduli (`physics/world.ts`, `spawner.ts`, `faceDetector.ts`, `constants.ts`). Le geometrie ricevono UV per supportare texture singole UV-mapped. I pack vivono come asset bundled in `webapp/public/dice-packs/<id>/` e sono caricati lazy via `THREE.TextureLoader`. Il flusso roll è unificato in `useRollAndPersist`: 3D-physics-driven o `crypto.getRandomValues`-driven a seconda di `animate3d` + reduced-motion.

**Tech Stack:** React + TypeScript + Vite, three.js + @react-three/fiber + @react-three/drei, cannon-es 0.20.0, Zustand (store), TanStack Query (mutations), Zod (manifest validation), FastAPI + Pydantic v2 (backend), pytest non disponibile in repo (verifica manuale + `npx tsc --noEmit` + `python -m py_compile`).

**Spec di riferimento:** `docs/superpowers/specs/2026-04-25-3d-dice-revamp-design.md`.

**Branch corrente:** `feat/3d-dice-revamp`.

**Vincoli ambiente (CLAUDE.md):**
- WSL: **mai** eseguire `uv sync`, `uv run`, `uv venv` (corrompe `.venv` Windows). Verifica Python = solo `python3 -m py_compile` (syntax check) + utente esegue server da Windows per integration test.
- Webapp deve essere ribuilt prima del commit (`cd webapp && npm run build:prod`) e `docs/app/` committato a fine plan.

**Convenzioni di commit:** Conventional Commits (`feat:`, `refactor:`, `chore:`, `docs:`). Co-Author trailer come negli altri commit del repo.

---

## File map

### Modificati (esistenti)

- `webapp/src/dice/types.ts` — esteso (`PackId`, `DetectedResult`, `DicePlayRequest.groups[].results` opzionale)
- `webapp/src/dice/DiceScene.tsx` — phase order, camera, output `onComplete`, consumo pack via context
- `webapp/src/dice/DiceAnimationProvider.tsx` — esteso per esporre callback risultati e wrappare `DicePackProvider`
- `webapp/src/dice/geometries/index.ts` — aggiunge UV + `computeTangents`
- `webapp/src/dice/materials.ts` — accetta pack, produce material PBR composito
- `webapp/src/dice/numeralTexture.ts` — accetta override colori da pack tints (signature retro-compatibile)
- `webapp/src/store/diceSettings.ts` — aggiunge `packId`
- `webapp/src/components/DiceOverlay.tsx` — usa `useRollAndPersist`, FAB hide su `/char/:id/settings`
- `webapp/src/pages/Dice.tsx` — usa `useRollAndPersist`
- `webapp/src/pages/Settings.tsx` — aggiunge sezione pack selector
- `webapp/src/locales/it.json`, `en.json` — chiavi i18n nuove
- `webapp/src/api/client.ts` — sostituisce `dice.roll` con `dice.result`
- `api/routers/dice.py` — rimuove `/dice/roll`, aggiunge `/dice/result`
- `api/schemas/common.py` — aggiunge `DiceResultRequest`, `DiceResultEntry` (oppure file dedicato `api/schemas/dice.py`)

### Eliminati

- `webapp/src/dice/physics.ts` — il contenuto si sposta in `physics/world.ts`, `physics/spawner.ts`, `physics/faceDetector.ts`. Il file diventa redirect-only (re-export per backward import) o eliminato (preferito) dopo refactor.

### Creati

- `webapp/src/dice/physics/world.ts`
- `webapp/src/dice/physics/spawner.ts`
- `webapp/src/dice/physics/faceDetector.ts`
- `webapp/src/dice/physics/constants.ts`
- `webapp/src/dice/geometries/uvLayouts.ts`
- `webapp/src/dice/packs/manifest.ts`
- `webapp/src/dice/packs/registry.ts`
- `webapp/src/dice/packs/loader.ts`
- `webapp/src/dice/packs/DicePackProvider.tsx`
- `webapp/src/dice/rng.ts`
- `webapp/src/dice/useRollAndPersist.ts`
- `webapp/scripts/generate-uv-templates.mjs`
- `webapp/public/dice-packs/default/pack.json`
- `webapp/public/dice-packs/_templates/d4.uv.png`, `d6.uv.png`, `d8.uv.png`, `d10.uv.png`, `d12.uv.png`, `d20.uv.png`
- `webapp/public/dice-packs/_templates/README.md`

---

## Task ordering and dependencies

Le tasks sono ordinate in 6 fasi con dipendenze chiare. Ogni fase termina con almeno un commit + verifica `tsc`. La fase 8 (build prod) è l'ultimo gate prima del merge.

- **Phase 1 (Task 1–2):** Setup struttura `physics/` e costanti → preparatorio, niente cambio comportamento.
- **Phase 2 (Task 3–6):** Fisica retunata + risultato geometrico → comportamento utente cambia.
- **Phase 3 (Task 7–9):** UV layout + templates → comportamento utente invariato (UV non ancora usate).
- **Phase 4 (Task 10–13):** Texture pack system + integrazione DiceScene → comportamento utente: nuovo pack `default`, identico ad oggi.
- **Phase 5 (Task 14–17):** API change + nuovo roll flow → comportamento utente: vecchio endpoint rimosso.
- **Phase 6 (Task 18–20):** FAB hide + Settings pack selector + build prod.

---

## Phase 1 — Struttura modulare

### Task 1: Estrai physics in sottocartella + crea `constants.ts`

**Files:**
- Create: `webapp/src/dice/physics/world.ts`
- Create: `webapp/src/dice/physics/spawner.ts`
- Create: `webapp/src/dice/physics/faceDetector.ts`
- Create: `webapp/src/dice/physics/constants.ts`
- Delete: `webapp/src/dice/physics.ts` (contenuto migrato)
- Modify: `webapp/src/dice/DiceScene.tsx` (aggiorna import path da `./physics` a `./physics/world` e `./physics/spawner`)

- [ ] **Step 1: Crea `physics/constants.ts` con costanti correnti (pre-tune)**

```ts
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
```

(I valori "tunati" arrivano in Task 3 — qui solo migrazione.)

- [ ] **Step 2: Crea `physics/world.ts` con `createDiceWorld` + `disposeDiceWorld`**

Sposta esattamente il contenuto da `webapp/src/dice/physics.ts` (righe 1-56), usando `PHYSICS` per le costanti.

```ts
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
```

- [ ] **Step 3: Crea `physics/spawner.ts` con `spawnDiceBody`, `computeSpawnPositions`, `diceScaleForCount`**

Sposta esattamente da `physics.ts` (righe 58-101), usando `PHYSICS` per costanti random.

```ts
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
```

- [ ] **Step 4: Crea `physics/faceDetector.ts` con `faceUp` (move) + `quaternionForFace` (move)**

Sposta esattamente da `physics.ts` (righe 103-139). `quaternionForFace` resta esportata per ora (sarà rimossa in Task 5 quando snapping sparisce).

```ts
// webapp/src/dice/physics/faceDetector.ts
import * as THREE from 'three'

export function faceUp(
  faceNormals: Record<number, THREE.Vector3>,
  bodyQuat: THREE.Quaternion,
  worldTarget: THREE.Vector3 = new THREE.Vector3(0, 1, 0),
): { value: number; dot: number } {
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
  return { value: bestValue, dot: bestDot }
}

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
```

**Note:** `faceUp` ora restituisce `{value, dot}` invece di solo `value` — più informativo, serve in Task 5. Aggiorna i call site sotto.

- [ ] **Step 5: Aggiorna import in `DiceScene.tsx`**

Modifica l'import in `webapp/src/dice/DiceScene.tsx:9-15` da:

```ts
import {
  createDiceWorld,
  spawnDiceBody,
  computeSpawnPositions,
  quaternionForFace,
  type DiceWorld,
} from './physics'
```

A:

```ts
import { createDiceWorld, type DiceWorld } from './physics/world'
import { spawnDiceBody, computeSpawnPositions } from './physics/spawner'
import { quaternionForFace } from './physics/faceDetector'
```

(Non altrove usato `physics`. Verifica con grep.)

- [ ] **Step 6: Cancella `webapp/src/dice/physics.ts`**

```bash
rm webapp/src/dice/physics.ts
```

- [ ] **Step 7: Verifica TypeScript**

```bash
cd webapp && npx tsc --noEmit
```

Expected: nessun errore.

- [ ] **Step 8: Commit**

```bash
git add webapp/src/dice/physics/ webapp/src/dice/DiceScene.tsx
git rm webapp/src/dice/physics.ts
git commit -m "$(cat <<'EOF'
refactor(dice): extract physics into physics/ subfolder

Split physics.ts into world.ts, spawner.ts, faceDetector.ts, constants.ts.
faceUp now returns {value, dot} for orientation-ambiguity logic in Task 5.
No behavior change.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Tuning costanti fisica + soffitto

**Files:**
- Modify: `webapp/src/dice/physics/constants.ts`
- Modify: `webapp/src/dice/physics/world.ts` (aggiungi soffitto)

- [ ] **Step 1: Aggiorna `constants.ts` con valori spec**

Sostituisci interamente il contenuto di `constants.ts`:

```ts
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
```

- [ ] **Step 2: Aggiungi soffitto invisibile a `world.ts`**

Modifica `createDiceWorld()` in `webapp/src/dice/physics/world.ts` per aggiungere un `Plane` body a `y = PHYSICS.ceilingY` con normale verso il basso. Inseriscilo dopo i 4 muri (prima del `return`):

```ts
// soffitto invisibile (impedisce ai dadi di volare via verso l'alto)
const ceiling = new CANNON.Body({
  mass: 0,
  shape: new CANNON.Plane(),
  material: floorMaterial,
})
ceiling.quaternion.setFromAxisAngle(new CANNON.Vec3(1, 0, 0), Math.PI / 2)
ceiling.position.set(0, PHYSICS.ceilingY, 0)
world.addBody(ceiling)
```

Aggiungi la `wallRestitution` al ContactMaterial dei walls. Modifica la creazione del `ContactMaterial` per usare due materiali distinti (dice ↔ wall vs dice ↔ floor):

```ts
// Sostituisci la creazione di un solo `ContactMaterial` con due:
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
```

Poi cambia il loop walls per usare `wallMaterial` invece di `floorMaterial`. Esporta `wallMaterial` nel `DiceWorld` interface se serve altrove (per ora no, basta locale).

- [ ] **Step 3: Verifica TypeScript**

```bash
cd webapp && npx tsc --noEmit
```

Expected: nessun errore.

- [ ] **Step 4: Verifica visiva manuale**

```bash
cd webapp && npm run dev
```

Apri http://localhost:5173/, vai su `/char/<id>/dice`, tira un d20. Aspettati: dadi cadono più in fretta, rimbalzano più visibilmente, restano dentro l'area. Sleep tempo finale leggermente più lungo (60ms in più vs prima).

- [ ] **Step 5: Commit**

```bash
git add webapp/src/dice/physics/constants.ts webapp/src/dice/physics/world.ts
git commit -m "$(cat <<'EOF'
feat(dice): tune physics constants for stronger throws & wall bounce

Gravity -32, throw 4-7, restitution floor 0.55 / wall 0.7,
sleep limits tighter for accurate face read in next task.
Add invisible ceiling at y=5.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 2 — Lancio + risultato dalla geometria

### Task 3: Spawner riprogettato (lancio "vero")

**Files:**
- Modify: `webapp/src/dice/physics/spawner.ts`

- [ ] **Step 1: Sostituisci `spawnDiceBody` e `computeSpawnPositions`**

Riscrivi `webapp/src/dice/physics/spawner.ts` interamente:

```ts
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
```

- [ ] **Step 2: Verifica TypeScript**

```bash
cd webapp && npx tsc --noEmit
```

- [ ] **Step 3: Verifica visiva**

`npm run dev`, tira 1, 2, 5 dadi. Aspettati: dadi spawnano lato +Z, lanciati verso -Z (lontano dal player), spin marcato in volo, atterrano dopo ~0.5-1.5s, rotolano e si fermano. Niente compenetrazioni iniziali.

- [ ] **Step 4: Commit**

```bash
git add webapp/src/dice/physics/spawner.ts
git commit -m "$(cat <<'EOF'
feat(dice): redesign spawn — throw forward with cone spread

Position dice on player side (+Z), throw direction (0,0,-1) ± 20° yaw,
linear speed 4-7, multi-die offset to prevent initial compenetration.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Walls dinamiche da viewport

**Files:**
- Modify: `webapp/src/dice/physics/world.ts` (aggiungi `updateWalls`)
- Modify: `webapp/src/dice/DiceScene.tsx` (chiama `updateWalls` su resize)

- [ ] **Step 1: Aggiungi `updateWalls` a `world.ts`**

Append in fondo a `webapp/src/dice/physics/world.ts`:

```ts
import * as THREE from 'three'

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
  size: { width: number; height: number },
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
```

(`PHYSICS.floorY` non importato per evitare ciclo ridicolo; valore literal `-0.9` allineato a `PHYSICS.floorY`. Se cambi `floorY` in `constants.ts`, aggiornare anche qui — non dimenticare.)

- [ ] **Step 2: Aggiorna `DiceScene.tsx` per chiamare `updateWalls` quando viewport cambia**

In `webapp/src/dice/DiceScene.tsx`, modifica `Orchestrator` per sincronizzare i walls. Aggiungi dopo il blocco `if (!worldRef.current) worldRef.current = createDiceWorld()`:

```ts
const { invalidate, camera, size } = useThree()
useEffect(() => {
  if (!(camera instanceof THREE.PerspectiveCamera)) return
  updateWalls(worldRef.current!, camera, size)
}, [camera, size.width, size.height])
```

E aggiungi import:

```ts
import { createDiceWorld, updateWalls, type DiceWorld } from './physics/world'
```

(Sostituisci la dichiarazione esistente `const { invalidate, camera } = useThree()` esistente in linea 105 — ora include `size`.)

- [ ] **Step 3: Verifica TypeScript**

```bash
cd webapp && npx tsc --noEmit
```

- [ ] **Step 4: Verifica visiva**

`npm run dev`, apri DevTools, ridimensiona browser durante un roll: dadi non escono dallo schermo. Su mobile (DevTools mobile mode) i dadi rimbalzano contro i bordi del viewport.

- [ ] **Step 5: Commit**

```bash
git add webapp/src/dice/physics/world.ts webapp/src/dice/DiceScene.tsx
git commit -m "$(cat <<'EOF'
feat(dice): walls follow screen edges (raycast viewport → floor)

updateWalls reprojects screen edges onto floor plane and repositions
the 4 wall bodies. DiceScene calls it on size/camera change.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Phase order: rimuovi `snapping`, aggiungi `reading`

**Files:**
- Modify: `webapp/src/dice/DiceScene.tsx`
- Modify: `webapp/src/dice/types.ts` (aggiunge `DetectedResult`)

- [ ] **Step 1: Aggiungi `DetectedResult` + `count` a `types.ts`, lascia `play` invariato**

Modifica `webapp/src/dice/types.ts`. Aggiunge `DetectedResult`, rende `results` opzionale, aggiunge `count` opzionale come hint per il provider quando `results` è assente. **Non cambia `DiceAnimationApi.play`** (resta `Promise<void>`) per non rompere i consumer; `playAndCollect` viene aggiunto in Task 16.

```ts
export type DiceKind = 'd4' | 'd6' | 'd8' | 'd10' | 'd12' | 'd20' | 'd100'

export type DiceTint = 'normal' | 'crit' | 'fumble' | 'arcane' | 'ember'

export interface DiceGroup {
  kind: DiceKind
  /** Opzionale: se presente, attivava lo snap legacy (rimosso). Ora ignorato. */
  results?: number[]
  /** Numero di body fisici da spawnare quando results è assente. Default: 1. */
  count?: number
  tint?: DiceTint
  label?: string
}

export interface DicePlayRequest {
  groups: DiceGroup[]
  interGroupMs?: number
}

export interface DetectedResult {
  groupIndex: number
  kind: Exclude<DiceKind, 'd100'>
  value: number
}

export interface DiceAnimationApi {
  play: (req: DicePlayRequest) => Promise<void>
  isPlaying: boolean
}
```

- [ ] **Step 2: Riscrivi orchestrazione phase in `DiceScene.tsx`**

Riscrivi i blocchi phase in `Orchestrator` con `idle | simulating | reading | holding`. Cambia anche il tipo `Phase` (riga 19) e il blocco `useFrame`. Codice completo del blocco:

```ts
type Phase = 'idle' | 'simulating' | 'reading' | 'holding'

interface Entity {
  body: CANNON.Body
  group: THREE.Group | null
  detectedValue: number | null
  retries: number
  kind: Exclude<DiceKind, 'd100'>
}
```

Sostituisci l'intero corpo di `useFrame(() => { ... })` (righe ~161-269) con:

```ts
useFrame(() => {
  if (phaseRef.current === 'idle') return
  const now = performance.now()
  const elapsed = now - phaseStartRef.current
  const world = worldRef.current!.world

  if (phaseRef.current === 'simulating') {
    world.step(1 / 60)
    for (const e of entitiesRef.current) {
      if (e.group) {
        e.group.position.set(e.body.position.x, e.body.position.y, e.body.position.z)
        e.group.quaternion.set(
          e.body.quaternion.x,
          e.body.quaternion.y,
          e.body.quaternion.z,
          e.body.quaternion.w,
        )
      }
    }
    const allSleeping = entitiesRef.current.every(
      (e) => e.body.sleepState === CANNON.Body.SLEEPING,
    )
    const timedOut = elapsed > PHYSICS.simulationHardTimeoutMs
    if (allSleeping || timedOut) {
      if (timedOut) for (const e of entitiesRef.current) e.body.sleep()
      phaseRef.current = 'reading'
      phaseStartRef.current = now
    }
    return
  }

  if (phaseRef.current === 'reading') {
    const COS_15 = Math.cos((15 * Math.PI) / 180)
    const MAX_RETRIES = 2
    let needRetry = false
    for (const e of entitiesRef.current) {
      if (e.detectedValue !== null) continue
      const geomData = getDiceGeometry(e.kind)
      const q = new THREE.Quaternion(
        e.body.quaternion.x,
        e.body.quaternion.y,
        e.body.quaternion.z,
        e.body.quaternion.w,
      )
      const { value, dot } = faceUp(geomData.faceNormals, q)
      if (dot < COS_15 && e.retries < MAX_RETRIES) {
        // ambiguo: nudge + re-simulate
        e.body.wakeUp()
        e.body.applyImpulse(
          new CANNON.Vec3((Math.random() - 0.5) * 0.4, -0.3, (Math.random() - 0.5) * 0.4),
          new CANNON.Vec3(0, 0.1, 0),
        )
        e.body.angularVelocity.set(
          (Math.random() - 0.5) * 4,
          (Math.random() - 0.5) * 4,
          (Math.random() - 0.5) * 4,
        )
        e.retries += 1
        needRetry = true
      } else {
        e.detectedValue = value
      }
    }
    if (needRetry) {
      phaseRef.current = 'simulating'
      phaseStartRef.current = now
    } else {
      phaseRef.current = 'holding'
      phaseStartRef.current = now
    }
    return
  }

  if (phaseRef.current === 'holding') {
    const HOLD_MS = 1500
    const LIFT_IN = 220
    const LIFT_OUT = 300
    const SCALE_BOOST = 0.22
    let progress: number
    if (elapsed < LIFT_IN) {
      const t = elapsed / LIFT_IN
      progress = 1 - Math.pow(1 - t, 2)
    } else if (elapsed < HOLD_MS - LIFT_OUT) {
      progress = 1
    } else {
      const t = Math.min(1, (elapsed - (HOLD_MS - LIFT_OUT)) / LIFT_OUT)
      progress = 1 - (1 - Math.pow(1 - t, 2))
    }
    const scale = 1 + SCALE_BOOST * progress
    entitiesRef.current.forEach((e) => {
      if (!e.group) return
      e.group.scale.setScalar(scale)
    })
    if (elapsed > HOLD_MS) {
      phaseRef.current = 'idle'
      // emetti risultati al consumer
      const results: DetectedResult[] = entitiesRef.current.map((e, i) => ({
        groupIndex: i,
        kind: e.kind,
        value: e.detectedValue ?? 1,
      }))
      onCompleteRef.current?.(results)
    }
  }
})
```

- [ ] **Step 3: Aggiorna setup spawn entities (rimuovi `targetFace`, aggiungi `detectedValue` + `retries`)**

Sostituisci il blocco di setup entities nel `useEffect(() => { ... }, [request, invalidate])` (righe 113-159). Codice nuovo:

```ts
useEffect(() => {
  if (!request) return
  const world = worldRef.current!.world

  for (const e of entitiesRef.current) world.removeBody(e.body)
  entitiesRef.current = []

  const group = request.group
  const kindBase: Exclude<DiceKind, 'd100'> = group.kind === 'd100' ? 'd10' : group.kind
  const geomData = getDiceGeometry(kindBase)

  // numero di body fisici da spawnare
  const bodyCount = group.kind === 'd100' ? 2 : group.results?.length ?? 1

  const positions = computeSpawnPositions(bodyCount)
  const entities: Entity[] = []
  for (let i = 0; i < bodyCount; i++) {
    const body = spawnDiceBody({
      shape: geomData.shape,
      material: worldRef.current!.diceMaterial,
      position: positions[i],
    })
    world.addBody(body)
    entities.push({ body, group: null, detectedValue: null, retries: 0, kind: kindBase })
  }
  entitiesRef.current = entities
  phaseRef.current = 'simulating'
  phaseStartRef.current = performance.now()
  setVersion((v) => v + 1)

  let raf = 0
  const tick = () => {
    invalidate()
    if (phaseRef.current !== 'idle') raf = requestAnimationFrame(tick)
  }
  tick()
  return () => cancelAnimationFrame(raf)
}, [request, invalidate])
```

- [ ] **Step 4: Aggiungi `onCompleteRef` e modifica `SceneRequest`**

Modifica `SceneRequest` (riga 17) e aggiungi ref. Sostituisci:

```ts
export type SceneRequest = { id: number; group: DiceGroup; onComplete: () => void }
```

con:

```ts
export type SceneRequest = {
  id: number
  group: DiceGroup
  onComplete: (results: DetectedResult[]) => void
}
```

E nell'`Orchestrator`, aggiungi:

```ts
const onCompleteRef = useRef<((results: DetectedResult[]) => void) | undefined>(undefined)
useEffect(() => {
  onCompleteRef.current = request?.onComplete
}, [request])
```

Rimuovi tutte le ref legate a `snapping` (`snapFromRef`, `snapToRef`, `snapFromPosRef`, `snapToPosRef`).

- [ ] **Step 5: Aggiorna gli import in `DiceScene.tsx`**

```ts
import { faceUp } from './physics/faceDetector'
import { PHYSICS } from './physics/constants'
import type { DetectedResult } from './types'
```

Rimuovi l'import di `quaternionForFace` (non più usato in DiceScene).

- [ ] **Step 6: Aggiorna `DiceAnimationProvider.tsx` per accettare il callback nuovo**

Apri `webapp/src/dice/DiceAnimationProvider.tsx` e trova dove costruisce il `SceneRequest`. Cambia il `onComplete` per accettare `results: DetectedResult[]` e ignorarli (sono usati solo da `playAndCollect`, aggiunto in Task 16):

```tsx
import type { DetectedResult } from './types'
// ... dove crea SceneRequest:
onComplete: (_results: DetectedResult[]) => {
  // Task 5 wiring: ignora i risultati, restituisce solo void.
  // Task 16 introdurrà playAndCollect che li propaga al consumer.
  resolveCurrent?.()
},
```

(`resolveCurrent` o equivalente nome dipende dal codice esistente — adatta.)

- [ ] **Step 7: Verifica TypeScript**

```bash
cd webapp && npx tsc --noEmit
```

Expected: nessun errore. Se ne hai, sono nei consumer (`DiceOverlay.tsx`, `Dice.tsx`) che ancora passano `results: number[]` a `play()`. Soluzione temporanea: lascia `results` opzionale (già fatto in Step 1 — il campo è ignorato).

- [ ] **Step 8: Verifica visiva**

`npm run dev`, tira un d20. Dadi atterrano, NON snappano più (rotation finale = quella naturale dopo simulazione). La faccia in alto è la lettura della geometria.

Apri Console e ispeziona log: console.log temporaneo del `value` letto in `reading` phase aiuta a verificare che la lettura funzioni. Aggiungi temporaneamente:

```ts
console.debug('[dice] detected', { kind: e.kind, value, dot })
```

(Da rimuovere prima del commit finale del plan.)

- [ ] **Step 9: Commit**

```bash
git add webapp/src/dice/types.ts webapp/src/dice/DiceScene.tsx webapp/src/dice/DiceAnimationProvider.tsx
git commit -m "$(cat <<'EOF'
feat(dice): replace snapping with reading phase, results from geometry

Phase order: simulating → reading → holding (no snap).
faceUp returns {value, dot}; dot < cos(15°) triggers nudge + re-simulate
(max 2 retries per body). Results flow through SceneRequest.onComplete.

DiceGroup.results now optional (provider passes count, not values).
DiceAnimationApi.play return type unchanged (still Promise<void>) to keep
consumers compiling; result propagation lands in Task 17.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Camera top-down

**Files:**
- Modify: `webapp/src/dice/DiceScene.tsx`

- [ ] **Step 1: Cambia camera position e fov**

In `webapp/src/dice/DiceScene.tsx`, modifica le righe 40-41 (Canvas camera setup) da:

```tsx
camera={{ position: [0, 2.2, 2.4], fov: 70, near: 0.1, far: 30 }}
onCreated={({ camera }) => camera.lookAt(0, -0.4, 0)}
```

a:

```tsx
camera={{ position: [0, 5.5, 1.8], fov: 42, near: 0.1, far: 30 }}
onCreated={({ camera }) => camera.lookAt(0, 0, 0)}
```

E modifica `CameraFit` (riga 77-91) per regolare il target half-width per il nuovo angolo. Sostituisci il corpo:

```ts
function CameraFit() {
  const { camera, size } = useThree()
  useEffect(() => {
    if (!(camera instanceof THREE.PerspectiveCamera)) return
    const aspect = size.width / Math.max(size.height, 1)
    camera.aspect = aspect
    camera.updateProjectionMatrix()
  }, [camera, size.width, size.height])
  return null
}
```

(`updateWalls` calcola già la dimensione physical effettiva, non serve fittare il fov a un half-width.)

- [ ] **Step 2: Verifica visiva**

`npm run dev`, apri `/char/<id>/dice`. La telecamera è leggermente top-down, dadi visibili dall'alto/avanti. Faccia in alto del dado (asse +Y mondo) = faccia visibile.

- [ ] **Step 3: Commit**

```bash
git add webapp/src/dice/DiceScene.tsx
git commit -m "$(cat <<'EOF'
feat(dice): top-down camera (5.5y, 42° fov)

Camera looks down so the world-up face is the player-facing face.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 3 — UV layouts e templates per ComfyUI

### Task 7: Definisci `uvLayouts.ts` e applica UV alle geometrie

**Files:**
- Create: `webapp/src/dice/geometries/uvLayouts.ts`
- Modify: `webapp/src/dice/geometries/index.ts`

- [ ] **Step 1: Studia `geometries/index.ts` per trovare `FaceFrame.up`, `halfWidth`, `halfHeight`**

```bash
sed -n '300,360p' webapp/src/dice/geometries/index.ts
```

Verifica che `FaceFrame` esporti:
- `value: number` (numero faccia 1..N)
- `centroid: THREE.Vector3`
- `normal: THREE.Vector3`
- `up: THREE.Vector3`
- `inradius: number`
- `halfWidth: number`
- `halfHeight: number`

(Confermato dal report exploration iniziale, ma verifica.)

- [ ] **Step 2: Crea `uvLayouts.ts`**

```ts
// webapp/src/dice/geometries/uvLayouts.ts
import * as THREE from 'three'

export type DiceUvKind = 'd4' | 'd6' | 'd8' | 'd10' | 'd12' | 'd20'

export interface UvCellLayout {
  cols: number
  rows: number
}

export const UV_LAYOUTS: Record<DiceUvKind, UvCellLayout> = {
  d4: { cols: 2, rows: 2 },
  d6: { cols: 3, rows: 2 },
  d8: { cols: 4, rows: 2 },
  d10: { cols: 5, rows: 2 },
  d12: { cols: 4, rows: 3 },
  d20: { cols: 5, rows: 4 },
}

/**
 * Mapping deterministico face index → cella nell'atlas.
 * Index 0 = top-left, scorre per righe.
 *
 * IMPORTANTE: gli indici devono corrispondere all'ordine in cui le facce sono iterate
 * in geometries/index.ts; il numero del valore stampato sul template è
 * `faceFrames[index].value`.
 */
export function cellForIndex(kind: DiceUvKind, index: number): { row: number; col: number } {
  const { cols } = UV_LAYOUTS[kind]
  return { row: Math.floor(index / cols), col: index % cols }
}

export interface FaceUv {
  value: number
  uvs: number[]  // pairs (u,v) per vertice della faccia, in ordine vertex
}

/**
 * Genera coordinate UV per una faccia, mappandole nella cella della griglia.
 * Riceve i 2D vertex coordinates della faccia nello spazio locale (basis: face.up + face.normal × face.up),
 * più la cella di destinazione.
 */
export function projectFaceUvs(
  faceVerts2D: Array<{ x: number; y: number }>,
  cell: { row: number; col: number },
  layout: UvCellLayout,
  faceHalfWidth: number,
  faceHalfHeight: number,
): number[] {
  const cellW = 1 / layout.cols
  const cellH = 1 / layout.rows
  const cellCenterU = cell.col * cellW + cellW / 2
  // y-flip: row 0 in atlas = top
  const cellCenterV = 1 - (cell.row * cellH + cellH / 2)

  const uvs: number[] = []
  for (const v of faceVerts2D) {
    const u = cellCenterU + (v.x / faceHalfWidth) * (cellW * 0.5 * 0.95)  // 95% per lasciare bordo
    const vv = cellCenterV + (v.y / faceHalfHeight) * (cellH * 0.5 * 0.95)
    uvs.push(u, vv)
  }
  return uvs
}
```

- [ ] **Step 3: Aggiungi UV attribute a tutte le geometrie in `geometries/index.ts`**

In `getDiceGeometry()`, dopo aver costruito `geometry` (BufferGeometry) e prima del `geometry.computeVertexNormals()`, aggiungi:

```ts
import { UV_LAYOUTS, cellForIndex, projectFaceUvs, type DiceUvKind } from './uvLayouts'

// ... dentro getDiceGeometry, dopo computeVertexNormals e build di faceFrames:
if (kind !== 'd100') {
  const uvKind = kind as DiceUvKind
  const layout = UV_LAYOUTS[uvKind]
  const positionAttr = geometry.getAttribute('position') as THREE.BufferAttribute
  const uvArray = new Float32Array(positionAttr.count * 2)

  // Per ogni triangolo (3 vertices in BufferGeometry non-indexed),
  // identifica a quale faccia "logica" appartiene (via face index 0..N-1)
  // e assegna UVs proiettate.
  // Nota: i triangoli per ogni faccia sono già consecutivi in `geometry`.
  let triCursor = 0
  for (let faceIdx = 0; faceIdx < faceFrames.length; faceIdx++) {
    const ff = faceFrames[faceIdx]
    const cell = cellForIndex(uvKind, faceIdx)

    // basis 2D della faccia: ff.up come Y locale, ff.normal × ff.up come X locale
    const xLocal = new THREE.Vector3().crossVectors(ff.normal, ff.up).normalize()
    const yLocal = ff.up.clone().normalize()
    const trianglesInFace = ff.triangleCount  // dipende da come faceFrames lo espone — vedi sotto
    for (let t = 0; t < trianglesInFace; t++) {
      for (let v = 0; v < 3; v++) {
        const idx = triCursor + t * 3 + v
        const pos = new THREE.Vector3(
          positionAttr.getX(idx),
          positionAttr.getY(idx),
          positionAttr.getZ(idx),
        )
        const local = pos.clone().sub(ff.centroid)
        const x2D = local.dot(xLocal)
        const y2D = local.dot(yLocal)
        const uvs = projectFaceUvs(
          [{ x: x2D, y: y2D }],
          cell,
          layout,
          ff.halfWidth,
          ff.halfHeight,
        )
        uvArray[idx * 2] = uvs[0]
        uvArray[idx * 2 + 1] = uvs[1]
      }
    }
    triCursor += trianglesInFace * 3
  }

  geometry.setAttribute('uv', new THREE.BufferAttribute(uvArray, 2))
  geometry.computeTangents?.()
}
```

**ATTENZIONE**: il codice sopra suppone che `FaceFrame` abbia un campo `triangleCount` che indica quanti triangoli formano la faccia (1 per triangoli singoli, 2 per quadrati, n per poligoni n-gon triangolati a ventaglio). **Se non esiste**, esamina come `geometries/index.ts` costruisce le geometrie: probabilmente per d4/d8/d20 = 1 triangolo per faccia, d6 = 2 triangoli, d10 (kite) = 2 triangoli, d12 (pentagono) = 3 triangoli. Aggiungi `triangleCount` a `FaceFrame` durante la costruzione di ciascuna geometria, oppure derivalo da una mappa locale per kind:

```ts
const TRIS_PER_FACE: Record<DiceUvKind, number> = {
  d4: 1,
  d6: 2,
  d8: 1,
  d10: 2,
  d12: 3,
  d20: 1,
}
```

Usa la mappa al posto di `ff.triangleCount` se il campo non esiste già.

- [ ] **Step 4: Verifica TypeScript**

```bash
cd webapp && npx tsc --noEmit
```

- [ ] **Step 5: Verifica visiva non regressione**

`npm run dev`, tira un d20. Aspetto deve essere identico (UV attribute non viene letta finché non c'è una map, arrivano in Task 12).

- [ ] **Step 6: Commit**

```bash
git add webapp/src/dice/geometries/index.ts webapp/src/dice/geometries/uvLayouts.ts
git commit -m "$(cat <<'EOF'
feat(dice): add UV coords to all dice geometries (atlas layout v1)

Each face index maps to a cell in a row×col grid (d4 2x2 ... d20 5x4).
projectFaceUvs maps the face-local 2D vertex coords to the cell.
computeTangents enabled for normal-map rendering. Fallback materials
ignore UV; pack-driven materials in Task 12 will use them.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Script `generate-uv-templates.mjs` + run

**Files:**
- Create: `webapp/scripts/generate-uv-templates.mjs`
- Create: `webapp/public/dice-packs/_templates/d4.uv.png` ... `d20.uv.png`

- [ ] **Step 1: Crea lo script**

```js
// webapp/scripts/generate-uv-templates.mjs
// Genera template UV PNG per ComfyUI (uno per kind).
// Usa node-canvas (zero deps three.js / cannon — solo grafica 2D).
// Run: node webapp/scripts/generate-uv-templates.mjs

import { createCanvas } from 'canvas'
import { writeFileSync, mkdirSync } from 'fs'
import { dirname } from 'path'

const SIZE = 1024
const OUT_DIR = 'webapp/public/dice-packs/_templates'

const LAYOUTS = {
  d4:  { cols: 2, rows: 2, faces: 4 },
  d6:  { cols: 3, rows: 2, faces: 6 },
  d8:  { cols: 4, rows: 2, faces: 8 },
  d10: { cols: 5, rows: 2, faces: 10 },
  d12: { cols: 4, rows: 3, faces: 12 },
  d20: { cols: 5, rows: 4, faces: 20 },
}

function generateOne(kind) {
  const { cols, rows, faces } = LAYOUTS[kind]
  const canvas = createCanvas(SIZE, SIZE)
  const ctx = canvas.getContext('2d')
  // sfondo grigio scuro (zone fuori cella che non saranno mappate)
  ctx.fillStyle = '#1a1a1a'
  ctx.fillRect(0, 0, SIZE, SIZE)

  const cellW = SIZE / cols
  const cellH = SIZE / rows

  for (let i = 0; i < faces; i++) {
    const col = i % cols
    const row = Math.floor(i / cols)
    const x0 = col * cellW
    const y0 = row * cellH

    // sfondo cella (variante alternata per vedere il bordo)
    ctx.fillStyle = i % 2 === 0 ? '#888888' : '#aaaaaa'
    ctx.fillRect(x0, y0, cellW, cellH)
    // bordo cella
    ctx.strokeStyle = '#000000'
    ctx.lineWidth = 6
    ctx.strokeRect(x0, y0, cellW, cellH)
    // numero faccia
    ctx.fillStyle = '#ff0000'
    ctx.font = `bold ${Math.floor(Math.min(cellW, cellH) * 0.6)}px sans-serif`
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(String(i + 1), x0 + cellW / 2, y0 + cellH / 2)
  }

  const outPath = `${OUT_DIR}/${kind}.uv.png`
  mkdirSync(dirname(outPath), { recursive: true })
  writeFileSync(outPath, canvas.toBuffer('image/png'))
  console.log(`generated ${outPath}`)
}

for (const kind of Object.keys(LAYOUTS)) generateOne(kind)
```

- [ ] **Step 2: Installa `canvas` come devDependency e esegui**

```bash
cd webapp && npm install --save-dev canvas
node scripts/generate-uv-templates.mjs
```

Expected output: 6 PNG generati in `webapp/public/dice-packs/_templates/`.

- [ ] **Step 3: Verifica file**

```bash
ls -la webapp/public/dice-packs/_templates/
```

Aspettati: `d4.uv.png ... d20.uv.png`.

- [ ] **Step 4: Apri uno dei PNG per ispezione manuale**

Apri `d20.uv.png` con un viewer immagini. Devi vedere una griglia 5×4, ogni cella alternata grigio chiaro/scuro, numeri 1..20 in rosso al centro.

- [ ] **Step 5: Crea `_templates/README.md`**

```markdown
# UV templates per ComfyUI

I PNG in questa cartella sono **template UV** generati una-tantum dallo script
`webapp/scripts/generate-uv-templates.mjs`. Ogni PNG mostra una griglia di celle
numerate (1..N) che corrisponde alla mappatura UV di un dado specifico.

## Workflow per creare un pack custom

1. Apri `<kind>.uv.png` come ControlNet input (Canny o Depth) in ComfyUI.
2. Prompt tematico, es. per "hell dice":
   ```
   molten lava texture, embers, hellish theme, glowing cracks,
   1024x1024, seamless cells, dark background between cells
   ```
3. Output: `<kind>.albedo.png` con stesso layout celle.
4. (Opzionale) Per **normal map**: usa nodo ComfyUI `Image to Normal` →
   `<kind>.normal.png`.
5. (Opzionale) Per **roughness**: desatura albedo + inverti, o nodo
   `Image to Roughness` → `<kind>.roughness.png`.
6. (Opzionale) Per **emissive** (zone "calde"): isola via mask le zone
   luminose dell'albedo, salva PNG con nero sui non-emissivi →
   `<kind>.emissive.png`.

## Installazione del pack

1. Crea cartella `webapp/public/dice-packs/<pack_id>/`.
2. Copia i PNG generati lì.
3. Crea `pack.json` (vedi schema in `webapp/src/dice/packs/manifest.ts`).
4. Aggiungi `<pack_id>` a `BUNDLED_PACKS` in `webapp/src/dice/packs/registry.ts`.
5. Esegui `npm run build:prod` per inserirli nel bundle prod.
6. In Settings → Dice pack, seleziona il nuovo pack.

## Rigenerare i template

I template **non vanno modificati a mano**. Per rigenerarli (ad es. dopo
cambio layout):

```bash
node webapp/scripts/generate-uv-templates.mjs
```

Il layout grid è definito in `webapp/src/dice/geometries/uvLayouts.ts` —
deve restare in sync con questo script.
```

- [ ] **Step 6: Commit**

```bash
git add webapp/scripts/generate-uv-templates.mjs webapp/public/dice-packs/_templates/ webapp/package.json webapp/package-lock.json
git commit -m "$(cat <<'EOF'
chore(dice): add UV template generator + bundled templates for ComfyUI

Script generates 6 PNG templates (d4..d20) using node-canvas, one per
dice kind. Output committed under public/dice-packs/_templates/.
README documents the ComfyUI workflow.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: Pack `default` (vuoto, fallback)

**Files:**
- Create: `webapp/public/dice-packs/default/pack.json`

- [ ] **Step 1: Crea il file**

```json
{
  "id": "default",
  "name": "Default",
  "numerals": "procedural",
  "dice": {}
}
```

- [ ] **Step 2: Commit**

```bash
git add webapp/public/dice-packs/default/pack.json
git commit -m "$(cat <<'EOF'
feat(dice): add empty 'default' pack manifest

Empty dice block → loader falls through to procedural rendering.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 4 — Texture pack system

### Task 10: Schema manifest + registry + loader

**Files:**
- Create: `webapp/src/dice/packs/manifest.ts`
- Create: `webapp/src/dice/packs/registry.ts`
- Create: `webapp/src/dice/packs/loader.ts`

- [ ] **Step 1: Crea `manifest.ts` con schema Zod**

```ts
// webapp/src/dice/packs/manifest.ts
import { z } from 'zod'
import type { DiceTint } from '../types'

const HexColor = z.string().regex(/^#[0-9a-fA-F]{6}$/)

const TintColorsSchema = z.object({
  ink: HexColor.optional(),
  outline: HexColor.optional(),
})

const DiceMapsSchema = z.object({
  albedo: z.string().min(1),
  normal: z.string().optional(),
  roughness: z.string().optional(),
  emissive: z.string().optional(),
  emissiveIntensity: z.number().min(0).max(5).optional(),
})

export const PackManifestSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  author: z.string().optional(),
  version: z.string().optional(),
  numerals: z.enum(['procedural', 'embedded']),
  tints: z
    .object({
      normal: TintColorsSchema.optional(),
      crit: TintColorsSchema.optional(),
      fumble: TintColorsSchema.optional(),
      arcane: TintColorsSchema.optional(),
      ember: TintColorsSchema.optional(),
    })
    .partial()
    .optional(),
  material: z
    .object({
      metalness: z.number().min(0).max(1).optional(),
      roughness: z.number().min(0).max(1).optional(),
      envMapIntensity: z.number().min(0).max(5).optional(),
    })
    .optional(),
  dice: z.object({
    d4: DiceMapsSchema.optional(),
    d6: DiceMapsSchema.optional(),
    d8: DiceMapsSchema.optional(),
    d10: DiceMapsSchema.optional(),
    d12: DiceMapsSchema.optional(),
    d20: DiceMapsSchema.optional(),
  }),
})

export type PackManifest = z.infer<typeof PackManifestSchema>
export type DiceMaps = z.infer<typeof DiceMapsSchema>
export type TintOverride = { ink?: string; outline?: string }

export function getTintOverride(manifest: PackManifest, tint: DiceTint): TintOverride | undefined {
  return manifest.tints?.[tint]
}
```

(Aggiungi `zod` se non già installato: verifica in `webapp/package.json`. È già usato in altri schema del repo? Se sì, ok. Altrimenti `npm install zod`.)

- [ ] **Step 2: Crea `registry.ts`**

```ts
// webapp/src/dice/packs/registry.ts
export const BUNDLED_PACKS = ['default'] as const
export type PackId = (typeof BUNDLED_PACKS)[number]

export function isBundledPack(id: string): id is PackId {
  return (BUNDLED_PACKS as readonly string[]).includes(id)
}
```

(`hell_dice` verrà aggiunto solo quando l'utente lo crea — per ora solo `default`.)

- [ ] **Step 3: Crea `loader.ts`**

```ts
// webapp/src/dice/packs/loader.ts
import * as THREE from 'three'
import { PackManifestSchema, type PackManifest, type DiceMaps } from './manifest'
import type { PackId } from './registry'
import type { DiceKind } from '../types'

type DiceKindNoD100 = Exclude<DiceKind, 'd100'>

export interface LoadedDiceMaps {
  albedo: THREE.Texture
  normal?: THREE.Texture
  roughness?: THREE.Texture
  emissive?: THREE.Texture
  emissiveIntensity?: number
}

export interface LoadedPack {
  manifest: PackManifest
  maps: Partial<Record<DiceKindNoD100, LoadedDiceMaps>>
}

const cache = new Map<PackId, Promise<LoadedPack>>()
const allTextures = new Map<PackId, THREE.Texture[]>()

const loader = new THREE.TextureLoader()

async function loadTexture(url: string, srgb: boolean): Promise<THREE.Texture> {
  const tex = await loader.loadAsync(url)
  tex.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.LinearSRGBColorSpace
  tex.wrapS = THREE.ClampToEdgeWrapping
  tex.wrapT = THREE.ClampToEdgeWrapping
  return tex
}

async function loadKindMaps(packId: PackId, maps: DiceMaps): Promise<LoadedDiceMaps> {
  const base = `/dice-packs/${packId}`
  const albedo = await loadTexture(`${base}/${maps.albedo}`, true)
  const out: LoadedDiceMaps = { albedo }
  if (maps.normal) out.normal = await loadTexture(`${base}/${maps.normal}`, false)
  if (maps.roughness) out.roughness = await loadTexture(`${base}/${maps.roughness}`, false)
  if (maps.emissive) out.emissive = await loadTexture(`${base}/${maps.emissive}`, true)
  if (maps.emissiveIntensity !== undefined) out.emissiveIntensity = maps.emissiveIntensity
  return out
}

async function loadPackInternal(id: PackId): Promise<LoadedPack> {
  const manifestRes = await fetch(`/dice-packs/${id}/pack.json`)
  if (!manifestRes.ok) throw new Error(`pack.json not found for ${id}`)
  const raw = await manifestRes.json()
  const manifest = PackManifestSchema.parse(raw)

  const maps: Partial<Record<DiceKindNoD100, LoadedDiceMaps>> = {}
  const collected: THREE.Texture[] = []
  for (const kindKey of Object.keys(manifest.dice) as DiceKindNoD100[]) {
    const def = manifest.dice[kindKey]
    if (!def) continue
    try {
      const loaded = await loadKindMaps(id, def)
      maps[kindKey] = loaded
      collected.push(loaded.albedo)
      if (loaded.normal) collected.push(loaded.normal)
      if (loaded.roughness) collected.push(loaded.roughness)
      if (loaded.emissive) collected.push(loaded.emissive)
    } catch (err) {
      console.warn(`[dice-pack] failed to load ${id}/${kindKey}`, err)
      // skip this kind, fallback per quel kind a default rendering
    }
  }
  allTextures.set(id, collected)
  return { manifest, maps }
}

export async function loadPack(id: PackId): Promise<LoadedPack> {
  const cached = cache.get(id)
  if (cached) return cached
  const promise = loadPackInternal(id).catch((err) => {
    cache.delete(id)
    throw err
  })
  cache.set(id, promise)
  return promise
}

export function disposePack(id: PackId): void {
  const textures = allTextures.get(id)
  if (textures) for (const tex of textures) tex.dispose()
  allTextures.delete(id)
  cache.delete(id)
}

export async function loadPackWithFallback(id: PackId): Promise<LoadedPack> {
  try {
    return await loadPack(id)
  } catch (err) {
    console.warn(`[dice-pack] falling back to default (failed to load ${id})`, err)
    if (id !== 'default') return await loadPack('default' as PackId)
    throw err
  }
}
```

- [ ] **Step 4: Verifica TypeScript**

```bash
cd webapp && npx tsc --noEmit
```

- [ ] **Step 5: Verifica fetch del pack default in browser**

Avvia `npm run dev`, in DevTools Console:

```js
import('./dice/packs/loader.js').then(m => m.loadPack('default')).then(console.log)
```

(Vite dev mode supporta dynamic import.) Expected: oggetto `LoadedPack` con `maps = {}`.

- [ ] **Step 6: Commit**

```bash
git add webapp/src/dice/packs/ webapp/package.json webapp/package-lock.json
git commit -m "$(cat <<'EOF'
feat(dice): pack manifest schema + registry + loader

Zod-validated pack.json schema (numerals, tints, material, dice).
TextureLoader-based loader with per-pack disposal, fallback chain
to 'default' on any failure.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 11: Estendi store + crea `DicePackProvider`

**Files:**
- Modify: `webapp/src/store/diceSettings.ts`
- Create: `webapp/src/dice/packs/DicePackProvider.tsx`

- [ ] **Step 1: Aggiungi `packId` allo store**

Sostituisci `webapp/src/store/diceSettings.ts`:

```ts
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface DiceSettingsStore {
  animate3d: boolean
  packId: string
  setAnimate3d: (value: boolean) => void
  setPackId: (id: string) => void
}

export const useDiceSettings = create<DiceSettingsStore>()(
  persist(
    (set) => ({
      animate3d: true,
      packId: 'default',
      setAnimate3d: (value) => set({ animate3d: value }),
      setPackId: (id) => set({ packId: id }),
    }),
    { name: 'dnd-dice-settings' },
  ),
)
```

- [ ] **Step 2: Crea `DicePackProvider`**

```tsx
// webapp/src/dice/packs/DicePackProvider.tsx
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { useDiceSettings } from '@/store/diceSettings'
import { loadPackWithFallback, disposePack, type LoadedPack } from './loader'
import { isBundledPack, type PackId } from './registry'

interface PackContext {
  pack: LoadedPack | null
  loading: boolean
  error: string | null
}

const Ctx = createContext<PackContext>({ pack: null, loading: false, error: null })

export function useDicePack(): PackContext {
  return useContext(Ctx)
}

export function DicePackProvider({ children }: { children: ReactNode }) {
  const packIdRaw = useDiceSettings((s) => s.packId)
  const setPackId = useDiceSettings((s) => s.setPackId)
  const packId = isBundledPack(packIdRaw) ? packIdRaw : ('default' as PackId)
  const [pack, setPack] = useState<LoadedPack | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const previousId: PackId | null = pack?.manifest.id && isBundledPack(pack.manifest.id) ? (pack.manifest.id as PackId) : null
    setLoading(true)
    setError(null)
    loadPackWithFallback(packId)
      .then((p) => {
        if (cancelled) return
        setPack(p)
        if (previousId && previousId !== packId) disposePack(previousId)
        if (p.manifest.id !== packId) {
          // fallback è scattato — ripristina lo store al pack effettivamente caricato
          setPackId(p.manifest.id)
          setError(`pack ${packId} not available, fell back to ${p.manifest.id}`)
        }
      })
      .catch((err) => {
        if (cancelled) return
        setError(String(err))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [packId, setPackId])

  return <Ctx.Provider value={{ pack, loading, error }}>{children}</Ctx.Provider>
}
```

- [ ] **Step 3: Wrappa `DiceAnimationProvider` con `DicePackProvider`**

In `webapp/src/dice/DiceAnimationProvider.tsx`, modifica il return JSX per inserire il `DicePackProvider` come padre del provider esistente. Esempio (adatta al codice attuale):

```tsx
import { DicePackProvider } from './packs/DicePackProvider'

// ...
return (
  <DicePackProvider>
    <Ctx.Provider value={value}>
      {children}
      {/* overlay esistente */}
    </Ctx.Provider>
  </DicePackProvider>
)
```

- [ ] **Step 4: Verifica TypeScript**

```bash
cd webapp && npx tsc --noEmit
```

- [ ] **Step 5: Verifica visiva**

`npm run dev`, naviga ovunque. Niente cambiamenti visivi (pack `default` non ha texture). Apri Console — verifica nessun errore loader.

- [ ] **Step 6: Commit**

```bash
git add webapp/src/store/diceSettings.ts webapp/src/dice/packs/DicePackProvider.tsx webapp/src/dice/DiceAnimationProvider.tsx
git commit -m "$(cat <<'EOF'
feat(dice): packId in store + DicePackProvider context

Settings store gains packId persisted alongside animate3d.
Provider loads the active pack via fallback chain and disposes the
previous one on switch. Falls back to 'default' silently and resets
store packId on load failure.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 12: Materials con pack PBR + numerali condizionali

**Files:**
- Modify: `webapp/src/dice/materials.ts`
- Modify: `webapp/src/dice/numeralTexture.ts` (accetta override colori)
- Modify: `webapp/src/dice/DiceScene.tsx`

- [ ] **Step 1: Estendi `numeralTexture.ts` con override colori**

Apri `webapp/src/dice/numeralTexture.ts`. La funzione `getNumeralTexture(label, tint)` deve accettare override opzionali. Aggiungi:

```ts
export interface NumeralColors {
  ink?: string
  outline?: string
}

const NUMERAL_PALETTE: Record<DiceTint, { ink: string; outline: string }> = {
  // copia i valori già esistenti di ink/outline per tint
  // (verifica nel file attuale e RICOPIALI qui — non lasciare placeholder)
  normal: { ink: '#1c160c', outline: '#f6e8b1' },
  crit:   { ink: '#1c160c', outline: '#fff5cc' },
  fumble: { ink: '#1c0808', outline: '#ffd6d6' },
  arcane: { ink: '#1a1432', outline: '#cfb8ff' },
  ember:  { ink: '#1c0d05', outline: '#ffd28a' },
}

const cache = new Map<string, THREE.CanvasTexture>()

export function getNumeralTexture(
  label: string,
  tint: DiceTint = 'normal',
  override?: NumeralColors,
): THREE.CanvasTexture {
  const palette = NUMERAL_PALETTE[tint]
  const ink = override?.ink ?? palette.ink
  const outline = override?.outline ?? palette.outline
  const key = `${tint}:${label}:${ink}:${outline}`
  // resto come prima, usa ink + outline al posto di valori hardcoded
  // ...
}
```

(Apri il file e adatta — i nomi delle costanti interne possono variare. **Importante**: il caching deve usare la chiave nuova per non riusare texture con colori sbagliati.)

- [ ] **Step 2: Estendi `materials.ts` per pack-aware material**

Riscrivi `webapp/src/dice/materials.ts` per accettare `LoadedPack` opzionale:

```ts
import * as THREE from 'three'
import type { DiceTint, DiceKind } from './types'
import { getNumeralTexture, type NumeralColors } from './numeralTexture'
import type { LoadedPack } from './packs/loader'

type DiceKindNoD100 = Exclude<DiceKind, 'd100'>

const palette: Record<DiceTint, {
  color: number
  emissive: number
  emissiveIntensity: number
  metalness: number
  roughness: number
}> = {
  normal: { color: 0xe6d49a, emissive: 0x000000, emissiveIntensity: 0, metalness: 0.15, roughness: 0.55 },
  crit:   { color: 0xf0c970, emissive: 0xf0c970, emissiveIntensity: 0.35, metalness: 0.3, roughness: 0.4 },
  fumble: { color: 0xb33030, emissive: 0xe85050, emissiveIntensity: 0.4, metalness: 0.2, roughness: 0.5 },
  arcane: { color: 0x6a56c8, emissive: 0x8b6ff0, emissiveIntensity: 0.3, metalness: 0.25, roughness: 0.45 },
  ember:  { color: 0xc46436, emissive: 0xd96040, emissiveIntensity: 0.3, metalness: 0.2, roughness: 0.5 },
}

const cache = new Map<string, THREE.MeshStandardMaterial>()

export function getDiceMaterial(
  tint: DiceTint = 'normal',
  pack?: LoadedPack | null,
  kind?: DiceKindNoD100,
): THREE.MeshStandardMaterial {
  const packMaps = pack && kind ? pack.maps[kind] : undefined
  const key = packMaps ? `pack:${pack!.manifest.id}:${kind}:${tint}` : `proc:${tint}`
  const cached = cache.get(key)
  if (cached) return cached

  if (packMaps) {
    const m = pack!.manifest.material ?? {}
    const mat = new THREE.MeshStandardMaterial({
      map: packMaps.albedo,
      normalMap: packMaps.normal ?? null,
      roughnessMap: packMaps.roughness ?? null,
      emissiveMap: packMaps.emissive ?? null,
      emissive: packMaps.emissive ? 0xffffff : 0x000000,
      emissiveIntensity: packMaps.emissiveIntensity ?? (packMaps.emissive ? 1.0 : 0),
      metalness: m.metalness ?? palette[tint].metalness,
      roughness: m.roughness ?? palette[tint].roughness,
      envMapIntensity: m.envMapIntensity ?? 1,
    })
    if (pack!.manifest.numerals === 'procedural') {
      // tint applicato come light multiplier (overlay)
      mat.color.setHex(palette[tint].color)
    } else {
      mat.color.setHex(0xffffff)
    }
    cache.set(key, mat)
    return mat
  }

  const p = palette[tint]
  const mat = new THREE.MeshStandardMaterial({
    color: p.color,
    emissive: p.emissive,
    emissiveIntensity: p.emissiveIntensity,
    metalness: p.metalness,
    roughness: p.roughness,
  })
  cache.set(key, mat)
  return mat
}

export function disposeDiceMaterials(): void {
  for (const mat of cache.values()) mat.dispose()
  cache.clear()
  for (const mat of numeralMatCache.values()) mat.dispose()
  numeralMatCache.clear()
}

const numeralMatCache = new Map<string, THREE.MeshStandardMaterial>()

export function getNumeralMaterial(
  label: string,
  tint: DiceTint = 'normal',
  override?: NumeralColors,
): THREE.MeshStandardMaterial {
  const key = `${tint}:${label}:${override?.ink ?? '_'}:${override?.outline ?? '_'}`
  const cached = numeralMatCache.get(key)
  if (cached) return cached
  const tex = getNumeralTexture(label, tint, override)
  const mat = new THREE.MeshStandardMaterial({
    map: tex,
    transparent: true,
    alphaTest: 0.05,
    depthWrite: false,
    metalness: 0,
    roughness: 0.8,
    polygonOffset: true,
    polygonOffsetFactor: -2,
    polygonOffsetUnits: -2,
  })
  numeralMatCache.set(key, mat)
  return mat
}
```

- [ ] **Step 3: Aggiorna `DiceScene.tsx` per consumare pack e passare a `getDiceMaterial`**

In `Orchestrator`, prima del `return`:

```ts
import { useDicePack } from './packs/DicePackProvider'
import { getTintOverride } from './packs/manifest'
// ...
const { pack } = useDicePack()
```

E nel render delle entities (riga ~275):

```tsx
const tint = request?.group.tint ?? 'normal'
const override = pack ? getTintOverride(pack.manifest, tint) : undefined
const skipNumerals = pack?.manifest.numerals === 'embedded'
return (
  <>
    {entities.map((e, i) => {
      const geomData = getDiceGeometry(e.kind)
      const baseMaterial = getDiceMaterial(tint, pack, e.kind)
      return (
        <group key={`${version}-${i}`} ref={(g: THREE.Group | null) => { e.group = g }}>
          <mesh geometry={geomData.geometry} material={baseMaterial} castShadow receiveShadow />
          {!skipNumerals &&
            geomData.faceFrames.map((ff) => {
              const planeSize = ff.inradius * 1.7
              return (
                <mesh
                  key={ff.value}
                  geometry={PLANE_GEOMETRY}
                  material={getNumeralMaterial(String(ff.value), tint, override)}
                  position={ff.offsetPosition.toArray()}
                  quaternion={[ff.quaternion.x, ff.quaternion.y, ff.quaternion.z, ff.quaternion.w]}
                  scale={planeSize}
                />
              )
            })}
        </group>
      )
    })}
  </>
)
```

- [ ] **Step 4: Verifica TypeScript**

```bash
cd webapp && npx tsc --noEmit
```

- [ ] **Step 5: Verifica visiva**

`npm run dev`. Pack `default` selezionato → render identico a oggi (no map → fallback procedural). Testa anche tinting normal/crit/fumble (forza temporaneo `tint: 'crit'` nel `DicePlayRequest` se non hai un percorso UI per provarlo).

- [ ] **Step 6: Commit**

```bash
git add webapp/src/dice/materials.ts webapp/src/dice/numeralTexture.ts webapp/src/dice/DiceScene.tsx
git commit -m "$(cat <<'EOF'
feat(dice): pack-aware materials (PBR maps + tint overrides + numeral skip)

getDiceMaterial accepts a pack + kind, building a MeshStandardMaterial
with albedo/normal/roughness/emissive when present. Numerals skipped
when manifest.numerals === 'embedded'. Procedural numerals accept
ink/outline override from manifest.tints.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 13: Cancella `quaternionForFace` (orphan)

**Files:**
- Modify: `webapp/src/dice/physics/faceDetector.ts`

- [ ] **Step 1: Verifica che nessuno la usi**

```bash
grep -rn "quaternionForFace" webapp/src
```

Expected: solo la definizione in `faceDetector.ts`. Se altri call site esistono, **non procedere** — investiga.

- [ ] **Step 2: Rimuovi la funzione**

Cancella il blocco `export function quaternionForFace(...)` in `webapp/src/dice/physics/faceDetector.ts`.

- [ ] **Step 3: Verifica TypeScript**

```bash
cd webapp && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add webapp/src/dice/physics/faceDetector.ts
git commit -m "$(cat <<'EOF'
refactor(dice): drop orphan quaternionForFace (snap-to-camera helper)

Snapping phase removed in Task 5; this helper has no remaining callers.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 5 — API change + roll flow nuovo

### Task 14: Backend — endpoint `/dice/result` + rimuovi `/dice/roll`

**Files:**
- Modify: `api/routers/dice.py`
- Modify: `api/schemas/common.py`

- [ ] **Step 1: Aggiungi `DiceResultRequest` + `DiceResultEntry` in `api/schemas/common.py`**

Apri `api/schemas/common.py`, aggiungi (in fondo o accanto a `DiceRollResult`):

```python
from typing import Literal


class DiceResultEntry(BaseModel):
    kind: Literal["d4", "d6", "d8", "d10", "d12", "d20"]
    value: int


class DiceResultRequest(BaseModel):
    rolls: list[DiceResultEntry] = Field(min_length=1, max_length=50)
    label: str | None = Field(default=None, max_length=120)
    modifier: int = 0
    notation: str | None = Field(default=None, max_length=80)
```

(Se `Field` non è già importato da pydantic, aggiungi `from pydantic import BaseModel, Field`.)

- [ ] **Step 2: Modifica `api/routers/dice.py`**

Cancella `roll_dice` (righe 42-65 nel file attuale) e aggiungi:

```python
from api.schemas.common import DiceResultRequest, DiceResultEntry

_RANGES_PER_KIND = {
    "d4": (1, 4),
    "d6": (1, 6),
    "d8": (1, 8),
    "d10": (0, 9),
    "d12": (1, 12),
    "d20": (1, 20),
}


@router.post("/{char_id}/dice/result", response_model=DiceRollResult)
async def post_dice_result(
    char_id: int,
    body: DiceResultRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DiceRollResult:
    # validate ranges
    for entry in body.rolls:
        lo, hi = _RANGES_PER_KIND[entry.kind]
        if not (lo <= entry.value <= hi):
            raise HTTPException(
                status_code=400,
                detail=f"value {entry.value} out of range for {entry.kind} ({lo}..{hi})",
            )

    rolls = [e.value for e in body.rolls]
    total = sum(rolls) + body.modifier

    # notation: prefer client-supplied, else infer
    if body.notation:
        notation = body.notation
    else:
        # group by kind, build "NdK + ..."
        from collections import Counter
        c = Counter(e.kind for e in body.rolls)
        notation = " + ".join(f"{n}{k}" if n > 1 else k for k, n in c.items())
        if body.modifier:
            notation += f"{'+' if body.modifier > 0 else ''}{body.modifier}"

    char = await _get_owned(char_id, user_id, session)
    history = list(char.rolls_history or [])
    history.append({"notation": notation, "rolls": rolls, "total": total})
    char.rolls_history = history[-_MAX_HISTORY:]

    return DiceRollResult(notation=notation, rolls=rolls, total=total)
```

Cancella anche la costante `_VALID_DICE` se non usata altrove (verifica con grep).

- [ ] **Step 3: Verifica syntax Python**

```bash
python3 -m py_compile api/routers/dice.py api/schemas/common.py
```

Expected: nessun output (success).

- [ ] **Step 4: User verifica integration**

(Lo sviluppatore/utente deve eseguire questi comandi su Windows perché WSL non può `uv run`:)

```powershell
# In Windows PowerShell, repo root
uv run uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

In altro terminale (cmd / PowerShell):

```powershell
# old endpoint deve essere 404/405
curl -i -X POST http://localhost:8000/characters/1/dice/roll -H "Content-Type: application/json" -d "{\"die\":\"d20\",\"count\":1}" -H "X-Telegram-Init-Data: <DEV_USER fixture>"

# new endpoint deve restituire 200
curl -i -X POST http://localhost:8000/characters/1/dice/result -H "Content-Type: application/json" -d "{\"rolls\":[{\"kind\":\"d20\",\"value\":17}]}" -H "X-Telegram-Init-Data: <DEV_USER fixture>"
```

- [ ] **Step 5: Commit**

```bash
git add api/routers/dice.py api/schemas/common.py
git commit -m "$(cat <<'EOF'
feat(api): replace /dice/roll with /dice/result (client-authoritative)

Client now lifts the result from physics; server stores & validates ranges.
DiceResultRequest accepts a list of {kind, value} entries plus optional
label, modifier, notation. Ranges enforced per kind; out-of-range → 400.
Old /dice/roll endpoint removed.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 15: Webapp — `dice/rng.ts` (fallback non-3D)

**Files:**
- Create: `webapp/src/dice/rng.ts`

- [ ] **Step 1: Crea il file**

```ts
// webapp/src/dice/rng.ts
import type { DiceKind } from './types'

const SIDES: Record<Exclude<DiceKind, 'd100'>, number> = {
  d4: 4, d6: 6, d8: 8, d10: 10, d12: 12, d20: 20,
}

/**
 * Genera un intero uniforme in [min, max] (incluso) usando crypto.getRandomValues
 * con rejection sampling per evitare bias modulo.
 */
function uniformInt(min: number, max: number): number {
  if (min > max) throw new Error('min > max')
  const range = max - min + 1
  const maxUint32 = 0xFFFFFFFF
  const limit = maxUint32 - (maxUint32 % range)
  const buf = new Uint32Array(1)
  // tipicamente loop esce al primo iter; cap al worst case
  for (let i = 0; i < 256; i++) {
    crypto.getRandomValues(buf)
    if (buf[0] < limit) return min + (buf[0] % range)
  }
  // failsafe estremo (mai raggiunto in pratica)
  return min + (buf[0] % range)
}

/** Tira N volte un dado di tipo `kind`. d100 è restituito come 2 entry d10 (decine, unità). */
export function rollMany(kind: DiceKind, count: number): { kind: Exclude<DiceKind, 'd100'>; value: number }[] {
  const out: { kind: Exclude<DiceKind, 'd100'>; value: number }[] = []
  for (let i = 0; i < count; i++) {
    if (kind === 'd100') {
      // due d10: tens 0..9, ones 0..9 (entrambi convention "0..9", server li valida)
      out.push({ kind: 'd10', value: uniformInt(0, 9) })
      out.push({ kind: 'd10', value: uniformInt(0, 9) })
    } else {
      const sides = SIDES[kind]
      // d10 range 0..9; altri 1..N
      if (kind === 'd10') {
        out.push({ kind, value: uniformInt(0, 9) })
      } else {
        out.push({ kind, value: uniformInt(1, sides) })
      }
    }
  }
  return out
}
```

- [ ] **Step 2: Verifica TypeScript**

```bash
cd webapp && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add webapp/src/dice/rng.ts
git commit -m "$(cat <<'EOF'
feat(dice): rng helper for non-3D fallback (crypto.getRandomValues)

Uniform int via rejection sampling. d100 → 2× d10 entries.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 16: API client + `useRollAndPersist` hook

**Files:**
- Modify: `webapp/src/api/client.ts`
- Create: `webapp/src/dice/useRollAndPersist.ts`

- [ ] **Step 1: Aggiorna `client.ts` `dice` block**

Sostituisci il blocco `dice:` (righe 444-459 attuali):

```ts
dice: {
  result: (charId: number, body: DiceResultRequestBody) =>
    request<DiceRollResult>(`/characters/${charId}/dice/result`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  history: (charId: number) => request<DiceRollResult[]>(`/characters/${charId}/dice/history`),
  clearHistory: (charId: number) =>
    request<void>(`/characters/${charId}/dice/history`, { method: 'DELETE' }),
  postToChat: (charId: number, result: { notation: string; rolls: number[]; total: number }) =>
    request<{ ok: boolean }>(`/characters/${charId}/dice/post-to-chat`, {
      method: 'POST',
      body: JSON.stringify(result),
    }),
},
```

E aggiungi all'inizio del file (sotto altri type alias):

```ts
export type DiceResultEntryBody = {
  kind: 'd4' | 'd6' | 'd8' | 'd10' | 'd12' | 'd20'
  value: number
}

export type DiceResultRequestBody = {
  rolls: DiceResultEntryBody[]
  label?: string | null
  modifier?: number
  notation?: string | null
}
```

- [ ] **Step 2: Crea `useRollAndPersist.ts`**

```ts
// webapp/src/dice/useRollAndPersist.ts
import { useCallback } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useReducedMotion } from 'framer-motion'
import { api, type DiceResultRequestBody } from '@/api/client'
import { useDiceSettings } from '@/store/diceSettings'
import { useDiceAnimation } from './useDiceAnimation'
import { rollMany } from './rng'
import type { DiceKind, DiceTint } from './types'

export interface RollEntry {
  kind: DiceKind
  count: number
  tint?: DiceTint
}

export interface RollOpts {
  label?: string
  modifier?: number
  notation?: string
}

export interface RollGroup {
  kind: DiceKind
  notation: string
  rolls: number[]
  total: number
}

export function useRollAndPersist(charId: number | null) {
  const animate3d = useDiceSettings((s) => s.animate3d)
  const reducedMotion = useReducedMotion()
  const dice = useDiceAnimation()
  const qc = useQueryClient()

  const persist = useMutation({
    mutationFn: (body: DiceResultRequestBody) =>
      charId ? api.dice.result(charId, body) : Promise.reject(new Error('no charId')),
    onSettled: () => {
      if (charId) qc.invalidateQueries({ queryKey: ['dice-history', charId] })
    },
  })

  const roll = useCallback(
    async (entries: RollEntry[], opts: RollOpts = {}): Promise<RollGroup[]> => {
      if (!charId) throw new Error('no charId')
      if (entries.length === 0) return []

      const useAnimation = animate3d && !reducedMotion

      let resultsPerEntry: number[][] // ogni entry → array di valori per quel gruppo

      if (useAnimation) {
        // 3D path: per ogni entry chiama playAndCollect (1 entry = 1 group fisicamente
        // simulato). Sequenziale, così le animazioni non si sovrappongono.
        resultsPerEntry = []
        for (const entry of entries) {
          const detected = await dice.playAndCollect([
            { kind: entry.kind, tint: entry.tint, count: entry.kind === 'd100' ? entry.count * 2 : entry.count },
          ])
          // detected: DetectedResult[] per questa entry
          resultsPerEntry.push(detected.map((d) => d.value))
        }
      } else {
        // fallback path: crypto.getRandomValues
        resultsPerEntry = entries.map((e) => rollMany(e.kind, e.count).map((r) => r.value))
      }

      // Costruisce body per POST: aggrega per kind splittando d100 in 2× d10
      const bodyRolls: DiceResultRequestBody['rolls'] = []
      const groupResults: RollGroup[] = entries.map((e, i) => {
        const vals = resultsPerEntry[i]
        const total =
          e.kind === 'd100'
            ? // d100: pair di d10 (decine, unità) → valore 1..100 (00 = 100)
              pairD100(vals)
            : vals.reduce((s, v) => s + v, 0)
        const notation = `${e.count}${e.kind}`
        // body: ogni d100 = 2 entry d10
        if (e.kind === 'd100') {
          for (const v of vals) bodyRolls.push({ kind: 'd10', value: v })
        } else {
          for (const v of vals) bodyRolls.push({ kind: e.kind as DiceResultRequestBody['rolls'][number]['kind'], value: v })
        }
        return { kind: e.kind, notation, rolls: vals, total }
      })

      await persist.mutateAsync({
        rolls: bodyRolls,
        label: opts.label ?? null,
        modifier: opts.modifier ?? 0,
        notation: opts.notation ?? null,
      })

      return groupResults
    },
    [animate3d, charId, dice, persist, reducedMotion],
  )

  return { roll, isPending: persist.isPending, error: persist.error }
}

function pairD100(vals: number[]): number {
  // vals = [tens, ones] per ogni dado d100; si presume sempre 2 valori per ogni d100
  // Convention: 00 + 0 = 100 (regola D&D). Più lanci sommati: ciascun pair = 1..100.
  let total = 0
  for (let i = 0; i < vals.length; i += 2) {
    const tens = vals[i]
    const ones = vals[i + 1]
    let v = tens * 10 + ones
    if (v === 0) v = 100
    total += v
  }
  return total
}
```

- [ ] **Step 3: Estendi `DiceAnimationApi` con `playAndCollect`**

In `webapp/src/dice/types.ts` aggiungi:

```ts
export interface PlayCollectGroup {
  kind: DiceKind
  tint?: DiceTint
  count: number
}

export interface DiceAnimationApi {
  play: (req: DicePlayRequest) => Promise<void>
  playAndCollect: (groups: PlayCollectGroup[]) => Promise<DetectedResult[]>
  isPlaying: boolean
}
```

(Task 16 si limita a un solo group per call — sufficiente perché useRollAndPersist itera per entry. Multi-group simultaneo = future work.)

In `webapp/src/dice/DiceAnimationProvider.tsx`, aggiungi `playAndCollect` al value del Context provider. Implementazione: costruisce un `SceneRequest` con `count` da `groups[0].count`, raccoglie `DetectedResult[]` via `onComplete`, lo restituisce dalla Promise. Esempio (i nomi delle ref/state esistenti possono variare, adatta):

```ts
const playAndCollect = useCallback(
  (groups: PlayCollectGroup[]): Promise<DetectedResult[]> => {
    if (groups.length !== 1) {
      return Promise.reject(new Error('playAndCollect: only single-group supported'))
    }
    const g = groups[0]
    return new Promise<DetectedResult[]>((resolve) => {
      const req: SceneRequest = {
        id: nextRequestIdRef.current++,
        group: { kind: g.kind, tint: g.tint, count: g.count },
        onComplete: (results) => resolve(results),
      }
      setShouldMountScene(true)
      setSceneRequest(req)
    })
  },
  [],
)

// includi playAndCollect nel value della Context.Provider
const value: DiceAnimationApi = useMemo(
  () => ({ play, playAndCollect, isPlaying }),
  [play, playAndCollect, isPlaying],
)
```

Il `SceneRequest.onComplete` adesso deve risolvere la Promise di `playAndCollect` invece di ignorare i results. Quando l'animazione viene scatenata da `play()` (vecchio path) i results vengono ancora ignorati. Per distinguere i due percorsi, conserva due "in-flight resolvers":

```ts
const resolvePlayRef = useRef<(() => void) | null>(null)
const resolveCollectRef = useRef<((r: DetectedResult[]) => void) | null>(null)

// in play(): resolvePlayRef.current = resolve
// in playAndCollect(): resolveCollectRef.current = resolve
// in SceneRequest.onComplete:
onComplete: (results) => {
  resolvePlayRef.current?.(); resolvePlayRef.current = null
  resolveCollectRef.current?.(results); resolveCollectRef.current = null
}
```

(Solo uno dei due ref è valorizzato per ciascuna call — l'altro rimane null e il `?.` skippa.)

- [ ] **Step 4: Verifica TypeScript**

```bash
cd webapp && npx tsc --noEmit
```

- [ ] **Step 5: Commit**

```bash
git add webapp/src/api/client.ts webapp/src/dice/useRollAndPersist.ts webapp/src/dice/types.ts webapp/src/dice/DiceAnimationProvider.tsx
git commit -m "$(cat <<'EOF'
feat(dice): useRollAndPersist hook unifies 3D + fallback paths

API client switches dice.roll → dice.result; new hook routes through
DiceAnimation.playAndCollect when animate3d && !reducedMotion, else
crypto.getRandomValues. Hook posts to /dice/result and invalidates
history. d100 split into 2× d10 entries with pair → 1..100 total.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 17: Migra `DiceOverlay` e `Dice.tsx` al nuovo hook

**Files:**
- Modify: `webapp/src/components/DiceOverlay.tsx`
- Modify: `webapp/src/pages/Dice.tsx`

- [ ] **Step 1: Aggiorna `DiceOverlay.tsx`**

In `webapp/src/components/DiceOverlay.tsx`, sostituisci il blocco `rollMutation` (righe ~95-123) con uso di `useRollAndPersist`:

```tsx
import { useRollAndPersist, type RollEntry } from '@/dice/useRollAndPersist'

// ...
const { roll, isPending } = useRollAndPersist(charId)

const handleRoll = useCallback(async () => {
  if (!entries.length || isPending || !charId) return
  try {
    const rollEntries: RollEntry[] = entries.map(([kind, count]) => ({ kind, count }))
    const groups = await roll(rollEntries, {
      notation: rollEntries.map((e) => `${e.count}${e.kind}`).join(' + '),
    })
    setPool({})
    setOpen(false)
    haptic.medium()
    showResults(groups)
  } catch {
    haptic.error()
    showError()
  }
}, [entries, isPending, charId, roll, showResults, showError])

const isRolling = isPending
```

(Cancella `import { useMutation } from '@tanstack/react-query'` se non più usato. Cancella `useDiceAnimation` import se non più usato direttamente.)

- [ ] **Step 2: Aggiorna `Dice.tsx`**

Apri `webapp/src/pages/Dice.tsx` e applica la stessa sostituzione (uso di `useRollAndPersist` invece di `api.dice.roll` mutation diretta). I dettagli specifici dipendono da come è implementata oggi — leggi il file e segui lo stesso pattern.

- [ ] **Step 3: Verifica TypeScript**

```bash
cd webapp && npx tsc --noEmit
```

- [ ] **Step 4: Verifica visiva**

`npm run dev`, tira dadi da:
- DiceOverlay (FAB sulla pagina sheet) → animazione + risultato corretto.
- Pagina `/char/<id>/dice` → animazione + risultato corretto.
- Imposta `prefers-reduced-motion: reduce` in DevTools → niente animazione, risultato istantaneo.

Verifica DevTools Network: POST a `/dice/result`, payload `{rolls: [...]}`, mai a `/dice/roll`.

- [ ] **Step 5: Commit**

```bash
git add webapp/src/components/DiceOverlay.tsx webapp/src/pages/Dice.tsx
git commit -m "$(cat <<'EOF'
feat(dice): wire DiceOverlay + Dice page to useRollAndPersist

Both consumers now drive rolls through the unified hook (3D physics
result for animate3d=true, crypto.getRandomValues for false / reduced-
motion). All POSTs target /dice/result.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 6 — FAB + Settings UI + build prod

### Task 18: FAB hide su `/char/:id/settings`

**Files:**
- Modify: `webapp/src/components/DiceOverlay.tsx`

- [ ] **Step 1: Aggiungi check route**

In `webapp/src/components/DiceOverlay.tsx`, modifica `useOverlayVisibility` (righe ~24-44) aggiungendo subito dopo il check `/char/:id/dice`:

```ts
if (matchPath('/char/:id/settings', path)) return { visible: false, charId: null }
```

- [ ] **Step 2: Verifica visiva**

`npm run dev`:
- `/char/1/sheet` → FAB visibile.
- `/char/1/settings` → FAB sparisce, sidebar e Roll button anche.
- Torna a `/char/1/sheet` → FAB ricompare.

- [ ] **Step 3: Commit**

```bash
git add webapp/src/components/DiceOverlay.tsx
git commit -m "$(cat <<'EOF'
feat(dice): hide FAB on character settings page

Adds /char/:id/settings to the route list that suppresses DiceOverlay,
so the FAB doesn't overlap the settings UI.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 19: Settings UI — pack selector + i18n

**Files:**
- Modify: `webapp/src/pages/Settings.tsx`
- Modify: `webapp/src/locales/it.json`
- Modify: `webapp/src/locales/en.json`

- [ ] **Step 1: Aggiungi chiavi i18n**

In `webapp/src/locales/it.json`, aggiungi (inserisci sotto la sezione `settings.dice` o equivalente):

```json
"settings": {
  "dice": {
    "pack": {
      "title": "Pacchetto dadi",
      "description": "Seleziona un pacchetto di texture per i dadi 3D.",
      "preview": "Anteprima",
      "fallback_warning": "Il pacchetto selezionato non è completo: alcuni dadi useranno il rendering predefinito.",
      "disabled_hint": "Attiva l'animazione 3D per scegliere un pacchetto.",
      "load_error": "Impossibile caricare il pacchetto, ripristinato il predefinito."
    }
  }
}
```

(Mantieni le chiavi esistenti, aggiungi solo queste 6.) Analogo in `en.json`:

```json
"settings": {
  "dice": {
    "pack": {
      "title": "Dice pack",
      "description": "Select a texture pack for the 3D dice.",
      "preview": "Preview",
      "fallback_warning": "Selected pack is incomplete: some dice will use the default rendering.",
      "disabled_hint": "Enable 3D animation to pick a pack.",
      "load_error": "Failed to load pack, restored default."
    }
  }
}
```

- [ ] **Step 2: Aggiungi sezione pack selector in `Settings.tsx`**

Sotto il toggle "3D Dice Animation" esistente, aggiungi una sezione (adatta al pattern di sezioni del file). Esempio minimal (lo stile va adattato ai design tokens del progetto):

```tsx
import { useDiceSettings } from '@/store/diceSettings'
import { BUNDLED_PACKS } from '@/dice/packs/registry'
import { useDicePack } from '@/dice/packs/DicePackProvider'

// ... dentro il component Settings:
const animate3d = useDiceSettings((s) => s.animate3d)
const packId = useDiceSettings((s) => s.packId)
const setPackId = useDiceSettings((s) => s.setPackId)
const { loading, error } = useDicePack()

// JSX:
<section className={animate3d ? '' : 'opacity-50 pointer-events-none'}>
  <h3 className="text-lg font-bold">{t('settings.dice.pack.title')}</h3>
  <p className="text-sm text-dnd-text-faint">{t('settings.dice.pack.description')}</p>
  {!animate3d && (
    <p className="text-xs text-dnd-text-faint italic">
      {t('settings.dice.pack.disabled_hint')}
    </p>
  )}
  <div className="flex flex-col gap-2 mt-2">
    {BUNDLED_PACKS.map((id) => (
      <label key={id} className="flex items-center gap-2 cursor-pointer">
        <input
          type="radio"
          name="dice-pack"
          value={id}
          checked={packId === id}
          onChange={() => setPackId(id)}
          disabled={!animate3d}
        />
        <span>{id}</span>
      </label>
    ))}
  </div>
  {loading && <p className="text-xs text-dnd-text-faint">…</p>}
  {error && (
    <p className="text-xs text-dnd-crimson-bright">
      {t('settings.dice.pack.load_error')}
    </p>
  )}
</section>
```

(MVP: niente preview canvas. Preview inline è una future improvement — lo spec menziona preview ma può essere implementato dopo se l'effort blocca questo plan. Se vuoi includerlo subito, monta un `<DiceScene>` mini con un solo `DicePlayRequest` di un d20 che ruota lentamente — ma è una pagina aggiuntiva di codice.)

- [ ] **Step 3: Verifica TypeScript**

```bash
cd webapp && npx tsc --noEmit
```

- [ ] **Step 4: Verifica visiva**

`npm run dev`, vai a `/char/1/settings`, vedi sezione "Pacchetto dadi" con un'opzione `default` selezionata. Disabilita "3D Dice Animation" → sezione si oscura, hint i18n appare. Riabilitalo, seleziona `default` (riconferma) → niente errore.

- [ ] **Step 5: Commit**

```bash
git add webapp/src/pages/Settings.tsx webapp/src/locales/it.json webapp/src/locales/en.json
git commit -m "$(cat <<'EOF'
feat(settings): dice pack selector + i18n

Settings page exposes a radio-list of bundled packs persisted via
useDiceSettings. Disabled when animate3d is off. New i18n keys
under settings.dice.pack.{title,description,preview,disabled_hint,
fallback_warning,load_error}.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 20: Build prod + commit `docs/app/`

**Files:**
- Modify: `docs/app/` (output di Vite build)

- [ ] **Step 1: Pre-build sanity**

Verifica che siano committati:
- `.env.local` NON committato (gitignored)
- Tutti gli altri file source

```bash
git status
```

Expected: working tree pulito.

- [ ] **Step 2: Run build prod**

```bash
cd webapp && npm run build:prod
```

(Lo script `build-prod.sh` switcha `.env.local` su URL prod, builda, ripristina `.env.local`, e fa `git add docs/app/`.)

Expected output: `tsc && vite build` esce 0, `docs/app/` viene aggiornato e staged.

- [ ] **Step 3: Verifica diff**

```bash
git status
git diff --cached --stat
```

Expected: solo file dentro `docs/app/` modificati.

- [ ] **Step 4: Commit**

```bash
git commit -m "$(cat <<'EOF'
chore: rebuild webapp for 3d dice revamp

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 5: Final manual verification (utente, su Windows)**

Lo sviluppatore (utente) verifica end-to-end su Windows:

1. `uv run uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload`
2. `cd webapp && npm run dev`
3. Apri http://localhost:5173/, login con DEV_USER, naviga a `/char/<id>/dice`.
4. Tira un d20: fisica nuova, dadi rimbalzano contro bordi, atterrano, faccia in alto è risultato.
5. Tira 5d6: spawn separati, niente compenetrazioni iniziali.
6. Cambia pack a `default` (rimane default, niente texture). Verifica che selettore funzioni e niente errori.
7. Naviga a `/char/<id>/settings` → FAB sparisce.
8. Apri DevTools → Settings → Rendering → "Emulate CSS prefers-reduced-motion: reduce". Tira un dado → istantaneo, niente animazione.
9. DevTools Network: POST `/dice/result` chiamato con payload corretto.
10. Spegni 3D animation → risultato istantaneo.
11. Visita `/char/<id>/dice` → cronologia mostra i lanci.

Se tutto ok, il branch è pronto per PR.

- [ ] **Step 6: (Opzionale) Push e apri PR**

```bash
git push -u origin feat/3d-dice-revamp
gh pr create --title "feat(dice): 3D dice revamp — physics-driven results, UV texture packs, FAB hide" --body "<corpo PR generato manualmente con gh CLI guidance>"
```

(Da fare solo dopo conferma utente. Push automatico non desiderato.)

---

## Recap

20 task suddivise in 6 fasi:
- **Phase 1 (1-2)**: Modularizzazione physics + tuning costanti.
- **Phase 2 (3-6)**: Lancio "vero" + risultato dalla geometria + camera top-down.
- **Phase 3 (7-9)**: UV layouts + templates ComfyUI + pack `default` vuoto.
- **Phase 4 (10-13)**: Pack system (manifest, loader, provider, materials).
- **Phase 5 (14-17)**: API change + RNG fallback + hook `useRollAndPersist` + migrazione consumer.
- **Phase 6 (18-20)**: FAB hide + Settings UI + build prod.

Ogni task termina con `git commit` su `feat/3d-dice-revamp`. Verifica end-to-end manuale è step 5 di Task 20.

**Pacchetti custom (es. "hell dice"):** non parte di questo plan (richiedono asset generati via ComfyUI e dipende dalla disponibilità del workflow IA dell'utente). La struttura permette di aggiungere un pack in 3 step:
1. Genera PNG via ComfyUI usando `_templates/`.
2. Crea `webapp/public/dice-packs/hell_dice/` con `pack.json` + maps.
3. Aggiungi `'hell_dice'` a `BUNDLED_PACKS` in `registry.ts` + `npm run build:prod` + commit.

Future work elencato nello spec, sezione "Out-of-scope".
