# Dice Pool Cap Fix + Heroic Inspiration Reroll

**Date:** 2026-04-29
**Branch:** `fix/dice-cap-and-inspiration-reroll`
**Scope:** Two independent items shipped together.

---

## 1. Problem Statement

### 1.1 Bug — DiceOverlay rolls fail at high count

Rolling a large pool from `DiceOverlay` (e.g. 50d20) returns **422 Unprocessable Entity** from `POST /characters/{id}/dice/result`. Root cause: server schema caps `rolls` array at 50 entries (`api/schemas/common.py:283`):

```python
rolls: list[DiceResultEntry] = Field(min_length=1, max_length=50)
```

The `DiceOverlay` FAB has no client-side cap, so users can stack arbitrary counts and trigger the validation error. Symptom in browser: 3D animation completes, no result modal appears, network tab shows 422. A console error from `THREE.BufferGeometry.computeTangents()` (`webapp/src/dice/geometries/index.ts:424`) is also visible — cosmetic, unrelated to the block, present on every cache miss because dice geometries are non-indexed.

### 1.2 Feature — Heroic inspiration reroll

D&D 5e: heroic inspiration lets the player reroll a d20 on attack rolls, ability checks (incl. skill checks), or saving throws. Currently the app stores `characters.heroic_inspiration` (boolean) and toggles it manually from `HeroScreen`, but it has no integration with the roll flow.

The existing dice result UX is inconsistent: `SavingThrows` and `Skills` use the centered `RollResultModal`, `Inventory` weapon attack uses `WeaponAttackModal`, but `DiceOverlay` shows a transient bottom toast (auto-dismissed at 3000ms). The toast is replaced by a parchment-styled popup matching the modal family.

---

## 2. Decisions (Q&A)

| # | Question | Answer |
|---|----------|--------|
| Q1 | Where to place the inspiration reroll button | DiceOverlay popup + RollResultModal + WeaponAttackModal |
| Q2 | DiceOverlay reroll scope with mixed pools | Button visible **only** when pool is exactly `1d20` |
| Q3 | Reroll output | Replaces previous result (RAW) |
| Q4 | WeaponAttack reroll scope | Re-executes full attack server-side (new to-hit AND new damage). Inspiration is the gate, but the reroll re-runs the whole flow. |
| — | Dice pool caps | **Server `max_length=200`**, **client cap=100** |
| — | Branch strategy | New branch `fix/dice-cap-and-inspiration-reroll` from `main` |

---

## 3. Architecture

```
DiceOverlay  ──► DicePoolResultModal (NEW)
                       └──► InspirationRerollButton (NEW)
                              └─► api.characters.updateInspiration(false)
                                  + dice.playAndCollect + api.dice.result

SavingThrows ──► RollResultModal (extended)
Skills       ──┘      └──► InspirationRerollButton
                              └─► api.characters.rollSavingThrow|rollSkill
                                  ({ die, with_inspiration: true })

Inventory    ──► WeaponAttackModal (extended)
                       └──► InspirationRerollButton
                              └─► api.items.attack(charId, itemId,
                                  { with_inspiration: true })
```

`InspirationRerollButton` is a pure presenter (icon + label + disabled state). Reroll logic lives in caller hooks because the flow differs between DicePool (PATCH inspiration + new pool roll + log) and d20 modals (single endpoint with `with_inspiration` flag).

Backend roll endpoints consume inspiration atomically inside the existing transaction: validate → set `heroic_inspiration=False` → re-roll → log history → return result.

---

## 4. Backend Changes

### 4.1 Schema cap bump + inspiration flag

`api/schemas/common.py:283`:

```python
class DiceResultRequest(BaseModel):
    rolls: list[DiceResultEntry] = Field(min_length=1, max_length=200)
    label: str | None = Field(default=None, max_length=120)
    modifier: int = 0
    notation: str | None = Field(default=None, max_length=80)
    with_inspiration: bool = False
```

`api/routers/dice.py` `post_dice_result` consumes inspiration atomically when `with_inspiration=True`: validate, set `char.heroic_inspiration=False`, prefix the history description with `"Reroll ispirazione — "`. Single transaction, no partial state.

No DB migration needed.

### 4.2 D20RollSubmission extension

`api/schemas/character.py`:

```python
class D20RollSubmission(BaseModel):
    die: int | None = None
    with_inspiration: bool = False
```

### 4.3 AttackSubmission introduction

`api/schemas/inventory.py` (or add inline in `api/routers/items.py`):

```python
class AttackSubmission(BaseModel):
    with_inspiration: bool = False
```

The current attack endpoint takes no body. Add an **optional** body parameter (`Body(None)`) so existing callers keep working.

