# Character Mechanics (Gruppo B) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aggiungere auto-HP alla creazione e al level-up, modificatori ability sugli oggetti inventario (assoluto+relativo con stacking), roll damage degli incantesimi con casting level+critico, e rewrite del click sugli spell slot (visual invertito + click simmetrico).

**Architecture:** Backend — nuovo modulo `core/game/stats.py` con funzioni pure (HP per livello, stacking ability), estensioni a 5 router API esistenti + nuovo endpoint `roll_damage` e `hp/recalc`. Frontend — nuovo componente `AbilityModifiersEditor`, nuovo sheet `SpellDamageSheet`, rewrite di `SpellSlots.tsx`, estensione di `Settings.tsx`, integrazione toast "+N HP" al level-up.

**Tech Stack:** Python 3.13 + FastAPI + SQLAlchemy 2 async + Pydantic v2 (backend), React 18.3 + Vite 5.4 + TypeScript 5.5 + TanStack Query + framer-motion + sonner + lucide-react (frontend).

**Testing approach:** Il repo non ha test suite. Ogni task di backend verifica via `python3 -c "import ast; ast.parse(open('<path>').read())"` (syntax check) o `python3 -c "import ...module"` quando possibile senza venv. La verifica runtime del backend richiede di chiedere all'utente (Windows/PowerShell) — il .venv non funziona da WSL. Ogni task di frontend verifica via `npx tsc --noEmit` (funziona da WSL). Verifica end-to-end manuale in Task 17.

**Branch:** `feat/character-mechanics-gruppo-b` (già creata da main post-merge Gruppo A).

**Spec di riferimento:** `docs/superpowers/specs/2026-04-23-character-mechanics-design.md`

---

## File map

**Creati:**
- `core/game/__init__.py` — (se non esiste) package init.
- `core/game/stats.py` — funzioni pure: `hit_points_for_level`, `total_base_hp`, `effective_ability_score`, `AppliedModifier` dataclass.
- `webapp/src/pages/inventory/AbilityModifiersEditor.tsx` — componente form per modificatori ability.
- `webapp/src/pages/spells/SpellDamageSheet.tsx` — bottom sheet per roll damage.
- `webapp/src/pages/spells/AbilityBreakdown.tsx` — breakdown espandibile per Stats page.

**Modificati:**
- `api/schemas/common.py` — estende `AbilityScoreRead` con `base_value`, `modifiers_applied`.
- `api/schemas/item.py` — valida `ability_modifiers` nel metadata.
- `api/schemas/character.py` — estende `CharacterCreate` con `first_class` opzionale; `XPUpdateResult` con `hp_gained`.
- `api/schemas/spell.py` — aggiunge `RollDamageRequest` e `RollDamageResult` + risposta.
- `api/routers/characters.py` — hook CON change in `update_ability_score`; response con `modifiers_applied`; nuovo endpoint `/hp/recalc`.
- `api/routers/classes.py` — bootstrap auto-HP per first class.
- `api/routers/items.py` — hook su equip/unequip / ability_modifiers change.
- `api/routers/spells.py` — nuovo endpoint `POST /spells/{id}/roll_damage`.
- `api/routers/hp.py` — (opzionale, se roll_damage aggiorna rolls_history) registra evento.
- `api/routers/dice.py` — (nessuna modifica, `_roll_dice` è già riutilizzabile).
- `webapp/src/types/index.ts` — estende `AbilityScore`, `Item` metadata shape; nuovi tipi `RollDamageRequest`, `RollDamageResult`.
- `webapp/src/api/client.ts` — nuovi wrapper: `api.spells.rollDamage`, `api.characters.recalcHp`, `api.characters.updateSettings` (se manca).
- `webapp/src/pages/Inventory.tsx` — integrazione editor modificatori nel form.
- `webapp/src/pages/inventory/ItemForm.tsx` — renderizza `AbilityModifiersEditor`.
- `webapp/src/pages/inventory/itemMetadata.ts` — build/parse `ability_modifiers`.
- `webapp/src/pages/AbilityScores.tsx` — mostra breakdown per ability.
- `webapp/src/pages/spells/SpellItem.tsx` — aggiunge bottone "Roll Damage".
- `webapp/src/pages/Spells.tsx` — wire-up `SpellDamageSheet` aperto da `SpellItem`.
- `webapp/src/pages/SpellSlots.tsx` — rewrite click handler + visual invertito.
- `webapp/src/pages/Settings.tsx` — aggiunge sezione "HP formula" con toggle + recalc button.
- `webapp/src/pages/Experience.tsx` — toast "+N HP" quando mutazione XP ritorna `hp_gained > 0`.
- `webapp/src/locales/it.json` + `en.json` — nuove chiavi.
- `docs/app/**` — rebuild finale.

---

## Task 1 — Compute layer `core/game/stats.py`

**Files:**
- Create: `core/game/__init__.py` (se non esiste)
- Create: `core/game/stats.py`

- [ ] **Step 1: Verifica se la directory `core/game/` esiste**

```bash
ls core/game/ 2>/dev/null || echo "MISSING"
```
Se stampa `MISSING`, crea la directory e il file `__init__.py`:

```bash
mkdir -p core/game && touch core/game/__init__.py
```

- [ ] **Step 2: Crea `core/game/stats.py`**

Contenuto esatto:

```python
"""Pure compute functions for D&D 5e character mechanics.

No side effects, no database access. Safe to unit-test in isolation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal


ABILITY_NAMES = (
    "strength",
    "dexterity",
    "constitution",
    "intelligence",
    "wisdom",
    "charisma",
)

ModifierKind = Literal["absolute", "relative"]


@dataclass(frozen=True)
class AppliedModifier:
    """A single ability modifier applied from an equipped item.

    Used for response breakdown on the frontend (Stats page).
    """
    source: str          # item name
    ability: str         # one of ABILITY_NAMES
    kind: ModifierKind
    value: int
    item_id: int


def hit_points_for_level(hit_die: int, con_mod: int, level: int) -> int:
    """HP gained for a single level-up event.

    Level 1: ``hit_die + con_mod`` (PHB max die value).
    Level 2+: ``(hit_die // 2 + 1) + con_mod`` (fixed method).

    The result is always clamped to a minimum of 1 (PHB rule:
    a level gives at least 1 HP even with very negative CON).
    """
    if level < 1:
        raise ValueError(f"level must be >= 1, got {level}")
    if hit_die <= 0:
        raise ValueError(f"hit_die must be > 0, got {hit_die}")

    if level == 1:
        raw = hit_die + con_mod
    else:
        raw = (hit_die // 2 + 1) + con_mod

    return max(1, raw)


def total_base_hp(
    classes: "Iterable[_ClassLike]",
    con_mod: int,
) -> int:
    """Sum of HP across every level of every class.

    The 'first class' (lowest id, i.e. DB insertion order) owns the
    character's level-1 slot and uses the level-1 formula.
    All other levels (including level 1 of any additional multiclass)
    use the level 2+ formula.

    Returns 0 if classes is empty.
    """
    sorted_classes = sorted(classes, key=lambda c: c.id)
    if not sorted_classes:
        return 0

    total = 0
    first_level_consumed = False

    for cls in sorted_classes:
        for level_within_class in range(1, cls.level + 1):
            if not first_level_consumed:
                total += hit_points_for_level(cls.hit_die, con_mod, 1)
                first_level_consumed = True
            else:
                total += hit_points_for_level(cls.hit_die, con_mod, 2)

    return total


def effective_ability_score(
    ability_name: str,
    base_value: int,
    equipped_items: "Iterable[_ItemLike]",
) -> tuple[int, list[AppliedModifier]]:
    """Compute the effective ability score after equipped-item modifiers.

    Stacking rule:
      - Sum of all *relative* modifiers for this ability
      - Max of all *absolute* modifiers for this ability (if any)
      - Final = max(base + sum(rel), max(abs)) if any absolute exists,
                else base + sum(rel)

    No cap applied (homebrew-friendly).

    Returns (effective_value, list_of_applied_modifiers_for_breakdown).
    """
    if ability_name not in ABILITY_NAMES:
        raise ValueError(f"unknown ability: {ability_name}")

    applied: list[AppliedModifier] = []
    relative_sum = 0
    absolutes: list[int] = []

    for item in equipped_items:
        mods = _extract_ability_modifiers(item)
        for mod in mods:
            if mod.get("ability") != ability_name:
                continue
            kind = mod.get("kind")
            value = mod.get("value")
            if not isinstance(value, int):
                continue
            if kind == "relative":
                relative_sum += value
                applied.append(AppliedModifier(
                    source=item.name,
                    ability=ability_name,
                    kind="relative",
                    value=value,
                    item_id=item.id,
                ))
            elif kind == "absolute":
                absolutes.append(value)
                applied.append(AppliedModifier(
                    source=item.name,
                    ability=ability_name,
                    kind="absolute",
                    value=value,
                    item_id=item.id,
                ))

    base_plus_rel = base_value + relative_sum
    if absolutes:
        effective = max(base_plus_rel, max(absolutes))
    else:
        effective = base_plus_rel

    return effective, applied


def _extract_ability_modifiers(item: "_ItemLike") -> list[dict]:
    """Read `ability_modifiers` from an item's metadata (parsed JSON).

    Defensive: returns empty list on any parse / structure error.
    """
    import json as _json

    raw = item.item_metadata
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            parsed = _json.loads(raw)
        except (ValueError, TypeError):
            return []
    else:
        parsed = raw

    if not isinstance(parsed, dict):
        return []
    mods = parsed.get("ability_modifiers")
    if not isinstance(mods, list):
        return []
    return [m for m in mods if isinstance(m, dict)]


# --- Structural typing (Protocol-like) ----------------------------------
# We intentionally avoid `Protocol` here so the module stays dependency-free
# and does not require importing SQLAlchemy models. Callers pass in anything
# with matching attribute shape.

class _ClassLike:
    id: int
    level: int
    hit_die: int


class _ItemLike:
    id: int
    name: str
    item_metadata: str | dict | None
```

- [ ] **Step 3: Verifica sintassi + import**

```bash
python3 -c "import ast; ast.parse(open('core/game/stats.py').read()); print('syntax ok')"
python3 -c "import sys; sys.path.insert(0, '.'); import core.game.stats as s; print('import ok', s.ABILITY_NAMES)"
```

Expected output:
```
syntax ok
import ok ('strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma')
```

