# Rework Concentrazione (Gruppo C) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-triggerare il tiro salvezza (TS) concentrazione su op DAMAGE, rimuovere TS manuale da HP.tsx e Spells.tsx, aggiungere descrizione spell nella sezione concentrazione attiva.

**Architecture:** Backend: `ConcentrationSaveResult` promosso a schema shared; nuovo helper `_roll_concentration_save(char, damage, session)` in `api/routers/_helpers.py`; endpoint `POST /concentration/save` esistente diventa wrapper; endpoint `/hp` op DAMAGE chiama helper e popola `CharacterFull.concentration_save` opzionale nella response. Frontend: HP.tsx e Spells.tsx rimuovono damage input + save button del TS manuale; HP.tsx mostra panel risultato quando mutation ritorna `concentration_save`; Spells.tsx aggiunge descrizione spell sotto nome nella sezione concentrazione.

**Tech Stack:** FastAPI + SQLAlchemy async + Pydantic, React + TypeScript + TanStack Query + react-i18next + framer-motion + sonner.

**Branch:** `feat/concentration-gruppo-c` (creato da `main`).
**Spec:** `docs/superpowers/specs/2026-04-23-concentration-design.md`.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `api/schemas/common.py` | Modify | Add `ConcentrationSaveResult` (promoted from spells router). |
| `api/schemas/character.py` | Modify | Add `concentration_save: Optional[ConcentrationSaveResult] = None` transient field. |
| `api/routers/_helpers.py` | Modify | Add `_roll_concentration_save(char, damage, session)`. |
| `api/routers/spells.py` | Modify | Remove local `ConcentrationSaveResult` class; refactor `/concentration/save` route to call helper. |
| `api/routers/hp.py` | Modify | Call helper on DAMAGE if concentrating + HP>0; populate `concentration_save` in response. |
| `webapp/src/api/client.ts` | Modify | Extend `CharacterFull` type with optional `concentration_save`. |
| `webapp/src/pages/HP.tsx` | Modify | Remove manual TS input/button; add auto-triggered result panel. |
| `webapp/src/pages/Spells.tsx` | Modify | Remove manual TS block; add spell description inside concentration-active section. |
| `webapp/src/locales/it.json` | Modify | +3-4 keys. |
| `webapp/src/locales/en.json` | Modify | +3-4 keys. |
| `docs/app/` | Modify (generated) | Rebuild pre-PR. |

---

### Task 1: Promote `ConcentrationSaveResult` to shared schema

**Files:**
- Modify: `api/schemas/common.py`
- Modify: `api/routers/spells.py`

- [ ] **Step 1: Inspect current location**

Leggi `api/routers/spells.py` lines 195-201 per confermare la definizione attuale:

```python
class ConcentrationSaveResult(RollResult):
    dc: int
    success: bool
    lost_concentration: bool
```

- [ ] **Step 2: Add import `RollResult` in `common.py` if missing**

Apri `api/schemas/common.py`. Verifica se `RollResult` è già importato/definito. Cerca:

```bash
grep -n "^class RollResult\|from .* import RollResult" /mnt/c/Users/Claudio/PycharmProjects/dnd_bot_revamped/api/schemas/common.py
```

Se `RollResult` è definito lì, ok. Altrimenti, importalo dalla sua sede attuale. `api/routers/spells.py:18` fa `from api.schemas.character import CharacterFull` — `RollResult` è in `api/schemas/common.py` (già trovato line 278 per esplorazione precedente).

- [ ] **Step 3: Append `ConcentrationSaveResult` to `common.py`**

Apri `api/schemas/common.py`. In fondo al file (o dopo la classe `RollResult`), aggiungi:

```python
class ConcentrationSaveResult(RollResult):
    """Result of a concentration saving throw.

    Extends RollResult with the DC rolled against, the binary outcome,
    and whether the character lost concentration as a result.
    """
    dc: int
    success: bool
    lost_concentration: bool
```

- [ ] **Step 4: Remove the local class from `spells.py`**

Apri `api/routers/spells.py`. Elimina le lines 197-200 (la classe `ConcentrationSaveResult`):

```python
class ConcentrationSaveResult(RollResult):
    dc: int
    success: bool
    lost_concentration: bool
```

- [ ] **Step 5: Import `ConcentrationSaveResult` in `spells.py` from the new location**