### 4.4 Endpoint changes

#### `POST /characters/{id}/skills/{skill_name}/roll`
**File:** `api/routers/characters.py`
**Change:** read `body.with_inspiration`. If true:
- Reject with 409 `Conflict` if `char.heroic_inspiration` is False.
- Set `char.heroic_inspiration = False`.
- Prepend `"Reroll ispirazione — "` to the history description.

#### `POST /characters/{id}/saving_throws/{ability}/roll`
Same pattern.

#### `POST /characters/{id}/items/{item_id}/attack`
**File:** `api/routers/items.py`
**Change:** accept `body: AttackSubmission | None = Body(None)`. If `body and body.with_inspiration`:
- Reject 409 if no inspiration.
- Consume `heroic_inspiration`.
- Prepend `"Reroll ispirazione (to-hit) — "` to history.
- Re-roll the entire attack (to-hit + damage as today). Damage rerolls are a side effect of rerolling the attack as a whole; only one inspiration is consumed.

### 4.5 New history descriptions

- `"Reroll ispirazione — Abilità Persuasione: d20=15 +3 = 18"`
- `"Reroll ispirazione — TS Destrezza: d20=4 +2 = 6"`
- `"Reroll ispirazione (to-hit) — Spada lunga: colpire d20=12+5=17 | Danno: 6+3=9"`

### 4.6 Atomicity

All three endpoints already run inside FastAPI's request-scoped `AsyncSession` with a single commit at lifespan boundary. Adding the inspiration mutation in the same handler keeps the operation atomic — if anything raises before commit, the DB rolls back and inspiration is preserved.

---

## 5. Frontend Changes

### 5.1 New components

#### `webapp/src/components/InspirationRerollButton.tsx`

```tsx
type Props = {
  available: boolean
  pending: boolean
  onClick: () => void
}
```

Render returns `null` when `available` is false. Otherwise: a button styled like the parchment modal `OK` button but using `bg-gradient-arcane` with a star icon (`GiPolarStar` from `react-icons/gi`) + label `t('character.inspiration.use_reroll')`. Disabled while `pending`. Tap scale 0.95.

#### `webapp/src/components/DicePoolResultModal.tsx`

Replaces the bottom toast in `DiceOverlay`. Layout mirrors `RollResultModal`:
- Centered modal, parchment background, gold border, `CornerFlourishes`.
- Title row: `t('character.dice_overlay.result_title')`.
- Per-group breakdown using existing `formatRollList()` helper (lines 19–28 of current `DiceOverlay.tsx`).
- Big total at the bottom.
- Inspiration button visible only when both:
  1. The pool is exactly `[{ kind: 'd20', count: 1 }]`.
  2. `char.heroic_inspiration === true`.
- After reroll: badge `t('character.inspiration.reroll_badge')` ("↻ Reroll ispirazione"), button hidden.

Props:

```tsx
type Props = {
  results: RollGroup[]
  pool: DicePool
  charId: number
  inspirationAvailable: boolean
  onClose: () => void
}
```

The reroll flow lives inside the modal because it needs access to `dice.playAndCollect`, `api.dice.result`, and `api.characters.updateInspiration`. Internal state: `wasRerolled`, `isRerolling`.

### 5.2 Modified components

#### `RollResultModal.tsx`

Add optional props:

```tsx
type Props = {
  result: RollResult
  title: string
  onClose: () => void
  inspirationAvailable?: boolean
  onInspirationReroll?: () => Promise<void>
  isRerolling?: boolean
  wasRerolled?: boolean
}
```

When `inspirationAvailable && onInspirationReroll && !wasRerolled`, render `<InspirationRerollButton>` above the OK button. When `wasRerolled`, render the reroll badge in the title row. The component remains **controlled** — caller updates `result` after a successful reroll.

#### `WeaponAttackModal.tsx`

Same pattern. Inspiration button visible only when `inspirationAvailable && !wasRerolled`. Damage section auto-updates because the caller passes the fresh `WeaponAttackResult` after the reroll.

#### `DiceOverlay.tsx`

- Remove the result toast block (lines 268–305) and the `errorVisible` toast.
- Mount `<DicePoolResultModal>` instead.
- Add a client cap on pool total in `increment()`:

```ts
const POOL_CAP = 100

const increment = useCallback((kind: DiceKind) => {
  setPool((p) => {
    const total = Object.values(p).reduce((s, n) => s + (n ?? 0), 0)
    if (total >= POOL_CAP) {
      haptic.warning?.()
      // toast: "Limite massimo dadi raggiunto"
      return p
    }
    haptic.light()
    return { ...p, [kind]: (p[kind] ?? 0) + 1 }
  })
}, [])
```