Se il secondo comando fallisce con `ModuleNotFoundError: No module named 'core'`, usa:
```bash
python3 -c "
import sys
sys.path.insert(0, '.')
from core.game import stats
assert stats.hit_points_for_level(8, 2, 1) == 10
assert stats.hit_points_for_level(8, 2, 2) == 7
assert stats.hit_points_for_level(8, -10, 2) == 1, 'floor clamp'
print('functional checks ok')
"
```

Expected: `functional checks ok`.

- [ ] **Step 4: Commit**

```bash
git add core/game/__init__.py core/game/stats.py
git commit -m "feat(core): add character stats compute layer (pure functions)

Modulo core/game/stats.py con funzioni pure per:
- hit_points_for_level(hit_die, con_mod, level) — formula D&D 5e fixed
  (livello 1 = HD_max + CON_mod; livello 2+ = (HD/2 + 1) + CON_mod),
  clampato a minimo 1 per livello.
- total_base_hp(classes, con_mod) — somma HP per tutti i livelli di
  tutte le classi; la first class (lowest id) possiede il livello 1.
- effective_ability_score(ability, base, equipped_items) — stacking
  rule: relativi sommano, assoluti prendono il max, finale = max(base
  + sum(rel), max(abs) se presenti). Ritorna anche breakdown per UI.
- AppliedModifier dataclass per la response breakdown.

Nessuna dipendenza da SQLAlchemy; funzioni pure isolabili per future
unit test.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2 — `AbilityScoreRead` response extension

**Files:**
- Modify: `api/schemas/common.py`
- Modify: `api/routers/characters.py` (se la response è costruita manualmente in qualche endpoint)

- [ ] **Step 1: Leggi `api/schemas/common.py` per vedere la struttura attuale**

```bash
grep -n "AbilityScoreRead" api/schemas/common.py
```

Il modello attuale (righe ~15-21):
```python
class AbilityScoreRead(BaseModel):
    id: int
    name: str
    value: int
    modifier: int
    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Estendi lo schema**

Applica un edit sul blocco `class AbilityScoreRead(BaseModel):` sostituendolo con:

```python
class AppliedModifierRead(BaseModel):
    """A single equipped-item modifier applied to an ability score."""
    source: str
    ability: str
    kind: str  # "absolute" | "relative"
    value: int
    item_id: int
    model_config = {"from_attributes": True}


class AbilityScoreRead(BaseModel):
    id: int
    name: str
    value: int           # effective value (after equipped-item modifiers)
    base_value: int      # raw value stored on AbilityScore row
    modifier: int        # derived from effective value
    modifiers_applied: list[AppliedModifierRead] = []
    model_config = {"from_attributes": True}
```

- [ ] **Step 3: Aggiungi un resolver per `value` / `base_value` / `modifiers_applied`**

Il modello SQLAlchemy `AbilityScore` ha `value` (il valore base) e `modifier` (computed). Dobbiamo far sì che la response ritorni:
- `base_value` = il campo DB
- `value` = effective (base + equipped modifiers)
- `modifier` = derivato da effective
- `modifiers_applied` = lista AppliedModifier

Siccome `from_attributes=True` chiama direttamente gli attributi del modello, serve un resolver. Aggiungi in `api/schemas/common.py` (sopra `AbilityScoreRead`):

```python
from pydantic import model_validator
from typing import Any


def _resolve_ability_effective(ability_obj: Any, equipped_items: list[Any]) -> dict:
    """Build response payload for a single AbilityScore given equipped items.

    Imports stats lazily to avoid circular imports.
    """
    from core.game.stats import effective_ability_score

    base_value = ability_obj.value
    effective, applied = effective_ability_score(
        ability_obj.name,
        base_value,
        equipped_items,
    )
    return {
        "id": ability_obj.id,
        "name": ability_obj.name,
        "value": effective,
        "base_value": base_value,
        "modifier": (effective - 10) // 2,
        "modifiers_applied": [
            {
                "source": m.source,
                "ability": m.ability,
                "kind": m.kind,
                "value": m.value,
                "item_id": m.item_id,
            }
            for m in applied
        ],
    }
```

- [ ] **Step 4: Trova dove `CharacterFull` viene costruito e wire `_resolve_ability_effective`**

```bash
grep -rn "ability_scores" api/schemas/ api/routers/ | grep -v ".pyc"
```

Il punto di serializzazione del `CharacterFull` usa `from_attributes=True`. Per iniettare i `modifiers_applied` abbiamo due opzioni:
- (a) Build manuale del dict prima di `CharacterFull(**data)`.
- (b) Pydantic `model_validator(mode="before")` su `CharacterFull` che rimappa `ability_scores`.

**Scelta:** (b) per consistency.

In `api/schemas/character.py` (il file che definisce `CharacterFull`), trova la classe `CharacterFull` e aggiungi un model_validator:

```python
@model_validator(mode="before")
@classmethod
def _resolve_abilities(cls, data: Any) -> Any:
    """Resolve each AbilityScore to include effective value + modifiers_applied."""
    if not hasattr(data, "ability_scores"):
        return data
    equipped = [i for i in getattr(data, "items", []) if i.is_equipped]
    raw_abilities = list(data.ability_scores)
    # Mutate data.ability_scores in place via a resolved list on a dict copy
    # so Pydantic still gets AbilityScoreRead via from_attributes path.
    from api.schemas.common import _resolve_ability_effective
    resolved = [_resolve_ability_effective(a, equipped) for a in raw_abilities]
    # Return a modified structure
    if isinstance(data, dict):
        data["ability_scores"] = resolved
        return data
    # ORM object — Pydantic v2 supports attribute proxies; we convert manually
    as_dict = {k: getattr(data, k) for k in data.__dict__.keys() if not k.startswith("_")}
    as_dict["ability_scores"] = resolved
    return as_dict
```

**Nota al sub-agent**: questo resolver può collidere con altri validator esistenti in `CharacterFull`. Leggi il file intero prima di applicare; se ci sono già `model_validator(mode="before")` combina il codice. Se scopri che la serializzazione passa altrove (es. manualmente costruita in ogni endpoint), preferisci build manuale nel router di helper `_serialize_character()`.

- [ ] **Step 5: Verifica sintassi**

```bash
python3 -c "import ast; ast.parse(open('api/schemas/common.py').read()); print('ok common')"
python3 -c "import ast; ast.parse(open('api/schemas/character.py').read()); print('ok character')"
```

- [ ] **Step 6: Commit**

```bash
git add api/schemas/common.py api/schemas/character.py
git commit -m "feat(api): extend AbilityScoreRead with base_value + modifiers_applied

- Nuovo AppliedModifierRead schema per breakdown per-item.
- AbilityScoreRead ora include base_value (DB raw) + value (effective
  con modificatori equipped) + modifiers_applied (lista).
- CharacterFull model_validator risolve le ability_scores lazy-leggendo
  gli items equipped e invocando core.game.stats.effective_ability_score.
- Backward compatible: clients vecchi usano solo value/modifier, il
  resto sono campi opzionali.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3 — Item metadata `ability_modifiers` validation

**Files:**
- Modify: `api/schemas/item.py`

- [ ] **Step 1: Leggi lo schema ItemRead + ItemCreate/Update**

```bash
grep -n "ItemRead\|ItemCreate\|ItemUpdate\|ability_modifiers\|item_metadata" api/schemas/item.py | head -30
```

- [ ] **Step 2: Aggiungi validazione in `api/schemas/item.py`**

In cima al file (dopo gli altri import), aggiungi:

```python
_ALLOWED_ABILITIES = {
    "strength", "dexterity", "constitution",
    "intelligence", "wisdom", "charisma",
}
_ALLOWED_KINDS = {"absolute", "relative"}


def _validate_ability_modifiers(mods: Any) -> list[dict]:
    """Normalize and validate item_metadata.ability_modifiers array.

    Raises ValueError with descriptive message on invalid entry.
    Silently strips malformed-but-non-fatal entries (missing keys).
    """
    if mods is None:
        return []
    if not isinstance(mods, list):
        raise ValueError("ability_modifiers must be an array")
    result: list[dict] = []
    for i, m in enumerate(mods):
        if not isinstance(m, dict):
            raise ValueError(f"ability_modifiers[{i}] must be an object")
        ability = m.get("ability")
        kind = m.get("kind")
        value = m.get("value")
        if ability not in _ALLOWED_ABILITIES:
            raise ValueError(
                f"ability_modifiers[{i}].ability must be one of "
                f"{sorted(_ALLOWED_ABILITIES)}, got {ability!r}"
            )
        if kind not in _ALLOWED_KINDS:
            raise ValueError(
                f"ability_modifiers[{i}].kind must be 'absolute' or "
                f"'relative', got {kind!r}"
            )
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(
                f"ability_modifiers[{i}].value must be an integer, "
                f"got {type(value).__name__}"
            )
        result.append({"ability": ability, "kind": kind, "value": value})
    return result
```

- [ ] **Step 3: Integra la validazione nel path di scrittura metadata**

Trova lo schema che accetta `item_metadata` in input (`ItemCreate` e/o `ItemUpdate`). Aggiungi un `@field_validator` che invoca `_validate_ability_modifiers` se presente:

```python
from pydantic import field_validator


class ItemUpdate(BaseModel):
    # ... existing fields ...

    @field_validator("item_metadata", mode="after")
    @classmethod
    def validate_ability_mods(cls, v: Any) -> Any:
        if isinstance(v, dict) and "ability_modifiers" in v:
            v["ability_modifiers"] = _validate_ability_modifiers(v["ability_modifiers"])
        return v


class ItemCreate(BaseModel):
    # ... existing fields ...

    @field_validator("item_metadata", mode="after")
    @classmethod
    def validate_ability_mods(cls, v: Any) -> Any:
        if isinstance(v, dict) and "ability_modifiers" in v:
            v["ability_modifiers"] = _validate_ability_modifiers(v["ability_modifiers"])
        return v
```

- [ ] **Step 4: Verifica sintassi**

```bash
python3 -c "import ast; ast.parse(open('api/schemas/item.py').read()); print('ok')"
```

- [ ] **Step 5: Commit**

```bash
git add api/schemas/item.py
git commit -m "feat(api): validate item_metadata.ability_modifiers schema

Aggiunto validator su ItemCreate e ItemUpdate per:
- ability: deve essere uno dei 6 ability slug validi
- kind: 'absolute' o 'relative'
- value: intero (rifiuta bool, float, stringhe)

Errori di validazione emettono 422 con messaggio descrittivo del
campo che ha fallito. Entry malformate rifiutate hard, non silenziate.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4 — Item equip/unequip: hook HP su CON

**Files:**
- Modify: `api/routers/items.py`

- [ ] **Step 1: Leggi il range 129-174 di `api/routers/items.py`**

