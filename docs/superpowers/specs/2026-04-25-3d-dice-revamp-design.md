# 3D Dice Revamp — Design

**Date**: 2026-04-25
**Author**: Cioscos (with Claude)
**Scope**: webapp 3D dice subsystem
**Status**: approved by user, ready for plan phase

## Goals

1. Lanci di dadi più "fisici": forza maggiore, bordi schermo come muri tira-dadi, rimbalzi visibili.
2. Fisica realistica e naturale (gravity, friction, restitution, sleep).
3. Geometrie dei dadi con conteggio facce corretto (già OK, da preservare aggiungendo UV).
4. **Risultato del lancio determinato dalla geometria**: la faccia che resta esposta verso la telecamera dopo che la fisica si stabilizza è il valore. Niente snap pre-determinato.
5. Sistema di **texture pack custom** UV-mapped, con cartelle bundled (`webapp/public/dice-packs/<pack_id>/`), selezionabili dalle impostazioni, fallback a default se mancanti.
6. **FAB nascosto** quando l'utente è sulla pagina settings del personaggio.

## Non-goals

- Replay condivisi tra giocatori (multiplayer same-physics): fuori scope. Se un giorno servirà, valutare migrazione a Rapier deterministico.
- Anti-cheat su rolls inviati dal client: fuori scope (single-user app, equivalente a D&D Beyond).
- Pack uploadabili da UI: fuori scope, pack solo bundled per ora.
- Test automatizzati: nessuna suite configurata in repo, verifica manuale (vedi sezione Verification).

## Architectural decisions

### A1 — Risultato dalla geometria (modello "B" stile D&D Beyond)

**Decisione**: il client lancia i dadi liberamente, legge la faccia in alto a fine simulazione, invia il risultato al server.

**Razionale**: D&D Beyond usa lo stesso modello (confermato da staff DDB su forum ufficiale). Server-authoritative non offre vantaggi reali in app single-user (utente già può manipolare DOM/JS), e impedisce fisica naturale. Alternativa A (server pre-rolla, client snappa) fornirebbe sensazione fasulla; alternativa C (deterministico cross-platform Rapier) richiede infrastruttura sproporzionata.

**Conseguenze**:
- API: nuovo endpoint `POST /characters/{id}/dice/result` che accetta risultato dal client. Vecchio `POST /characters/{id}/dice/roll` rimosso.
- Death save resta server-authoritative (regola D&D 5e, source of truth lato server).
- Storia rolls: nessuna migrazione (record esistenti sono interi, schema invariato).

### A2 — Texture pack: UV-mapped PBR opzionale, bundled

**Decisione**: ogni pack è una cartella in `webapp/public/dice-packs/<pack_id>/` con `pack.json` + un albedo PNG obbligatorio per kind e mappe normal/roughness/emissive opzionali. Numerali decisi per pack tramite `numerals: "embedded" | "procedural"`.

**Razionale**: utente non è artista, genera texture via ComfyUI. UV singolo è più semplice per workflow IA (solo input texture per dado). PBR opzionale permette pack premium ("Hell Dice" con normal + emissive) senza forzare semplici a fornire mappe extra. Bundled = no backend, no upload UI, no validazione runtime di file utente. Manifest `numerals: "procedural"` garantisce leggibilità con pack semplici (overlay canvas attuale); `numerals: "embedded"` permette pack con numeri tematici dipinti dall'IA.

### A3 — Engine fisica: cannon-es retunato (no migrazione)

**Decisione**: si mantiene `cannon-es` (versione 0.20.0 già in `package.json`). Si retuna costanti, walls, forze.

**Razionale**: cannon-es funziona oggi. I problemi attuali sono di tuning, non di engine. Migrazione a Rapier porterebbe +500KB WASM bundle, rewrite completo di `physics.ts`, e regressioni potenziali sulle geometrie convex polyhedra. Beneficio (deterministic mode) non serve a questo flusso.

### A4 — FAB hide via route check

**Decisione**: in `webapp/src/components/DiceOverlay.tsx`, `useOverlayVisibility()` aggiunge check su `/char/:id/settings`. Settings è una page route esistente, non un modale → check route-based è sufficiente.