Toast surface: a transient warning toast (similar to the existing error toast slot, kept for this case).

### 5.3 Caller updates (saves, skills, attack)

`SavingThrows.tsx`, `Skills.tsx`, `Inventory.tsx`: each `useState` for the modal result becomes a small reducer-like state including `wasRerolled` and `isRerolling`. The `rollMutation` gains a sibling mutation `rerollWithInspiration` that:

1. Optimistically disables further rerolls.
2. Plays the 3D animation (when `animate3d && !reducedMotion`) to obtain a fresh die.
3. Calls the same roll endpoint with `with_inspiration: true`.
4. On success: replaces `result`, sets `wasRerolled: true`, invalidates `['character', charId]`.
5. On 409: shows error toast, restores button state, keeps modal open.
6. On other errors: same as 409 (no inspiration consumed because backend rolls back).

### 5.4 Reroll flow — DiceOverlay (DicePool)

```
1. Click "Usa Ispirazione" (visible only if pool === 1d20 and char has inspiration)
2. dice.playAndCollect([{ kind: 'd20', count: 1 }]) → fresh die
3. api.dice.result(charId, {
     rolls: [{ kind: 'd20', value: die }],
     label: "Reroll ispirazione",
     notation: "1d20",
     with_inspiration: true,
   })
4. setResults(new) + setWasRerolled(true)
5. qc.invalidateQueries(['character', charId])
```

Single API call. Server consumes inspiration and persists the roll in one transaction. If the call fails, inspiration is preserved (rollback) and the reroll surfaces as a retryable toast — same UX as d20 modals.

### 5.5 i18n keys to add

`webapp/src/locales/it.json` and `en.json`:

```
character.inspiration.use_reroll        — "Usa Ispirazione" / "Use Inspiration"
character.inspiration.reroll_badge      — "↻ Reroll ispirazione" / "↻ Inspiration reroll"
character.inspiration.unavailable_error — "Ispirazione non disponibile" / "Inspiration unavailable"
character.dice_overlay.result_title     — "Risultato" / "Result"
character.dice_overlay.pool_cap_reached — "Limite massimo dadi raggiunto" / "Maximum dice limit reached"
```

### 5.6 Bug fix — computeTangents warning

`webapp/src/dice/geometries/index.ts:424`: remove the line. THREE.js MeshStandardMaterial falls back to derivative-based tangents in the shader when the attribute is missing, so visual quality is unaffected for the procedural materials in this project. Pack normal-map quality is unaffected too because the derivative fallback handles it.

---

## 6. Error Handling & Edge Cases

| Case | Behavior |
|------|----------|
| `with_inspiration=true` but `heroic_inspiration=false` | 409 → toast `unavailable_error`, modal stays open, button re-enabled if char actually has it (re-fetch shows truth) |
| Network failure during reroll (any path) | toast retry; inspiration **not** consumed (server transaction rolled back) |
| DicePool reroll endpoint failure | Single retry toast; inspiration preserved; modal reverts to original state |
| Modal unmounted during in-flight reroll | useEffect cleanup ignores stale setState (existing pattern in `useRollAndPersist`) |
| Double click reroll button | `disabled={isRerolling}` blocks; button also hides immediately on success |
| DicePool with exactly `1d20` only | Inspiration button visible; mixed pools (`1d20+1d6`, `2d20`, etc.) hide it |
| Reroll critical→fumble (WeaponAttack) | Server re-runs full attack: damage_total becomes 0 because new die is a fumble |
| Reroll on a previous crit | Server re-rolls without auto-doubling damage unless new die is also 20 |
| `animate3d=false` or reduced motion | 3D animation skipped, server-rolled die used; reroll button still visible |
| Multiplayer session sync | `heroic_inspiration` snapshot updated via TanStack invalidation (same as HP/conditions); no WS push added |
| Pool cap reached client-side | `increment()` returns unchanged pool, fires haptic.warning and surfaces a transient toast |

State machine for modals post-reroll:

```
[idle] ──click ispirazione──► [rerolling]
[rerolling] ──success──► [rerolled]   (badge visible, button hidden, OK remains)
[rerolling] ──fail──► [idle]          (toast, button re-enabled if applicable)
[rerolled] ──OK click──► closed
```

Single consumption per modal lifecycle. No double-spend.

---

## 7. Testing & Verification

No automated test suite (per CLAUDE.md). Verification is manual + type-check + prod build.

### 7.1 Type check

```
cd webapp && npx tsc --noEmit
```

Must pass before commit.

### 7.2 Manual checks (local stack — `uv run uvicorn` + `npm run dev`)

