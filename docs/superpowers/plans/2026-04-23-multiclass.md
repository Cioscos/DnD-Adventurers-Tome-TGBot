# Multiclasse (Gruppo G) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aggiungere il flow di level-up multiclass con modale di scelta classe (§2.1) e il flow "Modifica classe" per redistribuire atomicamente i livelli tra classi esistenti (§2.2), incluso il caricamento dei dati di progressione da `dnd5e_classi.md`.

**Architecture:** Parser Python one-shot (`scripts/parse_class_progression.py`) legge il markdown gitignorato e genera `webapp/src/data/class-progression.json` (committato, consumato dal FE). Nuovo endpoint `PATCH /characters/{id}/classes/distribute` applica atomicamente un array di `{class_id, level}`, valida `sum == levelFromXp(xp)`, sincronizza resources/HP. Due modali React (`LevelUpModal`, `EditClassesModal`) e un componente shared (`LevelUpBanner`). Rimozione dei controlli `+/-` e pip tracker per classe in `Multiclass.tsx` — i livelli si cambiano solo via modale.

**Tech Stack:** Python 3.12 + stdlib (parser), FastAPI + SQLAlchemy async + Pydantic (backend), React + TypeScript + TanStack Query + react-i18next + framer-motion (frontend), Tailwind CSS.

**Branch:** `feat/multiclass-gruppo-g` (creato da tip di `feat/xp-level-up-gruppo-f`).
**Spec:** `docs/superpowers/specs/2026-04-23-multiclass-design.md`.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `scripts/parse_class_progression.py` | Create | Parser CLI: legge `dnd5e_classi.md`, scrive `webapp/src/data/class-progression.json`. |
| `webapp/src/data/class-progression.json` | Create (generated) | Dati di progressione per 12 classi × 20 livelli. |
| `webapp/src/types.ts` o file dedicato | Modify | Tipo `ClassProgressionEntry` condiviso dai 3 componenti FE. |
| `api/schemas/common.py` | Modify | Nuovi Pydantic `ClassLevelEntry` + `ClassDistribute`. |
| `api/routers/classes.py` | Modify | Nuovo endpoint `PATCH /{char_id}/classes/distribute`. |
| `webapp/src/api/client.ts` | Modify | Aggiunge `api.classes.distribute(...)`. |
| `webapp/src/pages/multiclass/LevelUpBanner.tsx` | Create | Banner clickable shared tra Experience e Multiclass. |
| `webapp/src/pages/multiclass/LevelUpModal.tsx` | Create | Modale §2.1 (scelta classe + preview sblocchi). |
| `webapp/src/pages/multiclass/EditClassesModal.tsx` | Create | Modale §2.2 (redistribute atomic). |
| `webapp/src/pages/Experience.tsx` | Modify | Banner esistente diventa clickable → apre `LevelUpModal`. |
| `webapp/src/pages/Multiclass.tsx` | Modify | Rimuove `+/-` e pip per classe, aggiunge banner + bottone "Edit classes", integra modali. |
| `webapp/src/locales/it.json` | Modify | +13 chiavi sotto `character.multiclass`. |
| `webapp/src/locales/en.json` | Modify | +13 chiavi sotto `character.multiclass`. |
| `docs/app/` | Modify (generated) | Rebuild finale via `npm run build:prod`. |

---

### Task 1: Parser Python `parse_class_progression.py`

**Files:**
- Create: `scripts/parse_class_progression.py`

- [ ] **Step 1: Creare lo script**

Crea `scripts/parse_class_progression.py` con il contenuto completo:

```python
#!/usr/bin/env python3
"""Parser for dnd5e_classi.md -> webapp/src/data/class-progression.json.

Reads the Italian-labelled D&D 5e class progression tables and produces a
structured JSON consumed by the webapp multiclass level-up modal (Gruppo G).
Run manually whenever dnd5e_classi.md changes.

Usage:
    uv run python scripts/parse_class_progression.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MD_PATH = REPO_ROOT / "dnd5e_classi.md"
OUT_PATH = REPO_ROOT / "webapp" / "src" / "data" / "class-progression.json"

EN_TO_IT: dict[str, str] = {
    "Barbarian": "Barbaro",
    "Bard": "Bardo",
    "Cleric": "Chierico",
    "Druid": "Druido",
    "Fighter": "Guerriero",
    "Monk": "Monaco",
    "Paladin": "Paladino",
    "Ranger": "Ranger",
    "Rogue": "Ladro",
    "Sorcerer": "Stregone",
    "Warlock": "Warlock",
    "Wizard": "Mago",
}

FEATURES_LABELS = {"Caratteristiche", "Features"}
PB_LABELS = {"Bonus Competenza", "Bonus Comp."}
SLOT_PATTERN = re.compile(r"^([1-9])°$")
LEVEL_PATTERN = re.compile(r"^(\d+)°$")
SEPARATOR_PATTERN = re.compile(r"^\|[\s:|-]+\|?\s*$")


def _split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _parse_int_or_zero(s: str) -> int:
    s = s.strip()
    if s in ("—", "-", ""):
        return 0
    try:
        return int(s)
    except ValueError:
        return 0


def _parse_class_table(rows: list[str]) -> list[dict]:
    """Parse one class's markdown table rows and return 20-level progression."""
    if len(rows) < 2:
        raise ValueError("table too short")
    header = _split_row(rows[0])

    feat_idx = next((i for i, h in enumerate(header) if h in FEATURES_LABELS), None)
    pb_idx = next((i for i, h in enumerate(header) if h in PB_LABELS), None)
    if feat_idx is None:
        raise ValueError(f"no Caratteristiche column in header: {header}")
    if pb_idx is None:
        raise ValueError(f"no Bonus Comp. column in header: {header}")

    # Standard spellcaster columns 1°..9°
    slot_cols: dict[int, int] = {}
    for i, h in enumerate(header):
        m = SLOT_PATTERN.match(h)
        if m:
            slot_cols[int(m.group(1))] = i

    # Warlock pact magic columns
    warlock_count_idx = next((i for i, h in enumerate(header) if h == "Slot"), None)
    warlock_level_idx = next((i for i, h in enumerate(header) if h == "Livello Slot"), None)
    is_warlock = warlock_count_idx is not None and warlock_level_idx is not None
    has_casting = bool(slot_cols) or is_warlock

    progression: list[dict] = []
    for row in rows[1:]:
        if SEPARATOR_PATTERN.match(row):
            continue
        cells = _split_row(row)
        if not cells or not LEVEL_PATTERN.match(cells[0]):
            continue
        level = int(cells[0].rstrip("°"))
        if level < 1 or level > 20:
            continue

        features = cells[feat_idx] if feat_idx < len(cells) else "—"
        pb_raw = cells[pb_idx].replace("+", "").strip() if pb_idx < len(cells) else "0"
        pb = int(pb_raw) if pb_raw.isdigit() else 0

        if has_casting:
            spell_slots = [0] * 9
            if is_warlock:
                count = _parse_int_or_zero(cells[warlock_count_idx])
                lvl_str = cells[warlock_level_idx].strip()
                lvl_m = re.match(r"^(\d+)°?$", lvl_str)
                slot_level = int(lvl_m.group(1)) if lvl_m else 0
                if 1 <= slot_level <= 9 and count > 0:
                    spell_slots[slot_level - 1] = count
            else:
                for lvl, idx in slot_cols.items():
                    if idx < len(cells):
                        spell_slots[lvl - 1] = _parse_int_or_zero(cells[idx])
        else:
            spell_slots = None

        progression.append(
            {
                "features": features,
                "proficiency_bonus": pb,
                "spell_slots": spell_slots,
            }
        )

    return progression


def main() -> None:
    if not MD_PATH.exists():
        raise SystemExit(f"missing source: {MD_PATH}")

    text = MD_PATH.read_text(encoding="utf-8")
    # Split on class headers (## ClassName)
    sections = re.split(r"^## ", text, flags=re.MULTILINE)[1:]

    out: dict[str, list[dict]] = {}
    for section in sections:
        lines = section.splitlines()
        if not lines:
            continue
        name_en = lines[0].strip()
        if name_en not in EN_TO_IT:
            continue
        name_it = EN_TO_IT[name_en]
        table_lines = [ln for ln in lines[1:] if ln.startswith("|")]
        progression = _parse_class_table(table_lines)
        if len(progression) != 20:
            raise SystemExit(
                f"{name_en}: expected 20 levels, parsed {len(progression)}"
            )
        out[name_it] = progression

    missing = set(EN_TO_IT.values()) - set(out.keys())
    if missing:
        raise SystemExit(f"missing classes in output: {sorted(missing)}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    rel = OUT_PATH.relative_to(REPO_ROOT)
    print(f"wrote {rel}: {len(out)} classes x 20 levels")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit lo script (senza output JSON ancora)**

```bash
git add scripts/parse_class_progression.py
git commit -m "feat(scripts): parser dnd5e_classi.md -> class-progression.json