```bash
sed -n '125,180p' api/routers/items.py
```

Questo è il block `update_item` che già gestisce equip/unequip di armor/shield (righe 152-171).

- [ ] **Step 2: Aggiungi helper `_recompute_hp_for_con_change` in cima al file**

Dopo gli import esistenti in `api/routers/items.py`:

```python
from core.game.stats import effective_ability_score


async def _snapshot_effective_con_mod(char) -> int:
    """Compute current effective CON modifier from equipped items."""
    con_row = next((a for a in char.ability_scores if a.name == "constitution"), None)
    if con_row is None:
        return 0
    eq_items = [i for i in char.items if i.is_equipped]
    effective, _ = effective_ability_score("constitution", con_row.value, eq_items)
    return (effective - 10) // 2


def _apply_hp_delta(char, delta_hp: int) -> None:
    """Apply an integer HP delta to both max and current, floor current at 0."""
    if delta_hp == 0:
        return
    char.hit_points = max(0, char.hit_points + delta_hp)
    char.current_hit_points = max(0, min(char.current_hit_points + delta_hp, char.hit_points))
```

- [ ] **Step 3: Estendi `update_item` con snapshot pre/post**

Nel corpo di `update_item`, prima di applicare le modifiche a `item` (subito dopo aver recuperato `item` e `char`), snapshot:

```python
    old_con_mod = await _snapshot_effective_con_mod(char)
```

Poi, dopo aver applicato tutte le modifiche al `item` e aver commesso la transazione parziale (o appena prima del commit finale), calcola di nuovo e applica il delta:

```python
    # After updating item fields, recompute effective CON mod
    new_con_mod = await _snapshot_effective_con_mod(char)
    delta = new_con_mod - old_con_mod
    if delta != 0:
        # Respect settings.hp_auto_calc flag (default True if unset)
        settings = char.settings or {}
        if settings.get("hp_auto_calc", True):
            _apply_hp_delta(char, delta * char.total_level)
```

**Nota al sub-agent**: il flusso esatto dipende da come `update_item` struttura i commit. Se usa `await session.commit()` a fine funzione con più `session.add(...)` intermedi, basta piazzare lo snapshot-post + delta prima del commit finale. Se usa `await session.flush()` dopo l'update, piazzalo dopo il flush.

- [ ] **Step 4: Verifica sintassi**

```bash
python3 -c "import ast; ast.parse(open('api/routers/items.py').read()); print('ok')"
```

- [ ] **Step 5: Commit**

```bash
git add api/routers/items.py
git commit -m "feat(api): auto-recompute HP when equipping/unequipping CON-affecting items

In PATCH /items/{id}:
- Snapshot CON modifier effettivo (base + equipped items) prima della
  modifica.
- Post-modifica, se il delta_mod è != 0, applica delta * total_level
  a max_hp e current_hp (clamp current >= 0 e <= new max).
- Rispetta il flag character.settings.hp_auto_calc (default True).

Pattern consistente con il recompute AC già esistente per armor/shield.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5 — `POST /classes`: auto-HP bootstrap per first class

**Files:**
- Modify: `api/routers/classes.py`

- [ ] **Step 1: Leggi range 73-107 di `api/routers/classes.py`**

```bash
sed -n '70,115p' api/routers/classes.py
```

- [ ] **Step 2: Modifica `add_class` per auto-HP**

Dopo aver creato la CharacterClass row e prima del commit finale (o appena dopo il `session.add(new_class)`), aggiungi:

```python
from core.game.stats import hit_points_for_level


async def add_class(...):
    # ... existing logic: load char, create new_class, add to session ...

    # Auto-HP bootstrap: solo se è la PRIMA classe e HP sono ancora a 0
    is_first_class = len(char.classes) == 0  # before adding new_class
    # Il flag settings.hp_auto_calc gate l'automazione (default True)
    settings = char.settings or {}
    auto_calc = settings.get("hp_auto_calc", True)

    if is_first_class and char.hit_points == 0 and auto_calc:
        con_row = next((a for a in char.ability_scores if a.name == "constitution"), None)
        con_mod = (con_row.value - 10) // 2 if con_row else 0
        hp = hit_points_for_level(new_class.hit_die or 8, con_mod, 1)
        char.hit_points = hp
        char.current_hit_points = hp

    # ... existing commit / return ...
```

**Nota al sub-agent**: l'ordinamento corretto dipende dal codice esistente. Se `len(char.classes)` viene valutato DOPO aver aggiunto `new_class` alla collection, usa `len(char.classes) == 1` invece. Leggi il file per stabilire l'ordine.

Se `new_class.hit_die` è `None` (classe custom senza hit_die), usa un fallback sensato — la spec dice di rifiutare `hit_die` invalido, ma qui stiamo sul path di auto-HP. Se `None`, **salta** il bootstrap (non fare assunzioni):

```python
    if is_first_class and char.hit_points == 0 and auto_calc and new_class.hit_die:
        # ...
```

- [ ] **Step 3: Verifica sintassi**

```bash
python3 -c "import ast; ast.parse(open('api/routers/classes.py').read()); print('ok')"
```

- [ ] **Step 4: Commit**

```bash
git add api/routers/classes.py
git commit -m "feat(api): auto-HP bootstrap on first class add

In POST /characters/{id}/classes:
- Se la classe appena aggiunta è la prima (char non aveva classes) E
  HP correnti sono 0 E settings.hp_auto_calc è True E hit_die è
  definito → imposta char.hit_points = hit_points_for_level(
  hit_die, con_mod, 1) e current uguale al max.
- Il successivo cambio di CON (o equip di item CON-affecting) applicherà
  il delta retroattivo.

Scope: solo bootstrap single-class. Multiclassing manuale NON trigga
auto-HP (fuori scope per Gruppo B — Gruppo G gestirà multiclass
level-up flow).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6 — `PATCH /xp`: auto-HP al level-up

**Files:**
- Modify: `api/routers/characters.py`
- Modify: `api/schemas/character.py` (aggiunta `hp_gained` nella response opzionale)

- [ ] **Step 1: Leggi range 317-342 di `api/routers/characters.py`**

```bash
sed -n '310,350p' api/routers/characters.py
```

Questo è il blocco `update_xp` che già sincronizza `CharacterClass.level` al level XP-derivato.

- [ ] **Step 2: Modifica `update_xp` per calcolare hp_gained**

Prima che il livello venga aggiornato (riga ~333), snapshot `old_level`. Dopo l'update, calcola il delta HP per ciascun livello guadagnato e accumula:

```python
from core.game.stats import hit_points_for_level


async def update_xp(char_id, body, user_id, session):
    # ... existing: load char, compute new xp, derive new target level ...

    settings = char.settings or {}
    auto_calc = settings.get("hp_auto_calc", True)

    total_hp_gained = 0

    for cls in char.classes:  # single-class: only one iteration
        old_cls_level = cls.level
        new_cls_level = xp_to_level(char.experience_points)  # existing helper

        if new_cls_level > old_cls_level:
            cls.level = new_cls_level
            # update_resources_for_level(...)  # existing call
            if auto_calc and cls.hit_die:
                con_row = next((a for a in char.ability_scores if a.name == "constitution"), None)
                con_mod = (con_row.value - 10) // 2 if con_row else 0
                for lvl in range(old_cls_level + 1, new_cls_level + 1):
                    # lvl == 1 → use level-1 formula only if this is the first class AND this is character's level-1;
                    # but on an XP update we're never at level 1 (level-1 HP already set at char creation).
                    # So safe to always use level 2+ formula here.
                    hp = hit_points_for_level(cls.hit_die, con_mod, max(2, lvl))
                    total_hp_gained += hp

    if total_hp_gained > 0:
        char.hit_points += total_hp_gained
        char.current_hit_points += total_hp_gained

    # ... existing commit + return ...
```

- [ ] **Step 3: Estendi la response con `hp_gained`**

La response attuale è `Character` (via `CharacterFull`). Invece di cambiare il tipo di ritorno (breaking change), aggiungi un campo opzionale nel character schema e lo setta la funzione:

In `api/schemas/character.py`, alla definizione di `CharacterFull`, aggiungi:

```python
class CharacterFull(CharacterSummary):
    # ... existing fields ...
    hp_gained: int | None = None  # populated only by /xp response on level-up
```

Poi in `update_xp`, prima del return:

```python
    result = CharacterFull.model_validate(char)
    if total_hp_gained > 0:
        result.hp_gained = total_hp_gained
    return result
```

**Nota al sub-agent**: se la response corrente usa `from_attributes=True` con un altro pattern di costruzione, adatta — l'idea è solo aggiungere un campo opzionale al JSON ritornato.

- [ ] **Step 4: Verifica sintassi**

```bash
python3 -c "import ast; ast.parse(open('api/routers/characters.py').read()); print('ok chars')"
python3 -c "import ast; ast.parse(open('api/schemas/character.py').read()); print('ok schema')"
```

- [ ] **Step 5: Commit**

```bash
git add api/routers/characters.py api/schemas/character.py
git commit -m "feat(api): auto-HP increment on XP level-up

In PATCH /characters/{id}/xp:
- Quando il livello della classe incrementa (single-class auto-sync),
  calcola HP guadagnati via hit_points_for_level per ciascun livello
  nuovo (formula level 2+).
- Aggiorna char.hit_points e char.current_hit_points.
- Ritorna hp_gained nella response (campo opzionale di CharacterFull)
  per permettere al frontend di mostrare un toast.
- Rispetta settings.hp_auto_calc (default True); se False, nessun
  cambio HP al level-up.

Multi-level in un'unica mutazione (es. +10000 XP oltre 2 soglie):
hp_gained è la somma di tutti i livelli saliti.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7 — `PATCH /ability_scores/{ability}`: CON change hook

**Files:**
- Modify: `api/routers/characters.py`

- [ ] **Step 1: Trova l'endpoint `update_ability_score`**

```bash
grep -n "ability_score\|update_ability\|PATCH.*ability" api/routers/characters.py | head -10
```

- [ ] **Step 2: Modifica `update_ability_score` per il hook CON**

Dopo aver aggiornato il valore dell'ability row, se è `constitution`, calcola delta_mod e applica a HP. Riutilizza i helper di Task 4 (`_snapshot_effective_con_mod`):

```python
async def update_ability_score(char_id, ability, body, user_id, session):
    # ... existing: load char, find ability row ...

    settings = char.settings or {}
    auto_calc = settings.get("hp_auto_calc", True)

    is_constitution = ability == "constitution"
    old_con_mod = 0
    if is_constitution and auto_calc:
        # Snapshot con equipped items BEFORE the change
        old_con_mod = await _snapshot_effective_con_mod_for_char(char)

    # Apply value change (existing logic)
    ability_row.value = body.value

    if is_constitution and auto_calc:
        new_con_mod = await _snapshot_effective_con_mod_for_char(char)
        delta = new_con_mod - old_con_mod
        if delta != 0:
            char.hit_points = max(0, char.hit_points + delta * char.total_level)
            char.current_hit_points = max(
                0,
                min(char.current_hit_points + delta * char.total_level, char.hit_points),
            )

    # ... commit + return ...