## File layout (target)

```
webapp/src/dice/
├── DiceScene.tsx              # canvas + orchestrazione (modificato)
├── DiceAnimationProvider.tsx  # context + lazy load (invariato)
├── useDiceAnimation.ts        # hook (invariato)
├── types.ts                   # types (esteso: PackId, DetectedResult)
├── physics/
│   ├── world.ts               # cannon-es world setup, walls, gravity (estratto)
│   ├── spawner.ts             # spawn con force/velocity scalate (estratto)
│   ├── faceDetector.ts        # legge faccia in alto da quaternion finale (NUOVO)
│   └── constants.ts           # costanti tunabili (NUOVO)
├── geometries/
│   ├── index.ts               # entry point (esteso con UV)
│   └── uvLayouts.ts           # UV mapping per kind (NUOVO)
├── packs/
│   ├── registry.ts            # lista bundled packs (NUOVO)
│   ├── loader.ts              # fetch + cache texture/manifest (NUOVO)
│   ├── manifest.ts            # schema Zod + parser pack.json (NUOVO)
│   └── fallback.ts            # fallback chain a default (NUOVO)
├── materials.ts               # esteso: applica pack texture, numerali condizionali
├── numeralTexture.ts          # invariato (usato solo se pack.numerals=procedural)
├── rng.ts                     # crypto.getRandomValues per fallback no-3D (NUOVO)
├── useRollAndPersist.ts       # hook unificato roll → persist (NUOVO)
└── preload.ts                 # invariato

webapp/public/dice-packs/
├── default/
│   └── pack.json              # pack vuoto, fallback rendering procedurale
├── hell_dice/
│   ├── pack.json
│   ├── d4.albedo.png
│   ├── d4.normal.png
│   ├── d4.roughness.png
│   ├── d4.emissive.png
│   ├── d6.albedo.png
│   └── ...                    # set per d4/d6/d8/d10/d12/d20
└── _templates/                # template UV (committati, non caricati a runtime)
    ├── d4.uv.png
    ├── d6.uv.png
    └── ... + README.md con istruzioni ComfyUI

api/
├── routers/dice.py            # rimosso /roll, aggiunto /result
└── schemas/dice.py            # DiceResultRequest, DiceResultEntry

webapp/scripts/
└── generate-uv-templates.ts   # script una-tantum, genera _templates/*.uv.png da geometrie (NUOVO)
```

## Section 1 — Architecture overview

Webapp store `diceSettings` esteso:

```ts
interface DiceSettings {
  animate3d: boolean
  packId: string  // 'default' | 'hell_dice' | ...
}
```

Persistito in localStorage, key `dnd-dice-settings` (esistente).

`DiceAnimationProvider` invariato come API esterna; internamente usa nuovi moduli `physics/`, `packs/`. Il pack corrente (`LoadedPack`) è esposto via un nuovo `DicePackProvider` (context) consumato da `DiceScene` e dal preview in Settings. `DiceScene` legge il pack dal contesto e lo passa a `getDiceMaterial()`.

Tre code path per il roll:
1. **3D fisica** (`animate3d=true` AND non reduced-motion): hook `useRollAndPersist` invoca animation → physics → face detect → POST `/dice/result`.
2. **Fallback no-3D** (`animate3d=false` OR reduced-motion): hook genera valori via `crypto.getRandomValues` → POST `/dice/result`.
3. **Death save** (`POST /death_saves/roll`): server-side, invariato.

## Section 2 — Physics retune & geometry-driven result

### Costanti (in `dice/physics/constants.ts`)

| Parametro | Attuale | Nuovo | Note |
|---|---|---|---|
| `gravity` | -16 | **-32** | Caduta più rapida |
| `throwLinearVelocity` | random ±0.5 | **random 4–7 + direzione orizzontale casuale (cono ±20° da -Z)** | Lancio "forte" |
| `throwAngularVelocity` | random ±6 | **random ±25 (per asse)** | Spin marcato |
| `floorRestitution` | 0.3 | **0.55** | Rimbalzi su pavimento visibili |
| `wallRestitution` | 0.3 | **0.7** | Bordi schermo come muri |
| `friction` | 0.45 | **0.4** | Rotolamento più lungo |
| `linearDamping` | 0.15 | **0.1** | Meno smorzamento |
| `angularDamping` | 0.18 | **0.1** | Spin dura più a lungo |
| `sleepSpeedLimit` | 0.18 | **0.05** | Soglia sleep più stretta |
| `sleepTimeLimit` | 0.35s | **0.6s** | Verifica reale fermata |
| `simulationHardTimeoutMs` | (n/a) | **5000** | Force-sleep dopo 5s |

