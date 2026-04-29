# Dice Pool Cap Fix + Heroic Inspiration Reroll — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the 422 error that blocks DiceOverlay rolls past 50 dice and add D&D 5e heroic inspiration reroll on saving throws, skill checks, weapon attacks, and the new dice-pool result popup.

**Architecture:** Backend roll endpoints accept a `with_inspiration: bool` flag and consume `characters.heroic_inspiration` atomically inside their existing transaction. Frontend modals (`RollResultModal`, `WeaponAttackModal`, new `DicePoolResultModal`) gain a shared `<InspirationRerollButton>`. The DiceOverlay result toast is replaced by `DicePoolResultModal`, and the FAB pool gets a client-side cap (100) to stay under the bumped server cap (200).

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy AsyncSession (backend); React 18, TanStack Query, framer-motion, Three.js / cannon-es / @react-three/fiber (frontend); i18next; TypeScript.

**Spec reference:** `docs/superpowers/specs/2026-04-29-dice-fixes-and-inspiration-reroll-design.md`.

**Branch:** `fix/dice-cap-and-inspiration-reroll`.

**Testing harness note:** This repo has no automated test suite (per `CLAUDE.md`). Each task uses **TypeScript type-check** for frontend changes (`cd webapp && npx tsc --noEmit`) and **manual curl smoke** for backend endpoints. Final manual UI verification happens at Task 16 against the matrix in spec §7.2.

**Environment rule:** Per `CLAUDE.md`, never run `uv sync` / `uv run` inside WSL. The engineer runs Python verification commands from a Windows shell. Frontend commands run from WSL or Windows interchangeably (Vite is platform-neutral).

---

## File Structure

### Backend
- `api/schemas/common.py` — bump `DiceResultRequest.rolls` `max_length`, add `with_inspiration` flag to `DiceResultRequest` and `D20RollSubmission`.
- `api/routers/dice.py` — consume inspiration in `post_dice_result` when flag set.
- `api/routers/characters.py` — same logic in `roll_skill` and `roll_saving_throw`.
- `api/routers/items.py` — accept optional body with `with_inspiration` in `attack_with_weapon`. Inline `AttackSubmission` schema in this router (no new schema file).

### Frontend — new files
- `webapp/src/components/InspirationRerollButton.tsx` — shared presenter for the reroll button.
- `webapp/src/components/DicePoolResultModal.tsx` — replaces the DiceOverlay result toast; reroll lives inside.

### Frontend — modified files
- `webapp/src/dice/geometries/index.ts` — drop the cosmetic `computeTangents` warning.
- `webapp/src/components/RollResultModal.tsx` — add inspiration props.
- `webapp/src/components/WeaponAttackModal.tsx` — add inspiration props.
- `webapp/src/components/DiceOverlay.tsx` — remove result/error toasts, mount the new modal, add pool cap.
- `webapp/src/api/client.ts` — extend `rollSkill`, `rollSavingThrow`, `attack`, `dice.result` and `DiceResultRequestBody` to carry `with_inspiration`.
- `webapp/src/pages/SavingThrows.tsx` — wire reroll mutation.
- `webapp/src/pages/Skills.tsx` — wire reroll mutation.
- `webapp/src/pages/Inventory.tsx` — wire reroll mutation.
- `webapp/src/locales/it.json`, `webapp/src/locales/en.json` — i18n keys.

---

## Task 1: Cosmetic — Remove `computeTangents` warning

**Files:**
- Modify: `webapp/src/dice/geometries/index.ts:424`

This is a no-op for procedural materials and the derivative-based tangent fallback covers normal-mapped pack materials. Safe to remove. Proves the dev environment is wired (type-check, build, commit) before larger edits.

- [ ] **Step 1.1: Remove the line**

In `webapp/src/dice/geometries/index.ts`, delete line 424:

```ts
  geometry.computeTangents?.()
```

The surrounding block becomes:

```ts
  geometry.setAttribute('uv', new THREE.BufferAttribute(uvArray, 2))

  cache.set(key, data)
  return data
}
```

- [ ] **Step 1.2: Type-check**

```bash
cd /mnt/c/Users/Claudio/PycharmProjects/dnd_bot_revamped/webapp && npx tsc --noEmit
```

Expected: zero errors.

- [ ] **Step 1.3: Commit**

```bash
git add webapp/src/dice/geometries/index.ts
git commit -m "$(cat <<'EOF'
fix(dice): drop computeTangents call on non-indexed geometry

The dice geometry is a raw triangle list (no index buffer), so
THREE.BufferGeometry.computeTangents() always logged a console.error
and returned without producing tangents. Procedural materials don't use
normal maps and pack normal maps fall back to derivative-based tangents
in the shader, so removing the call has no visual impact.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Backend — schema cap bump + `with_inspiration` flags

**Files:**
- Modify: `api/schemas/common.py`

- [ ] **Step 2.1: Bump `DiceResultRequest` cap and add flag**

In `api/schemas/common.py` find the existing class (around lines 282–286):

```python
class DiceResultRequest(BaseModel):
    rolls: list[DiceResultEntry] = Field(min_length=1, max_length=50)
    label: str | None = Field(default=None, max_length=120)
    modifier: int = 0
    notation: str | None = Field(default=None, max_length=80)
```

Replace with:

```python
class DiceResultRequest(BaseModel):
    rolls: list[DiceResultEntry] = Field(min_length=1, max_length=200)
    label: str | None = Field(default=None, max_length=120)
    modifier: int = 0
    notation: str | None = Field(default=None, max_length=80)
    with_inspiration: bool = False
```

- [ ] **Step 2.2: Add flag to `D20RollSubmission`**

In the same file, find the existing class (around lines 309–311):

```python
class D20RollSubmission(BaseModel):
    """Optional client-supplied d20 value (from 3D physics face detection)."""
    die: Optional[int] = Field(default=None, ge=1, le=20)
```

Replace with:

```python
class D20RollSubmission(BaseModel):
    """Optional client-supplied d20 value (from 3D physics face detection)."""
    die: Optional[int] = Field(default=None, ge=1, le=20)
    with_inspiration: bool = False
```

- [ ] **Step 2.3: Verify no syntax error**

Open `api/schemas/common.py` and confirm both classes parse. Static review only — no Python execution from WSL.

- [ ] **Step 2.4: Commit**

```bash
git add api/schemas/common.py
git commit -m "$(cat <<'EOF'
feat(api): raise dice pool cap to 200, add with_inspiration flag

DiceResultRequest.max_length goes from 50 to 200 so DiceOverlay rolls
past 50 dice no longer 422. Adds with_inspiration on DiceResultRequest
and D20RollSubmission for upcoming heroic-inspiration reroll.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Backend — `dice.py` consumes inspiration

**Files:**
- Modify: `api/routers/dice.py`

- [ ] **Step 3.1: Consume inspiration when flag set**

In `api/routers/dice.py`, find the body of `post_dice_result` (around lines 81–101 — between `_get_owned` call and the `session.add(CharacterHistory(...))` line).

The existing block reads:

```python
    char = await _get_owned(char_id, user_id, session)
    history = list(char.rolls_history or [])
    history.append({"notation": notation, "rolls": rolls, "total": total})
    char.rolls_history = history[-_MAX_HISTORY:]
    flag_modified(char, "rolls_history")

    # Log to CharacterHistory (general events feed) so the roll appears in /history.
    if len(rolls) > 1:
        rolls_str = "+".join(str(r) for r in rolls)
        description = f"🎲 {notation}: [{rolls_str}] = {total}"
    else:
        description = f"🎲 {notation}: {total}"
    if body.label:
        description = f"{body.label} — {description}"
```

Replace with:

```python
    char = await _get_owned(char_id, user_id, session)

    if body.with_inspiration:
        if not char.heroic_inspiration:
            raise HTTPException(status_code=409, detail="Ispirazione non disponibile")
        char.heroic_inspiration = False

    history = list(char.rolls_history or [])
    history.append({"notation": notation, "rolls": rolls, "total": total})
    char.rolls_history = history[-_MAX_HISTORY:]
    flag_modified(char, "rolls_history")

    # Log to CharacterHistory (general events feed) so the roll appears in /history.
    if len(rolls) > 1:
        rolls_str = "+".join(str(r) for r in rolls)
        description = f"🎲 {notation}: [{rolls_str}] = {total}"
    else:
        description = f"🎲 {notation}: {total}"
    if body.label:
        description = f"{body.label} — {description}"
    if body.with_inspiration:
        description = f"Reroll ispirazione — {description}"
```

- [ ] **Step 3.2: Smoke (Windows shell, after API restart)**

The user runs the API. Provide them the verification commands:

```bash
# Replace 1 with a real char id, ensure heroic_inspiration=true first.
curl -X POST http://localhost:8000/characters/1/dice/result \
  -H 'X-Telegram-Init-Data: dev' \
  -H 'Content-Type: application/json' \
  -d '{"rolls":[{"kind":"d20","value":5}],"notation":"1d20","with_inspiration":true}'
# Expected: 200 + DiceRollResult body. char.heroic_inspiration becomes false.
# Re-run same command: 409 with detail "Ispirazione non disponibile".
```

