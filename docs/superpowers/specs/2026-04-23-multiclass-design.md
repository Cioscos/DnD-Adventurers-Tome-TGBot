# Gruppo G — Multiclasse (design)

**Gruppo roadmap:** G — `istruzioni.md` §2 (sia 2.1 che 2.2).
**Data:** 2026-04-23.
**Branch:** `feat/multiclass-gruppo-g` (creato da tip di `feat/xp-level-up-gruppo-f`).
**Dipendenze:** Gruppo F ✅ (LEVEL UP button + flow XP multiclass), Gruppo B ✅ (auto-HP + `total_base_hp`, `hit_points_for_level`, flag `hp_auto_calc`).

---

## 1. Obiettivo

Due feature coordinate dalla stessa decomposizione:

- **§2.1 Level-up multiclass:** al level-up di un personaggio multiclass, mostrare una modale per scegliere su quale classe salire. La modale mostra preview dei prossimi sblocchi della classe selezionata.
- **§2.2 Modifica classe:** nuovo flow per redistribuire i livelli tra le classi esistenti di un personaggio, preservando il livello totale derivato dall'XP.

Fonte: `istruzioni.md` §2.

## 2. Scope

### In-scope

- Parser Python `scripts/parse_class_progression.py` che legge `dnd5e_classi.md` (gitignored) e produce `webapp/src/data/class-progression.json` (committato).
- Modale "Sali di livello" per multiclass (trigger da banner clickable in `/xp` e in `Multiclass.tsx`).
- Modale "Modifica classe" per redistribuzione atomic (trigger da nuovo bottone in `Multiclass.tsx`).
- Endpoint `PATCH /characters/{char_id}/classes/distribute` atomic con validazione somma e HP recalc.
- Rimozione dei controlli `+/-` e pip tracker per classe in `Multiclass.tsx`: livelli si cambiano solo via modale.
- i18n keys IT/EN.

### Fuori scope

- Multiclass prereq check D&D 5e (STR 13, CHA 13, ecc.).
- Aggiungere nuova classe dalla modale level-up (resta "Aggiungi classe" esistente, separato).
- Subclass-specific features progression (la modale usa solo colonna "Caratteristiche" main class).
- Spell slots DB sync (la preview mostra slot ma non modifica la tabella `spell_slots`).
- Warlock Pact tracking dedicato (rappresentato come regular caster con slot nel livello spell corrente del patto).

## 3. Decisioni

### 3.1 Dati di progressione

Parser Python `scripts/parse_class_progression.py`, committato. Legge `dnd5e_classi.md` e produce JSON committato in `webapp/src/data/class-progression.json`. User ri-esegue se MD cambia.

Mapping EN→IT hardcoded nello script (le 12 classi D&D 5e):

```python
EN_TO_IT = {
    "Barbarian": "Barbaro", "Bard": "Bardo", "Cleric": "Chierico",
    "Druid": "Druido", "Fighter": "Guerriero", "Monk": "Monaco",
    "Paladin": "Paladino", "Ranger": "Ranger", "Rogue": "Ladro",
    "Sorcerer": "Stregone", "Warlock": "Warlock", "Wizard": "Mago",
}
```

Shape del JSON:

```json
{
  "Barbaro": [
    { "features": "Rage, Unarmored Defense", "proficiency_bonus": 2, "spell_slots": null },
    { "features": "Reckless Attack, Danger Sense", "proficiency_bonus": 2, "spell_slots": null }
  ],
  "Chierico": [
    { "features": "Spellcasting, Divine Domain", "proficiency_bonus": 2, "spell_slots": [2,0,0,0,0,0,0,0,0] }
  ]
}
```

Array indicizzato 0..19 (livello 1..20). `spell_slots`: array di 9 ints (count per spell-level 1..9) per caster, `null` per non-caster. Warlock: slot patto mappati nel corresponding spell-level (es. Warlock liv 3 → `[0,0,2,0,0,0,0,0,0]`).

Comando per rigenerare:

```bash
uv run python scripts/parse_class_progression.py
```

### 3.2 Backend — endpoint distribute

**Nuovo:** `PATCH /characters/{char_id}/classes/distribute` in `api/routers/classes.py`.

**Pydantic schemas (aggiunti in `api/schemas/common.py`):**

```python
class ClassLevelEntry(BaseModel):
    class_id: int
    level: int = Field(ge=1, le=20)

class ClassDistribute(BaseModel):
    classes: list[ClassLevelEntry]
```