### Walls dinamiche

Walls oggi fissi a `±1.0` X/Z. Nuovo: `world.ts` esporta `updateWalls(viewport, camera)`. Walls calcolate proiettando i bordi schermo sul piano floor (`y = -0.9`) tramite raycast inverso da camera. Hot-update su `window.resize` event.

Soffitto invisibile a `y = +5` per evitare che dadi escano dall'alto con spin alto.

### Spawner (`dice/physics/spawner.ts`)

- Spawn area: dentro il frustum visibile, lato player (asse +Z, davanti alla telecamera), in alto. Centro spawn a `(random(-0.4, 0.4), 3.5 + random(0..0.4), 1.0)` — già dentro le walls dinamiche, alto sopra il floor.
- Direzione lancio: vettore `(0, 0, -1)` ruotato di cono random ±20° su Y.
- Magnitudine velocità linear: `random(4, 7)`.
- Spin angolare: `random(±25)` per asse.
- Quaternion iniziale: `THREE.Quaternion.random()` (nessun bias).
- Dadi multipli stesso group: spawn con offset X piccolo (±0.3) per evitare collisione iniziale tra di loro.

### `dice/physics/faceDetector.ts`

```ts
detectFaceUp(
  faceNormals: Record<number, THREE.Vector3>,  // already in DiceGeometryData
  bodyQuaternion: CANNON.Quaternion,
  worldUp: THREE.Vector3 = new THREE.Vector3(0, 1, 0)
): { value: number; dot: number }
```

Per ogni face normal: ruota tramite quaternion → ottieni world-space normal → calcola `dot(worldNormal, worldUp)`. Faccia con `dot` massimo = faccia in alto. Restituisce anche dot per logica retry.

### Phase order in `DiceScene`

`idle → simulating → reading → holding → idle` (sostituisce `snapping`).

**`simulating`**:
- `world.step(1/60, deltaTime, 3)` ogni frame.
- Sync visivo body → mesh.
- Esci quando **tutti** body `sleepState === Body.SLEEPING` OR `simulationHardTimeoutMs` scaduto (in tal caso `body.sleep()` forzato).

**`reading`**:
- Per ogni body: `detectFaceUp` su quaternion finale.
- Se `dot < cos(15°)` (≈ 0.966): orientamento ambiguo (dado su spigolo). Applica nudge: `body.wakeUp()` + piccolo impulso casuale verso il basso (`applyImpulse` su top centroid) + torch angolare random. Re-trigger `simulating` per quel body (max 2 retry per body). Counter `body.userData.readRetries` incrementato. Dopo 2 retry: accetta valore con dot massimo trovato.
- Salva `value` in `body.userData.detectedValue`.

**`holding`**:
- 1.5s come oggi, scale-up animation.
- Niente movimento del dado (no snap).

### Telecamera

`<PerspectiveCamera makeDefault position={[0, 5.5, 1.8]} fov={42}>`. Vista leggermente top-down, faccia in alto della fisica = faccia visibile al player.

### Output

`DiceScene.onComplete(results: DetectedResult[])` dove `DetectedResult = { kind: DiceKind; value: number; groupIndex: number }`. Provider chiama callback consumer.

## Section 3 — Texture pack format

### Manifest (`pack.json`)