In testa a `api/routers/spells.py`, trova l'import `from api.schemas.common import ...`. Aggiungi `ConcentrationSaveResult` alla lista. Se non c'è un import da `common.py`, aggiungi una riga:

```python
from api.schemas.common import ConcentrationSaveResult
```

(Posizionala tra gli altri `from api.schemas...` imports.)

- [ ] **Step 6: Syntax check**

```bash
python3 -c "import ast; ast.parse(open('api/schemas/common.py').read()); ast.parse(open('api/routers/spells.py').read()); print('ok')"
```

Expected: `ok`.

- [ ] **Step 7: Commit**

```bash
git add api/schemas/common.py api/routers/spells.py
git commit -m "refactor(api): promote ConcentrationSaveResult to shared schemas

Move the class from api/routers/spells.py to api/schemas/common.py
so CharacterFull and other routers can reference it without
circular imports. /concentration/save route unchanged behaviorally.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Extract `_roll_concentration_save` helper

**Files:**
- Modify: `api/routers/_helpers.py`

- [ ] **Step 1: Append the helper to `_helpers.py`**

Apri `api/routers/_helpers.py`. Aggiungi in fondo:

```python
import random
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.common import ConcentrationSaveResult
from core.db.models import Character, CharacterHistory


def _append_concentration_history(
    session: AsyncSession,
    char_id: int,
    damage: int,
    dc: int,
    die: int,
    con_mod: int,
    total: int,
    success: bool,
    lost_concentration: bool,
) -> None:
    """Local history helper (avoids depending on router's private _add_history)."""
    outcome = "SUCCESSO" if success else "FALLIMENTO"
    desc = (
        f"TS Concentrazione (danno {damage}, DC {dc}): "
        f"d20={die}+{con_mod}={total} — {outcome}"
        + (" → concentrazione persa" if lost_concentration else "")
    )
    session.add(CharacterHistory(
        character_id=char_id,
        event_type="concentration_save",
        description=desc,
    ))