**Validation (in ordine):**

1. Ownership via `_get_owned_full(char_id, user_id, session)`.
2. Ogni `class_id` in body deve appartenere a `char.classes`. Altrimenti 403.
3. Il body deve coprire **tutte** le classi esistenti. Mismatch (missing or extra class_id) → 400 `classes_mismatch`.
4. `sum(level)` deve essere uguale a `xp_to_level(char.experience_points)`. Altrimenti 400 `sum_mismatch`.

**Apply (single transaction, atomic):**

1. Per ogni classe in body con `new_level != current_level`:
   - `cls.level = new_level`.
   - `update_resources_for_level(cls.class_name, new_level, list(cls.resources), char)`.
   - Aggiungi nuove resources via `get_resources_for_class(cls.class_name, new_level, char)` per quelle non ancora presenti (coerente con `update_class` esistente).
2. **HP recalc** (solo se `settings.hp_auto_calc=true`):
   - Calcola `new_total_hp` con `total_base_hp(char)` (Gruppo B), somma `hit_points_for_level` per ogni classe alla sua nuova `level`.
   - Se `char.hit_points > 0` preserva ratio: `new_current = round(char.current_hit_points * new_total_hp / char.hit_points)`.
   - Se `char.hit_points == 0` o ratio non calcolabile: `new_current = char.current_hit_points` (lascia invariato).
   - `char.hit_points = new_total_hp`, `char.current_hit_points = clamp(new_current, 0, new_total_hp)`.
3. Return `CharacterFull`.

**Interazione con endpoints esistenti:** `POST /classes`, `PATCH /classes/{id}`, `DELETE /classes/{id}` restano invariati (backwards compat, ancora usabili per operazioni non-atomic come add/remove class). Nuovo endpoint dedicato a level-updates atomic.

### 3.3 Level-up modal (§2.1)

**Componente:** `webapp/src/pages/multiclass/LevelUpModal.tsx`.

**Trigger:**

- In `Experience.tsx`: il banner "livello disponibile" esistente (`levelUpAvailable && isMulticlass`) diventa clickable (`<button>` wrapper). Click → apre modale.
- In `Multiclass.tsx`: lo stesso banner è replicato (quando `level > totalClassLevel`). Click → apre modale.
- Componente shared: `webapp/src/pages/multiclass/LevelUpBanner.tsx` con prop `onOpen: () => void`.

**Stato interno:**

```ts
const [selectedClassId, setSelectedClassId] = useState<number>(char.classes[0].id)
```

Prima classe pre-selezionata.

**Layout dall'alto al basso:**

1. **Header:** titolo `t('character.multiclass.level_up.title')` + subtitle `t('character.multiclass.level_up.subtitle', { level: xpLevel })` dove `xpLevel = levelFromXp(char.experience_points)`.
2. **Preview sblocchi (top section):** per la classe selezionata, mostra i prossimi **3 livelli** (clamp a 20). Per ciascun livello visualizzato:
   - Numero livello large gold.
   - `features: progression[className][targetLevel - 1].features` — stringa raw.
   - Se `proficiency_bonus(target) !== proficiency_bonus(target - 1)`, mostra `t('character.multiclass.level_up.proficiency_change', { from, to })`.
   - Per ogni slot-level `i` in `spell_slots`: se `spell_slots(target)[i] > 0 && spell_slots(target - 1)[i] === 0`, mostra `t('character.multiclass.level_up.new_spell_slot', { level: i + 1 })`.
   - Se `progression[className]` non esiste (classe custom/non mappata): mostra `t('character.multiclass.level_up.progression_missing')`.
3. **Class selector (bottom section):** una riga di bottoni (flex-wrap), uno per ogni classe esistente. La classe selezionata: gradient gold + border. Altre: surface neutro. Click → `setSelectedClassId(cls.id)`.
4. **Conferma button full-width, variant `primary`, size `lg`.** Click → `distributeMutation.mutate({ classes: char.classes.map(c => ({ class_id: c.id, level: c.id === selectedClassId ? c.level + 1 : c.level })) })`. Disabled se `selectedClassLevel >= 20`.

**Multi-pending levels:** se dopo il confirm resta `levelFromXp(xp) > sum(class_levels)`, la modale si ri-apre (gestito da `useEffect` del componente ospite).