```json
{
  "id": "hell_dice",
  "name": "Hell Dice",
  "author": "Cioscos",
  "version": "1.0.0",
  "numerals": "procedural",
  "tints": {
    "normal": { "ink": "#1a0a0a", "outline": "#ffd66b" },
    "crit":   { "ink": "#fff5cc", "outline": "#fff5cc" },
    "fumble": { "ink": "#ffaaaa", "outline": "#ffaaaa" }
  },
  "material": {
    "metalness": 0.3,
    "roughness": 0.55,
    "envMapIntensity": 1.2
  },
  "dice": {
    "d4":  { "albedo": "d4.albedo.png", "normal": "d4.normal.png", "roughness": "d4.roughness.png", "emissive": "d4.emissive.png", "emissiveIntensity": 0.8 },
    "d6":  { "albedo": "d6.albedo.png" },
    "d8":  { "albedo": "d8.albedo.png", "normal": "d8.normal.png" },
    "d10": { "albedo": "d10.albedo.png" },
    "d12": { "albedo": "d12.albedo.png" },
    "d20": { "albedo": "d20.albedo.png", "normal": "d20.normal.png", "roughness": "d20.roughness.png", "emissive": "d20.emissive.png", "emissiveIntensity": 1.0 }
  }
}
```

**Schema Zod** in `dice/packs/manifest.ts`. Validazione fail-fast: pack invalido → fallback a `default`.

**Regole**:
- `albedo` obbligatorio per ogni kind dichiarato. Altre maps opzionali.
- Kind non dichiarato in `dice` → quel kind cade su default per quel pack (numerali procedurali, niente body texture).
- `numerals: "embedded"` → numerali parte dell'albedo, niente overlay procedurale. `tints` ignorato per questo pack.
- `numerals: "procedural"` → texture body senza numeri, overlay canvas-generated come oggi. `tints` se presente sovrascrive i colori default per i tint dichiarati (`normal`, `crit`, `fumble`, `arcane`, `ember`).
- `material` opzionale, default ai valori attuali (metalness 0.15, roughness 0.55).

### Pack `default`

`webapp/public/dice-packs/default/pack.json`:

```json
{
  "id": "default",
  "name": "Default",
  "numerals": "procedural",
  "dice": {}
}
```

Pack vuoto = render procedurale attuale, code path unificato.

### Registry

`webapp/src/dice/packs/registry.ts`:

```ts
export const BUNDLED_PACKS = ['default', 'hell_dice'] as const
export type PackId = typeof BUNDLED_PACKS[number]
```

Aggiungere un pack = entry in array + cartella in `public/dice-packs/`.

### Loader

`webapp/src/dice/packs/loader.ts`:

```ts
async function loadPack(id: PackId): Promise<LoadedPack>
disposePack(id: PackId): void
```

- Fetch `/dice-packs/{id}/pack.json` → parse + validate Zod.
- Per ogni kind: `THREE.TextureLoader.loadAsync` per albedo (sempre se dichiarata) + normal/roughness/emissive (se presenti).
- Texture: `colorSpace = SRGBColorSpace` per albedo+emissive, `LinearSRGBColorSpace` per normal+roughness; `wrapS/T = ClampToEdge`; `anisotropy = renderer.capabilities.getMaxAnisotropy()`.
- Cache module-level per pack ID.
- Switch pack: `disposePack(prev)` libera `texture.dispose()` di tutte le texture caricate.
- Errori (file 404, JSON invalido, mancata albedo per kind dichiarato): log warning, fallback automatico a `default`. Toast errore mostrato all'utente.

### UV Layouts

`webapp/src/dice/geometries/uvLayouts.ts`: per ogni kind, mapping deterministico face index → cella UV in atlas 1024×1024.

| Kind | Layout cells | Cell size | Forma cella |
|---|---|---|---|
| d4 | 2×2 | 512×512 | Triangolo iscritto |
| d6 | 3×2 | ~341×512 | Quadrato pieno |
| d8 | 4×2 | 256×512 | Triangolo |
| d10 | 5×2 | ~204×512 | Kite iscritto |
| d12 | 4×3 | 256×~341 | Pentagono iscritto |
| d20 | 5×4 | ~204×256 | Triangolo |

**Index → cella**: face index ordinato come oggi in `geometries/index.ts`. UV computato dal `FaceFrame` esistente (ha `up`, `halfWidth`, `halfHeight`) trasformato a UV-space nella cella corrispondente.

`BufferGeometry.setAttribute('uv', uvArray)` aggiunto in fase di build geometria (one-shot, cached come oggi).