| # | Case | Expected |
|---|------|----------|
| 1 | Roll 50d20 from DiceOverlay | DicePoolResultModal opens, total + per-group breakdown visible, console clean (no computeTangents warning) |
| 2 | Roll 100d20 (cap) | Modal opens; further increments past 100 trigger warning toast |
| 3 | Roll 200d20 via direct API call | 200 → success; 201 → 422 |
| 4 | Saving throw with inspiration | Button visible, click → animation, badge after, inspiration off in HeroScreen |
| 5 | Skill check with inspiration | Same |
| 6 | Weapon attack with inspiration (hit→hit) | New to-hit + new damage shown; inspiration off |
| 7 | Weapon attack with inspiration (fumble→hit) | Damage section appears with new value |
| 8 | Weapon attack with inspiration (crit→non-crit) | Damage drops back to non-doubled rolls |
| 9 | DiceOverlay 1d20 pure with inspiration | Button visible, reroll works |
| 10 | DiceOverlay 1d20+1d6 | Button hidden |
| 11 | DiceOverlay 2d20 | Button hidden |
| 12 | Reroll with `heroic_inspiration=false` (race) | 409 → toast, modal open, no double-spend |
| 13 | `animate3d=false` | Reroll skips 3D, still works |
| 14 | Reduced motion | Same |
| 15 | Telegram Android (real initData) | Roll + reroll OK |
| 16 | Localhost dev (DEV_USER_ID bypass) | Roll + reroll OK |
| 17 | SessionRoom snapshot post-reroll | `heroic_inspiration` updates without manual refresh |

### 7.3 Backend smoke

```
curl -X POST http://localhost:8000/characters/1/saving_throws/dexterity/roll \
  -H 'X-Telegram-Init-Data: dev' \
  -H 'Content-Type: application/json' \
  -d '{"die": 5, "with_inspiration": true}'
# Expect: 200, char.heroic_inspiration=false post-call
# Re-call with same body: 409
```

### 7.4 Prod build

```
cd webapp && npm run build:prod
```

Must exit clean. `git diff docs/app/` shows expected rebuild. After build, restore `webapp/.env.local`:

```
printf 'VITE_API_BASE_URL=http://127.0.0.1:8000\n' > webapp/.env.local
```

(per CLAUDE.md quirk note).

### 7.5 Regression surfaces

- HP, condition, spell, equipment, currency pages: unchanged.
- `Dice.tsx` page (different roll surface, already capped at 10 per kind): unchanged.
- `SpellDamageSheet.tsx`: unchanged (out of scope — damage isn't an inspiration target).

---

## 8. Out of Scope

- Damage rolls, hit dice, death saves, concentration saves: inspiration does not apply (RAW).
- Spell attack rolls (currently no dedicated spell attack endpoint): not extended in this design. If introduced later, follow the same `with_inspiration` pattern.
- Bot side: bot does not perform rolls; no changes.
- WebSocket push for inspiration changes during a session: continues to rely on TanStack invalidation (same model as HP/conditions).
- Cap above 100 client-side: not exposed in UI; advanced users can hit 200 only via direct API.

---

## 9. Files Touched

### New

- `webapp/src/components/InspirationRerollButton.tsx`
- `webapp/src/components/DicePoolResultModal.tsx`

### Modified

**Backend**
- `api/schemas/common.py` — bump `max_length`, add `DiceResultRequest.with_inspiration`.
- `api/schemas/character.py` — `D20RollSubmission.with_inspiration`.
- `api/schemas/inventory.py` (or inline in router) — `AttackSubmission`.
- `api/routers/dice.py` — consume inspiration in `post_dice_result`.
- `api/routers/characters.py` — extend `roll_skill`, `roll_saving_throw`.
- `api/routers/items.py` — extend `attack_with_weapon`.

**Frontend**
- `webapp/src/components/RollResultModal.tsx` — add inspiration props.
- `webapp/src/components/WeaponAttackModal.tsx` — add inspiration props.
- `webapp/src/components/DiceOverlay.tsx` — remove toast, mount DicePoolResultModal, add pool cap.
- `webapp/src/api/client.ts` — extend `rollSkill`, `rollSavingThrow`, `attack`, `dice.result` signatures.
- `webapp/src/pages/SavingThrows.tsx` — wire reroll mutation.
- `webapp/src/pages/Skills.tsx` — wire reroll mutation.
- `webapp/src/pages/Inventory.tsx` — wire reroll mutation.
- `webapp/src/dice/geometries/index.ts` — remove `computeTangents?.()` call.
- `webapp/src/locales/it.json`, `en.json` — new keys.