- [ ] **Step 3.3: Commit**

```bash
git add api/routers/dice.py
git commit -m "$(cat <<'EOF'
feat(api): consume heroic inspiration in dice result endpoint

When with_inspiration=true, validate the character has inspiration,
flip the flag to false, and prefix the history description with
"Reroll ispirazione —". 409 if inspiration is unavailable. All
mutations stay inside the existing AsyncSession transaction.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Backend — `characters.py` skill + saving throw consume inspiration

**Files:**
- Modify: `api/routers/characters.py`

- [ ] **Step 4.1: Update `roll_skill`**

In `api/routers/characters.py` find the body of `roll_skill` (lines ~379–421). After the line:

```python
    char = await _get_owned(char_id, user_id, session, full=True)
```

(line ~389) and before the ability_mod lookup, insert:

```python
    if body and body.with_inspiration:
        if not char.heroic_inspiration:
            raise HTTPException(status_code=409, detail="Ispirazione non disponibile")
        char.heroic_inspiration = False
```

Then change the existing history call (line ~410):

```python
    _add_history(session, char.id, "skill_roll",
                 f"Abilità {skill_name}: d20={die} {'+ ' if bonus >= 0 else ''}{bonus} = {total}"
                 + (" (CRITICO)" if is_crit else " (FUMBLE)" if is_fumble else ""))
```

into:

```python
    history_msg = (
        f"Abilità {skill_name}: d20={die} {'+ ' if bonus >= 0 else ''}{bonus} = {total}"
        + (" (CRITICO)" if is_crit else " (FUMBLE)" if is_fumble else "")
    )
    if body and body.with_inspiration:
        history_msg = f"Reroll ispirazione — {history_msg}"
    _add_history(session, char.id, "skill_roll", history_msg)
```

- [ ] **Step 4.2: Update `roll_saving_throw`**

In the same file find `roll_saving_throw` (lines ~428–464). After:

```python
    char = await _get_owned(char_id, user_id, session, full=True)
```

(line ~438) and before the score lookup, insert the same guard:

```python
    if body and body.with_inspiration:
        if not char.heroic_inspiration:
            raise HTTPException(status_code=409, detail="Ispirazione non disponibile")
        char.heroic_inspiration = False
```

Then change the existing `_add_history` call (line ~453):

```python
    _add_history(session, char.id, "saving_throw",
                 f"TS {ability}: d20={die} {'+ ' if bonus >= 0 else ''}{bonus} = {total}"
                 + (" (CRITICO)" if is_crit else " (FUMBLE)" if is_fumble else ""))
```

into:

```python
    history_msg = (
        f"TS {ability}: d20={die} {'+ ' if bonus >= 0 else ''}{bonus} = {total}"
        + (" (CRITICO)" if is_crit else " (FUMBLE)" if is_fumble else "")
    )
    if body and body.with_inspiration:
        history_msg = f"Reroll ispirazione — {history_msg}"
    _add_history(session, char.id, "saving_throw", history_msg)
```

- [ ] **Step 4.3: Smoke (after API restart)**

```bash
# Pre-condition: char 1 has heroic_inspiration=true.
curl -X POST http://localhost:8000/characters/1/saving_throws/dexterity/roll \
  -H 'X-Telegram-Init-Data: dev' \
  -H 'Content-Type: application/json' \
  -d '{"die": 12, "with_inspiration": true}'
# Expected: 200 with RollResult, heroic_inspiration becomes false.
# Re-run: 409.

# Same with skill:
curl -X POST http://localhost:8000/characters/1/skills/perception/roll \
  -H 'X-Telegram-Init-Data: dev' \
  -H 'Content-Type: application/json' \
  -d '{"die": 8, "with_inspiration": true}'
# Without the flag (existing flow):
curl -X POST http://localhost:8000/characters/1/saving_throws/dexterity/roll \
  -H 'X-Telegram-Init-Data: dev' -H 'Content-Type: application/json' -d '{}'
# Expected: 200, no inspiration consumed.
```

- [ ] **Step 4.4: Commit**

```bash
git add api/routers/characters.py
git commit -m "$(cat <<'EOF'
feat(api): consume heroic inspiration on skill/saving-throw rolls

with_inspiration=true validates the character has inspiration, flips
the flag to false, and prefixes the history line with
"Reroll ispirazione —". 409 when unavailable. Existing callers that
omit the flag are unaffected.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Backend — `items.py` weapon attack accepts inspiration body

**Files:**
- Modify: `api/routers/items.py`

- [ ] **Step 5.1: Add inline `AttackSubmission` and accept body**

Open `api/routers/items.py`. Near the top imports add (or extend the existing FastAPI import):

```python
from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
```

(Confirm `Body` and `BaseModel` are imported — add them if missing without removing existing imports.)

Above the `attack_with_weapon` definition (around line 239, just under the section comment block) add:

```python
class AttackSubmission(BaseModel):
    """Optional payload for weapon attacks. Today only carries the inspiration flag."""
    with_inspiration: bool = False
```

Change the function signature from:

```python
@router.post("/{char_id}/items/{item_id}/attack", response_model=WeaponAttackResult)
async def attack_with_weapon(
    char_id: int,
    item_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WeaponAttackResult:
```

to:

```python
@router.post("/{char_id}/items/{item_id}/attack", response_model=WeaponAttackResult)
async def attack_with_weapon(
    char_id: int,
    item_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    body: Annotated[AttackSubmission | None, Body()] = None,
) -> WeaponAttackResult:
```

- [ ] **Step 5.2: Consume inspiration and tweak history**

Inside the function, after:

```python
    char = await _get_owned_full(char_id, user_id, session)
```

(line ~246) insert:

```python
    if body and body.with_inspiration:
        if not char.heroic_inspiration:
            raise HTTPException(status_code=409, detail="Ispirazione non disponibile")
        char.heroic_inspiration = False
```

Then locate the `result_str = (...)` block (around line 303) and the immediately following `_add_history(...)` call. Replace just that history call:

```python
    _add_history(session, char.id, "attack_roll", result_str)
```

with:

```python
    if body and body.with_inspiration:
        result_str = f"Reroll ispirazione (to-hit) — {result_str}"
    _add_history(session, char.id, "attack_roll", result_str)
```

- [ ] **Step 5.3: Smoke**

```bash
# Pre-condition: char 1 owns weapon item with id=42 (any weapon), heroic_inspiration=true.
curl -X POST http://localhost:8000/characters/1/items/42/attack \
  -H 'X-Telegram-Init-Data: dev' \
  -H 'Content-Type: application/json' \
  -d '{"with_inspiration": true}'
# Expected: 200 WeaponAttackResult; heroic_inspiration false; history entry begins
# "Reroll ispirazione (to-hit) — ".

# Existing zero-body call must still work:
curl -X POST http://localhost:8000/characters/1/items/42/attack \
  -H 'X-Telegram-Init-Data: dev'
# Expected: 200, no inspiration consumed.
```

- [ ] **Step 5.4: Commit**

```bash
git add api/routers/items.py
git commit -m "$(cat <<'EOF'
feat(api): allow weapon attack to consume heroic inspiration

attack_with_weapon now accepts an optional AttackSubmission body. When
with_inspiration=true the endpoint validates the character has
inspiration, flips it to false, and prefixes the history entry with
"Reroll ispirazione (to-hit) —". The reroll re-runs the existing
attack flow so to-hit and damage are both rerolled.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: i18n keys

**Files:**
- Modify: `webapp/src/locales/it.json`
- Modify: `webapp/src/locales/en.json`

- [ ] **Step 6.1: Add Italian keys**

In `webapp/src/locales/it.json`:

(a) extend the `dice_overlay` block at line 229. Replace:

```json
    "dice_overlay": {
      "open": "Apri lanciatore dadi",
      "close": "Chiudi lanciatore",
      "roll": "Lancia",
      "roll_failed": "Errore durante il lancio",
      "clear_kind": "Resetta",
      "rolling": "Sto lanciando…"
    },
```

with:

```json
    "dice_overlay": {
      "open": "Apri lanciatore dadi",
      "close": "Chiudi lanciatore",
      "roll": "Lancia",
      "roll_failed": "Errore durante il lancio",
      "clear_kind": "Resetta",
      "rolling": "Sto lanciando…",
      "result_title": "Risultato",
      "pool_cap_reached": "Limite massimo dadi raggiunto"
    },
```

(b) extend the `inspiration` block at line 313. Replace:

```json
    "inspiration": {
      "title": "Ispirazione Eroica",
      "tap_to_grant": "Tocca per concedere",
      "tap_to_spend": "Tocca per usare"
    },
```

with:

```json
    "inspiration": {
      "title": "Ispirazione Eroica",
      "tap_to_grant": "Tocca per concedere",
      "tap_to_spend": "Tocca per usare",
      "use_reroll": "Usa Ispirazione",
      "reroll_badge": "↻ Reroll ispirazione",
      "unavailable_error": "Ispirazione non disponibile"
    },