**Accessibility:** backdrop click → close; ESC key → close; `role="dialog"`, `aria-modal="true"`, focus trap sul primo bottone classe.

### 3.4 Modifica classe modal (§2.2)

**Componente:** `webapp/src/pages/multiclass/EditClassesModal.tsx`.

**Trigger:** nuovo bottone `Edit classes` in `Multiclass.tsx`, accanto al bottone `Add class` esistente:

```tsx
<div className="grid grid-cols-2 gap-2">
  <Button variant="primary" icon={<Plus/>} onClick={() => setShowAddClass(true)}>
    {t('character.multiclass.add_class')}
  </Button>
  <Button variant="secondary" icon={<Edit3/>} onClick={() => setShowEditModal(true)} disabled={classes.length < 2}>
    {t('character.multiclass.edit_classes')}
  </Button>
</div>
```

Bottone "Edit classes" disabled se `classes.length < 2` (una sola classe è già sincronizzata via XP auto-sync, non c'è nulla da redistribuire).

**Stato interno:**

```ts
const [draft, setDraft] = useState<Record<number, number>>(
  Object.fromEntries(classes.map(c => [c.id, c.level]))
)
```

**Layout:**

1. **Header:** titolo `t('character.multiclass.edit.title')` + hint `t('character.multiclass.edit.hint', { target })` dove `target = levelFromXp(char.experience_points)`.
2. **Live sum indicator (center, large):**
   - `currentSum = Object.values(draft).reduce((s, v) => s + v, 0)`.
   - Formato: `{currentSum} / {target}`.
   - Colore: gold quando `currentSum === target`, crimson altrimenti.
3. **Classes list:** per ogni classe una riga con:
   - Class name + subclass a sinistra.
   - Input `type="number"` con `min={1} max={20}` a destra, controllato da `draft[classId]`.
4. **Footer:**
   - `Annulla` (ghost) → chiude modale, nessuna modifica.
   - `Conferma` (primary) disabled se `currentSum !== target` → `distributeMutation.mutate({ classes: Object.entries(draft).map(([id, lv]) => ({ class_id: Number(id), level: lv })) })`.

**Error handling:** se backend ritorna 400 con `sum_mismatch`, mostra toast error (defensive — UI già valida lato client).

**Rimozione +/- per-class:** in `Multiclass.tsx`:

- Rimuovo i `<m.button onClick={() => updateLevel.mutate(...)}>` con `Plus`/`Minus` icons.
- Rimuovo il pip tracker (`Array.from({ length: 20 }).map(...)`).
- Lascio visibile il numero livello della classe in lettura + il bottone X per delete classe.
- Rimuovo la mutation `updateLevel` non più necessaria.

Classe card resta display-only per livello. Cambi di livello avvengono solo via modale.

### 3.5 HP recalc sul redistribute

Quando il backend applica `distribute`:

- Se `settings.hp_auto_calc=true`:
  - `new_total_hp = total_base_hp(char)` ricalcolato con i nuovi `cls.level`.
  - Se `char.hit_points > 0`: `ratio = char.current_hit_points / char.hit_points`, `new_current = round(ratio * new_total_hp)`.
  - Se `char.hit_points == 0`: `new_current = char.current_hit_points` (lascia com'è).
  - `char.hit_points = new_total_hp`, `char.current_hit_points = clamp(new_current, 0, new_total_hp)`.
- Se `settings.hp_auto_calc=false`: skip totale, HP non toccato.

### 3.6 i18n keys

**`webapp/src/locales/it.json`** (sotto `character.multiclass`):

```json
{
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
    "sum_display": "{{current}} / {{target}}",
    "confirm": "Conferma",
    "cancel": "Annulla"
  }
}
```

**`webapp/src/locales/en.json`:**

```json
{
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
    "sum_display": "{{current}} / {{target}}",
    "confirm": "Confirm",
    "cancel": "Cancel"
  }
}
```

EN: ordinal usa "th" genericamente (semplificato; full ordinal logic non necessario).

## 4. Edge cases

- **Char senza classi (liv 0):** non atteso (char creation crea almeno 1 classe). Endpoint `distribute` con array vuoto → 400 `sum_mismatch`.
- **Classe mancante da `class-progression.json`:** preview mostra `progression_missing`; conferma comunque funziona (solo preview incompleta).
- **Class al livello 20 al trigger level-up:** nel selector della modale, click su quella classe mostra toast `at_max_toast`; bottone Conferma disabled se selezionata classe è a 20.
- **HP=0 (personaggio morto) su redistribute:** skip HP recalc per evitare divide-by-zero; `hit_points` (max) comunque aggiornato, `current_hit_points` lasciato a 0.
- **Concurrent mutation (race):** TanStack Query gestisce retry; se backend 400 `sum_mismatch` per state drift, FE mostra toast e user riapre modal.
- **Banner su single-class:** `levelUpAvailable = isMulticlass && level > totalClassLevel` — single-class non mostra banner (invariato).

## 5. Testing (verifica manuale — nessun test suite)

1. **Parser:** `uv run python scripts/parse_class_progression.py` produce `webapp/src/data/class-progression.json` valido con 12 classi.
2. **Level-up single-class:** invariato dopo G — PATCH `/xp` auto-sync, toast HP.
3. **Level-up multiclass:** Chierico 3/Guerriero 2 (liv 5), add XP fino a liv 6. Banner clickable → modal. Preview Chierico 4/5/6 features, proficiency change se presente, new spell slots se presenti. Click Guerriero → preview 3/4/5. Conferma Chierico → sum=6, Chierico=4/Guerriero=2, HP +N.
4. **Level-up multi-pending:** XP skip 2 livelli. Conferma prima scelta, modal si ri-apre automaticamente per seconda scelta.
5. **Modifica classe:** Chierico 18/Guerriero 1 (liv 19). Apri modal, input Chierico=17, Guerriero=2. Sum=19, gold. Conferma → applicato, HP ratio preserved.
6. **Modifica classe sum invalido:** 18/3=21 != 19. Sum indicator rosso, Conferma disabled.
7. **Modifica classe HP ratio:** current=50/max=100 prima. Dopo redistribute che porta max a 105 con `hp_auto_calc=true`, current diventa 53 (`round(50 * 105/100)`). Con `hp_auto_calc=false`, HP invariato.
8. **Modifica classe bloccato 1 classe:** bottone "Edit classes" disabled con 1 classe sola.
9. **Rimozione +/-:** class cards in `Multiclass.tsx` non hanno più +/- né pip tracker. Livello visibile in read-only + X delete.
10. **Classe a 20 nel selector:** selezionandola, bottone Conferma disabled + toast `at_max_toast`.

## 6. File impattati

| File | Action | Responsibility |
|------|--------|----------------|
| `scripts/parse_class_progression.py` | Create | Parser MD → JSON |
| `webapp/src/data/class-progression.json` | Create (generated) | Static progression data |
| `api/routers/classes.py` | Modify | Nuovo endpoint `distribute` |
| `api/schemas/common.py` | Modify | Nuovi schema `ClassLevelEntry`, `ClassDistribute` |
| `webapp/src/api/client.ts` | Modify | Aggiungi `api.classes.distribute(charId, body)` |
| `webapp/src/pages/multiclass/LevelUpModal.tsx` | Create | Modal §2.1 |
| `webapp/src/pages/multiclass/EditClassesModal.tsx` | Create | Modal §2.2 |
| `webapp/src/pages/multiclass/LevelUpBanner.tsx` | Create | Banner clickable shared |
| `webapp/src/pages/Multiclass.tsx` | Modify | Bottone "Edit classes", integra modals, rimuovi +/- e pip |
| `webapp/src/pages/Experience.tsx` | Modify | Banner clickable → apre modal |
| `webapp/src/locales/it.json` | Modify | +12 chiavi multiclass |
| `webapp/src/locales/en.json` | Modify | +12 chiavi multiclass |
| `docs/app/` | Modify (generated) | Rebuild pre-commit finale |

## 7. Dipendenze e roadmap

- **Gruppo F** (mergeato/in-flight): LEVEL UP button + flow XP multiclass già esistente. Questo gruppo aggiunge solo handler al click del banner + endpoint backend distribute.
- **Gruppo B** (mergeato): `total_base_hp`, `hit_points_for_level`, flag `hp_auto_calc` riusati direttamente.
- **Gruppi C/D/E/H:** indipendenti, non impattati.

Post-merge roadmap aggiornato:
- Tabella Gruppo G: `⬜ Pending` → `✅ Done (PR #<n> merged → main)`.
- Sezione `## Gruppo G`: `⬜` → `✅`.
- Ordine consigliato: `→ G →` diventa `→ ✅ G →`.