```

Siccome `_snapshot_effective_con_mod` vive in `api/routers/items.py`, spostalo in un helper condiviso. Crea `api/routers/_helpers.py` (se non esiste):

```python
"""Shared helpers for router logic (avoid circular imports)."""
from core.game.stats import effective_ability_score


def effective_con_mod(char) -> int:
    """Compute effective CON modifier given character's current state
    (base CON + modifiers from equipped items)."""
    con_row = next((a for a in char.ability_scores if a.name == "constitution"), None)
    if con_row is None:
        return 0
    eq_items = [i for i in char.items if i.is_equipped]
    effective, _ = effective_ability_score("constitution", con_row.value, eq_items)
    return (effective - 10) // 2
```

Aggiorna `api/routers/items.py` (Task 4) a importare da `_helpers` invece di definire localmente, e usa lo stesso import in `characters.py`.

- [ ] **Step 3: Verifica sintassi**

```bash
python3 -c "import ast; ast.parse(open('api/routers/characters.py').read()); print('ok')"
python3 -c "import ast; ast.parse(open('api/routers/_helpers.py').read()); print('ok helpers')"
python3 -c "import ast; ast.parse(open('api/routers/items.py').read()); print('ok items')"
```

- [ ] **Step 4: Commit**

```bash
git add api/routers/_helpers.py api/routers/characters.py api/routers/items.py
git commit -m "feat(api): CON change hook — retroactive HP recompute

- Nuovo helper api/routers/_helpers.py con effective_con_mod() (evita
  duplicazione tra characters.py e items.py).
- In PATCH /ability_scores/{ability}, se ability=='constitution' e
  auto_calc=True: snapshot old/new CON mod (base+items equipped),
  applica delta_mod * total_level a max_hp e current_hp.
- items.py refattorizzato per importare lo helper condiviso.

Regola D&D 5e: quando la CON aumenta, gli HP max aumentano retroattiva-
mente di delta_mod per ogni livello del personaggio.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8 — `/hp/recalc` endpoint + `hp_auto_calc` flag

**Files:**
- Modify: `api/routers/hp.py`
- Modify: `api/schemas/common.py` (già fatto in task 2; qui solo se servono enum extra)

- [ ] **Step 1: Leggi il router HP**

```bash
sed -n '1,50p' api/routers/hp.py
sed -n '100,180p' api/routers/hp.py
```

- [ ] **Step 2: Aggiungi endpoint `POST /characters/{id}/hp/recalc`**

Aggiungi in fondo a `api/routers/hp.py` (prima del `router`):

```python
from core.game.stats import total_base_hp
from api.routers._helpers import effective_con_mod


@router.post("/characters/{char_id}/hp/recalc", response_model=CharacterFull)
async def recalc_hp(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    """Recalculate hit_points from D&D 5e fixed formula.

    Computes total_base_hp using character's current classes (with first
    class owning level 1), current CON mod (effective with equipped items),
    then sets hit_points to that value. current_hit_points is clamped:
    - If new_max > old_max: current += (new_max - old_max)
    - If new_max < old_max: current = min(current, new_max)
    """
    char = await _get_owned_full(session, char_id, user_id)

    con_mod = effective_con_mod(char)
    new_max = total_base_hp(char.classes, con_mod)

    old_max = char.hit_points
    char.hit_points = new_max
    if new_max > old_max:
        char.current_hit_points = max(0, char.current_hit_points + (new_max - old_max))
    else:
        char.current_hit_points = min(char.current_hit_points, new_max)

    _add_history(session, char.id, "hp_change",
                 f"HP ricalcolati da formula: {old_max} → {new_max}")

    await session.commit()
    await session.refresh(char)
    return CharacterFull.model_validate(char)
```

**Nota al sub-agent**: verifica che gli import necessari (`_get_owned_full`, `_add_history`, `CharacterFull`, `Annotated`, `Depends`, `AsyncSession`, `get_current_user`, `get_db`) siano già presenti nel file.

- [ ] **Step 3: Flag `settings.hp_auto_calc` — documenta in `api/schemas/character.py`**

Siccome `settings` è un `dict` libero su `Character`, non serve migration. Documenta nel commento del modello (se presente) o aggiungi una costante enum. Per ora basta farsi trovare per grep:

```python
# In api/schemas/character.py, vicino ad altri commenti dominio:
# settings.hp_auto_calc: bool, default True. If False, disables:
#   - auto-HP bootstrap on first class add
#   - auto-HP on XP level-up
#   - CON change hook retroactive HP
# The manual recalc endpoint (POST /hp/recalc) remains available regardless.
```

- [ ] **Step 4: Verifica sintassi**

```bash
python3 -c "import ast; ast.parse(open('api/routers/hp.py').read()); print('ok')"
```

- [ ] **Step 5: Commit**

```bash
git add api/routers/hp.py api/schemas/character.py
git commit -m "feat(api): add POST /hp/recalc endpoint + document hp_auto_calc flag

- Nuovo endpoint POST /characters/{id}/hp/recalc: ricalcola hit_points
  da formula D&D 5e fixed (total_base_hp), usando CON mod effettivo
  (base+equipped items). Current clampato a new_max o incrementato se
  new_max aumenta.
- Aggiunge evento 'hp_change' alla cronologia del personaggio.
- Documento character.settings.hp_auto_calc: flag boolean (default True)
  che gate l'automazione auto-HP; quando False disattiva bootstrap +
  level-up + CON hook. L'endpoint /hp/recalc è sempre disponibile.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9 — `POST /spells/{id}/roll_damage` endpoint

**Files:**
- Modify: `api/routers/spells.py`
- Modify: `api/schemas/spell.py`

- [ ] **Step 1: Leggi range 40-65 di `api/routers/dice.py` per il pattern `_roll_dice`**

```bash
sed -n '35,70p' api/routers/dice.py
```

Pattern: `_roll_dice(notation) -> tuple[list[int], int]` dove il secondo elemento è il bonus piatto.

- [ ] **Step 2: Aggiungi schema in `api/schemas/spell.py`**

```python
import re

_EXTRA_DICE_RE = re.compile(r"^(\d+)d(\d+)([+-]\d+)?$", re.IGNORECASE)