`computeTangents()` chiamato dopo set UV per supportare normal map correttamente.

### UV templates per ComfyUI

Script `webapp/scripts/generate-uv-templates.ts` (eseguibile manualmente, una-tantum):
- Per ogni kind: rasterizza griglia + numero centro-cella + bordo a `webapp/public/dice-packs/_templates/<kind>.uv.png`.
- Output committato nel repo. Non caricato a runtime.

README in `_templates/` documenta workflow ComfyUI:
1. Apri `<kind>.uv.png` come ControlNet input (Canny/Depth).
2. Prompt tematico (es. "molten lava texture, embers, hellish theme, 1024x1024, seamless cells").
3. Output: `<kind>.albedo.png` con stesso layout.
4. Per normal map: nodo `Image to Normal` ComfyUI → `<kind>.normal.png`.
5. Per roughness: `Image to Roughness` o desaturate+invert → `<kind>.roughness.png`.
6. Per emissive: mask zone "calde" + isolate → `<kind>.emissive.png`.
7. Drop tutti i PNG in `webapp/public/dice-packs/<pack_id>/`, scrivi `pack.json`, aggiungi entry in `registry.ts`.

### Materiale composto (`materials.ts`)

`getDiceMaterial(kind, tint, pack)`:

- Se `pack.dice[kind]` con almeno `albedo` esiste:
  - `MeshStandardMaterial` con `map = albedoTexture`, `normalMap`, `roughnessMap`, `emissiveMap`, `emissiveIntensity` se presenti.
  - `metalness/roughness/envMapIntensity` da `pack.material` (con fallback ai default attuali).
  - Tint applicato come overlay color (`material.color`) solo per `numerals === "procedural"` (tint visivo del corpo); per `embedded` tint ignorato (texture è già definitiva).
- Altrimenti (pack default o kind non dichiarato): material procedurale attuale (codice esistente in `materials.ts`).

`pack.numerals === "procedural"` → `numeralTexture.ts` genera overlay come oggi, ma `getNumeralTexture` accetta opzionali `inkColor/outlineColor` da `pack.tints[tint]` se presenti.

`pack.numerals === "embedded"` → niente chiamate a `numeralTexture.ts`, niente overlay quad.

## Section 4 — API & state flow

### Endpoint nuovo

`POST /characters/{id}/dice/result` in `api/routers/dice.py`:

```python
class DiceResultEntry(BaseModel):
    kind: Literal["d4", "d6", "d8", "d10", "d12", "d20"]
    value: int

class DiceResultRequest(BaseModel):
    rolls: list[DiceResultEntry] = Field(min_length=1, max_length=50)
    label: str | None = Field(default=None, max_length=120)
    modifier: int = 0
    notation: str | None = Field(default=None, max_length=80)
```

**d100 handling**: il client lo splitta sempre in 2 entry `kind="d10"` (uno per decine 0..9, uno per unità 0..9). Il server **non** ha mai un `kind="d100"`. Convention identica al codice attuale che usa già 2× d10 per il dado a 100 facce. Riferimento: `DiceScene.tsx:126-134`. La label/notation client esprime il fatto che siano d100 (es. `notation: "1d100"`).

Validazione:
- Range per kind:
  - d4: 1..4
  - d6: 1..6
  - d8: 1..8
  - d10: 0..9
  - d12: 1..12
  - d20: 1..20
- Out-of-range → `400 Bad Request`.
- Auth: `Depends(get_current_user)` come tutti gli altri endpoint.
- Ownership: `_get_owned(session, Character, char_id, user_id)`.
- Salva in `roll_history` (stesso schema di oggi).
- Ritorna `{id, total, rolls, modifier, label, notation, created_at}`.

### Endpoint rimosso

`POST /characters/{id}/dice/roll` rimosso. Single-user app, no consumatori esterni → safe. Webapp non lo usa più.

### Endpoint invariati

- `POST /characters/{id}/dice/post-to-chat` — invariato.
- `DELETE /characters/{id}/dice/history` — invariato.
- `POST /characters/{id}/death_saves/roll` — invariato (server-authoritative per rule compliance).