```

- [ ] **Step 6.2: Add English keys**

In `webapp/src/locales/en.json` apply the parallel changes:

```json
    "dice_overlay": {
      "open": "Open dice tray",
      "close": "Close dice tray",
      "roll": "Roll",
      "roll_failed": "Roll failed",
      "clear_kind": "Clear",
      "rolling": "Rolling…",
      "result_title": "Result",
      "pool_cap_reached": "Maximum dice limit reached"
    },
```

```json
    "inspiration": {
      "title": "Heroic Inspiration",
      "tap_to_grant": "Tap to grant",
      "tap_to_spend": "Tap to spend",
      "use_reroll": "Use Inspiration",
      "reroll_badge": "↻ Inspiration reroll",
      "unavailable_error": "Inspiration unavailable"
    },
```

- [ ] **Step 6.3: Type-check**

```bash
cd /mnt/c/Users/Claudio/PycharmProjects/dnd_bot_revamped/webapp && npx tsc --noEmit
```

Expected: zero errors.

- [ ] **Step 6.4: Commit**

```bash
git add webapp/src/locales/it.json webapp/src/locales/en.json
git commit -m "$(cat <<'EOF'
i18n: add inspiration reroll and dice overlay popup keys

New keys for the inspiration reroll button, the rerolled badge, the
409 error toast, and the DiceOverlay popup title plus pool cap
warning. Italian default + English mirror.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: API client signatures

**Files:**
- Modify: `webapp/src/api/client.ts`

- [ ] **Step 7.1: Extend `DiceResultRequestBody`**

In `webapp/src/api/client.ts` find the type at line 96–101:

```ts
export type DiceResultRequestBody = {
  rolls: DiceResultEntryBody[]
  label?: string | null
  modifier?: number
  notation?: string | null
}
```

Replace with:

```ts
export type DiceResultRequestBody = {
  rolls: DiceResultEntryBody[]
  label?: string | null
  modifier?: number
  notation?: string | null
  with_inspiration?: boolean
}
```

- [ ] **Step 7.2: Extend `rollSkill` and `rollSavingThrow`**

Find lines 238–247 inside the `characters` namespace:

```ts
    rollSkill: (id: number, skillName: string, die?: number) =>
      request<RollResult>(`/characters/${id}/skills/${encodeURIComponent(skillName)}/roll`, {
        method: 'POST',
        body: die != null ? JSON.stringify({ die }) : undefined,
      }),
    rollSavingThrow: (id: number, ability: string, die?: number) =>
      request<RollResult>(`/characters/${id}/saving_throws/${encodeURIComponent(ability)}/roll`, {
        method: 'POST',
        body: die != null ? JSON.stringify({ die }) : undefined,
      }),
```

Replace with:

```ts
    rollSkill: (
      id: number,
      skillName: string,
      die?: number,
      withInspiration: boolean = false,
    ) =>
      request<RollResult>(`/characters/${id}/skills/${encodeURIComponent(skillName)}/roll`, {
        method: 'POST',
        body:
          die != null || withInspiration
            ? JSON.stringify({ die, with_inspiration: withInspiration })
            : undefined,
      }),
    rollSavingThrow: (
      id: number,
      ability: string,
      die?: number,
      withInspiration: boolean = false,
    ) =>
      request<RollResult>(`/characters/${id}/saving_throws/${encodeURIComponent(ability)}/roll`, {
        method: 'POST',
        body:
          die != null || withInspiration
            ? JSON.stringify({ die, with_inspiration: withInspiration })
            : undefined,
      }),
```

- [ ] **Step 7.3: Extend `items.attack`**

Find the `attack` entry around lines 386–389:

```ts
    attack: (charId: number, itemId: number) =>
      request<WeaponAttackResult>(`/characters/${charId}/items/${itemId}/attack`, {
        method: 'POST',
      }),
```

Replace with:

```ts
    attack: (charId: number, itemId: number, withInspiration: boolean = false) =>
      request<WeaponAttackResult>(`/characters/${charId}/items/${itemId}/attack`, {
        method: 'POST',
        body: withInspiration
          ? JSON.stringify({ with_inspiration: true })
          : undefined,
      }),
```

- [ ] **Step 7.4: Type-check**

```bash
cd /mnt/c/Users/Claudio/PycharmProjects/dnd_bot_revamped/webapp && npx tsc --noEmit
```

Expected: zero errors. Existing callers (`SavingThrows`, `Skills`, `Inventory`) are still valid because the new params are optional with safe defaults.

- [ ] **Step 7.5: Commit**

```bash
git add webapp/src/api/client.ts
git commit -m "$(cat <<'EOF'
feat(webapp): pass with_inspiration through API client

DiceResultRequestBody, rollSkill, rollSavingThrow and items.attack now
accept an optional withInspiration / with_inspiration field that maps
1:1 onto the backend payload. Existing callers continue to work
without changes.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: New `<InspirationRerollButton>`

**Files:**
- Create: `webapp/src/components/InspirationRerollButton.tsx`

- [ ] **Step 8.1: Create the component**

Create `webapp/src/components/InspirationRerollButton.tsx`:

```tsx
import { m } from 'framer-motion'
import { useTranslation } from 'react-i18next'
import { GiPolarStar as Star } from 'react-icons/gi'

type Props = {
  available: boolean
  pending?: boolean
  onClick: () => void
}

export default function InspirationRerollButton({ available, pending = false, onClick }: Props) {
  const { t } = useTranslation()
  if (!available) return null

  return (
    <m.button
      type="button"
      onClick={onClick}
      disabled={pending}
      className="w-full py-2.5 rounded-xl border border-dnd-arcane/60
                 bg-gradient-to-r from-[var(--dnd-arcane-deep)]/40 to-[var(--dnd-gold-deep)]/30
                 text-dnd-gold-bright font-cinzel uppercase tracking-wider
                 flex items-center justify-center gap-2 min-h-[44px]
                 disabled:opacity-50"
      whileTap={{ scale: 0.95 }}
    >
      <Star size={16} className="text-dnd-arcane-bright" fill="currentColor" />
      {t('character.inspiration.use_reroll')}
    </m.button>
  )
}
```

- [ ] **Step 8.2: Type-check**

```bash
cd /mnt/c/Users/Claudio/PycharmProjects/dnd_bot_revamped/webapp && npx tsc --noEmit
```

Expected: zero errors.

- [ ] **Step 8.3: Commit**

```bash
git add webapp/src/components/InspirationRerollButton.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): add InspirationRerollButton presenter

Shared button used by RollResultModal, WeaponAttackModal and
DicePoolResultModal to trigger a heroic-inspiration reroll. Pure
presenter: caller decides availability and supplies the click handler.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Extend `RollResultModal` with inspiration props

**Files:**
- Modify: `webapp/src/components/RollResultModal.tsx`

- [ ] **Step 9.1: Update props and render the reroll button**

Open `webapp/src/components/RollResultModal.tsx`. Replace the entire file with:

```tsx
import { m, AnimatePresence } from 'framer-motion'
import { useTranslation } from 'react-i18next'
import { spring } from '@/styles/motion'
import { CornerFlourishes } from './ui/Ornament'
import InspirationRerollButton from './InspirationRerollButton'

export type RollResult = {
  die: number
  bonus: number
  total: number
  is_critical: boolean
  is_fumble: boolean
  description?: string
}

type Props = {
  result: RollResult
  title: string
  onClose: () => void
  inspirationAvailable?: boolean
  isRerolling?: boolean
  wasRerolled?: boolean
  onInspirationReroll?: () => void
}

export default function RollResultModal({
  result,
  title,
  onClose,
  inspirationAvailable = false,
  isRerolling = false,
  wasRerolled = false,
  onInspirationReroll,
}: Props) {
  const { t } = useTranslation()
  const { die, bonus, total, is_critical, is_fumble } = result

  const borderColor = is_critical
    ? 'border-dnd-gold'
    : is_fumble
      ? 'border-dnd-crimson'
      : 'border-dnd-emerald'

  const pulseClass = is_critical
    ? 'animate-pulse-gold'
    : is_fumble
      ? 'animate-pulse-danger'
      : ''

  const dieColor = is_critical
    ? 'text-dnd-gold-bright'
    : is_fumble
      ? 'text-[var(--dnd-crimson-bright)]'
      : 'text-dnd-text'

  const bonusStr = bonus >= 0 ? `+${bonus}` : `${bonus}`
  const showInspirationButton =
    inspirationAvailable && !wasRerolled && onInspirationReroll != null

  return (
    <AnimatePresence>
      <m.div
        className="fixed inset-0 flex items-center justify-center z-50 p-4"
        style={{ background: 'var(--dnd-overlay)', backdropFilter: 'blur(6px)' }}
        onClick={onClose}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      >
        <m.div
          className={`relative rounded-3xl p-6 pt-8 w-full max-w-xs text-center space-y-3
                      bg-gradient-parchment surface-parchment border-2 ${borderColor} ${pulseClass}
                      shadow-parchment-2xl`}
          onClick={(e) => e.stopPropagation()}
          initial={{ opacity: 0, scale: 0.8, y: 30 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.9, y: 20 }}
          transition={spring.elastic}
        >
          <div className="text-dnd-gold-dim">
            <CornerFlourishes />
          </div>

          <p className="text-sm text-dnd-text-muted font-cinzel uppercase tracking-widest">{title}</p>

          {wasRerolled && (
            <p className="text-[11px] text-dnd-arcane-bright font-cinzel uppercase tracking-wider">
              {t('character.inspiration.reroll_badge')}
            </p>
          )}

          {is_critical && (
            <m.p
              className="text-dnd-gold-bright font-bold text-sm font-cinzel uppercase tracking-wider"
              initial={{ scale: 0.5 }}
              animate={{ scale: [0.5, 1.2, 1] }}
              transition={{ duration: 0.5 }}
            >
              ✦ CRITICO!
            </m.p>
          )}
          {is_fumble && (
            <m.p
              className="text-[var(--dnd-crimson-bright)] font-bold text-sm font-cinzel uppercase tracking-wider"
              initial={{ scale: 0.5 }}
              animate={{ scale: [0.5, 1.2, 1] }}
              transition={{ duration: 0.5 }}
            >
              💀 FUMBLE!
            </m.p>
          )}

          <m.div
            className={`text-7xl font-black font-display ${dieColor}`}
            initial={{ scale: 0, rotate: -180 }}
            animate={{ scale: 1, rotate: 0 }}
            transition={{ ...spring.elastic, delay: 0.1 }}
          >
            {die}
          </m.div>

          <p className="text-dnd-text-muted text-sm font-body">
            d20 ({die}) {bonusStr} = <span className="text-dnd-text font-bold text-lg font-mono">{total}</span>
          </p>

          {result.description && (
            <p className="text-xs text-dnd-text-muted italic font-body">{result.description}</p>
          )}

          {showInspirationButton && (
            <InspirationRerollButton
              available
              pending={isRerolling}
              onClick={onInspirationReroll}
            />
          )}

          <m.button
            onClick={onClose}
            className="w-full py-2.5 rounded-xl bg-gradient-gold text-dnd-ink font-semibold mt-2
                       min-h-[48px] shadow-engrave font-cinzel uppercase tracking-wider"
            whileTap={{ scale: 0.97 }}
          >
            OK
          </m.button>
        </m.div>
      </m.div>
    </AnimatePresence>
  )
}
```

- [ ] **Step 9.2: Type-check**

```bash
cd /mnt/c/Users/Claudio/PycharmProjects/dnd_bot_revamped/webapp && npx tsc --noEmit
```

Expected: zero errors. Existing `RollResultModal` callers compile without changes (new props all optional).

- [ ] **Step 9.3: Commit**

```bash
git add webapp/src/components/RollResultModal.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): add inspiration reroll props to RollResultModal

Renders InspirationRerollButton above OK when the parent supplies an
inspirationAvailable + onInspirationReroll pair. Shows a "↻ Reroll
ispirazione" badge once wasRerolled is true. All new props are
optional so existing callers continue to compile.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Extend `WeaponAttackModal` with inspiration props

**Files:**
- Modify: `webapp/src/components/WeaponAttackModal.tsx`

- [ ] **Step 10.1: Replace the file**

Replace `webapp/src/components/WeaponAttackModal.tsx` with:

```tsx
import { m, AnimatePresence } from 'framer-motion'
import { useTranslation } from 'react-i18next'
import { spring } from '@/styles/motion'
import { CornerFlourishes } from './ui/Ornament'
import InspirationRerollButton from './InspirationRerollButton'

export type WeaponAttackResult = {
  weapon_name: string
  to_hit_die: number
  to_hit_bonus: number
  to_hit_total: number
  is_critical: boolean
  is_fumble: boolean
  damage_dice: string
  damage_rolls: number[]
  damage_bonus: number
  damage_total: number
}

type Props = {
  result: WeaponAttackResult
  onClose: () => void
  inspirationAvailable?: boolean
  isRerolling?: boolean
  wasRerolled?: boolean
  onInspirationReroll?: () => void
}

export default function WeaponAttackModal({
  result,
  onClose,
  inspirationAvailable = false,
  isRerolling = false,
  wasRerolled = false,
  onInspirationReroll,
}: Props) {
  const { t } = useTranslation()
  const {
    weapon_name, to_hit_die, to_hit_bonus, to_hit_total,
    is_critical, is_fumble, damage_dice, damage_rolls, damage_bonus, damage_total,
  } = result

  const bonusStr = (n: number) => n >= 0 ? `+${n}` : `${n}`

  const borderColor = is_critical
    ? 'border-dnd-gold'
    : is_fumble
      ? 'border-dnd-crimson'
      : 'border-dnd-emerald'

  const pulseClass = is_critical
    ? 'animate-pulse-gold'
    : is_fumble
      ? 'animate-pulse-danger'
      : ''

  const showInspirationButton =
    inspirationAvailable && !wasRerolled && onInspirationReroll != null

  return (
    <AnimatePresence>
      <m.div
        className="fixed inset-0 flex items-center justify-center z-50 p-4"
        style={{ background: 'var(--dnd-overlay)', backdropFilter: 'blur(6px)' }}
        onClick={onClose}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      >
        <m.div
          className={`relative rounded-3xl p-5 pt-7 w-full max-w-sm space-y-4
                      bg-gradient-parchment surface-parchment border-2 ${borderColor} ${pulseClass}
                      shadow-parchment-2xl`}
          onClick={(e) => e.stopPropagation()}
          initial={{ opacity: 0, scale: 0.85, y: 30 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.92, y: 20 }}
          transition={spring.elastic}
        >
          <div className="text-dnd-gold-dim">
            <CornerFlourishes />
          </div>

          <div className="text-center">
            <p className="text-sm text-dnd-text-muted font-cinzel uppercase tracking-widest">⚔️ {weapon_name}</p>
            {wasRerolled && (
              <p className="text-[11px] text-dnd-arcane-bright font-cinzel uppercase tracking-wider mt-1">
                {t('character.inspiration.reroll_badge')}
              </p>
            )}
            {is_critical && <p className="text-dnd-gold-bright font-bold font-cinzel">✦ CRITICO!</p>}
            {is_fumble && <p className="text-[var(--dnd-crimson-bright)] font-bold font-cinzel">💀 FUMBLE!</p>}
          </div>

          <m.div
            className="rounded-2xl bg-dnd-surface/80 border border-dnd-border p-3 text-center"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
          >
            <p className="text-[10px] text-dnd-text-faint mb-1 font-cinzel uppercase tracking-wider">Per colpire</p>
            <p className="text-xs text-dnd-text-muted font-body">
              d20 ({to_hit_die}) {bonusStr(to_hit_bonus)}
            </p>
            <p className={`text-4xl font-black font-display mt-1
              ${is_critical ? 'text-dnd-gold-bright' : is_fumble ? 'text-[var(--dnd-crimson-bright)]' : 'text-dnd-text'}`}>
              {to_hit_total}
            </p>
          </m.div>

          {!is_fumble && (
            <m.div
              className="rounded-2xl bg-dnd-surface/80 border border-dnd-border p-3 text-center"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
            >
              <p className="text-[10px] text-dnd-text-faint mb-1 font-cinzel uppercase tracking-wider">
                Danno{is_critical ? ' (critico)' : ''} — {damage_dice}
              </p>
              <p className="text-xs text-dnd-text-muted font-body font-mono">
                [{damage_rolls.join(', ')}] {bonusStr(damage_bonus)}
              </p>
              <p className="text-4xl font-black font-display mt-1 text-[var(--dnd-crimson-bright)]">{damage_total}</p>
            </m.div>
          )}

          {showInspirationButton && (
            <InspirationRerollButton
              available
              pending={isRerolling}
              onClick={onInspirationReroll}
            />
          )}

          <m.button
            onClick={onClose}
            className="w-full py-2.5 rounded-xl bg-gradient-gold text-dnd-ink font-semibold
                       min-h-[48px] shadow-engrave font-cinzel uppercase tracking-wider"
            whileTap={{ scale: 0.97 }}
          >
            OK
          </m.button>
        </m.div>
      </m.div>
    </AnimatePresence>
  )
}
```

- [ ] **Step 10.2: Type-check**

```bash
cd /mnt/c/Users/Claudio/PycharmProjects/dnd_bot_revamped/webapp && npx tsc --noEmit
```

Expected: zero errors.

- [ ] **Step 10.3: Commit**

```bash
git add webapp/src/components/WeaponAttackModal.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): add inspiration reroll props to WeaponAttackModal

Same controlled-component pattern as RollResultModal: caller passes
inspirationAvailable + onInspirationReroll, the modal renders the
button above OK and shows the rerolled badge when wasRerolled is set.
The result prop is replaced wholesale by the caller after a reroll.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Wire reroll in `SavingThrows.tsx`

**Files:**
- Modify: `webapp/src/pages/SavingThrows.tsx`