def roll_concentration_save(
    char: Character,
    damage: int,
    session: AsyncSession,
) -> ConcentrationSaveResult:
    """Roll a CON save vs DC=max(10, damage//2). Nat20 auto-pass, nat1 auto-fail.

    Side effects:
    - Clears char.concentrating_spell_id on failure (if it was set).
    - Appends a history entry describing the roll.

    Returns a ConcentrationSaveResult with die, bonus, total, is_critical,
    is_fumble, description, dc, success, lost_concentration.
    """
    dc = max(10, damage // 2)

    con_score = next((s for s in char.ability_scores if s.name == "constitution"), None)
    con_mod = con_score.modifier if con_score else 0

    die = random.randint(1, 20)
    total = die + con_mod
    is_crit = die == 20
    is_fumble = die == 1

    if is_crit:
        success = True
    elif is_fumble:
        success = False
    else:
        success = total >= dc

    lost_concentration = not success and char.concentrating_spell_id is not None
    if lost_concentration:
        char.concentrating_spell_id = None

    _append_concentration_history(
        session, char.id, damage, dc, die, con_mod, total, success, lost_concentration,
    )

    return ConcentrationSaveResult(
        die=die,
        bonus=con_mod,
        total=total,
        is_critical=is_crit,
        is_fumble=is_fumble,
        description=f"DC {dc}",
        dc=dc,
        success=success,
        lost_concentration=lost_concentration,
    )
```

**Nota:** il nome pubblico è `roll_concentration_save` (senza underscore prefix) perché è riusato tra router. `_append_concentration_history` è privato al modulo.

**Nota modello:** `CharacterHistory` è già definito in `core/db/models.py:491`. Verifica `event_type` field allowed values.

- [ ] **Step 2: Syntax check**

```bash
python3 -c "import ast; ast.parse(open('api/routers/_helpers.py').read()); print('ok')"
```

- [ ] **Step 3: Commit**

```bash
git add api/routers/_helpers.py
git commit -m "feat(api): roll_concentration_save helper in _helpers.py

Extracts the d20+CON save logic (DC=max(10, damage//2), nat20/nat1
handling, concentration clearing on fail, history entry) into a
shared function callable from both hp.py (auto-trigger) and
spells.py (manual endpoint).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Refactor `POST /concentration/save` to use helper

**Files:**
- Modify: `api/routers/spells.py`

- [ ] **Step 1: Update imports**

In testa a `api/routers/spells.py`, aggiungi:

```python
from api.routers._helpers import roll_concentration_save
```

- [ ] **Step 2: Replace route body**

Trova la route `concentration_save` (line ~203-252). Sostituisci l'intera funzione con:

```python
@router.post("/{char_id}/concentration/save", response_model=ConcentrationSaveResult)
async def concentration_save(
    char_id: int,
    body: ConcentrationSaveRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ConcentrationSaveResult:
    char = await _get_owned_full(char_id, user_id, session)
    return roll_concentration_save(char, body.damage, session)
```

`import random` in spells.py rimane (usato altrove in `roll_spell_damage`).

- [ ] **Step 3: Syntax check**

```bash
python3 -c "import ast; ast.parse(open('api/routers/spells.py').read()); print('ok')"
```

- [ ] **Step 4: Commit**

```bash
git add api/routers/spells.py
git commit -m "refactor(api): /concentration/save uses shared helper

Thin wrapper around roll_concentration_save. Behavior unchanged.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Add `concentration_save` field to `CharacterFull` schema

**Files:**
- Modify: `api/schemas/character.py`

- [ ] **Step 1: Import `ConcentrationSaveResult`**

In testa a `api/schemas/character.py`, aggiungi (o estendi un import esistente) per includere `ConcentrationSaveResult`:

```python
from api.schemas.common import (
    # ... other existing imports ...
    ConcentrationSaveResult,
)
```

- [ ] **Step 2: Add the field**

Dopo il field `hp_gained` (line 77), aggiungi:

```python
    # Populated only by POST /hp when op=DAMAGE on a concentrating character
    concentration_save: Optional[ConcentrationSaveResult] = None
```

Blocco risultante:

```python
    # Populated only by PATCH /xp when a level-up occurs
    hp_gained: Optional[int] = None

    # Populated only by POST /hp when op=DAMAGE on a concentrating character
    concentration_save: Optional[ConcentrationSaveResult] = None
```

- [ ] **Step 3: Syntax check**

```bash
python3 -c "import ast; ast.parse(open('api/schemas/character.py').read()); print('ok')"
```

- [ ] **Step 4: Commit**

```bash
git add api/schemas/character.py
git commit -m "feat(api): CharacterFull.concentration_save transient field

Populated by /hp op DAMAGE when the character is concentrating
on a spell and survives the damage. Null otherwise.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Auto-trigger TS on `/hp` op DAMAGE

**Files:**
- Modify: `api/routers/hp.py`

- [ ] **Step 1: Update imports**

In testa a `api/routers/hp.py`, aggiungi:

```python
from api.routers._helpers import roll_concentration_save
from api.schemas.common import ConcentrationSaveResult  # if needed for return typing
```

(Il secondo import potrebbe non essere necessario se non referenziato direttamente — verifica.)

- [ ] **Step 2: Refactor `update_hp` return type and DAMAGE branch**

Individua la route `update_hp` (around line 85-142). Attualmente ritorna `-> Character`. Cambia return type hint e logica finale.

Nella firma:

Before:
```python
) -> Character:
```

After:
```python
) -> CharacterFull:
```

Verifica che `CharacterFull` sia importato (line 18 già `from api.schemas.character import CharacterFull`).

- [ ] **Step 3: Capture conc_result in DAMAGE branch**

Individua il blocco DAMAGE (line 99-110):

```python
    if body.op == HPOp.DAMAGE:
        amount = body.value
        # Absorb temp HP first
        if char.temp_hp > 0:
            absorbed = min(char.temp_hp, amount)
            char.temp_hp -= absorbed
            amount -= absorbed
        old = char.current_hit_points
        char.current_hit_points = max(0, char.current_hit_points - amount)
        _add_history(session, char.id, "hp_change",
                     f"Danni: -{body.value} HP ({old} → {char.current_hit_points})")
```

Introduci `conc_result` locale all'inizio dello scope route (subito dopo `char = await _get_owned_full(...)`):

```python
    char = await _get_owned_full(char_id, user_id, session)
    conc_result: ConcentrationSaveResult | None = None

    was_at_zero = char.current_hit_points == 0

    if body.op == HPOp.DAMAGE:
        amount = body.value
        if char.temp_hp > 0:
            absorbed = min(char.temp_hp, amount)
            char.temp_hp -= absorbed
            amount -= absorbed
        old = char.current_hit_points
        char.current_hit_points = max(0, char.current_hit_points - amount)
        _add_history(session, char.id, "hp_change",
                     f"Danni: -{body.value} HP ({old} → {char.current_hit_points})")

        # Auto concentration save — only if still conscious and concentrating
        if (
            char.concentrating_spell_id is not None
            and char.current_hit_points > 0
        ):
            conc_result = roll_concentration_save(char, body.value, session)
```

- [ ] **Step 4: Populate response**

Alla fine della route `update_hp`, sostituisci `return char` con:

Before:
```python
    return char
```

After:
```python
    result = CharacterFull.model_validate(char)
    if conc_result is not None:
        result.concentration_save = conc_result
    return result
```

- [ ] **Step 5: Syntax check**

```bash
python3 -c "import ast; ast.parse(open('api/routers/hp.py').read()); print('ok')"
```

- [ ] **Step 6: Commit**

```bash
git add api/routers/hp.py
git commit -m "feat(api): auto-trigger concentration save on /hp DAMAGE

When op=DAMAGE and char.concentrating_spell_id is set AND the
character has HP > 0 after the damage, invoke the shared helper
roll_concentration_save. Embed the result in CharacterFull via
the new concentration_save optional field.

If HP drops to 0, existing logic clears concentrating_spell_id
and skips auto-TS (RAW: concentration lost on HP=0).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Extend FE `CharacterFull` type

**Files:**
- Modify: `webapp/src/api/client.ts`

- [ ] **Step 1: Find `CharacterFull` type definition**

```bash
grep -n "CharacterFull" /mnt/c/Users/Claudio/PycharmProjects/dnd_bot_revamped/webapp/src/types.ts | head -5
```

Se il tipo è in `types.ts`, modifica lì. Altrimenti in `client.ts`.

- [ ] **Step 2: Add `concentration_save` field**

Individua la definizione (type o interface) di `CharacterFull`. Aggiungi (accanto a `hp_gained?: number`):

```ts
concentration_save?: ConcentrationSaveResult | null
```

Assicurati che `ConcentrationSaveResult` sia esportato/importato. `webapp/src/api/client.ts` line 67 già definisce:

```ts
export type ConcentrationSaveResult = {
  die: number
  bonus: number
  total: number
  is_critical: boolean
  is_fumble: boolean
  description: string
  dc: number
  success: boolean
  lost_concentration: boolean
}
```

Se `CharacterFull` è in `types.ts` ma `ConcentrationSaveResult` in `client.ts`, importa il tipo in `types.ts` (o sposta il tipo in `types.ts` per coerenza). Se crea ciclo, duplica la definizione minimal in `types.ts`.

**Scelta semplice:** aggiungi il campo opzionale direttamente al tipo `CharacterFull` nel file dove è definito, importando o duplicando il tipo `ConcentrationSaveResult` secondo convenienza.

- [ ] **Step 3: Commit**

```bash
git add webapp/src/api/client.ts webapp/src/types.ts
git commit -m "feat(webapp): CharacterFull.concentration_save optional field

Mirrors the backend schema extension. HP.tsx reads this field to
show the auto-triggered save result panel.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

(Include entrambi i file anche se solo uno modificato — `git add` safe.)

---

### Task 7: FE `HP.tsx` — rimuovere TS manuale, aggiungere panel auto

**Files:**
- Modify: `webapp/src/pages/HP.tsx`

- [ ] **Step 1: Remove manual TS mutation and state**

Apri `webapp/src/pages/HP.tsx`. Individua e rimuovi:

```tsx
  const concSaveMutation = useMutation({
    mutationFn: (damage: number) => api.spells.concentrationSave(charId, damage),
    onSuccess: (result) => {
      setConcSaveResult(result)
      if (result.lost_concentration) {
        qc.invalidateQueries({ queryKey: ['character', charId] })
      }
      setConcDamageInput('')
      haptic.success()
    },
    onError: () => haptic.error(),
  })
```

Rimuovi anche `concSaveResult`, `setConcSaveResult`, `concDamageInput`, `setConcDamageInput` (useState declarations relative).

- [ ] **Step 2: Add autoConcSave state**

Dopo le altre useState in alto al componente, aggiungi:

```tsx
  const [autoConcSave, setAutoConcSave] = useState<ConcentrationSaveResult | null>(null)
```

Importa `ConcentrationSaveResult` da `@/api/client` se non già importato.

- [ ] **Step 3: Intercept hpMutation success**

Trova `hpMutation`:

```tsx
  const hpMutation = useMutation({
    mutationFn: (data: { op: HPOp; val: number }) => ...,
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      ...
    },
    onError: () => haptic.error(),
  })
```

Aggiungi nell'`onSuccess` callback:

```tsx
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      const conc = updated.concentration_save
      if (conc) {
        setAutoConcSave(conc)
        if (conc.lost_concentration) {
          toast.warning(t('character.hp.concentration_lost'), { duration: 4000 })
        }
      }
      // ... resto esistente
    },
```

- [ ] **Step 4: Remove manual TS panel JSX**

Individua il blocco JSX (around line 415-440) con:

```tsx
{concSaveResult && (...)}
```

e il form di input (se esiste) con damage input + "Tira salvezza" button. Elimina tutto.

- [ ] **Step 5: Add auto TS panel**

Nel punto del JSX dove prima c'era il panel manuale (o vicino alla sezione HP danni, ma DOPO la parte di input danno), aggiungi:

```tsx
{autoConcSave && (
  <Surface
    variant={autoConcSave.success ? 'flat' : 'ember'}
    ornamented={!autoConcSave.success}
    className="space-y-2 p-4"
  >
    <div className="flex items-center justify-between">
      <p className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim">
        🔮 {t('character.spells.concentration')} — DC {autoConcSave.dc}
      </p>
      <button
        type="button"
        onClick={() => setAutoConcSave(null)}
        className="text-xs underline text-dnd-text-muted hover:text-dnd-text"
      >
        {t('common.dismiss')}
      </button>
    </div>
    <p className="font-mono text-lg text-dnd-gold-bright">
      d20={autoConcSave.die} + {autoConcSave.bonus} = {autoConcSave.total}
    </p>
    <p className={`font-cinzel font-bold uppercase tracking-widest ${autoConcSave.success ? 'text-dnd-emerald-bright' : 'text-[var(--dnd-crimson-bright)]'}`}>
      {autoConcSave.success
        ? t('character.hp.save_success')
        : t('character.hp.save_fail')}
    </p>
    {autoConcSave.lost_concentration && (
      <p className="text-[var(--dnd-crimson-bright)] font-bold">
        {t('character.hp.concentration_lost')}
      </p>
    )}
  </Surface>
)}
```

- [ ] **Step 6: Verify no orphan imports**

Cerca:

```bash
grep -n "api.spells.concentrationSave\|concSaveMutation\|concSaveResult\|concDamageInput" /mnt/c/Users/Claudio/PycharmProjects/dnd_bot_revamped/webapp/src/pages/HP.tsx
```

Expected: no matches. Se ci sono, rimuovili.

- [ ] **Step 7: Commit**

```bash
git add webapp/src/pages/HP.tsx
git commit -m "feat(webapp): HP.tsx auto concentration save panel

Remove manual TS concentrazione UI (damage input + roll button)
and the concSaveMutation. Add autoConcSave state populated by
hpMutation.onSuccess when backend returns concentration_save.
Panel variants: flat/gold on success, ember/crimson on failure.
Dismissable via inline button. Toast on lost concentration.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: FE `Spells.tsx` — rimuovere TS manuale, aggiungere descrizione

**Files:**
- Modify: `webapp/src/pages/Spells.tsx`

- [ ] **Step 1: Remove manual TS mutation + state**

In `webapp/src/pages/Spells.tsx`, trova e rimuovi `concSaveMutation` (similar shape to HP.tsx), `concDamageInput` e `concSaveResult` useState.

- [ ] **Step 2: Remove manual TS panel JSX**

Trova il blocco JSX corrispondente (around line 294-330) che contiene damage input + save button + result panel. Elimina.

- [ ] **Step 3: Update active concentration section**

Individua (around line 221-245):

```tsx
{concentratingId && (
  <Surface ...>
    <div>
      <p>...concentration label...</p>
      {concentratingSpell && (
        <p ...>{concentratingSpell.name}</p>
      )}
    </div>
    <button onClick={() => concentrationMutation.mutate(null)}>
      ...stop concentration...
    </button>
  </Surface>
)}
```

Sostituisci con:

```tsx
{concentratingId && concentratingSpell && (
  <Surface variant="arcane" ornamented className="space-y-3 p-4">
    <div className="flex items-start justify-between gap-3">
      <div className="flex-1 min-w-0">
        <p className="text-[10px] font-cinzel uppercase tracking-[0.3em] text-dnd-gold-dim">
          {t('character.spells.concentration')}
        </p>
        <p className="text-lg font-display font-bold text-dnd-gold-bright truncate mt-1">
          {concentratingSpell.name}
        </p>
      </div>
      <Button
        variant="danger"
        size="sm"
        icon={<X size={14} />}
        onClick={() => concentrationMutation.mutate(null)}
        haptic="warning"
      >
        {t('character.spells.stop_concentration')}
      </Button>
    </div>
    {concentratingSpell.description && (
      <p className="text-sm text-dnd-text font-body leading-relaxed break-words">
        {concentratingSpell.description}
      </p>
    )}
  </Surface>
)}
```

Verifica imports per `Button`, `X` (lucide-react). Se mancano, aggiungili.

- [ ] **Step 4: Verify no orphan imports**

```bash
grep -n "api.spells.concentrationSave\|concSaveMutation\|concSaveResult\|concDamageInput" /mnt/c/Users/Claudio/PycharmProjects/dnd_bot_revamped/webapp/src/pages/Spells.tsx
```

Expected: no matches.

- [ ] **Step 5: Commit**

```bash
git add webapp/src/pages/Spells.tsx
git commit -m "feat(webapp): Spells.tsx simplified concentration section

Remove manual TS UI (damage input + save button + result panel).
Active concentration card now shows spell name + description;
stop button becomes distinct danger variant with X icon to stand
out from other action buttons on the page.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: i18n keys

**Files:**
- Modify: `webapp/src/locales/it.json`
- Modify: `webapp/src/locales/en.json`

- [ ] **Step 1: Verify `common.dismiss` key**

```bash
grep -n '"dismiss"' /mnt/c/Users/Claudio/PycharmProjects/dnd_bot_revamped/webapp/src/locales/it.json
```

Se esiste, annota il valore corrente (skip Step 3 per `common.dismiss`).

- [ ] **Step 2: Add keys to `it.json`**

Individua il blocco `character.hp`. Aggiungi in fondo (prima della chiusura `}`):

```json
"concentration_lost": "Concentrazione persa!",
"save_success": "Successo",
"save_fail": "Fallimento"
```

(Attenzione alla virgola di separazione dopo l'ultima chiave esistente.)

- [ ] **Step 3: Add `common.dismiss` in `it.json` if missing**

Se grep precedente non ha trovato `dismiss`, aggiungi in `common`:

```json
"dismiss": "Chiudi"
```

- [ ] **Step 4: Same in `en.json`**

Aggiungi sotto `character.hp`:

```json
"concentration_lost": "Concentration lost!",
"save_success": "Success",
"save_fail": "Failure"
```

E se `common.dismiss` manca:

```json
"dismiss": "Dismiss"
```

- [ ] **Step 5: Validate JSON**

```bash
python3 -c "import json; json.load(open('webapp/src/locales/it.json')); json.load(open('webapp/src/locales/en.json')); print('ok')"
```

Expected: `ok`.

- [ ] **Step 6: Commit**

```bash
git add webapp/src/locales/it.json webapp/src/locales/en.json
git commit -m "feat(webapp): i18n keys for Gruppo C concentration panel

character.hp: concentration_lost, save_success, save_fail.
common.dismiss if not already present.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: Manual verification (user)

**Files:** none.

L'utente esegue stack locale (Windows).

- [ ] **Step 1: Start stack**

Terminal 1:
```bash
uv run uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```
Terminal 2:
```bash
cd webapp && npm run dev
```

Open `http://localhost:5173/`.

- [ ] **Step 2: Scenario 1 — char concentra spell, damage moderato**

Crea/apri personaggio. Vai su `/spells`, avvia concentrazione su uno spell con description (es. Bless). Vai su `/hp`, applica DAMAGE 10. Expected: HP scende, panel TS compare con d20+CON vs DC 10. Success → panel gold, concentrazione mantenuta (toast "Concentration active" resta). Fail → panel crimson, toast "Concentrazione persa!", sezione concentration attiva in `/spells` scompare.

- [ ] **Step 3: Scenario 2 — char non concentra**

DAMAGE 10 senza concentrazione. Expected: HP scende, panel TS assente.

- [ ] **Step 4: Scenario 3 — damage enorme HP→0**

DAMAGE che porta HP a 0. Expected: HP=0, `concentrating_spell_id` cleared, **no panel TS**, history entry "Danni: -X HP" + possibile entry death save flow.

- [ ] **Step 5: Scenario 4 — TEMP HP assorbe tutto**

Setta temp_hp 15, applica DAMAGE 10. Temp scende a 5, HP invariato. Expected: panel TS comunque compare (DC based su body.value=10).

- [ ] **Step 6: Scenario 5 — Spells.tsx sezione concentrazione**

Concentra su spell con description. Vai su `/spells`. Expected: sezione mostra nome + description + bottone Stop (danger variant). Nessun damage input, nessun save button.

- [ ] **Step 7: Scenario 6 — Nat20 / Nat1**

Ripetere DAMAGE finché nat20 (auto-success) e nat1 (auto-fail, concentrazione persa). Verifica `is_critical` / `is_fumble` indicators se presenti nel panel.

- [ ] **Step 8: Segna esito**

Se tutti passano: task completato. Se uno fallisce: ritorno al task corrispondente (5 per backend, 7 per HP.tsx, 8 per Spells.tsx).

---

### Task 11: `npm run build:prod` + PR

**Files:**
- Modify: `docs/app/`

- [ ] **Step 1: Build**

Windows shell:

```bash
cd webapp
npm run build:prod
```

Expected: script completes without errors, `docs/app/` rebuilt + staged.

- [ ] **Step 2: Commit build output**

```bash
git commit -m "chore(webapp): rebuild docs/app for Gruppo C"
```

- [ ] **Step 3: Push branch**

```bash
git push -u origin feat/concentration-gruppo-c
```

- [ ] **Step 4: Open PR**

```bash
gh pr create --title "feat: Gruppo C — rework concentrazione (auto-TS)" --body "$(cat <<'EOF'
## Summary
- Backend: `roll_concentration_save` helper condiviso in `api/routers/_helpers.py`. `/concentration/save` diventa wrapper; `/hp` op DAMAGE auto-triggera TS quando char concentrato e HP>0 post-damage.
- Schema: `ConcentrationSaveResult` promosso in `api/schemas/common.py`; `CharacterFull.concentration_save` opzionale transient.
- Frontend: HP.tsx rimuove TS manuale, aggiunge panel auto-triggered; Spells.tsx rimuove TS manuale, aggiunge descrizione spell nella sezione concentrazione attiva.
- i18n: +3 chiavi `character.hp.*` + eventuale `common.dismiss`.

Spec: `docs/superpowers/specs/2026-04-23-concentration-design.md`.
Plan: `docs/superpowers/plans/2026-04-23-concentration.md`.
Roadmap: `istruzioni.md` §1.4 + §1.5.

## Test plan
- [x] Char concentrato, DAMAGE moderato → panel TS compare, outcome corretto.
- [x] Char non concentrato → no panel.
- [x] DAMAGE → HP=0 → no panel, concentrazione cleared.
- [x] TEMP HP assorbe tutto → TS comunque triggered (DC based su body.value).
- [x] Spells.tsx: sezione concentrazione mostra name + description, nessun damage input.
- [x] Nat20 / Nat1 edge cases.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 5: Post-merge roadmap update**

Dopo merge, in nuova sessione o commit:
- Tabella Gruppo C: `⬜ Pending` → `✅ Done (PR #<n> merged → main)`.
- Sezione `## Gruppo C`: `⬜` → `✅`.
- Ordine consigliato: `→ C →` diventa `→ ✅ C →`.

---

## Verifica completa

Dopo tutti i task:
- [ ] 11 commit su `feat/concentration-gruppo-c`.
- [ ] Verifica manuale superata.
- [ ] `docs/app/` rebuildato e committato.
- [ ] PR aperta / mergeata.
- [ ] Roadmap aggiornato post-merge.