Reads the Italian progression tables from dnd5e_classi.md (gitignored)
and writes webapp/src/data/class-progression.json. Handles standard
casters (1°-9° columns) and Warlock's Pact Magic layout.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Generate and commit class-progression.json

**Files:**
- Create: `webapp/src/data/class-progression.json` (output del parser)

**Nota per Claude in WSL:** NON eseguire `uv run python ...` (viola la regola CLAUDE.md sulla `.venv`). Chiedi all'utente di eseguire il parser da Windows, poi proseguire con le verifiche sul file JSON emesso.

- [ ] **Step 1: L'utente esegue il parser**

Da shell **Windows**:

```bash
uv run python scripts/parse_class_progression.py
```

Expected output: `wrote webapp/src/data/class-progression.json: 12 classes x 20 levels`.

- [ ] **Step 2: Validare il JSON emesso**

Da WSL o Windows:

```bash
python3 -c "import json; data = json.load(open('webapp/src/data/class-progression.json')); assert set(data.keys()) == {'Barbaro','Bardo','Chierico','Druido','Guerriero','Ladro','Mago','Monaco','Paladino','Ranger','Stregone','Warlock'}; assert all(len(v) == 20 for v in data.values()); print('ok')"
```

Expected: stampa `ok`, exit 0. Se errore, sistemare il parser (Task 1) e rieseguire.

- [ ] **Step 3: Verifica spot-check**

Ispeziona 3 entry chiave con `jq` (o manualmente):

```bash
python3 -c "import json; d = json.load(open('webapp/src/data/class-progression.json')); print(d['Barbaro'][0], d['Chierico'][0], d['Warlock'][2])"
```

Expected:
- `Barbaro[0]`: `features` contiene "Rage", `proficiency_bonus` = 2, `spell_slots` = `None` (Python) / `null` (JSON).
- `Chierico[0]`: `features` contiene "Spellcasting, Divine Domain", `spell_slots` = `[2,0,0,0,0,0,0,0,0]`.
- `Warlock[2]` (livello 3°): `spell_slots[1]` (indice per 2° livello spell) = `2`.

Se non corrisponde, sistemare parser (Task 1) e rieseguire.

- [ ] **Step 4: Commit output JSON**

```bash
git add webapp/src/data/class-progression.json
git commit -m "feat(webapp): ship class-progression.json (12 classes x 20 levels)

Generated via scripts/parse_class_progression.py from dnd5e_classi.md.
Consumed by the multiclass level-up modal (Gruppo G).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Pydantic schemas `ClassLevelEntry` + `ClassDistribute`

**Files:**
- Modify: `api/schemas/common.py`

- [ ] **Step 1: Aggiungere schemi subito dopo `CharacterClassUpdate`**

Apri `api/schemas/common.py`. Individua la chiusura di `CharacterClassUpdate` (circa linea 131). Dopo quella classe, aggiungi:

```python
class ClassLevelEntry(BaseModel):
    """One (class_id, level) pair for the distribute endpoint."""
    class_id: int
    level: int = Field(ge=1, le=20)


class ClassDistribute(BaseModel):
    """Atomic redistribution of class levels for a character.

    The body must cover every existing class on the character; the sum of
    `level` values must equal the character's XP-derived total level.
    """
    classes: list[ClassLevelEntry]
```

Verifica che `Field` sia già importato in testa al file; altrimenti aggiungilo a `from pydantic import BaseModel, Field`.

- [ ] **Step 2: Verifica JSON schema integrity (manuale)**

Nessun import externo. Controlla la sintassi scorrendo il file.

- [ ] **Step 3: Commit**

```bash
git add api/schemas/common.py
git commit -m "feat(api): Pydantic schemas for class level distribute

ClassLevelEntry (class_id + 1<=level<=20) and ClassDistribute (list of
entries). Consumed by the new PATCH /classes/distribute endpoint.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Backend endpoint `PATCH /{char_id}/classes/distribute`

**Files:**
- Modify: `api/routers/classes.py`

- [ ] **Step 1: Aggiornare gli import in testa al file**

Apri `api/routers/classes.py`. Modifica l'import da `api.schemas.common` per includere i nuovi schemi:

Prima:
```python
from api.schemas.common import (
    CharacterClassCreate,
    CharacterClassRead,
    CharacterClassUpdate,
    ClassResourceCreate,
    ClassResourceRead,
    ClassResourceUpdate,
)
```

Dopo:
```python
from api.schemas.common import (
    CharacterClassCreate,
    CharacterClassRead,
    CharacterClassUpdate,
    ClassDistribute,
    ClassResourceCreate,
    ClassResourceRead,
    ClassResourceUpdate,
)
```

Aggiungi inoltre in testa (se non presente):

```python
from core.data.xp_thresholds import xp_to_level
from core.game.stats import total_base_hp
from api.routers._helpers import effective_con_mod
```