- [ ] **Step 11.1: Add the reroll mutation and pass props**

Replace the entire `webapp/src/pages/SavingThrows.tsx` with:

```tsx
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Check } from 'lucide-react'
import { GiShieldEchoes as ShieldAlert } from 'react-icons/gi'
import { api, ApiError } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import StatPill from '@/components/ui/StatPill'
import Reveal from '@/components/ui/Reveal'
import DiceIcon from '@/components/ui/DiceIcon'
import RollResultModal, { type RollResult } from '@/components/RollResultModal'
import { haptic } from '@/auth/telegram'
import { stagger } from '@/styles/motion'
import { useDiceAnimation } from '@/dice/useDiceAnimation'
import { useDiceSettings } from '@/store/diceSettings'
import { useReducedMotion } from '@/hooks/useReducedMotion'

const ABILITIES = ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma'] as const

const ABILITY_TONE: Record<string, 'crimson' | 'emerald' | 'amber' | 'cobalt' | 'arcane' | 'gold'> = {
  strength: 'crimson',
  dexterity: 'emerald',
  constitution: 'amber',
  intelligence: 'cobalt',
  wisdom: 'arcane',
  charisma: 'gold',
}

function profBonus(level: number) {
  return Math.floor((level - 1) / 4) + 2
}

type RollState = {
  result: RollResult
  title: string
  ability: string
  wasRerolled: boolean
}

export default function SavingThrows() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const dice = useDiceAnimation()
  const animate3d = useDiceSettings((s) => s.animate3d)
  const reducedMotion = useReducedMotion()
  const [rollState, setRollState] = useState<RollState | null>(null)

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  const mutation = useMutation({
    mutationFn: (saving_throws: Record<string, boolean>) =>
      api.characters.updateSavingThrows(charId, saving_throws),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      haptic.light()
    },
    onError: () => haptic.error(),
  })

  const rollMutation = useMutation({
    mutationFn: async (ability: string) => {
      const useAnimation = animate3d && !reducedMotion
      let die: number | undefined
      if (useAnimation) {
        const detected = await dice.playAndCollect([{ kind: 'd20', count: 1 }])
        die = detected[0]?.value
      }
      const result = await api.characters.rollSavingThrow(charId, ability, die)
      return { result, ability }
    },
    onSuccess: ({ result, ability }) => {
      setRollState({
        result,
        ability,
        title: `${t('character.saves.title')} — ${t(`character.stats.${ability}`)}`,
        wasRerolled: false,
      })
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const rerollMutation = useMutation({
    mutationFn: async (ability: string) => {
      const useAnimation = animate3d && !reducedMotion
      let die: number | undefined
      if (useAnimation) {
        const detected = await dice.playAndCollect([{ kind: 'd20', count: 1 }])
        die = detected[0]?.value
      }
      return api.characters.rollSavingThrow(charId, ability, die, true)
    },
    onSuccess: (result) => {
      setRollState((prev) => prev && { ...prev, result, wasRerolled: true })
      qc.invalidateQueries({ queryKey: ['character', charId] })
      haptic.success()
    },
    onError: (err) => {
      haptic.error()
      if (err instanceof ApiError && err.status === 409) {
        qc.invalidateQueries({ queryKey: ['character', charId] })
      }
    },
  })

  if (!char) return null

  const saves: Record<string, boolean> = (char.saving_throws as Record<string, boolean>) ?? {}
  const pb = profBonus(char.total_level || 1)

  const toggle = (ability: string) => {
    const current = saves[ability] ?? false
    mutation.mutate({ ...saves, [ability]: !current })
  }

  return (
    <Layout title={t('character.saves.title')} backTo={`/char/${charId}`} group="combat" page="saves">
      <Surface variant="elevated" className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-dnd-gold">
          <ShieldAlert size={16} />
          <p className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim">
            {t('character.skills.prof_bonus')}
          </p>
        </div>
        <StatPill tone="gold" value={`+${pb}`} />
      </Surface>

      <Reveal.Stagger stagger={stagger.list} className="grid grid-cols-2 gap-2">
        {ABILITIES.map((ability) => {
          const isProficient = saves[ability] ?? false
          const score = char.ability_scores.find((s) => s.name === ability)
          const abilMod = score?.modifier ?? 0
          const total = abilMod + (isProficient ? pb : 0)
          const tone = ABILITY_TONE[ability]

          return (
            <Reveal.Item key={ability}>
              <Surface
                variant={isProficient ? 'elevated' : 'flat'}
                interactive
                onClick={() => rollMutation.mutate(ability)}
                className={`relative !p-3 text-center
                  ${isProficient ? 'border-dnd-gold/50 shadow-halo-gold' : ''}`}
              >
                <div className="flex items-center justify-between -mx-1 -mt-1 mb-2">
                  <m.button
                    onClick={(e) => {
                      e.stopPropagation()
                      toggle(ability)
                    }}
                    className="w-10 h-10 flex items-center justify-center rounded-full"
                    whileTap={{ scale: 0.85 }}
                    aria-label="Proficiency"
                  >
                    <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center transition-colors
                      ${isProficient
                        ? 'bg-dnd-gold border-dnd-gold-bright shadow-[0_0_6px_var(--dnd-gold-glow)]'
                        : 'border-dnd-border'}`}>
                      {isProficient && <Check size={12} className="text-dnd-ink" strokeWidth={3} />}
                    </div>
                  </m.button>
                  <DiceIcon sides={20} size={28} className="text-dnd-gold/80 mr-0.5" />
                </div>

                <p className="text-[10px] font-cinzel uppercase tracking-[0.25em] text-dnd-text-muted">
                  {t(`character.stats.${ability}`)}
                </p>
                <p className={`text-4xl font-display font-black leading-none mt-1.5 mb-1 ${
                  tone === 'crimson' ? 'text-[var(--dnd-crimson-bright)]'
                  : tone === 'emerald' ? 'text-[var(--dnd-emerald-bright)]'
                  : tone === 'amber' ? 'text-[var(--dnd-amber)]'
                  : tone === 'cobalt' ? 'text-[var(--dnd-cobalt-bright)]'
                  : tone === 'arcane' ? 'text-dnd-arcane-bright'
                  : 'text-dnd-gold-bright'
                }`}>
                  {total >= 0 ? '+' : ''}{total}
                </p>
                <p className="text-[10px] text-dnd-text-faint font-mono">
                  {abilMod >= 0 ? '+' : ''}{abilMod}{isProficient ? ` +${pb}` : ''}
                </p>
              </Surface>
            </Reveal.Item>
          )
        })}
      </Reveal.Stagger>

      {rollState && (
        <RollResultModal
          result={rollState.result}
          title={rollState.title}
          inspirationAvailable={Boolean(char.heroic_inspiration)}
          isRerolling={rerollMutation.isPending}
          wasRerolled={rollState.wasRerolled}
          onInspirationReroll={() => rerollMutation.mutate(rollState.ability)}
          onClose={() => setRollState(null)}
        />
      )}
    </Layout>
  )
}
```

- [ ] **Step 11.2: Type-check**

```bash
cd /mnt/c/Users/Claudio/PycharmProjects/dnd_bot_revamped/webapp && npx tsc --noEmit
```

Expected: zero errors.

- [ ] **Step 11.3: Commit**

```bash
git add webapp/src/pages/SavingThrows.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): wire heroic-inspiration reroll on saving throws

Adds a sibling rerollMutation that plays the 3D animation, calls the
roll endpoint with with_inspiration=true and replaces the modal result
in place. wasRerolled hides the button + shows the badge. 409 paths
re-fetch the character so the UI no longer offers a stale reroll.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Wire reroll in `Skills.tsx`

**Files:**
- Modify: `webapp/src/pages/Skills.tsx`

- [ ] **Step 12.1: Add the mutation and pass props**

In `webapp/src/pages/Skills.tsx`:

(a) Add `ApiError` to the API import. Replace the existing line `import { api } from '@/api/client'` with:

```ts
import { api, ApiError } from '@/api/client'
```

(b) Replace the existing `useState` and `rollMutation` block (lines ~71–107) with:

```tsx
  type RollState = {
    result: RollResult
    skillName: string
    wasRerolled: boolean
  }
  const [rollState, setRollState] = useState<RollState | null>(null)

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  const mutation = useMutation({
    mutationFn: (skills: Record<string, unknown>) =>
      api.characters.updateSkills(charId, skills),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      haptic.light()
    },
    onError: () => haptic.error(),
  })

  const rollMutation = useMutation({
    mutationFn: async (skillName: string) => {
      const useAnimation = animate3d && !reducedMotion
      let die: number | undefined
      if (useAnimation) {
        const detected = await dice.playAndCollect([{ kind: 'd20', count: 1 }])
        die = detected[0]?.value
      }
      const result = await api.characters.rollSkill(charId, skillName, die)
      return { result, skillName }
    },
    onSuccess: ({ result, skillName }) => {
      setRollState({ result, skillName, wasRerolled: false })
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const rerollMutation = useMutation({
    mutationFn: async (skillName: string) => {
      const useAnimation = animate3d && !reducedMotion
      let die: number | undefined
      if (useAnimation) {
        const detected = await dice.playAndCollect([{ kind: 'd20', count: 1 }])
        die = detected[0]?.value
      }
      return api.characters.rollSkill(charId, skillName, die, true)
    },
    onSuccess: (result) => {
      setRollState((prev) => prev && { ...prev, result, wasRerolled: true })
      qc.invalidateQueries({ queryKey: ['character', charId] })
      haptic.success()
    },
    onError: (err) => {
      haptic.error()
      if (err instanceof ApiError && err.status === 409) {
        qc.invalidateQueries({ queryKey: ['character', charId] })
      }
    },
  })
```