### Client flow (animate3d=true, no reduced-motion)

```
User clicks "Roll"
    → useRollAndPersist({entries, label?, modifier?})
    → DicePlayRequest costruito SENZA results
    → DiceAnimationProvider.play(request) → mount DiceScene
    → DiceScene: spawn → simulating → reading → holding
    → DiceScene.onComplete(detectedResults)
    → mutation TanStack Query: POST /dice/result {rolls, label, modifier}
    → toast risultato
    → opzionale: send to chat (POST .../dice/post-to-chat)
```

### Client flow (animate3d=false OR reduced-motion)

```
User clicks "Roll"
    → useRollAndPersist({entries, ...})
    → branch: rng path
    → rollMany() per kind con crypto.getRandomValues + rejection sampling
    → POST /dice/result diretto
    → toast risultato istantaneo
```

### `dice/rng.ts`

```ts
export function rollDie(sides: number): number  // crypto.getRandomValues + rejection sampling
export function rollMany(kind: DiceKind, count: number): number[]
```

d100 split: come oggi, due d10 separati (decine 0/10/.../90, unità 0..9). Convention mantenuta.

### `dice/useRollAndPersist.ts`

```ts
function useRollAndPersist(charId: number) {
  const { animate3d, packId } = useDiceSettings()
  const reducedMotion = useReducedMotion()
  const animationApi = useDiceAnimation()
  const mutation = useMutation({ mutationFn: postDiceResult })

  return {
    roll: async (entries: RollEntry[], opts?: {label?, modifier?, notation?}) => SavedRoll
  }
}
```

Internamente sceglie code path. Sostituisce uso diretto di `dice/roll` mutation in `Dice.tsx` e `DiceOverlay.tsx`.

### Errori

| Caso | Handling |
|---|---|
| Network fail su POST `/dice/result` | Toast errore + retry button. Animazione visibile, ma non persistito. |
| Validation 400 | Log a console + toast generico. Indica bug face detector → alert sviluppatore. |
| Physics timeout | Force sleep + read. Risultato emesso comunque. |
| Pack load fail | Fallback a `default`, toast warning. |
| Reduced-motion + crypto.getRandomValues fail | Estremamente raro. Fallback `Math.random()` + warning console. |

## Section 5 — Settings UI, FAB hide, edge cases

### Settings page (`webapp/src/pages/Settings.tsx`)

Nuova sezione sotto il toggle "3D Dice Animation":

```
[Section: Dice pack]
  [Description text]
  [Selector: dropdown / radio cards con icona pack]
    ○ Default
    ● Hell Dice
  [Preview: piccolo Canvas 300×200 mostrando un d20 statico autorotate col pack selezionato]
  [Loading spinner mentre fetch texture per cambio pack]
```

- Selection persistita in `diceSettings` store (key `dnd-dice-settings`).
- Cambio pack: `setPackId(id)` → loader fetch + cache. Preview aggiornato (cambio texture istantaneo).
- Pack non disponibile: toast errore, dropdown torna a `default`.
- Disabled state: se `animate3d=false`, sezione dimmed con hint i18n `settings.dice.pack.disabled_hint`.

### i18n keys nuove

In `webapp/src/locales/it.json` e `en.json`:

- `settings.dice.pack.title`
- `settings.dice.pack.description`
- `settings.dice.pack.preview`
- `settings.dice.pack.fallback_warning`
- `settings.dice.pack.disabled_hint`
- `settings.dice.pack.load_error`

### FAB hide

`webapp/src/components/DiceOverlay.tsx:24-44` (`useOverlayVisibility`):

```ts
function useOverlayVisibility(): { visible: boolean; charId: number | null } {
  const location = useLocation()
  const activeCharId = useCharacterStore((s) => s.activeCharId)
  const path = location.pathname

  if (matchPath('/char/:id/dice', path)) return { visible: false, charId: null }
  if (matchPath('/char/:id/settings', path)) return { visible: false, charId: null }  // NUOVO
  // ... rest invariato (sheet, session)
}
```

Side-effect: anche sidebar kind buttons e Roll button spariscono. Voluto.

### Edge cases