class RollDamageRequest(BaseModel):
    casting_level: int | None = None
    extra_dice: str | None = None
    is_critical: bool = False

    @field_validator("extra_dice")
    @classmethod
    def validate_extra_dice(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        if not _EXTRA_DICE_RE.match(v.strip()):
            raise ValueError(
                f"extra_dice must match '<count>d<sides>[+/-bonus]' "
                f"(e.g. '2d6', '1d8+3'), got {v!r}"
            )
        return v.strip()


class RollDamageResult(BaseModel):
    rolls: list[int]
    total: int
    half_damage: int
    damage_type: str | None
    breakdown: str
    casting_level: int
    is_critical: bool
    model_config = {"from_attributes": True}
```

- [ ] **Step 3: Aggiungi endpoint in `api/routers/spells.py`**

In fondo al file (prima di eventuali ultimi decoratori), aggiungi:

```python
from api.routers.dice import _roll_dice, _DICE_RE


@router.post(
    "/characters/{char_id}/spells/{spell_id}/roll_damage",
    response_model=RollDamageResult,
)
async def roll_spell_damage(
    char_id: int,
    spell_id: int,
    body: RollDamageRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RollDamageResult:
    char = await _get_owned_full(session, char_id, user_id)
    spell = next((s for s in char.spells if s.id == spell_id), None)
    if spell is None:
        raise HTTPException(status_code=404, detail="Spell not found")
    if not spell.damage_dice:
        raise HTTPException(status_code=400, detail="Spell has no damage_dice")

    casting_level = body.casting_level if body.casting_level is not None else spell.level
    if casting_level < spell.level:
        raise HTTPException(
            status_code=400,
            detail=f"casting_level {casting_level} < spell.level {spell.level}",
        )
    if casting_level > 9:
        raise HTTPException(status_code=400, detail="casting_level must be <= 9")

    # Parse spell.damage_dice using same regex
    m = _DICE_RE.match(spell.damage_dice.strip())
    if not m:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid spell.damage_dice format: {spell.damage_dice!r}",
        )
    base_count = int(m.group(1))
    sides = int(m.group(2))
    base_bonus = int(m.group(3)) if m.group(3) else 0

    # Apply critical (double dice, not the flat bonus)
    dice_count = base_count * 2 if body.is_critical else base_count

    # Parse optional extra_dice (already validated by Pydantic)
    extra_rolls: list[int] = []
    extra_bonus = 0
    if body.extra_dice:
        em = _DICE_RE.match(body.extra_dice)
        if em:
            e_count = int(em.group(1))
            e_sides = int(em.group(2))
            e_bonus = int(em.group(3)) if em.group(3) else 0
            extra_dice_count = e_count * 2 if body.is_critical else e_count
            import random
            extra_rolls = [random.randint(1, e_sides) for _ in range(extra_dice_count)]
            extra_bonus = e_bonus

    import random
    main_rolls = [random.randint(1, sides) for _ in range(dice_count)]

    total = sum(main_rolls) + sum(extra_rolls) + base_bonus + extra_bonus
    half_damage = (total + 1) // 2  # round up half damage (D&D 5e standard)

    breakdown_parts = [f"{dice_count}d{sides}={main_rolls}"]
    if extra_rolls:
        breakdown_parts.append(f"+{len(extra_rolls)}d{em.group(2)}={extra_rolls}")
    if base_bonus:
        breakdown_parts.append(f"{'+' if base_bonus >= 0 else ''}{base_bonus}")
    if extra_bonus:
        breakdown_parts.append(f"{'+' if extra_bonus >= 0 else ''}{extra_bonus}")
    breakdown = " ".join(breakdown_parts) + f" = {total}"

    # Append to character rolls_history (if field exists and is mutable)
    history_entry = {
        "type": "spell_damage",
        "spell_name": spell.name,
        "rolls": main_rolls + extra_rolls,
        "total": total,
        "damage_type": spell.damage_type,
        "casting_level": casting_level,
        "is_critical": body.is_critical,
    }
    if hasattr(char, "rolls_history") and isinstance(char.rolls_history, list):
        char.rolls_history.append(history_entry)
        await session.commit()

    return RollDamageResult(
        rolls=main_rolls + extra_rolls,
        total=total,
        half_damage=half_damage,
        damage_type=spell.damage_type,
        breakdown=breakdown,
        casting_level=casting_level,
        is_critical=body.is_critical,
    )
```

- [ ] **Step 4: Verifica sintassi**

```bash
python3 -c "import ast; ast.parse(open('api/schemas/spell.py').read()); print('ok schema')"
python3 -c "import ast; ast.parse(open('api/routers/spells.py').read()); print('ok router')"
```

- [ ] **Step 5: Commit**

```bash
git add api/schemas/spell.py api/routers/spells.py
git commit -m "feat(api): add POST /spells/{id}/roll_damage endpoint

- RollDamageRequest: casting_level?, extra_dice? (regex-validated),
  is_critical bool (default false).
- RollDamageResult: rolls list, total, half_damage (ceil), damage_type,
  breakdown string, casting_level echo, is_critical echo.
- Logic: parsa spell.damage_dice, raddoppia i dadi se critico
  (non il bonus piatto), aggiunge extra_dice (anche questi raddoppiati
  se critico).
- Half damage arrotondato per eccesso (regola D&D 5e).
- Append alla rolls_history del character se disponibile.
- Validazioni: casting_level in [spell.level, 9]; extra_dice regex
  ^(\\d+)d(\\d+)([+-]\\d+)?\$.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 10 — Frontend: `AbilityModifiersEditor` + integration in ItemForm

**Files:**
- Create: `webapp/src/pages/inventory/AbilityModifiersEditor.tsx`
- Modify: `webapp/src/pages/inventory/itemMetadata.ts` (build/parse `ability_modifiers`)
- Modify: `webapp/src/pages/inventory/ItemForm.tsx` (integra editor)
- Modify: `webapp/src/types/index.ts` (tipo `AbilityModifier`)

- [ ] **Step 1: Aggiungi tipi in `webapp/src/types/index.ts`**

In cima al file (dopo altri exports tipo):

```ts
export type AbilityName =
  | 'strength'
  | 'dexterity'
  | 'constitution'
  | 'intelligence'
  | 'wisdom'
  | 'charisma'

export type AbilityModifierKind = 'absolute' | 'relative'

export interface AbilityModifier {
  ability: AbilityName
  kind: AbilityModifierKind
  value: number
}

export interface AppliedModifier {
  source: string
  ability: AbilityName
  kind: AbilityModifierKind
  value: number
  item_id: number
}
```

Aggiorna `AbilityScore` esistente:

```ts
export interface AbilityScore {
  id: number
  name: AbilityName
  value: number          // effective
  base_value?: number    // raw DB (new)
  modifier: number
  modifiers_applied?: AppliedModifier[]
}
```

- [ ] **Step 2: Crea `webapp/src/pages/inventory/AbilityModifiersEditor.tsx`**

```tsx
import { useTranslation } from 'react-i18next'
import { Plus, X } from 'lucide-react'
import type { AbilityModifier, AbilityName, AbilityModifierKind } from '@/types'

const ABILITY_ORDER: AbilityName[] = [
  'strength', 'dexterity', 'constitution',
  'intelligence', 'wisdom', 'charisma',
]

interface AbilityModifiersEditorProps {
  modifiers: AbilityModifier[]
  onChange: (next: AbilityModifier[]) => void
}

export default function AbilityModifiersEditor({
  modifiers,
  onChange,
}: AbilityModifiersEditorProps) {
  const { t } = useTranslation()

  const add = () => {
    onChange([
      ...modifiers,
      { ability: 'strength', kind: 'relative', value: 0 },
    ])
  }

  const update = (index: number, patch: Partial<AbilityModifier>) => {
    onChange(
      modifiers.map((m, i) => (i === index ? { ...m, ...patch } : m))
    )
  }

  const remove = (index: number) => {
    onChange(modifiers.filter((_, i) => i !== index))
  }

  return (
    <div className="space-y-2">
      <p className="font-cinzel text-xs uppercase tracking-widest text-dnd-gold-dim">
        {t('character.inventory.item.modifiers.title')}
      </p>
      {modifiers.length === 0 && (
        <p className="text-xs italic text-dnd-text-faint">
          {t('character.inventory.item.modifiers.empty')}
        </p>
      )}
      {modifiers.map((m, i) => (
        <div key={i} className="flex items-center gap-2">
          <select
            value={m.ability}
            onChange={(e) => update(i, { ability: e.target.value as AbilityName })}
            className="flex-1 bg-dnd-surface border border-dnd-border rounded-md px-2 py-1 text-sm"
            aria-label={t('character.inventory.item.modifiers.ability')}
          >
            {ABILITY_ORDER.map((ab) => (
              <option key={ab} value={ab}>
                {t(`character.ability.${ab}_short`)}
              </option>
            ))}
          </select>
          <select
            value={m.kind}
            onChange={(e) => update(i, { kind: e.target.value as AbilityModifierKind })}
            className="bg-dnd-surface border border-dnd-border rounded-md px-2 py-1 text-sm"
            aria-label={t('character.inventory.item.modifiers.kind_label')}
          >
            <option value="relative">{t('character.inventory.item.modifiers.kind.relative')}</option>
            <option value="absolute">{t('character.inventory.item.modifiers.kind.absolute')}</option>
          </select>
          <input
            type="number"
            value={m.value}
            onChange={(e) => update(i, { value: parseInt(e.target.value, 10) || 0 })}
            className="w-20 bg-dnd-surface border border-dnd-border rounded-md px-2 py-1 text-sm text-center font-mono"
            aria-label={t('character.inventory.item.modifiers.value')}
          />
          <button
            type="button"
            onClick={() => remove(i)}
            className="text-dnd-text-muted hover:text-[var(--dnd-crimson-bright)] transition-colors p-1"
            aria-label={t('character.inventory.item.modifiers.remove')}
          >
            <X size={16} />
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={add}
        className="inline-flex items-center gap-1 text-xs text-dnd-gold-bright hover:text-dnd-gold transition-colors px-2 py-1"
      >
        <Plus size={14} />
        {t('character.inventory.item.modifiers.add')}
      </button>
    </div>
  )
}
```

- [ ] **Step 3: Estendi `webapp/src/pages/inventory/itemMetadata.ts`**

Aggiungi un campo `ability_modifiers` a `ItemFormData` e integra nella build/parse:

```ts
// In ItemFormData interface (around line 36-58), add:
export interface ItemFormData {
  // ... existing fields ...
  ability_modifiers: AbilityModifier[]
}

// In buildItemMetadata(form), dopo il blocco type-specific, aggiungi:
export function buildItemMetadata(form: ItemFormData): Record<string, unknown> {
  const meta: Record<string, unknown> = {}
  // ... existing type-specific logic ...

  // Ability modifiers (all types)
  if (form.ability_modifiers && form.ability_modifiers.length > 0) {
    meta.ability_modifiers = form.ability_modifiers
  }

  return meta
}

// In itemToFormData(item), alla fine:
export function itemToFormData(item: Item): ItemFormData {
  // ... existing ...
  const ability_modifiers = (
    (item.item_metadata as Record<string, unknown> | undefined)?.ability_modifiers as AbilityModifier[] | undefined
  ) ?? []

  return {
    // ... existing fields ...
    ability_modifiers,
  }
}
```

Aggiorna i default in `defaultFormData` / `emptyFormData` per includere `ability_modifiers: []`.

- [ ] **Step 4: Integra in `webapp/src/pages/inventory/ItemForm.tsx`**

Nel componente, prima del pulsante "Salva" (o dopo i campi type-specific), aggiungi l'editor:

```tsx
import AbilityModifiersEditor from './AbilityModifiersEditor'

// Dentro il form, dopo il blocco type-specific:
<AbilityModifiersEditor
  modifiers={form.ability_modifiers ?? []}
  onChange={(next) => setForm({ ...form, ability_modifiers: next })}
/>
```

- [ ] **Step 5: Verifica TypeScript**

```bash
cd webapp && npx tsc --noEmit
```
Expected: zero errori.

- [ ] **Step 6: Commit**

```bash
git add webapp/src/types/index.ts webapp/src/pages/inventory/AbilityModifiersEditor.tsx webapp/src/pages/inventory/itemMetadata.ts webapp/src/pages/inventory/ItemForm.tsx
git commit -m "feat(webapp): add AbilityModifiersEditor component + form integration

- Nuovo componente AbilityModifiersEditor con rows add/remove per
  modificatori ability: select ability + toggle abs/rel + input valore
  + bottone remove.
- Integrato nel form ItemForm per tutti i tipi di oggetto.
- itemMetadata.ts estende buildItemMetadata/itemToFormData per
  serializzare/deserializzare ability_modifiers array.
- types/index.ts: aggiunti AbilityName, AbilityModifier, AppliedModifier,
  esteso AbilityScore con base_value? + modifiers_applied?.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 11 — Frontend: Stats page breakdown display

**Files:**
- Modify: `webapp/src/pages/AbilityScores.tsx`
- (opzionale) Create: `webapp/src/pages/stats/AbilityBreakdown.tsx`

- [ ] **Step 1: Leggi il layout corrente della card ability**

```bash
sed -n '64,150p' webapp/src/pages/AbilityScores.tsx
```

- [ ] **Step 2: Aggiungi sezione breakdown dentro ogni card (collapsed view)**

Sotto il valore principale, aggiungi un blocco espandibile (o sempre visibile se ci sono modifiers_applied):

```tsx
{score.modifiers_applied && score.modifiers_applied.length > 0 && (
  <div className="mt-2 pt-2 border-t border-dnd-border/50 space-y-1 text-[11px] font-body">
    <div className="flex items-center justify-between text-dnd-text-faint">
      <span>{t('character.ability.breakdown.base')}</span>
      <span className="font-mono">{score.base_value ?? score.value}</span>
    </div>
    {score.modifiers_applied.map((mod, idx) => (
      <div key={idx} className="flex items-center justify-between text-dnd-gold-dim">
        <span className="truncate flex-1">{mod.source}</span>
        <span className="font-mono shrink-0 ml-2">
          {mod.kind === 'relative'
            ? (mod.value >= 0 ? `+${mod.value}` : mod.value)
            : `=${mod.value}`}
        </span>
      </div>
    ))}
    <div className="flex items-center justify-between text-dnd-gold-bright font-bold">
      <span>{t('character.ability.breakdown.effective')}</span>
      <span className="font-mono">{score.value}</span>
    </div>
  </div>
)}
```

- [ ] **Step 3: Verifica TypeScript**

```bash
cd webapp && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add webapp/src/pages/AbilityScores.tsx
git commit -m "feat(webapp): show ability breakdown in Stats page

Ogni card ability ora mostra — se modifiers_applied è non vuoto — un
blocco espandibile con:
- Base: valore raw dal DB
- Ogni modifier applicato (source, kind, value formattato)
- Effective: valore finale (colored gold bold)

Il blocco è nascosto quando non ci sono modifier attivi (retroazione
compatibile con char senza item equipaggiati).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 12 — Frontend: `SpellDamageSheet` + wire-up in SpellItem

**Files:**
- Create: `webapp/src/pages/spells/SpellDamageSheet.tsx`
- Modify: `webapp/src/api/client.ts` (wrapper `api.spells.rollDamage`)
- Modify: `webapp/src/types/index.ts` (`RollDamageRequest`, `RollDamageResult`)
- Modify: `webapp/src/pages/spells/SpellItem.tsx` (bottone Roll Damage + hook)
- Modify: `webapp/src/pages/Spells.tsx` (state per sheet aperto)

- [ ] **Step 1: Aggiungi tipi in `webapp/src/types/index.ts`**

```ts
export interface RollDamageRequest {
  casting_level?: number
  extra_dice?: string
  is_critical?: boolean
}

export interface RollDamageResult {
  rolls: number[]
  total: number
  half_damage: number
  damage_type: string | null
  breakdown: string
  casting_level: number
  is_critical: boolean
}
```

- [ ] **Step 2: Aggiungi wrapper in `webapp/src/api/client.ts`**

Dentro `api.spells`:

```ts
rollDamage: async (
  charId: number,
  spellId: number,
  body: RollDamageRequest,
): Promise<RollDamageResult> => {
  return request<RollDamageResult>(
    `/characters/${charId}/spells/${spellId}/roll_damage`,
    { method: 'POST', body: JSON.stringify(body) }
  )
},
```

Sostituendo il placeholder con il pattern di chiamata del client esistente (vedere altri metodi POST nel file).

- [ ] **Step 3: Crea `webapp/src/pages/spells/SpellDamageSheet.tsx`**

```tsx
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation } from '@tanstack/react-query'
import { m } from 'framer-motion'
import { Dices, Minus, Plus, Swords, Shield } from 'lucide-react'
import { api } from '@/api/client'
import type { Spell, RollDamageRequest, RollDamageResult } from '@/types'
import Sheet from '@/components/ui/Sheet'
import { haptic } from '@/auth/telegram'

interface SpellDamageSheetProps {
  charId: number
  spell: Spell | null
  onClose: () => void
}

export default function SpellDamageSheet({
  charId,
  spell,
  onClose,
}: SpellDamageSheetProps) {
  const { t } = useTranslation()
  const [castingLevel, setCastingLevel] = useState(spell?.level ?? 1)
  const [extraDice, setExtraDice] = useState('')
  const [isCritical, setIsCritical] = useState(false)
  const [result, setResult] = useState<RollDamageResult | null>(null)

  const mutation = useMutation({
    mutationFn: (body: RollDamageRequest) => {
      if (!spell) throw new Error('no spell')
      return api.spells.rollDamage(charId, spell.id, body)
    },
    onSuccess: (data) => {
      haptic.success()
      setResult(data)
    },
    onError: () => haptic.error(),
  })

  if (!spell) return null

  const isAttack = spell.attack_save === 'ATK' || spell.attack_save === null || !spell.attack_save
  const maxLevel = 9
  const minLevel = spell.level

  const handleRoll = () => {
    mutation.mutate({
      casting_level: castingLevel,
      extra_dice: extraDice || undefined,
      is_critical: isCritical,
    })
  }

  const reset = () => {
    setResult(null)
    setExtraDice('')
    setIsCritical(false)
    setCastingLevel(spell.level)
  }

  const handleClose = () => {
    reset()
    onClose()
  }

  return (
    <Sheet open={!!spell} onClose={handleClose} title={t('character.spells.roll_damage.title', { name: spell.name })}>
      {!result ? (
        <div className="space-y-4 p-1">
          {/* Casting level */}
          <div>
            <label className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim">
              {t('character.spells.roll_damage.casting_level')}
            </label>
            <div className="mt-1 flex items-center gap-2">
              <button
                type="button"
                onClick={() => setCastingLevel((v) => Math.max(minLevel, v - 1))}
                className="w-8 h-8 rounded-md bg-dnd-surface border border-dnd-border"
                aria-label={t('character.spells.roll_damage.decrease_level')}
              >
                <Minus size={14} className="mx-auto" />
              </button>
              <div className="flex-1 text-center font-display text-xl font-bold">
                {castingLevel}
              </div>
              <button
                type="button"
                onClick={() => setCastingLevel((v) => Math.min(maxLevel, v + 1))}
                className="w-8 h-8 rounded-md bg-dnd-surface border border-dnd-border"
                aria-label={t('character.spells.roll_damage.increase_level')}
              >
                <Plus size={14} className="mx-auto" />
              </button>
            </div>
          </div>

          {/* Extra dice */}
          <div>
            <label className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim">
              {t('character.spells.roll_damage.extra_dice')}
            </label>
            <input
              type="text"
              value={extraDice}
              onChange={(e) => setExtraDice(e.target.value)}
              placeholder={t('character.spells.roll_damage.extra_dice_placeholder')}
              className="mt-1 w-full bg-dnd-surface border border-dnd-border rounded-md px-3 py-2 text-sm font-mono"
            />
          </div>

          {/* Critical toggle */}
          {isAttack && (
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={isCritical}
                onChange={(e) => setIsCritical(e.target.checked)}
                className="w-4 h-4"
              />
              <span>{t('character.spells.roll_damage.critical')}</span>
            </label>
          )}

          <m.button
            type="button"
            onClick={handleRoll}
            disabled={mutation.isPending}
            whileTap={{ scale: 0.97 }}
            className="w-full inline-flex items-center justify-center gap-2 bg-gradient-to-r from-dnd-gold-deep to-dnd-gold-bright text-black px-4 py-3 rounded-md font-cinzel font-bold uppercase tracking-widest disabled:opacity-60"
          >
            <Dices size={18} />
            {t('character.spells.roll_damage.roll_button')}
          </m.button>
        </div>
      ) : (
        <div className="space-y-4 p-1">
          <div className="text-center">
            <p className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim mb-2">
              {result.breakdown}
            </p>
            {result.damage_type && (
              <p className="text-sm italic text-dnd-text-muted mb-3">
                {t(`character.inventory.damage_types.dmg_${result.damage_type}`, { defaultValue: result.damage_type })}
              </p>
            )}
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-dnd-surface border border-dnd-crimson/40 rounded-md p-3 text-center">
              <Swords size={16} className="mx-auto text-[var(--dnd-crimson-bright)]" />
              <p className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim mt-1">
                {t('character.spells.roll_damage.full_damage')}
              </p>
              <p className="text-2xl font-display font-black text-dnd-text mt-0.5">
                {result.total}
              </p>
            </div>
            {!isAttack && (
              <div className="bg-dnd-surface border border-dnd-cobalt/40 rounded-md p-3 text-center">
                <Shield size={16} className="mx-auto text-[var(--dnd-cobalt-bright)]" />
                <p className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim mt-1">
                  {t('character.spells.roll_damage.half_damage')}
                </p>
                <p className="text-2xl font-display font-black text-dnd-text mt-0.5">
                  {result.half_damage}
                </p>
              </div>
            )}
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={reset}
              className="flex-1 px-3 py-2 rounded-md bg-dnd-surface border border-dnd-border text-sm"
            >
              {t('character.spells.roll_damage.reroll')}
            </button>
            <button
              type="button"
              onClick={handleClose}
              className="flex-1 px-3 py-2 rounded-md bg-dnd-surface border border-dnd-border text-sm"
            >
              {t('character.spells.roll_damage.close')}
            </button>
          </div>
        </div>
      )}
    </Sheet>
  )
}
```

- [ ] **Step 4: Aggiungi bottone "Roll Damage" in `SpellItem.tsx`**

Nel blocco action buttons (riga ~119-177), prima del bottone Edit, aggiungi:

```tsx
{isExpanded && spell.damage_dice && onRollDamage && (
  <button
    type="button"
    onClick={() => onRollDamage(spell)}
    className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md bg-dnd-surface border border-dnd-gold-dim/30 text-xs hover:border-dnd-gold transition-colors"
  >
    <Dices size={14} className="text-dnd-gold-bright" />
    {t('character.spells.roll_damage.button')}
  </button>
)}
```

E aggiungi il prop `onRollDamage?: (spell: Spell) => void` alla firma del componente, passato dall'alto.

- [ ] **Step 5: Wire-up in `Spells.tsx`**

```tsx
import SpellDamageSheet from '@/pages/spells/SpellDamageSheet'
// ...

const [rollDamageSpell, setRollDamageSpell] = useState<Spell | null>(null)

// Nel JSX, passa il callback ai SpellItem:
<SpellItem
  spell={spell}
  // ... existing props ...
  onRollDamage={setRollDamageSpell}
/>

// Alla fine del JSX (prima del return finale):
<SpellDamageSheet
  charId={charId}
  spell={rollDamageSpell}
  onClose={() => setRollDamageSpell(null)}
/>
```

- [ ] **Step 6: Verifica TypeScript**

```bash
cd webapp && npx tsc --noEmit
```

- [ ] **Step 7: Commit**

```bash
git add webapp/src/types/index.ts webapp/src/api/client.ts webapp/src/pages/spells/SpellDamageSheet.tsx webapp/src/pages/spells/SpellItem.tsx webapp/src/pages/Spells.tsx
git commit -m "feat(webapp): add spell damage roll sheet + button

- Nuovo componente SpellDamageSheet: bottom sheet con casting level
  stepper, extra_dice input, critical toggle (se attack spell), pulsante
  Roll. Risultato in-place con dados pieno/dimezzato (dimezzato nascosto
  se attack spell) + breakdown.
- api.spells.rollDamage wrapper + RollDamageRequest/Result tipi.
- SpellItem mostra bottone 'Roll Damage' inline se damage_dice presente;
  callback passato dal parent Spells.tsx che gestisce lo state del sheet.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 13 — Frontend: SpellSlots rewrite (visual inverted + symmetric click)

**Files:**
- Modify: `webapp/src/pages/SpellSlots.tsx`

- [ ] **Step 1: Leggi il click handler attuale**

```bash
sed -n '115,145p' webapp/src/pages/SpellSlots.tsx
```

- [ ] **Step 2: Riscrivi il click handler + visual classes**

Sostituisci il blocco `m.button` per la gemma e la sua logica (righe ~118-140) con:

```tsx
<m.button
  key={i}
  type="button"
  onClick={() => {
    if (i < slot.used) {
      // Clicked a used gem → free the last used one
      haptic.light()
      updateSlot.mutate({ slotId: slot.id, used: Math.max(0, slot.used - 1) })
    } else {
      // Clicked an available gem → consume the first available
      haptic.medium()
      updateSlot.mutate({ slotId: slot.id, used: Math.min(slot.total, slot.used + 1) })
    }
  }}
  whileTap={{ scale: 0.9 }}
  aria-label={t('character.slots.gem_aria', {
    level: slot.level,
    index: i + 1,
    total: slot.total,
    state: i < slot.used
      ? t('character.slots.state_used')
      : t('character.slots.state_available'),
  })}
  aria-pressed={i < slot.used}
  className={`w-7 h-7 rounded-full border-2 transition-all ${
    i < slot.used
      ? 'bg-gradient-to-br from-dnd-gold-deep to-dnd-gold-bright border-dnd-gold-bright shadow-[0_0_10px_rgba(244,208,111,0.5)]'
      : 'bg-transparent border-dnd-gold-dim/60 hover:border-dnd-gold-bright'
  }`}
/>
```

**Nota**: il visual è invertito rispetto al design precedente — `i < slot.used` = gemma piena (usata); `i >= slot.used` = gemma vuota (disponibile).

- [ ] **Step 3: Verifica TypeScript**

```bash
cd webapp && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add webapp/src/pages/SpellSlots.tsx
git commit -m "refactor(webapp): rewrite spell slot click behavior + invert visual

Nuovo click handler simmetrico:
- Click su gemma pieno (i < used): used-- (libera l'ultimo usato).
- Click su gemma vuoto (i >= used): used++ (consuma il primo disponibile).

Visual invertito:
- Gemma piena (gold gradient con glow) = slot usato.
- Gemma vuota (outline transparent) = slot disponibile.

aria-label descrittivo con level/index/total/state. aria-pressed
tracciato dallo state 'used'.

Edge case naturali: all full + click qualsiasi (tutti pieni) → used--.
All empty + click qualsiasi → used++. No stato 'click does nothing'.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 14 — Frontend: Settings recalc HP + auto-calc toggle

**Files:**
- Modify: `webapp/src/pages/Settings.tsx`
- Modify: `webapp/src/api/client.ts` (wrapper `api.characters.recalcHp`)

- [ ] **Step 1: Aggiungi wrapper in `webapp/src/api/client.ts`**

Dentro `api.characters`:

```ts
recalcHp: async (charId: number): Promise<CharacterFull> => {
  return request<CharacterFull>(
    `/characters/${charId}/hp/recalc`,
    { method: 'POST' }
  )
},
```

- [ ] **Step 2: Aggiungi sezione in `webapp/src/pages/Settings.tsx`**

Prima o dopo le sezioni esistenti (spell_slots_mode, carry_capacity, language, dice_3d), aggiungi:

```tsx
{/* Auto-HP section */}
<div>
  <h3 className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim mb-2">
    {t('character.settings.hp.title')}
  </h3>
  <div className="space-y-3">
    {/* Auto-calc toggle */}
    <label className="flex items-center justify-between bg-dnd-surface border border-dnd-border rounded-md p-3">
      <div>
        <p className="text-sm font-body">{t('character.settings.hp.auto_calc_toggle')}</p>
        <p className="text-xs text-dnd-text-faint italic">
          {t('character.settings.hp.auto_calc_hint')}
        </p>
      </div>
      <input
        type="checkbox"
        checked={(char?.settings as Record<string, unknown>)?.hp_auto_calc !== false}
        onChange={(e) => {
          const current = (char?.settings as Record<string, unknown>) ?? {}
          updateSettings.mutate({ ...current, hp_auto_calc: e.target.checked })
        }}
        className="w-5 h-5"
      />
    </label>

    {/* Recalc button */}
    <button
      type="button"
      onClick={() => setShowRecalcConfirm(true)}
      className="w-full inline-flex items-center justify-center gap-2 px-3 py-2 rounded-md bg-dnd-surface border border-[var(--dnd-crimson-bright)]/40 text-[var(--dnd-crimson-bright)] text-sm"
    >
      <RefreshCw size={14} />
      {t('character.settings.hp.recalc')}
    </button>
  </div>
</div>

{/* Recalc confirm dialog */}
{showRecalcConfirm && (
  <Sheet
    open={showRecalcConfirm}
    onClose={() => setShowRecalcConfirm(false)}
    title={t('character.settings.hp.recalc_confirm_title')}
  >
    <div className="space-y-4 p-2">
      <p className="text-sm">{t('character.settings.hp.recalc_confirm_body')}</p>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => setShowRecalcConfirm(false)}
          className="flex-1 px-3 py-2 rounded-md bg-dnd-surface border border-dnd-border text-sm"
        >
          {t('common.cancel')}
        </button>
        <button
          type="button"
          onClick={() => {
            recalcMutation.mutate()
            setShowRecalcConfirm(false)
          }}
          className="flex-1 px-3 py-2 rounded-md bg-[var(--dnd-crimson-bright)] text-white text-sm font-bold"
        >
          {t('common.confirm')}
        </button>
      </div>
    </div>
  </Sheet>
)}
```

Aggiungi state + mutations:

```tsx
const [showRecalcConfirm, setShowRecalcConfirm] = useState(false)

const recalcMutation = useMutation({
  mutationFn: () => api.characters.recalcHp(charId),
  onSuccess: (updated) => {
    qc.setQueryData(['character', charId], updated)
    haptic.success()
  },
  onError: () => haptic.error(),
})
```

Import mancanti: `useState, useMutation, api, Sheet, RefreshCw from 'lucide-react', haptic`.

- [ ] **Step 3: Verifica TypeScript**

```bash
cd webapp && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add webapp/src/api/client.ts webapp/src/pages/Settings.tsx
git commit -m "feat(webapp): add HP auto-calc toggle + recalc button in Settings

- api.characters.recalcHp wrapper per POST /hp/recalc.
- Sezione 'HP' in Settings con toggle 'HP automatici' che setta
  char.settings.hp_auto_calc (default True quando assente).
- Pulsante 'Ricalcola HP dalla formula' con dialog di conferma; su
  accept invoca recalcMutation → TanStack invalidation.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 15 — Frontend: Level-up HP toast + history

**Files:**
- Modify: `webapp/src/pages/Experience.tsx`

- [ ] **Step 1: Leggi la mutation XP**

```bash
grep -n "updateXP\|mutate" webapp/src/pages/Experience.tsx | head -10
```

- [ ] **Step 2: Aggiungi toast nel `onSuccess` del mutate XP**

Trova il `onSuccess` della mutation XP e aggiungi:

```tsx
import { toast } from 'sonner'
// ...

onSuccess: (updated) => {
  qc.setQueryData(['character', charId], updated)
  haptic.success()
  if (updated.hp_gained && updated.hp_gained > 0) {
    toast.success(t('character.xp.hp_gained_toast', { hp: updated.hp_gained }), {
      duration: 2000,
      icon: '❤',
    })
  }
},
```

- [ ] **Step 3: Verifica TypeScript**

```bash
cd webapp && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add webapp/src/pages/Experience.tsx
git commit -m "feat(webapp): show +N HP toast at level-up

Quando la mutation XP ritorna hp_gained > 0 (level-up triggered),
mostra un toast sonner '+N HP' per 2 secondi.

Gli HP max + correnti sono già aggiornati dal backend e TanStack
invalidation fa rianimare HPGauge automaticamente.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 16 — i18n keys

**Files:**
- Modify: `webapp/src/locales/it.json`
- Modify: `webapp/src/locales/en.json`

- [ ] **Step 1: Aggiungi le chiavi italiane**

In `webapp/src/locales/it.json` aggiungi i seguenti nodi (mergendo con i nodi esistenti):

```json
{
  "character": {
    "ability": {
      "strength_short": "FOR",
      "dexterity_short": "DES",
      "constitution_short": "COS",
      "intelligence_short": "INT",
      "wisdom_short": "SAG",
      "charisma_short": "CAR",
      "breakdown": {
        "base": "Base",
        "effective": "Effettivo"
      }
    },
    "inventory": {
      "item": {
        "modifiers": {
          "title": "Modificatori caratteristiche",
          "add": "Aggiungi modificatore",
          "empty": "Nessun modificatore",
          "ability": "Caratteristica",
          "kind_label": "Tipo",
          "kind": {
            "absolute": "=",
            "relative": "±"
          },
          "value": "Valore",
          "remove": "Rimuovi modificatore"
        }
      }
    },
    "spells": {
      "roll_damage": {
        "title": "Tiro danni: {{name}}",
        "button": "Rolla danni",
        "casting_level": "Livello di casting",
        "decrease_level": "Diminuisci livello",
        "increase_level": "Aumenta livello",
        "extra_dice": "Dadi extra",
        "extra_dice_placeholder": "es. 2d6",
        "critical": "Critico (raddoppia i dadi)",
        "roll_button": "Rolla",
        "full_damage": "Pieno",
        "half_damage": "Dimezzato",
        "close": "Chiudi",
        "reroll": "Nuovo tiro"
      }
    },
    "slots": {
      "gem_aria": "Livello {{level}} slot {{index}}/{{total}} {{state}}",
      "state_used": "usato",
      "state_available": "disponibile"
    },
    "settings": {
      "hp": {
        "title": "Punti Ferita",
        "recalc": "Ricalcola HP dalla formula",
        "recalc_confirm_title": "Conferma ricalcolo",
        "recalc_confirm_body": "Gli HP massimi saranno ricalcolati secondo la formula D&D 5e (fisso: liv 1 = HD_max + CON_mod; liv 2+ = (HD/2+1) + CON_mod). Gli HP correnti saranno clampati. Continuare?",
        "auto_calc_toggle": "HP automatici",
        "auto_calc_hint": "Quando attivi, HP aumentano automaticamente alla creazione, ai level-up e ai cambi di CON."
      }
    },
    "xp": {
      "hp_gained_toast": "+{{hp}} HP"
    }
  },
  "common": {
    "cancel": "Annulla",
    "confirm": "Conferma"
  }
}
```

- [ ] **Step 2: Aggiungi le chiavi inglesi equivalenti in `en.json`**

```json
{
  "character": {
    "ability": {
      "strength_short": "STR",
      "dexterity_short": "DEX",
      "constitution_short": "CON",
      "intelligence_short": "INT",
      "wisdom_short": "WIS",
      "charisma_short": "CHA",
      "breakdown": {
        "base": "Base",
        "effective": "Effective"
      }
    },
    "inventory": {
      "item": {
        "modifiers": {
          "title": "Ability modifiers",
          "add": "Add modifier",
          "empty": "No modifiers",
          "ability": "Ability",
          "kind_label": "Kind",
          "kind": {
            "absolute": "=",
            "relative": "±"
          },
          "value": "Value",
          "remove": "Remove modifier"
        }
      }
    },
    "spells": {
      "roll_damage": {
        "title": "Damage roll: {{name}}",
        "button": "Roll damage",
        "casting_level": "Casting level",
        "decrease_level": "Decrease level",
        "increase_level": "Increase level",
        "extra_dice": "Extra dice",
        "extra_dice_placeholder": "e.g. 2d6",
        "critical": "Critical (doubles dice)",
        "roll_button": "Roll",
        "full_damage": "Full",
        "half_damage": "Half",
        "close": "Close",
        "reroll": "Roll again"
      }
    },
    "slots": {
      "gem_aria": "Level {{level}} slot {{index}}/{{total}} {{state}}",
      "state_used": "used",
      "state_available": "available"
    },
    "settings": {
      "hp": {
        "title": "Hit Points",
        "recalc": "Recalculate HP from formula",
        "recalc_confirm_title": "Confirm recalculation",
        "recalc_confirm_body": "Max HP will be recalculated using the D&D 5e fixed formula (lvl 1 = HD_max + CON_mod; lvl 2+ = (HD/2+1) + CON_mod). Current HP will be clamped. Continue?",
        "auto_calc_toggle": "Auto HP",
        "auto_calc_hint": "When enabled, HP updates automatically on creation, level-up, and CON changes."
      }
    },
    "xp": {
      "hp_gained_toast": "+{{hp}} HP"
    }
  },
  "common": {
    "cancel": "Cancel",
    "confirm": "Confirm"
  }
}
```

- [ ] **Step 3: Verifica JSON ben formato**

```bash
node -e "JSON.parse(require('fs').readFileSync('webapp/src/locales/it.json','utf8')); console.log('it.json OK')"
node -e "JSON.parse(require('fs').readFileSync('webapp/src/locales/en.json','utf8')); console.log('en.json OK')"
```

Controlla che le chiavi chiave siano accessibili:

```bash
node -e "
const it = JSON.parse(require('fs').readFileSync('webapp/src/locales/it.json','utf8'));
const keys = [
  'character.inventory.item.modifiers.title',
  'character.spells.roll_damage.button',
  'character.spells.roll_damage.full_damage',
  'character.slots.state_used',
  'character.settings.hp.recalc',
  'character.xp.hp_gained_toast',
  'character.ability.strength_short',
  'common.cancel'
];
const get = (o, p) => p.split('.').reduce((x, s) => x?.[s], o);
keys.forEach(k => {
  const v = get(it, k);
  console.log(k, v === undefined ? 'MISSING' : JSON.stringify(v));
});
"
```

Ogni chiave deve stampare il suo valore (non `MISSING`).

- [ ] **Step 4: Commit**

```bash
git add webapp/src/locales/it.json webapp/src/locales/en.json
git commit -m "feat(webapp): i18n keys for character mechanics Gruppo B

Chiavi nuove in it.json + en.json:
- character.ability.*_short: abbreviazioni FOR/DES/COS/INT/SAG/CAR
  (STR/DEX/CON/INT/WIS/CHA) usate nell'AbilityModifiersEditor.
- character.ability.breakdown.{base, effective}: labels Stats page.
- character.inventory.item.modifiers.*: editor modificatori.
- character.spells.roll_damage.*: sheet roll damage.
- character.slots.{gem_aria, state_used, state_available}: aria labels.
- character.settings.hp.{title, recalc, auto_calc_toggle, auto_calc_hint,
  recalc_confirm_{title,body}}: sezione HP settings.
- character.xp.hp_gained_toast: toast level-up.
- common.{cancel, confirm}: labels dialog standard.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 17 — Production build + manual verification

**Files:**
- Modify: `docs/app/**` (build output)

- [ ] **Step 1: Preflight**

```bash
git status --porcelain
```
Expected: vuoto (tutti i commit dei task precedenti già fatti).

- [ ] **Step 2: Chiedi all'utente di avviare il server**

**IMPORTANTE**: l'utente DEVE eseguire `uv run uvicorn` da Windows (non da WSL). Messaggio da passare:

> Backend pronto per verifica. Per testare, avvia da **PowerShell Windows**:
>
> ```
> uv run uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
> ```
>
> E in un altro terminale avvia il dev server webapp (da qualsiasi shell, incluso WSL):
>
> ```
> cd webapp && npm run dev
> ```
>
> Apri `http://localhost:5173/` e verifica i seguenti scenari.

- [ ] **Step 3: Checklist verifica manuale (l'utente conferma ogni voce)**

**Scenario A — Creazione character + prima classe**:
- [ ] Crea nuovo character "TestHP" → HP mostra 0.
- [ ] Aggiungi classe Fighter (d10) → HP diventa 10 (CON default 10 = mod 0).
- [ ] Modifica CON a 14 (mod +2) → HP diventa 12 (level-1 HP = 10 + 2 retro).

**Scenario B — Level-up auto-HP**:
- [ ] Aggiungi XP per portare il char a livello 2 → HP aumenta di 7 (6 + 2 CON mod, formula level 2+ con Fighter d10 = 10/2+1=6).
- [ ] Toast "+7 HP" compare per 2s.

**Scenario C — Item modifier assoluto + relativo**:
- [ ] Crea un item "Belt of Giant Strength" di tipo wondrous con ability_modifier `STR = 21 (absolute)`.
- [ ] Equipaggia → STR effettiva = 21.
- [ ] Aggiungi un secondo item "Cloak of STR +2" con modifier `STR +2 (relative)`.
- [ ] Equipaggia → STR effettiva = max(base+2, 21) = 21 (se base < 19). Se base è 14 → max(16, 21) = 21.
- [ ] Alza base a 20 → max(22, 21) = 22.

**Scenario D — CON change via item**:
- [ ] Equipaggia item con modifier `CON +2 (relative)` → HP max aumenta di 2 × total_level.
- [ ] Disequipaggia → HP max diminuisce di 2 × total_level.

**Scenario E — Spell damage roll**:
- [ ] Crea spell "Fireball" level 3 damage_dice "8d6" damage_type "fire" attack_save "DEX".
- [ ] Click "Rolla danni" → sheet si apre.
- [ ] Casting level 3 → 8 dadi; click Rolla → risultato con pieno + dimezzato (arrotondato up).
- [ ] Casting level 5 + extra_dice "2d6" → 10 dadi totali.
- [ ] Spell con attack_save "ATK" (es. "Ray of Frost") → toggle "Critico" visibile. Abilitato → dadi raddoppiati. Dimezzato non mostrato.

**Scenario F — Spell slot click**:
- [ ] Slot level 3, total=3, used=0 → 3 gemme vuote (outline).
- [ ] Click qualsiasi gemma → used=1, prima gemma piena (gold).
- [ ] Click ultima gemma vuota → used=2.
- [ ] Click una gemma piena → used=1 (la terza torna vuota).
- [ ] Click "Reset" → used=0.

**Scenario G — Settings**:
- [ ] Settings del character → sezione HP visibile.
- [ ] Toggle "HP automatici" OFF → al successivo level-up, HP non cambia.
- [ ] Toggle "HP automatici" ON.
- [ ] Click "Ricalcola HP" → dialog di conferma; accept → HP riallineato alla formula.

**Scenario H — Regressione**:
- [ ] Flow esistenti non regrediti: HP page (damage/heal/rest), spell use (consuma slot), item toggle equip (AC aggiornata per armor/shield), concentrazione, death saves.

- [ ] **Step 4: Se tutti i scenari passano, esegui production build**

```bash
cd webapp && npm run build:prod
```

Expected: zero errori TypeScript, `docs/app/` aggiornato e staged.

- [ ] **Step 5: Commit build**

```bash
git commit -m "chore(webapp): rebuild docs/app for character mechanics (Gruppo B)

Rebuild di produzione con VITE_API_BASE_URL=https://api.cischi.dev.
Include tutti i cambi del Gruppo B: AbilityModifiersEditor, Stats
breakdown, SpellDamageSheet, SpellSlots rewrite, Settings HP section,
level-up toast, i18n.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 6: Push + PR**

```bash
git push -u origin feat/character-mechanics-gruppo-b
```

Aprire PR via `gh pr create` o GitHub UI con titolo `feat(webapp+api): character mechanics (Gruppo B)` e body che riassume le 5 feature + criteri di successo dello spec.

---

## Criteri di successo (ripresi dallo spec)

- [ ] Creazione character + add class → HP auto = `hit_die + con_mod`.
- [ ] Level-up (via XP threshold) → HP aumenta di `(HD/2 + 1) + con_mod`, mai < 1 per livello.
- [ ] Cambio CON → HP max e current si aggiornano retroattivamente di `delta_mod * total_level`.
- [ ] Inventory item editor: sezione "Modificatori caratteristiche" con add/remove rows funzionante.
- [ ] Equipaggiare item con `+2 DEX` modifica la DEX effettiva.
- [ ] Stacking: 2 items `+1 DEX` → +2; 2 items `=19` e `=21` STR → 21; mixed `base 10 + +2 rel + =19 abs` → 19 (max).
- [ ] `/stats` mostra breakdown: base + modifier list per ability.
- [ ] Spell damage: pulsante inline funzionante, sheet con casting level / extra_dice / crit, risultato con pieno + dimezzato (dove applicabile).
- [ ] Spell slot: click su vuoto consuma primo disponibile (`used++`); click su pieno libera ultimo (`used--`). Visual invertito (vuoto=disponibile, pieno=usato).
- [ ] Setting "Ricalcola HP" funzionante con dialog di conferma.
- [ ] Toggle "HP automatici" disattiva i hook.
- [ ] `npm run build:prod` completa senza errori TypeScript.
- [ ] Tutte le stringhe via i18n (it + en).
- [ ] Nessuna regressione su flow esistenti.