The `[rollResult, setRollResult]` state name disappears. Update any in-file references to use `rollState`.

(c) Replace the modal at the bottom (lines ~237–243):

```tsx
      {rollResult && (
        <RollResultModal
          result={rollResult.result}
          title={rollResult.title}
          onClose={() => setRollResult(null)}
        />
      )}
```

with:

```tsx
      {rollState && (
        <RollResultModal
          result={rollState.result}
          title={t(`character.skills.${rollState.skillName}`)}
          inspirationAvailable={Boolean(char.heroic_inspiration)}
          isRerolling={rerollMutation.isPending}
          wasRerolled={rollState.wasRerolled}
          onInspirationReroll={() => rerollMutation.mutate(rollState.skillName)}
          onClose={() => setRollState(null)}
        />
      )}
```

- [ ] **Step 12.2: Type-check**

```bash
cd /mnt/c/Users/Claudio/PycharmProjects/dnd_bot_revamped/webapp && npx tsc --noEmit
```

Expected: zero errors.

- [ ] **Step 12.3: Commit**

```bash
git add webapp/src/pages/Skills.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): wire heroic-inspiration reroll on skill checks

Mirrors the SavingThrows wiring: animation + with_inspiration call,
in-place result swap, 409 invalidates the character cache so a stale
button cannot be pressed twice.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: Wire reroll in `Inventory.tsx`

**Files:**
- Modify: `webapp/src/pages/Inventory.tsx`

- [ ] **Step 13.1: Add the mutation and pass props**

In `webapp/src/pages/Inventory.tsx`:

(a) Replace the existing import line `import { api } from '@/api/client'` with:

```ts
import { api, ApiError } from '@/api/client'
```

(b) Replace the existing state declaration:

```tsx
  const [attackResult, setAttackResult] = useState<WeaponAttackResult | null>(null)
```

with:

```tsx
  type AttackState = {
    result: WeaponAttackResult
    itemId: number
    wasRerolled: boolean
  }
  const [attackState, setAttackState] = useState<AttackState | null>(null)
```

(c) Replace the existing `attackMutation` block (lines ~119–126):

```tsx
  const attackMutation = useMutation({
    mutationFn: (itemId: number) => api.items.attack(charId, itemId),
    onSuccess: (result) => {
      setAttackResult(result)
      haptic.success()
    },
    onError: () => haptic.error(),
  })