| Caso | Comportamento |
|---|---|
| Pack dichiara solo `albedo` per d20, user tira d6 | d6 cade su default per quel pack |
| `pack.json` malformato | Loader fail → fallback `default`, toast warning |
| Texture PNG 404 | Loader fail per quel pack → fallback `default`, toast warning |
| Cambio pack durante animazione in corso | Pack switch pending finché animazione finisce, poi applicato |
| Memoria GPU dopo molti switch | `disposePack(prevId)` libera texture vecchie |
| Pack `default` (vuoto) | Code path identico ad oggi, zero texture caricate |
| Dado finisce su spigolo (orientamento ambiguo) | `reading` retry con nudge (max 2), poi accetta dot massimo |
| Fisica timeout 5s | Force sleep + read |
| Network fail su POST `/dice/result` | Toast errore con retry, animazione già visibile |
| `animate3d=false` o reduced-motion | Bypass fisica, `crypto.getRandomValues` → POST diretto |

## Verification

Nessuna test suite configurata. Verifica manuale prima di considerare "done":

1. **Distribuzione**: lancia 100× d20 in DevTools console (script ad-hoc), conta occorrenze, verifica visivamente uniforme.
2. **Walls**: ridimensiona browser durante animazione, dadi non escono dallo schermo.
3. **Face detection**: durante `reading`, log `{detectedFace, dot}`. `dot` sempre > cos(15°) o retry triggerato.
4. **Pack switch**:
   - Default → Hell Dice → Default. Texture cambia, `performance.memory` stabile dopo 10 switch.
   - Pack con file mancante → fallback `default`, toast.
5. **FAB**:
   - `/char/1/sheet` → FAB visibile.
   - `/char/1/settings` → FAB sparisce.
   - Torna a `/char/1/sheet` → FAB ricompare.
6. **Reduced motion**: imposta `prefers-reduced-motion: reduce` in DevTools, tira → nessuna animazione, risultato istantaneo.
7. **API**:
   - DevTools Network: POST `/dice/result` chiamato dopo physics, non prima.
   - GET `/dice/history` mostra il roll appena fatto.
   - `/dice/roll` (vecchio) ritorna 404.
8. **TypeScript**: `cd webapp && npx tsc --noEmit` passa.
9. **Build prod**: `cd webapp && npm run build:prod` (genera `docs/app/`, da committare).

## Risks

1. **Cannon-es convex polyhedra sleep bug**: `sleepSpeedLimit` basso può causare twitch occasionali. Mitigato da `sleepTimeLimit` 0.6s + retry su orientamento ambiguo.
2. **Bundle size**: pack assets servono come static. Default ~zero, Hell Dice PBR ~3MB. Bundled = +~3MB su `docs/app/`. Accettabile, GitHub Pages serve. Pack futuri additivi.
3. **UV layout schema v1**: il layout celle (sezione 3) è "schema v1". Cambiarlo in futuro invalida tutti i pack esistenti che lo seguivano. Decisione conscia di non aggiungere campo `uvLayoutVersion` al manifest finché esiste un solo schema; se in futuro nascerà v2, allora si aggiunge il campo + migrazione. Va da sé che il layout v1 deve essere studiato bene una volta sola (cell sizes, ordine indici, allineamento `FaceFrame.up`).
4. **ComfyUI workflow**: documentazione minima a corredo. README in `_templates/` con istruzioni base. Utente principale (Cioscos) familiare con ComfyUI.
5. **Death save**: resta server-side, nessuna interazione con questo redesign.
6. **Race condition pack-switch durante animazione**: gestito con pending switch. Test manuale richiesto.
7. **Reduced-motion regression**: il path `crypto.getRandomValues` deve passare lo stesso schema validation server-side. Test manuale.

## Out-of-scope (future work)

- Pack uploadabili da UI con scompattazione ZIP backend.
- Cataloghi pack remoti (CDN, marketplace).
- Replay condivisi multiplayer (richiederebbe Rapier deterministico).
- Editor UV in-app per modificare layout senza rigenerare templates.
- Animazione fisica condivisa in sessioni di gruppo (vedi sopra).
- Migrazione a Rapier engine (giustificata solo se cannon-es diventa bloccante).