Verifica: `hit_points_for_level` è già importato al Task 4.1 originale (linea 30). `effective_con_mod` è già esportato da `api.routers._helpers` (vedi `api/routers/items.py:22`).

- [ ] **Step 2: Aggiungere la route dopo `remove_class`**

Individua la funzione `remove_class` (circa linea 151). Dopo la sua chiusura ma prima della sezione `# Class Resources`, inserisci:

```python
@router.patch("/{char_id}/classes/distribute", response_model=CharacterFull)
async def distribute_class_levels(
    char_id: int,
    body: ClassDistribute,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CharacterFull:
    """Atomically redistribute class levels.

    Validates that:
    1. Every entry's `class_id` belongs to the character.
    2. The body covers every existing class (no missing nor extra ids).
    3. `sum(level)` equals `xp_to_level(char.experience_points)`.

    On success, updates each class's level, syncs predefined class
    resources (grow or shrink via `update_resources_for_level`),
    and recalculates HP proportionally if `settings.hp_auto_calc` is true.
    """
    char = await _get_owned_full(char_id, user_id, session)

    existing_ids = {cls.id for cls in char.classes}
    body_ids = {entry.class_id for entry in body.classes}
    if existing_ids != body_ids:
        raise HTTPException(status_code=400, detail="classes_mismatch")

    target_sum = xp_to_level(char.experience_points or 0)
    new_sum = sum(entry.level for entry in body.classes)
    if new_sum != target_sum:
        raise HTTPException(status_code=400, detail="sum_mismatch")

    # Map id -> new_level for O(1) lookup
    new_levels = {entry.class_id: entry.level for entry in body.classes}

    # Snapshot old total HP for ratio scaling
    old_total_hp = char.hit_points or 0
    old_current_hp = char.current_hit_points or 0

    # Apply level changes + resource sync
    for cls in char.classes:
        new_level = new_levels[cls.id]
        if new_level == cls.level:
            continue
        cls.level = new_level
        update_resources_for_level(
            cls.class_name, new_level, list(cls.resources), char
        )
        existing_names = {r.name for r in cls.resources}
        for res_data in get_resources_for_class(cls.class_name, new_level, char):
            if res_data["name"] not in existing_names:
                session.add(ClassResource(class_id=cls.id, **res_data))

    # HP recalc (respecting hp_auto_calc); populate hp_gained for toast parity with PATCH /xp
    settings = char.settings or {}
    hp_gained = 0
    if settings.get("hp_auto_calc", True):
        con_mod = effective_con_mod(char)
        new_total_hp = total_base_hp(char.classes, con_mod)
        if old_total_hp > 0:
            ratio = old_current_hp / old_total_hp
            new_current = round(ratio * new_total_hp)
        else:
            new_current = old_current_hp
        hp_gained = max(0, new_total_hp - old_total_hp)
        char.hit_points = new_total_hp
        char.current_hit_points = max(0, min(new_current, new_total_hp))

    await session.flush()
    result = CharacterFull.model_validate(char)
    if hp_gained > 0:
        result.hp_gained = hp_gained
    return result
```

- [ ] **Step 3: Verifica che `get_resources_for_class`/`update_resources_for_level` siano già importati**

All'inizio del file (linea 24-29) dovrebbe già esserci:

```python
from core.data.classes import (
    CLASS_HIT_DIE,
    CLASS_SPELLCASTING,
    get_resources_for_class,
    update_resources_for_level,
)
```

Se manca qualche simbolo, aggiungilo.

- [ ] **Step 4: Validazione statica Python (user da Windows)**

Chiedi all'utente di eseguire da Windows:

```bash
uv run python -c "from api.routers import classes; print('ok')"
```

Expected: stampa `ok`. Se ImportError, sistemare gli import.

- [ ] **Step 5: Commit**

```bash
git add api/routers/classes.py
git commit -m "feat(api): atomic PATCH /classes/distribute endpoint

Validates {class_id, level} array covers all existing classes and
sum == xp_to_level(xp). Applies level changes + resource sync via
update_resources_for_class; recalcs HP proportionally if
settings.hp_auto_calc=true. Single transaction, all-or-nothing.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: FE API client `api.classes.distribute`

**Files:**
- Modify: `webapp/src/api/client.ts`

- [ ] **Step 1: Aggiungere `distribute` nella sezione `classes`**

Apri `webapp/src/api/client.ts`. Individua l'oggetto `classes:` (circa linee 242-272). Subito dopo `remove`, prima di `addResource`, aggiungi:

Prima:
```ts
    remove: (charId: number, classId: number) =>
      request<CharacterFull>(`/characters/${charId}/classes/${classId}`, {
        method: 'DELETE',
      }),
    addResource: (charId: number, classId: number, data: Record<string, unknown>) =>
```

Dopo:
```ts
    remove: (charId: number, classId: number) =>
      request<CharacterFull>(`/characters/${charId}/classes/${classId}`, {
        method: 'DELETE',
      }),
    distribute: (charId: number, classes: { class_id: number; level: number }[]) =>
      request<CharacterFull>(`/characters/${charId}/classes/distribute`, {
        method: 'PATCH',
        body: JSON.stringify({ classes }),
      }),
    addResource: (charId: number, classId: number, data: Record<string, unknown>) =>
```

- [ ] **Step 2: Commit**

```bash
git add webapp/src/api/client.ts
git commit -m "feat(webapp): api.classes.distribute() helper

POSTs { classes: [{class_id, level}] } to the new distribute endpoint
and returns CharacterFull.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: `LevelUpBanner.tsx` shared component

**Files:**
- Create: `webapp/src/pages/multiclass/LevelUpBanner.tsx`

- [ ] **Step 1: Creare il file con il contenuto completo**

Crea `webapp/src/pages/multiclass/LevelUpBanner.tsx`:

```tsx
import { m } from 'framer-motion'
import { useTranslation } from 'react-i18next'
import { Sparkles } from 'lucide-react'
import { spring } from '@/styles/motion'
import { haptic } from '@/auth/telegram'

interface LevelUpBannerProps {
  onOpen: () => void
  className?: string
}

export default function LevelUpBanner({ onOpen, className = '' }: LevelUpBannerProps) {
  const { t } = useTranslation()

  const handleClick = () => {
    haptic.medium()
    onOpen()
  }

  return (
    <m.button
      type="button"
      onClick={handleClick}
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={spring.elastic}
      whileTap={{ scale: 0.97 }}
      aria-label={t('character.xp.level_up_available')}
      className={`w-full rounded-2xl bg-gradient-gold border border-dnd-gold text-dnd-ink
                  px-4 py-3 text-sm font-cinzel uppercase tracking-wider
                  flex items-center justify-center gap-2 shadow-parchment-lg
                  hover:brightness-110 transition ${className}`}
    >
      <Sparkles size={16} className="animate-shimmer" />
      {t('character.xp.level_up_available')}
    </m.button>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add webapp/src/pages/multiclass/LevelUpBanner.tsx
git commit -m "feat(webapp): LevelUpBanner shared clickable banner

Replaces the static level_up_available motion.div with a button that
fires onOpen on tap. Used by both Experience.tsx and Multiclass.tsx.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: `LevelUpModal.tsx`

**Files:**
- Create: `webapp/src/pages/multiclass/LevelUpModal.tsx`

- [ ] **Step 1: Creare il file con il contenuto completo**

Crea `webapp/src/pages/multiclass/LevelUpModal.tsx`:

```tsx
import { useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { ChevronsUp } from 'lucide-react'
import { api } from '@/api/client'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import { toast } from 'sonner'
import { haptic } from '@/auth/telegram'
import classProgression from '@/data/class-progression.json'
import type { CharacterFull, CharacterClass } from '@/types'

type ProgressionEntry = {
  features: string
  proficiency_bonus: number
  spell_slots: number[] | null
}

type ClassProgression = Record<string, ProgressionEntry[]>

const PROGRESSION = classProgression as ClassProgression

interface LevelUpModalProps {
  char: CharacterFull
  xpLevel: number
  onClose: () => void
}

export default function LevelUpModal({ char, xpLevel, onClose }: LevelUpModalProps) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const classes: CharacterClass[] = char.classes ?? []
  const [selectedClassId, setSelectedClassId] = useState<number>(classes[0]?.id ?? 0)

  const selectedClass = useMemo(
    () => classes.find((c) => c.id === selectedClassId) ?? classes[0],
    [classes, selectedClassId],
  )
  const selectedAtMax = !!selectedClass && selectedClass.level >= 20

  const distribute = useMutation({
    mutationFn: () => {
      if (!selectedClass) return Promise.reject(new Error('no class selected'))
      const payload = classes.map((c) => ({
        class_id: c.id,
        level: c.id === selectedClass.id ? c.level + 1 : c.level,
      }))
      return api.classes.distribute(char.id, payload)
    },
    onSuccess: (updated) => {
      qc.setQueryData(['character', char.id], updated)
      haptic.success()
      if ((updated as any).hp_gained && (updated as any).hp_gained > 0) {
        toast.success(t('character.xp.hp_gained_toast', { hp: (updated as any).hp_gained }), {
          duration: 2000,
          icon: '❤',
        })
      }
      onClose()
    },
    onError: () => haptic.error(),
  })

  if (!selectedClass) return null

  const nextLevels = useMemo(() => {
    const out: number[] = []
    for (let i = 1; i <= 3; i++) {
      const target = selectedClass.level + i
      if (target <= 20) out.push(target)
    }
    return out
  }, [selectedClass])

  const entriesForClass = PROGRESSION[selectedClass.class_name]

  return (
    <div
      className="fixed inset-0 bg-black/70 z-50 flex items-end sm:items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <m.div
        initial={{ y: 40, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        className="w-full max-w-lg max-h-[90vh] overflow-y-auto"
      >
        <Surface variant="tome" ornamented className="space-y-4">
          {/* Header */}
          <div className="text-center">
            <h2 className="font-display text-2xl font-black text-dnd-gold-bright uppercase tracking-widest">
              {t('character.multiclass.level_up.title')}
            </h2>
            <p className="text-xs text-dnd-text-muted mt-1 font-body italic">
              {t('character.multiclass.level_up.subtitle', { level: xpLevel })}
            </p>
          </div>

          {/* Preview unlocks */}
          <Surface variant="flat" className="space-y-3">
            <p className="text-[10px] font-cinzel uppercase tracking-[0.3em] text-dnd-gold-dim text-center">
              {t('character.multiclass.level_up.preview_next_levels')}
            </p>
            {!entriesForClass ? (
              <p className="text-sm text-dnd-text-muted italic text-center">
                {t('character.multiclass.level_up.progression_missing')}
              </p>
            ) : (
              nextLevels.map((targetLevel) => {
                const curr = entriesForClass[targetLevel - 1]
                const prev = entriesForClass[targetLevel - 2] ?? null
                const pbChanged = prev && curr.proficiency_bonus !== prev.proficiency_bonus
                const newSlotLevels: number[] = []
                if (curr.spell_slots && prev?.spell_slots) {
                  curr.spell_slots.forEach((count, i) => {
                    if (count > 0 && prev.spell_slots![i] === 0) newSlotLevels.push(i + 1)
                  })
                } else if (curr.spell_slots && !prev?.spell_slots) {
                  curr.spell_slots.forEach((count, i) => {
                    if (count > 0) newSlotLevels.push(i + 1)
                  })
                }
                return (
                  <div key={targetLevel} className="flex gap-3 items-start">
                    <div className="w-10 text-center">
                      <p className="text-xs text-dnd-gold-dim font-cinzel">Liv</p>
                      <p className="font-display font-black text-2xl text-dnd-gold-bright leading-none">
                        {targetLevel}
                      </p>
                    </div>
                    <div className="flex-1 space-y-1">
                      <p className="text-sm text-dnd-text font-body">{curr.features || '—'}</p>
                      {pbChanged && (
                        <p className="text-xs text-dnd-gold font-mono">
                          {t('character.multiclass.level_up.proficiency_change', {
                            from: prev!.proficiency_bonus,
                            to: curr.proficiency_bonus,
                          })}
                        </p>
                      )}
                      {newSlotLevels.map((lvl) => (
                        <p key={lvl} className="text-xs text-dnd-arcane-bright font-mono">
                          {t('character.multiclass.level_up.new_spell_slot', { level: lvl })}
                        </p>
                      ))}
                    </div>
                  </div>
                )
              })
            )}
          </Surface>

          {/* Class selector */}
          <div className="flex gap-2 flex-wrap">
            {classes.map((cls) => {
              const active = cls.id === selectedClassId
              return (
                <button
                  key={cls.id}
                  type="button"
                  onClick={() => setSelectedClassId(cls.id)}
                  className={`min-h-[44px] px-3 rounded-xl font-cinzel text-xs uppercase tracking-widest flex-1 min-w-[100px] transition-colors
                    ${active
                      ? 'bg-gradient-gold text-dnd-ink shadow-engrave border border-dnd-gold'
                      : 'bg-dnd-surface text-dnd-text border border-dnd-border hover:border-dnd-gold/60'}`}
                >
                  {cls.class_name}
                  <span className="ml-1 opacity-70 font-mono">{cls.level}</span>
                </button>
              )
            })}
          </div>

          {/* Confirm */}
          <Button
            variant="primary"
            size="lg"
            fullWidth
            onClick={() => {
              if (selectedAtMax) {
                toast.info(t('character.multiclass.level_up.at_max_toast'))
                return
              }
              distribute.mutate()
            }}
            disabled={selectedAtMax}
            loading={distribute.isPending}
            icon={<ChevronsUp size={18} />}
            haptic="medium"
          >
            {t('character.multiclass.level_up.confirm')}
          </Button>
        </Surface>
      </m.div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add webapp/src/pages/multiclass/LevelUpModal.tsx
git commit -m "feat(webapp): LevelUpModal for multiclass level-up (§2.1)

Preview next 3 level unlocks (features, proficiency delta, new spell
slot levels) for the selected class. Confirm bumps the chosen class
+1 via api.classes.distribute, preserving other class levels.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: `EditClassesModal.tsx`

**Files:**
- Create: `webapp/src/pages/multiclass/EditClassesModal.tsx`

- [ ] **Step 1: Creare il file con il contenuto completo**

Crea `webapp/src/pages/multiclass/EditClassesModal.tsx`:

```tsx
import { useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Check } from 'lucide-react'
import { toast } from 'sonner'
import { api } from '@/api/client'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import { haptic } from '@/auth/telegram'
import type { CharacterFull, CharacterClass } from '@/types'

interface EditClassesModalProps {
  char: CharacterFull
  targetLevel: number
  onClose: () => void
}

export default function EditClassesModal({ char, targetLevel, onClose }: EditClassesModalProps) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const classes: CharacterClass[] = char.classes ?? []

  const [draft, setDraft] = useState<Record<number, number>>(
    Object.fromEntries(classes.map((c) => [c.id, c.level])),
  )

  const currentSum = useMemo(
    () => Object.values(draft).reduce((s, v) => s + (Number.isFinite(v) ? v : 0), 0),
    [draft],
  )
  const isValid = currentSum === targetLevel && Object.values(draft).every((v) => v >= 1 && v <= 20)

  const distribute = useMutation({
    mutationFn: () => {
      const payload = Object.entries(draft).map(([id, lv]) => ({
        class_id: Number(id),
        level: lv,
      }))
      return api.classes.distribute(char.id, payload)
    },
    onSuccess: (updated) => {
      qc.setQueryData(['character', char.id], updated)
      haptic.success()
      onClose()
    },
    onError: () => {
      haptic.error()
      toast.error(t('character.multiclass.edit.error_server'))
    },
  })

  const setLevel = (classId: number, level: number) => {
    const clamped = Math.max(1, Math.min(20, Math.round(level)))
    setDraft((d) => ({ ...d, [classId]: clamped }))
  }

  return (
    <div
      className="fixed inset-0 bg-black/70 z-50 flex items-end sm:items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <m.div
        initial={{ y: 40, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        className="w-full max-w-lg max-h-[90vh] overflow-y-auto"
      >
        <Surface variant="tome" ornamented className="space-y-4">
          <div className="text-center">
            <h2 className="font-display text-2xl font-black text-dnd-gold-bright uppercase tracking-widest">
              {t('character.multiclass.edit.title')}
            </h2>
            <p className="text-xs text-dnd-text-muted mt-1 font-body italic">
              {t('character.multiclass.edit.hint', { target: targetLevel })}
            </p>
          </div>

          {/* Sum indicator */}
          <div className={`text-center py-3 rounded-xl border transition-colors
              ${isValid
                ? 'bg-dnd-surface border-dnd-gold text-dnd-gold-bright'
                : 'bg-dnd-surface border-[var(--dnd-crimson)]/60 text-[var(--dnd-crimson-bright)]'}`}
          >
            <p className="text-[10px] font-cinzel uppercase tracking-[0.3em] opacity-80">
              {t('character.multiclass.edit.sum_label')}
            </p>
            <p className="font-display font-black text-3xl">
              {t('character.multiclass.edit.sum_display', { current: currentSum, target: targetLevel })}
            </p>
          </div>

          {/* Class rows */}
          <div className="space-y-2">
            {classes.map((cls) => (
              <Surface key={cls.id} variant="elevated" className="flex items-center gap-3 !py-2 !px-3">
                <div className="flex-1 min-w-0">
                  <p className="font-display font-bold text-dnd-gold-bright truncate">{cls.class_name}</p>
                  {cls.subclass && (
                    <p className="text-xs text-dnd-text-muted italic truncate">{cls.subclass}</p>
                  )}
                </div>
                <input
                  type="number"
                  inputMode="numeric"
                  min={1}
                  max={20}
                  value={draft[cls.id] ?? cls.level}
                  onChange={(e) => setLevel(cls.id, Number(e.target.value))}
                  className="w-20 min-h-[44px] rounded-lg bg-dnd-surface border border-dnd-border text-dnd-gold-bright font-mono text-center"
                  aria-label={`${cls.class_name} level`}
                />
              </Surface>
            ))}
          </div>

          {/* Footer */}
          <div className="grid grid-cols-2 gap-2">
            <Button variant="ghost" size="md" fullWidth onClick={onClose}>
              {t('character.multiclass.edit.cancel')}
            </Button>
            <Button
              variant="primary"
              size="md"
              fullWidth
              disabled={!isValid}
              loading={distribute.isPending}
              icon={<Check size={16} />}
              haptic="success"
              onClick={() => distribute.mutate()}
            >
              {t('character.multiclass.edit.confirm')}
            </Button>
          </div>
        </Surface>
      </m.div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add webapp/src/pages/multiclass/EditClassesModal.tsx
git commit -m "feat(webapp): EditClassesModal atomic redistribute (§2.2)

Numeric-input editor for class levels with live sum indicator vs.
target (levelFromXp). Confirm disabled unless sum == target. Calls
api.classes.distribute() atomically.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Integrate clickable banner in `Experience.tsx`

**Files:**
- Modify: `webapp/src/pages/Experience.tsx`

- [ ] **Step 1: Aggiornare gli import**

Apri `webapp/src/pages/Experience.tsx`. Rimuovi `Sparkles` dall'import `lucide-react` (non più usato direttamente qui, passa al banner component):

Prima:
```tsx
import { Sparkles, Star, Check, ChevronsUp } from 'lucide-react'
```

Dopo:
```tsx
import { Star, Check, ChevronsUp } from 'lucide-react'
```

Rimuovi `spring` dall'import `@/styles/motion` solo se non usato altrove nel file (verifica prima: se compare in altri blocchi, lascialo). Non rimuovere `m` da `framer-motion`.

Aggiungi in fondo agli import:

```tsx
import LevelUpBanner from '@/pages/multiclass/LevelUpBanner'
import LevelUpModal from '@/pages/multiclass/LevelUpModal'
```

Aggiungi import `useState` a quelli di React, se non già presente:

Prima:
```tsx
import { useState } from 'react'
```

(è già importato — verifica senza modificare se già presente).

- [ ] **Step 2: Aggiungere state per il modal**

Dopo `const [setMode, setSetMode] = useState(false)` (circa linea 24), aggiungi:

```tsx
  const [showLevelUpModal, setShowLevelUpModal] = useState(false)
```

- [ ] **Step 3: Sostituire il banner statico con `LevelUpBanner`**

Individua il blocco:

```tsx
      {/* Level-up notification */}
      {levelUpAvailable && (
        <m.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={spring.elastic}
          className="rounded-2xl bg-gradient-gold border border-dnd-gold text-dnd-ink px-4 py-3 text-sm font-cinzel uppercase tracking-wider flex items-center gap-2 shadow-parchment-lg"
        >
          <Sparkles size={16} className="animate-shimmer" />
          {t('character.xp.level_up_available')}
        </m.div>
      )}
```

Sostituiscilo con:

```tsx
      {/* Level-up notification — clickable for multiclass */}
      {levelUpAvailable && (
        <LevelUpBanner onOpen={() => setShowLevelUpModal(true)} />
      )}
```

- [ ] **Step 4: Renderizzare il modal**

Prima della chiusura `</Layout>` in fondo al JSX, aggiungi:

```tsx
      {showLevelUpModal && (
        <LevelUpModal
          char={char}
          xpLevel={level}
          onClose={() => setShowLevelUpModal(false)}
        />
      )}
```

- [ ] **Step 5: Commit**

```bash
git add webapp/src/pages/Experience.tsx
git commit -m "feat(webapp): Experience banner clickable opens LevelUpModal

Multiclass level-up banner now a button; click opens LevelUpModal to
pick the class for the next level (Gruppo G §2.1).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: Refactor `Multiclass.tsx` — remove +/-, add Edit button, integrate banner + modals

**Files:**
- Modify: `webapp/src/pages/Multiclass.tsx`

- [ ] **Step 1: Aggiornare gli import**

Sostituisci il blocco import completo in testa al file con:

```tsx
import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Plus, X, Swords, Scroll, Edit3 } from 'lucide-react'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import StatPill from '@/components/ui/StatPill'
import { FlourishDivider } from '@/components/ui/Ornament'
import { haptic } from '@/auth/telegram'
import { levelFromXp } from '@/lib/xpThresholds'
import AddClassForm, { resolveClassName, PREDEFINED_CLASSES, CUSTOM_KEY, type ClassForm } from '@/pages/multiclass/AddClassForm'
import ResourceManager from '@/pages/multiclass/ResourceManager'
import LevelUpBanner from '@/pages/multiclass/LevelUpBanner'
import LevelUpModal from '@/pages/multiclass/LevelUpModal'
import EditClassesModal from '@/pages/multiclass/EditClassesModal'
import type { CharacterClass } from '@/types'
```

(Rimossi: `Minus` — non più usato; `useState` rimasto da `useState` hooks già presenti. `useMemo` aggiunto per `targetLevel`.)

- [ ] **Step 2: Aggiungere state modals + rimuovere `updateLevel` mutation**

Individua la sezione dopo `const [showAddClass, setShowAddClass] = useState(false)`. Aggiungi:

```tsx
  const [showLevelUpModal, setShowLevelUpModal] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)
```

Individua e rimuovi l'intero blocco `updateLevel` (circa linee 52-56):

```tsx
  const updateLevel = useMutation({
    mutationFn: ({ classId, level }: { classId: number; level: number }) =>
      api.classes.update(charId, classId, { level: Math.max(1, level) }),
    onSuccess: (updated) => qc.setQueryData(['character', charId], updated),
  })
```

Non serve più: i level changes avvengono solo via modali.

- [ ] **Step 3: Calcolare `targetLevel` derivato dall'XP**

Individua il blocco dopo `if (!char) return null`. Sostituisci il calcolo `totalLevel` con:

Prima:
```tsx
  const classes: CharacterClass[] = char.classes ?? []
  const totalLevel = classes.reduce((s, c) => s + c.level, 0)
```

Dopo:
```tsx
  const classes: CharacterClass[] = char.classes ?? []
  const classLevelSum = useMemo(() => classes.reduce((s, c) => s + c.level, 0), [classes])
  const targetLevel = levelFromXp(char.experience_points ?? 0)
  const levelUpAvailable = classes.length > 0 && targetLevel > classLevelSum
```

- [ ] **Step 4: Aggiungere banner clickable + bottone "Edit classes"**

Individua il bottone `Aggiungi classe` esistente (circa linee 107-116). Sostituisci il blocco con:

Prima:
```tsx
      <Button
        variant="primary"
        size="lg"
        fullWidth
        onClick={() => setShowAddClass(true)}
        icon={<Plus size={18} />}
        haptic="medium"
      >
        {t('character.multiclass.add_class')}
      </Button>
```

Dopo:
```tsx
      {levelUpAvailable && (
        <LevelUpBanner onOpen={() => setShowLevelUpModal(true)} />
      )}

      <div className="grid grid-cols-2 gap-2">
        <Button
          variant="primary"
          size="md"
          onClick={() => setShowAddClass(true)}
          icon={<Plus size={16} />}
          haptic="medium"
        >
          {t('character.multiclass.add_class')}
        </Button>
        <Button
          variant="secondary"
          size="md"
          onClick={() => setShowEditModal(true)}
          disabled={classes.length < 2}
          icon={<Edit3 size={16} />}
          haptic="medium"
        >
          {t('character.multiclass.edit_classes')}
        </Button>
      </div>
```

- [ ] **Step 5: Aggiornare hero "Livello totale" per usare `targetLevel`**

Individua il blocco hero (circa linee 94-105):

```tsx
      {classes.length > 0 && (
        <Surface variant="tome" ornamented className="text-center">
          <p className="text-[10px] font-cinzel uppercase tracking-[0.3em] text-dnd-gold-dim mb-1">
            {t('character.multiclass.total_level', { defaultValue: 'Livello totale' })}
          </p>
          <p className="text-5xl font-display font-black text-dnd-gold-bright"
             style={{ textShadow: '0 2px 8px var(--dnd-gold-glow)' }}>
            {totalLevel}
          </p>
        </Surface>
      )}
```

Sostituisci `{totalLevel}` con `{targetLevel}` per mostrare il livello derivato dall'XP (source of truth):

```tsx
          <p className="text-5xl font-display font-black text-dnd-gold-bright"
             style={{ textShadow: '0 2px 8px var(--dnd-gold-glow)' }}>
            {targetLevel}
          </p>
```

- [ ] **Step 6: Rimuovere i controlli +/- e pip tracker dentro ogni class card**

Individua il blocco level controls + pip tracker (circa linee 164-203):

```tsx
              {/* Level pip tracker (1-20) + controls */}
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <p className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim flex-1">
                    {t('character.multiclass.level', { defaultValue: 'Livello' })}
                  </p>
                  <m.button
                    onClick={() => updateLevel.mutate({ classId: cls.id, level: cls.level - 1 })}
                    disabled={cls.level <= 1}
                    className="w-8 h-8 rounded-lg bg-dnd-surface border border-dnd-border flex items-center justify-center text-dnd-gold disabled:opacity-30"
                    whileTap={{ scale: 0.9 }}
                  >
                    <Minus size={14} />
                  </m.button>
                  <span className="w-10 text-center font-display font-black text-xl text-dnd-gold-bright">{cls.level}</span>
                  <m.button
                    onClick={() => updateLevel.mutate({ classId: cls.id, level: cls.level + 1 })}
                    disabled={cls.level >= 20}
                    className="w-8 h-8 rounded-lg bg-dnd-surface border border-dnd-border flex items-center justify-center text-dnd-gold disabled:opacity-30"
                    whileTap={{ scale: 0.9 }}
                  >
                    <Plus size={14} />
                  </m.button>
                </div>
                {/* 20 pip level track */}
                <div className="flex gap-0.5">
                  {Array.from({ length: 20 }).map((_, i) => {
                    const filled = i < cls.level
                    return (
                      <div
                        key={i}
                        className={`flex-1 h-1.5 rounded-full transition-colors
                          ${filled
                            ? 'bg-gradient-to-r from-dnd-gold-dim to-dnd-gold-bright shadow-[0_0_3px_var(--dnd-gold-glow)]'
                            : 'bg-dnd-ink/50 border border-dnd-border'}`}
                      />
                    )
                  })}
                </div>
              </div>
```

Sostituiscilo con un display read-only del livello:

```tsx
              {/* Level display (read-only; change via modals) */}
              <div className="flex items-center gap-2">
                <p className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim flex-1">
                  {t('character.multiclass.level')}
                </p>
                <span className="font-display font-black text-2xl text-dnd-gold-bright">
                  {cls.level}
                </span>
              </div>
```

- [ ] **Step 7: Renderizzare i modali in fondo al JSX**

Individua il blocco `{showAddClass && (...)}` in fondo al JSX. Subito dopo il relativo `)}`, aggiungi:

```tsx
      {showLevelUpModal && (
        <LevelUpModal
          char={char}
          xpLevel={targetLevel}
          onClose={() => setShowLevelUpModal(false)}
        />
      )}

      {showEditModal && (
        <EditClassesModal
          char={char}
          targetLevel={targetLevel}
          onClose={() => setShowEditModal(false)}
        />
      )}
```

- [ ] **Step 8: Verifica TypeScript (user da Windows)**

```bash
cd webapp
npx tsc --noEmit
```

Expected: nessun errore. Se errori su `useMemo`/`levelFromXp`/imports rimossi, correggi.

- [ ] **Step 9: Commit**

```bash
git add webapp/src/pages/Multiclass.tsx
git commit -m "feat(webapp): Multiclass page integrates G modals, drops +/-

- Add 'Edit classes' button (disabled <2 classes).
- Replace per-class +/- buttons and pip tracker with read-only level.
- Hero total level uses levelFromXp (XP-derived) as source of truth.
- Banner clickable opens LevelUpModal; Edit button opens EditClassesModal.
- Remove updateLevel mutation (all level changes now via modals).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 11: i18n keys IT + EN

**Files:**
- Modify: `webapp/src/locales/it.json`
- Modify: `webapp/src/locales/en.json`

- [ ] **Step 1: Aggiungere chiavi in `it.json`**

Apri `webapp/src/locales/it.json`. Individua il blocco `"multiclass": { ... }` sotto `"character"`. Aggiungi le seguenti chiavi **dentro** `"multiclass"` (in fondo, prima di `}` che chiude il blocco `multiclass`):

```json
"edit_classes": "Modifica classe",
"level_up": {
  "title": "Sali di livello",
  "subtitle": "Scegli la classe per il livello {{level}}",
  "preview_next_levels": "Prossimi sblocchi",
  "proficiency_change": "Bonus competenza: +{{from}} → +{{to}}",
  "new_spell_slot": "Nuovo slot di {{level}}° livello",
  "confirm": "Conferma",
  "at_max_toast": "Classe al livello massimo",
  "progression_missing": "Dati progressione non disponibili"
},
"edit": {
  "title": "Modifica classe",
  "hint": "La somma dei livelli deve essere {{target}}",
  "sum_label": "Somma livelli",
  "sum_display": "{{current}} / {{target}}",
  "confirm": "Conferma",
  "cancel": "Annulla",
  "error_server": "Errore nel server, riprova."
}
```

(Totale: 13 nuove chiavi incluse `edit_classes`.)

Attenzione: ricordati di aggiungere la virgola di separazione dopo l'ultima chiave esistente prima del nuovo blocco. Verifica che tutte le virgole siano corrette.

- [ ] **Step 2: Aggiungere chiavi in `en.json`**

Apri `webapp/src/locales/en.json`. Stessa posizione sotto `character.multiclass`:

```json
"edit_classes": "Edit classes",
"level_up": {
  "title": "Level up",
  "subtitle": "Pick a class for level {{level}}",
  "preview_next_levels": "Next unlocks",
  "proficiency_change": "Proficiency: +{{from}} → +{{to}}",
  "new_spell_slot": "New {{level}}th level spell slot",
  "confirm": "Confirm",
  "at_max_toast": "Class at max level",
  "progression_missing": "Progression data unavailable"
},
"edit": {
  "title": "Edit classes",
  "hint": "Level sum must be {{target}}",
  "sum_label": "Level sum",
  "sum_display": "{{current}} / {{target}}",
  "confirm": "Confirm",
  "cancel": "Cancel",
  "error_server": "Server error, try again."
}
```

- [ ] **Step 3: Validare JSON**

```bash
python3 -c "import json; json.load(open('webapp/src/locales/it.json')); json.load(open('webapp/src/locales/en.json')); print('ok')"
```

Expected: `ok`, exit 0.

- [ ] **Step 4: Commit**

```bash
git add webapp/src/locales/it.json webapp/src/locales/en.json
git commit -m "feat(webapp): i18n keys for multiclass level-up + edit modals

+13 keys IT/EN under character.multiclass: edit_classes, level_up.*,
edit.*. Consumed by Gruppo G modals.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 12: Manual verification (utente)

**Files:** nessuno modificato.

L'utente esegue lo stack locale (Windows) e verifica tutti gli scenari della spec §5.

- [ ] **Step 1: Avviare stack locale**

Terminal 1 (Windows):
```bash
uv run uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

Terminal 2 (Windows):
```bash
cd webapp && npm run dev
```

Apri `http://localhost:5173/`.

- [ ] **Step 2: Scenario 1 — parser output**

In WSL o Windows:

```bash
python3 -c "import json; d = json.load(open('webapp/src/data/class-progression.json')); print(len(d), 'classes'); print([(k, len(v)) for k,v in d.items()])"
```

Expected: `12 classes` + `[('Barbaro', 20), ('Bardo', 20), ..., ('Mago', 20)]`.

- [ ] **Step 3: Scenario 2 — level-up single-class (regressione F)**

Crea/apri personaggio single-class. Vai su `/xp`, click LEVEL UP. Expected: XP aumenta, class level +1, toast `+N HP`, nessuna modale aperta.

- [ ] **Step 4: Scenario 3 — level-up multiclass happy path**

Personaggio Chierico 3 / Guerriero 2 (liv totale 5). Vai su `/xp`. Aggiungi XP fino a liv 6 (es. click LEVEL UP se disponibile, o SET mode `14000`). Banner "livello disponibile" visibile + clickable. Click banner → modale aperta.

Verifica:
- Titolo "Sali di livello" + subtitle "Scegli la classe per il livello 6".
- Preview: Chierico pre-selezionato, mostra liv 4, 5, 6 features.
- Click "Guerriero" → preview cambia a liv 3, 4, 5 di Guerriero.
- Click Conferma con Chierico selezionato → modale chiude, classe Chierico = 4, Guerriero = 2, toast `+N HP`.

- [ ] **Step 5: Scenario 4 — level-up multi-pending**

Stesso char con liv 5 attuale. SET XP direttamente a 23000 (liv 7 threshold). Banner visibile. Click → modale. Conferma Chierico. Dopo commit, banner riappare (liv 7 > 6). Click di nuovo → modale seconda volta. Conferma Guerriero. Banner scompare (liv 7 == sum classi).

- [ ] **Step 6: Scenario 5 — Modifica classe happy path**

Personaggio Chierico 18 / Guerriero 1 (liv totale 19). Vai su `/char/{id}/classes`. Click "Modifica classe" → modale aperta.

Verifica:
- Titolo "Modifica classe" + hint "La somma dei livelli deve essere 19".
- Sum indicator: "19 / 19" gold.
- Cambia Chierico input a 17: sum "18 / 19" crimson, Conferma disabled.
- Cambia Guerriero input a 2: sum "19 / 19" gold, Conferma enabled.
- Click Conferma → modale chiude, classi Chierico=17 / Guerriero=2, HP ricalcolato proporzionalmente.

- [ ] **Step 7: Scenario 6 — Modifica classe HP ratio**

Setta manualmente (da DB o via SET XP) char con HP 50/100 prima di redistribute. Dopo redistribute che porta max HP a 105, current dovrebbe diventare 53 (`round(50 * 105/100)`). Con `hp_auto_calc=false` in settings, HP deve restare invariato.

- [ ] **Step 8: Scenario 7 — Edit bloccato 1 classe**

Personaggio con 1 sola classe. Vai su `/char/{id}/classes`. Bottone "Modifica classe" visibile ma **disabled**.

- [ ] **Step 9: Scenario 8 — Rimozione +/- e pip**

Apri `/char/{id}/classes` con personaggio multiclass. Verifica che:
- Nelle card di classe non ci sono più bottoni +/- accanto al livello.
- Non c'è più il pip tracker (20 pallini) sotto.
- Livello mostrato come numero grande read-only.

- [ ] **Step 10: Scenario 9 — Classe a liv 20**

Personaggio con una classe a liv 20 + altra minore. Banner level-up → modale. Seleziona classe liv 20 → Conferma disabled. Click Conferma comunque (o trigger programmatico) → toast `at_max_toast`.

- [ ] **Step 11: Scenario 10 — Progressione missing**

Se possibile, crea personaggio con classe custom (non mappata nel JSON). Apri modale level-up. Preview mostra "Dati progressione non disponibili".

- [ ] **Step 12: Firma verifica**

Se tutti gli scenari passano: task completato. Se fallisce qualche scenario, NON marcare completato: apri bug, torna al Task corrispondente.

---

### Task 13: `npm run build:prod` + PR

**Files:**
- Modify: `docs/app/`

- [ ] **Step 1: Build di produzione (utente Windows)**

```bash
cd webapp
npm run build:prod
```

Expected: script completa senza errori. Rebuild `docs/app/` + git add automatico.

- [ ] **Step 2: Verifica staging**

```bash
git status
```

Expected: file sotto `docs/app/` staged. `.env.local` NON staged.

- [ ] **Step 3: Commit build output**

```bash
git commit -m "chore(webapp): rebuild docs/app for Gruppo G

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 4: Push branch**

```bash
git push -u origin feat/multiclass-gruppo-g
```

- [ ] **Step 5: Apri PR**

Se **Gruppo F è ancora in review / non merged**: segnalo come PR dipendente (target: `feat/xp-level-up-gruppo-f`). Altrimenti target `main`:

```bash
gh pr create --title "feat: Gruppo G — multiclasse (level-up modal + redistribute)" --body "$(cat <<'EOF'
## Summary
- Parser `scripts/parse_class_progression.py` → `webapp/src/data/class-progression.json` (12 classi × 20 livelli).
- Nuovo endpoint `PATCH /characters/{id}/classes/distribute` atomic con sum validation e HP recalc proporzionale.
- `LevelUpModal` (§2.1): preview prossimi 3 livelli della classe selezionata + bottoni classi + Conferma.
- `EditClassesModal` (§2.2): redistribuzione atomic con live sum indicator vs `levelFromXp(xp)`.
- `Multiclass.tsx`: rimossi +/- per-class e pip tracker, aggiunto bottone "Modifica classe" (disabled <2 classi).
- `LevelUpBanner` shared tra `Experience.tsx` e `Multiclass.tsx` — clickable apre modale level-up.
- i18n: +13 chiavi IT/EN sotto `character.multiclass`.

Spec: `docs/superpowers/specs/2026-04-23-multiclass-design.md`.
Plan: `docs/superpowers/plans/2026-04-23-multiclass.md`.
Roadmap: `istruzioni.md` §2.

## Test plan
- [x] Parser produce JSON valido 12 × 20.
- [x] Level-up single-class invariato (regressione F).
- [x] Level-up multiclass: banner clickable → modale, preview, class switch, Conferma.
- [x] Level-up multi-pending: modale si riapre per livelli pendenti multipli.
- [x] Modifica classe: sum validation, Conferma disabled se mismatch, HP ratio preservato.
- [x] Edit bloccato con 1 classe.
- [x] +/- e pip rimossi da class cards.
- [x] Classe a liv 20 disabled in selector; toast `at_max_toast`.
- [x] Classe custom (unmapped): preview mostra "progression_missing".

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 6: Aggiornamento roadmap post-merge**

Dopo merge della PR, in una nuova sessione o commit finale:
- Riga tabella Gruppo G: `⬜ Pending` → `✅ Done (PR #<n> merged → main)`.
- Sezione `## Gruppo G`: header `⬜` → `✅`.
- Sezione "Ordine consigliato": `→ G →` diventa `→ ✅ G →`.

---

## Verifica completa del plan

Dopo aver completato tutti i task:
- [ ] 13 commit sul branch `feat/multiclass-gruppo-g`.
- [ ] Manual verification superata (Task 12).
- [ ] `docs/app/` rigenerato e committato (Task 13).
- [ ] PR aperta e in review / merged.
- [ ] Roadmap aggiornata post-merge.