```

with:

```tsx
  const attackMutation = useMutation({
    mutationFn: (itemId: number) => api.items.attack(charId, itemId),
    onSuccess: (result, itemId) => {
      setAttackState({ result, itemId, wasRerolled: false })
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const attackRerollMutation = useMutation({
    mutationFn: (itemId: number) => api.items.attack(charId, itemId, true),
    onSuccess: (result) => {
      setAttackState((prev) => prev && { ...prev, result, wasRerolled: true })
      qc.invalidateQueries({ queryKey: ['character', charId] })
      haptic.success()
    },
    onError: (err) => {
      haptic.error()
      if (err instanceof ApiError && err.status === 409) {
        qc.invalidateQueries({ queryKey: ['character', charId] })
      }
    },
  })
```

(d) Replace the modal mount near the bottom (lines ~319–321):

```tsx
      {attackResult && (
        <WeaponAttackModal result={attackResult} onClose={() => setAttackResult(null)} />
```

with:

```tsx
      {attackState && (
        <WeaponAttackModal
          result={attackState.result}
          inspirationAvailable={Boolean(char?.heroic_inspiration)}
          isRerolling={attackRerollMutation.isPending}
          wasRerolled={attackState.wasRerolled}
          onInspirationReroll={() => attackRerollMutation.mutate(attackState.itemId)}
          onClose={() => setAttackState(null)}
        />
```

- [ ] **Step 13.2: Type-check**

```bash
cd /mnt/c/Users/Claudio/PycharmProjects/dnd_bot_revamped/webapp && npx tsc --noEmit
```

Expected: zero errors.

- [ ] **Step 13.3: Commit**

```bash
git add webapp/src/pages/Inventory.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): wire heroic-inspiration reroll on weapon attacks

The reroll fires the existing /attack endpoint with with_inspiration=true
so the server re-runs the entire flow (new to-hit + new damage). The
modal swaps result in place; 409 invalidates the character cache.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: New `<DicePoolResultModal>`

**Files:**
- Create: `webapp/src/components/DicePoolResultModal.tsx`

- [ ] **Step 14.1: Create the modal**

Create `webapp/src/components/DicePoolResultModal.tsx`:

```tsx
import { useCallback, useState } from 'react'
import { m, AnimatePresence } from 'framer-motion'
import { useTranslation } from 'react-i18next'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { spring } from '@/styles/motion'
import { CornerFlourishes } from './ui/Ornament'
import InspirationRerollButton from './InspirationRerollButton'
import { api, ApiError, type DiceResultRequestBody } from '@/api/client'
import { useDiceAnimation } from '@/dice/useDiceAnimation'
import { useDiceSettings } from '@/store/diceSettings'
import { useReducedMotion } from '@/hooks/useReducedMotion'
import type { RollGroup } from '@/dice/useRollAndPersist'
import { haptic } from '@/auth/telegram'

const MAX_INLINE_ROLLS = 8

function formatRollList(rolls: number[]): string {
  if (rolls.length <= MAX_INLINE_ROLLS) {
    return `[${rolls.join('+')}]`
  }
  const visible = rolls.slice(0, MAX_INLINE_ROLLS).join('+')
  const remaining = rolls.length - MAX_INLINE_ROLLS
  const min = Math.min(...rolls)
  const max = Math.max(...rolls)
  return `[${visible}+… (+${remaining}, min ${min} · max ${max})]`
}

type Props = {
  charId: number
  initialResults: RollGroup[]
  inspirationAvailable: boolean
  onClose: () => void
}

function isPureD20Pool(results: RollGroup[]): boolean {
  return (
    results.length === 1 &&
    results[0].kind === 'd20' &&
    results[0].rolls.length === 1
  )
}

export default function DicePoolResultModal({
  charId,
  initialResults,
  inspirationAvailable,
  onClose,
}: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const dice = useDiceAnimation()
  const animate3d = useDiceSettings((s) => s.animate3d)
  const reducedMotion = useReducedMotion()

  const [results, setResults] = useState<RollGroup[]>(initialResults)
  const [wasRerolled, setWasRerolled] = useState(false)

  const rerollMutation = useMutation({
    mutationFn: async () => {
      const useAnimation = animate3d && !reducedMotion
      let dieValue: number
      if (useAnimation) {
        const detected = await dice.playAndCollect([{ kind: 'd20', count: 1 }])
        dieValue = detected[0]?.value ?? 1
      } else {
        dieValue = Math.floor(Math.random() * 20) + 1
      }
      const body: DiceResultRequestBody = {
        rolls: [{ kind: 'd20', value: dieValue }],
        notation: '1d20',
        label: 'Reroll ispirazione',
        with_inspiration: true,
      }
      await api.dice.result(charId, body)
      return { kind: 'd20' as const, notation: '1d20', rolls: [dieValue], total: dieValue }
    },
    onSuccess: (group) => {
      setResults([group])
      setWasRerolled(true)
      qc.invalidateQueries({ queryKey: ['character', charId] })
      qc.invalidateQueries({ queryKey: ['dice-history', charId] })
      qc.invalidateQueries({ queryKey: ['history', charId] })
      haptic.success()
    },
    onError: (err) => {
      haptic.error()
      if (err instanceof ApiError && err.status === 409) {
        qc.invalidateQueries({ queryKey: ['character', charId] })
      }
    },
  })

  const total = results.reduce((s, g) => s + g.total, 0)
  const showInspirationButton =
    inspirationAvailable && !wasRerolled && isPureD20Pool(results)

  const handleReroll = useCallback(() => {
    rerollMutation.mutate()
  }, [rerollMutation])

  return (
    <AnimatePresence>
      <m.div
        className="fixed inset-0 flex items-center justify-center z-50 p-4"
        style={{ background: 'var(--dnd-overlay)', backdropFilter: 'blur(6px)' }}
        onClick={onClose}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      >
        <m.div
          className="relative rounded-3xl p-6 pt-8 w-full max-w-sm space-y-4
                     bg-gradient-parchment surface-parchment border-2 border-dnd-gold-dim
                     shadow-parchment-2xl"
          onClick={(e) => e.stopPropagation()}
          initial={{ opacity: 0, scale: 0.85, y: 30 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.92, y: 20 }}
          transition={spring.elastic}
        >
          <div className="text-dnd-gold-dim">
            <CornerFlourishes />
          </div>

          <div className="text-center">
            <p className="text-sm text-dnd-text-muted font-cinzel uppercase tracking-widest">
              {t('character.dice_overlay.result_title')}
            </p>
            {wasRerolled && (
              <p className="text-[11px] text-dnd-arcane-bright font-cinzel uppercase tracking-wider mt-1">
                {t('character.inspiration.reroll_badge')}
              </p>
            )}
          </div>

          <div className="space-y-2 max-h-[40vh] overflow-y-auto">
            {results.map((g, i) => (
              <div
                key={i}
                className="flex items-baseline justify-between gap-2 font-mono text-sm"
              >
                <span className="text-dnd-gold-dim min-w-0 flex-1">
                  <span className="font-semibold">{g.notation}</span>
                  {g.rolls.length > 1 && (
                    <span className="text-dnd-text-faint text-[11px] ml-1.5 break-words">
                      {formatRollList(g.rolls)}
                    </span>
                  )}
                </span>
                <span className="font-display font-black text-dnd-gold-bright text-lg shrink-0">
                  {g.total}
                </span>
              </div>
            ))}
          </div>

          {results.length > 1 && (
            <p className="text-center text-dnd-text-muted text-xs font-body">
              Totale:{' '}
              <span className="font-display font-black text-dnd-gold-bright text-base">
                {total}
              </span>
            </p>
          )}

          {showInspirationButton && (
            <InspirationRerollButton
              available
              pending={rerollMutation.isPending}
              onClick={handleReroll}
            />
          )}

          <m.button
            type="button"
            onClick={onClose}
            className="w-full py-2.5 rounded-xl bg-gradient-gold text-dnd-ink font-semibold
                       min-h-[48px] shadow-engrave font-cinzel uppercase tracking-wider"
            whileTap={{ scale: 0.97 }}
          >
            OK
          </m.button>
        </m.div>
      </m.div>
    </AnimatePresence>
  )
}
```

- [ ] **Step 14.2: Type-check**

```bash
cd /mnt/c/Users/Claudio/PycharmProjects/dnd_bot_revamped/webapp && npx tsc --noEmit
```

Expected: zero errors. Component is not yet mounted anywhere, so no UI change yet.

- [ ] **Step 14.3: Commit**

```bash
git add webapp/src/components/DicePoolResultModal.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): add DicePoolResultModal for the dice tray result

Centered parchment modal that replaces the bottom-toast result of the
DiceOverlay. Shows the per-group breakdown plus a total, and exposes a
heroic-inspiration reroll only when the original pool was exactly 1d20.
The reroll calls /dice/result with with_inspiration=true so the
inspiration consumption stays atomic.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 15: Refactor `DiceOverlay.tsx` — toast → modal + cap

**Files:**
- Modify: `webapp/src/components/DiceOverlay.tsx`

- [ ] **Step 15.1: Replace the file**

Replace `webapp/src/components/DiceOverlay.tsx` with:

```tsx
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, matchPath } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m, AnimatePresence } from 'framer-motion'
import { GiPerspectiveDiceSixFacesRandom as Dices } from 'react-icons/gi'
import DiceIcon from '@/components/ui/DiceIcon'
import DicePoolResultModal from '@/components/DicePoolResultModal'
import { useCharacterStore } from '@/store/characterStore'
import { haptic } from '@/auth/telegram'
import { api } from '@/api/client'
import { useRollAndPersist, type RollEntry, type RollGroup } from '@/dice/useRollAndPersist'
import type { DiceKind } from '@/dice/types'

const KINDS: DiceKind[] = ['d4', 'd6', 'd8', 'd10', 'd12', 'd20', 'd100']
const SIDES_FOR = {
  d4: 4, d6: 6, d8: 8, d10: 10, d12: 12, d20: 20, d100: 100,
} as const satisfies Record<DiceKind, number>
const ERROR_DISMISS_MS = 3000
const POOL_CAP = 100

type DicePool = Partial<Record<DiceKind, number>>

function useOverlayVisibility(): { visible: boolean; charId: number | null } {
  const location = useLocation()
  const activeCharId = useCharacterStore((s) => s.activeCharId)

  return useMemo(() => {
    const path = location.pathname
    if (matchPath('/char/:id/dice', path)) return { visible: false, charId: null }
    if (matchPath('/char/:id/settings', path)) return { visible: false, charId: null }

    const charAny = matchPath('/char/:id/*', path) ?? matchPath('/char/:id', path)
    if (charAny) {
      const id = Number(charAny.params.id)
      return { visible: Number.isFinite(id), charId: Number.isFinite(id) ? id : null }
    }

    if (matchPath('/session/:id', path) && activeCharId != null) {
      return { visible: true, charId: activeCharId }
    }

    return { visible: false, charId: null }
  }, [location.pathname, activeCharId])
}

export default function DiceOverlay() {
  const { t } = useTranslation()
  const { visible, charId } = useOverlayVisibility()
  const [open, setOpen] = useState(false)
  const [pool, setPool] = useState<DicePool>({})

  const [results, setResults] = useState<RollGroup[] | null>(null)
  const [warningText, setWarningText] = useState<string | null>(null)

  const dismissTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const longPressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const longPressFiredRef = useRef(false)

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => (charId ? api.characters.get(charId) : Promise.reject()),
    enabled: charId != null,
  })

  useEffect(() => {
    return () => {
      if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current)
      if (longPressTimerRef.current) clearTimeout(longPressTimerRef.current)
    }
  }, [])

  const showWarning = useCallback((text: string) => {
    setWarningText(text)
    if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current)
    dismissTimerRef.current = setTimeout(() => setWarningText(null), ERROR_DISMISS_MS)
  }, [])

  const { roll, isPending } = useRollAndPersist(charId)

  const entries = useMemo(
    () => (Object.entries(pool) as Array<[DiceKind, number]>).filter(([, n]) => n > 0),
    [pool]
  )
  const poolTotal = entries.reduce((s, [, n]) => s + n, 0)
  const isRolling = isPending

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
      setResults(groups)
    } catch {
      haptic.error()
      showWarning(t('character.dice_overlay.roll_failed'))
    }
  }, [entries, isPending, charId, roll, showWarning, t])

  const increment = useCallback((kind: DiceKind) => {
    setPool((p) => {
      const total = Object.values(p).reduce((s, n) => s + (n ?? 0), 0)
      if (total >= POOL_CAP) {
        haptic.warning()
        showWarning(t('character.dice_overlay.pool_cap_reached'))
        return p
      }
      haptic.light()
      return { ...p, [kind]: (p[kind] ?? 0) + 1 }
    })
  }, [showWarning, t])

  const clearKind = useCallback((kind: DiceKind) => {
    haptic.medium()
    setPool((p) => {
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      const { [kind]: _removed, ...rest } = p
      return rest
    })
  }, [])

  const handlePointerDown = useCallback((kind: DiceKind) => {
    longPressFiredRef.current = false
    longPressTimerRef.current = setTimeout(() => {
      longPressFiredRef.current = true
      clearKind(kind)
    }, 500)
  }, [clearKind])

  const handlePointerUpOrLeave = useCallback(() => {
    if (longPressTimerRef.current) {
      clearTimeout(longPressTimerRef.current)
      longPressTimerRef.current = null
    }
  }, [])

  const handleKindClick = useCallback((kind: DiceKind) => {
    if (longPressFiredRef.current) {
      longPressFiredRef.current = false
      return
    }
    increment(kind)
  }, [increment])

  const toggleOpen = useCallback(() => {
    haptic.light()
    setOpen((o) => !o)
    setPool({})
  }, [])

  if (!visible) return null

  return (
    <>
      <div className="fixed bottom-4 right-4 z-[55]">
        <AnimatePresence>
          {open && (
            <m.div
              className="absolute bottom-full right-0 mb-2 flex flex-col-reverse gap-1.5"
              initial={{ opacity: 0, scaleY: 0.6, transformOrigin: 'bottom' }}
              animate={{ opacity: 1, scaleY: 1 }}
              exit={{ opacity: 0, scaleY: 0.6 }}
              transition={{ type: 'spring', stiffness: 320, damping: 26 }}
            >
              {KINDS.map((kind, idx) => {
                const count = pool[kind] ?? 0
                return (
                  <m.button
                    key={kind}
                    type="button"
                    onClick={() => handleKindClick(kind)}
                    onPointerDown={() => handlePointerDown(kind)}
                    onPointerUp={handlePointerUpOrLeave}
                    onPointerLeave={handlePointerUpOrLeave}
                    onPointerCancel={handlePointerUpOrLeave}
                    disabled={isRolling}
                    className="relative w-12 h-12 rounded-2xl bg-dnd-surface-raised border border-dnd-border
                               flex items-center justify-center text-dnd-gold-bright select-none
                               touch-manipulation [-webkit-touch-callout:none]
                               hover:border-dnd-gold/60 hover:shadow-halo-gold transition-[box-shadow,border-color]
                               disabled:opacity-40"
                    whileTap={{ scale: 0.9 }}
                    initial={{ opacity: 0, x: 10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: idx * 0.03 }}
                    aria-label={kind}
                  >
                    <DiceIcon sides={SIDES_FOR[kind]} size={28} />
                    {count > 0 && (
                      <span className="absolute -top-1 -right-1 min-w-[20px] h-5 px-1
                                       rounded-full bg-dnd-crimson text-white text-[11px]
                                       font-bold font-mono flex items-center justify-center
                                       border border-dnd-surface-raised">
                        {count}
                      </span>
                    )}
                  </m.button>
                )
              })}
            </m.div>
          )}
        </AnimatePresence>

        <AnimatePresence>
          {poolTotal > 0 && (
            <m.button
              type="button"
              onClick={handleRoll}
              disabled={isRolling}
              className="absolute right-full top-0 mr-2 h-14 px-5 rounded-2xl
                         bg-gradient-to-r from-dnd-gold-deep to-dnd-gold-bright
                         border border-dnd-gold-dim shadow-halo-gold
                         flex items-center justify-center gap-2 text-dnd-ink
                         font-cinzel uppercase tracking-wider font-bold text-sm
                         disabled:opacity-60 whitespace-nowrap"
              initial={{ opacity: 0, x: 10, scale: 0.9 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 10, scale: 0.9 }}
              whileTap={{ scale: 0.95 }}
              transition={{ type: 'spring', stiffness: 320, damping: 24 }}
            >
              <Dices size={18} />
              {isRolling ? t('character.dice_overlay.rolling') : t('character.dice_overlay.roll')}
            </m.button>
          )}
        </AnimatePresence>

        <m.button
          type="button"
          aria-label={open ? t('character.dice_overlay.close') : t('character.dice_overlay.open')}
          onClick={toggleOpen}
          className="w-14 h-14 rounded-full
                     bg-gradient-to-br from-dnd-gold-deep to-dnd-gold-bright
                     border border-dnd-gold-dim shadow-halo-gold
                     flex items-center justify-center text-dnd-ink touch-manipulation"
          whileTap={{ scale: 0.9 }}
          initial={{ opacity: 0, scale: 0.6 }}
          animate={{ opacity: 1, scale: 1, rotate: open ? 45 : 0 }}
          transition={{ type: 'spring', stiffness: 260, damping: 22 }}
        >
          <Dices size={26} />
        </m.button>
      </div>

      {results && results.length > 0 && charId != null && (
        <DicePoolResultModal
          charId={charId}
          initialResults={results}
          inspirationAvailable={Boolean(char?.heroic_inspiration)}
          onClose={() => setResults(null)}
        />
      )}

      <AnimatePresence>
        {warningText && (
          <m.button
            type="button"
            role="alert"
            onClick={() => setWarningText(null)}
            className="fixed bottom-24 left-4 right-4 mx-auto z-[55]
                       max-w-xs
                       rounded-2xl bg-dnd-surface-raised/95 backdrop-blur-md
                       border border-dnd-crimson shadow-parchment-xl
                       px-4 py-3 text-center font-body text-sm text-dnd-crimson-bright"
            initial={{ opacity: 0, y: 20, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.95 }}
            transition={{ type: 'spring', stiffness: 320, damping: 26 }}
          >
            {warningText}
          </m.button>
        )}
      </AnimatePresence>
    </>
  )
}
```

- [ ] **Step 15.2: Type-check**

```bash
cd /mnt/c/Users/Claudio/PycharmProjects/dnd_bot_revamped/webapp && npx tsc --noEmit
```

Expected: zero errors.

- [ ] **Step 15.3: Commit**

```bash
git add webapp/src/components/DiceOverlay.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): replace dice overlay toast with DicePoolResultModal + cap

Mounts the new modal as the result surface and removes the bottom
toast. Adds a client-side pool cap of 100; further increments emit a
warning toast plus haptic.warning. Pool cap stays under the bumped
server cap (200) so we never see another 422.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 16: Final type-check, prod build smoke, manual verification

**Files:** none modified beyond existing tasks.

This task does **not** introduce new code. It exists to enforce the gate before opening a PR.

- [ ] **Step 16.1: Final type-check**

```bash
cd /mnt/c/Users/Claudio/PycharmProjects/dnd_bot_revamped/webapp && npx tsc --noEmit
```

Expected: zero errors.

- [ ] **Step 16.2: Prod build smoke**

```bash
cd /mnt/c/Users/Claudio/PycharmProjects/dnd_bot_revamped/webapp && npm run build:prod
```

Expected: build exits clean, `docs/app/` updated. Per `CLAUDE.md` quirk note, restore the local env file:

```bash
printf 'VITE_API_BASE_URL=http://127.0.0.1:8000\n' > webapp/.env.local
```

If `docs/app/` produced changes, stage them:

```bash
git add docs/app/
git commit -m "$(cat <<'EOF'
chore(webapp): rebuild after dice cap fix and inspiration reroll

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 16.3: Manual verification matrix**

Run the local stack (Windows shell):

```
uv run uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
cd webapp && npm run dev
```

Open `http://localhost:5173/`. For a character with `heroic_inspiration=true`, walk through the spec table (§7.2):

1. DiceOverlay 50d20 → DicePoolResultModal opens, no console warning.
2. DiceOverlay increment past 100 → warning toast, count stops growing.
3. Saving throw with inspiration → reroll button visible, click triggers animation, badge appears, HeroScreen shows inspiration off.
4. Skill check with inspiration → same as #3.
5. Weapon attack with inspiration on a hit → new to-hit + new damage shown.
6. Weapon attack reroll on a fumble → damage section appears with new value if new roll hits.
7. DiceOverlay 1d20 with inspiration → reroll button visible, reroll works.
8. DiceOverlay 1d20+1d6 → no reroll button.
9. DiceOverlay 2d20 → no reroll button.
10. Race: spend inspiration in HeroScreen, attempt reroll in modal → 409 toast, modal stays open.
11. Toggle `animate3d=false` in settings, repeat #3 → reroll works without 3D animation.
12. Reduced motion via OS setting → reroll works.
13. Local DEV_USER_ID flow → all of the above pass without Telegram.

If any case fails, fix in place and re-run the affected tasks (each task is independent so you can amend its commit).

- [ ] **Step 16.4: Push and open PR**

Once all checks pass:

```bash
git push -u origin fix/dice-cap-and-inspiration-reroll
gh pr create --title "fix: dice pool cap + heroic inspiration reroll" --body "$(cat <<'EOF'
## Summary
- Fix 422 from `/characters/{id}/dice/result` past 50 dice (server cap → 200, client cap 100, warning toast).
- Add heroic inspiration reroll on skill checks, saving throws, weapon attacks and the new dice-pool popup.
- Replace DiceOverlay bottom toast with `DicePoolResultModal` (parchment popup matching the existing modal family).
- Drop the spurious `THREE.BufferGeometry.computeTangents()` console warning.

## Test plan
- [ ] DiceOverlay 50d20 succeeds, no console warning
- [ ] DiceOverlay pool cap (100) blocks further increments with warning toast
- [ ] Saving throw + skill check reroll button visible only when char has inspiration
- [ ] Weapon attack reroll re-runs full attack (new to-hit AND new damage)
- [ ] Reroll badge appears after success, button hidden, inspiration off in HeroScreen
- [ ] DiceOverlay reroll button only visible for pure 1d20 pools
- [ ] Race condition: 409 surfaces toast, modal stays open
- [ ] `animate3d=false` and reduced motion flows still work

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-Review

- **Spec coverage:** Every spec section maps to at least one task — schema bumps (Task 2), backend endpoints (Tasks 3–5), shared button (Task 8), modal extensions (Tasks 9–10), DicePool modal (Task 14), DiceOverlay refactor (Task 15), i18n (Task 6), client signatures (Task 7), bug fix #1 cosmetic (Task 1), pool cap (Task 15), manual verification (Task 16). The spec's WeaponAttack reroll variant (a) — full attack re-execution — is reflected in Task 5's history prefix and Task 13's `attackRerollMutation`. The spec's "atomic via DiceResultRequest" choice (Section 4.1 of spec) drives Task 3 + Task 14.

- **Placeholder scan:** No TBD/TODO entries remain. Code blocks are complete in every step.

- **Type consistency:**
  - `inspirationAvailable`, `isRerolling`, `wasRerolled`, `onInspirationReroll` props match across `RollResultModal`, `WeaponAttackModal`, `DicePoolResultModal` and their callers.
  - `withInspiration` is the camelCase TS argument; `with_inspiration` is the wire/JSON form. Mapping is consistent in `api/client.ts`.
  - `RollGroup` shape used by `DicePoolResultModal` matches the existing export in `webapp/src/dice/useRollAndPersist.ts`.
  - `ApiError` class import is the same in all reroll mutations.

No issues to fix.
