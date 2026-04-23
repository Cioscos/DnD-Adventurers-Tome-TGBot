# Character Mechanics — Auto-HP, Item Modifiers, Spell Damage, Spell Slots

**Data:** 2026-04-23
**Branch:** `feat/character-mechanics-gruppo-b`
**Fonte:** `istruzioni.md` — §1.1 (Meccaniche di Gioco) + §1.2 (Slot Incantesimi)
**Gruppo:** B (della decomposizione di `istruzioni.md` in 8 sottoprogetti)

## Obiettivo

Aggiungere automazione meccanica al character sheet che oggi manca:
1. **Auto-HP** alla creazione e ai level-up (formula fixed D&D 5e).
2. **Modificatori ability** sugli oggetti dell'inventario (assoluto o relativo).
3. **Roll damage** per gli incantesimi con casting level e critico.
4. **Rework click** sugli spell slot (inversione visual + click symmetric use/un-use).

Il gruppo tocca sia backend (compute layer in `core/game/`, nuovi endpoint API) sia webapp (UI item editor, spell damage sheet, spell slot interaction).

## Scope

### In scope

- **Backend**:
  - `core/game/stats.py` (nuovo): funzioni pure per HP per livello, totale HP di base, ability effettivi con stacking.
  - `api/routers/characters.py`: estensione `POST /characters` con `first_class` opzionale; `PATCH /xp` con auto-HP al level-up; nuovo `PATCH /hp/recalc`.
  - `api/routers/spells.py`: nuovo `POST /spells/{id}/roll_damage`.
  - `api/routers/items.py`: validation `ability_modifiers` nel metadata.
  - Character class add (`POST /classes`): auto-HP se è la prima classe e HP=0.
  - Hook su ability score update: ricalcolo HP quando CON change.
  - Hook su item equip/unequip: ricalcolo HP quando un modifier tocca CON.

- **Frontend**:
  - `webapp/src/pages/inventory/AbilityModifiersEditor.tsx` (nuovo): rows add/remove per modificatori.
  - Integrazione nel form di edit item esistente (tutti i tipi).
  - `webapp/src/pages/SpellItem.tsx`: pulsante "Roll Damage" inline + sheet modale risultato.
  - `webapp/src/pages/SpellSlots.tsx`: handler simmetrico use/un-use, visual invertito.
  - `webapp/src/pages/CharacterMain.tsx` hero: badge/indicatore se ability effettivo ≠ base.
  - `webapp/src/pages/Stats.tsx`: breakdown espandibile per ability (base + modifiers_applied).
  - Character settings: pulsante "Ricalcola HP dalla formula".
  - HPGauge toast/animation "+N HP" al level-up.

- **i18n**: nuove chiavi per spell damage sheet, settings button, hero effective badge.

### Out of scope

- **Roll-based HP** (random): scartato. Sempre fixed method.
- **Modificatori non-ability** (AC extra, velocità, TS, bonus attacco/danno oltre armi): futuro.
- **Cap ability a 30**: nessun cap hard, per supportare homebrew.
- **Crit max dice** (alcuni homebrew): critico sempre raddoppia i dadi.
- **Level-up wizard** (scelta ASI, nuove feature di classe): Gruppo F/G.
- **Modale multiclasse** per scegliere classe al level-up: Gruppo G.
- **Auto-HP su `POST /classes` quando aggiungi una seconda classe (multiclassing manuale)**: scartato. `POST /classes` auto-calcola HP solo se è la prima classe del personaggio (bootstrap). Per aggiungere un secondo class con relativo HP-gain, l'utente passerà dal flow di Gruppo G (modale multiclasse). Nel frattempo, il pulsante "Ricalcola HP" allinea manualmente.
- **Flow di level-up button dal frontend** (HeroXPBar già naviga a `/xp`): Gruppo F estenderà.
- **Integrazione concentrazione con spell damage**: nessuna — sono flussi opposti (danno in uscita vs danno subito); il TS su concentrazione di Gruppo C si lega al flow `/hp` "subisci danni".
- **Test suite automatizzata**: il repo non ha test. `core/game/stats.py` è ideale per unit test, ma aggiungere pytest è un sotto-progetto separato per tutti i gruppi.

## Design

### 1. Data model & backend

#### 1.1 Schema extensions

**`Item.item_metadata`** (campo JSON TEXT esistente) — aggiunto sottocampo opzionale:

```json
{
  ...existing type-specific fields...,
  "ability_modifiers": [
    { "ability": "dexterity", "kind": "relative", "value": 2 },
    { "ability": "strength", "kind": "absolute", "value": 21 }
  ]
}
```

Dove `ability ∈ {strength, dexterity, constitution, intelligence, wisdom, charisma}`, `kind ∈ {absolute, relative}`, `value` è intero (può essere negativo per relativi).

**`Character.settings`** (campo JSON TEXT esistente) — aggiunto flag opzionale:

```json
{ "hp_auto_calc": true }
```

Default `true` per nuovi character. Se `false`, la formula non si applica e gli HP restano manuali.

Nessuna migrazione schema: entrambi i campi sono già JSON TEXT su `core/db/models.py`. Il parsing è defensivo (assente o malformato → nessun modifier applicato, auto_calc default `true`).

#### 1.2 Compute layer — `core/game/stats.py` (nuovo)

Modulo di sole funzioni pure, facilmente testabili:

```python
def hit_points_for_level(hit_die: int, con_mod: int, level: int) -> int:
    """HP gained for a single level-up event.
    Level 1: hit_die + con_mod (max die value, PHB standard).
    Level 2+: (hit_die // 2 + 1) + con_mod (fixed method).
    Clamped to minimum 1 per level (PHB rule).
    """

def total_base_hp(classes: list[CharacterClass], con_mod: int) -> int:
    """Sum of HP gained across all levels of all classes.
    The 'first class' (lowest id, i.e. insertion order) owns the character's
    level-1 slot and uses the level-1 formula (HD_max + CON_mod).
    All other levels (including level 1 of any additional multiclass)
    use the level 2+ formula ((HD // 2 + 1) + CON_mod).
    """

def effective_ability_score(
    ability_name: str,
    base_value: int,
    equipped_items: list[Item],
) -> tuple[int, list[AppliedModifier]]:
    """Compute effective ability score applying stacking rule:
    - Sum of all relative modifiers on equipped items for this ability
    - Max of all absolute modifiers (if any)
    - Final = max(base + sum(rel), max(abs) if any else base + sum(rel))
    Returns (effective_value, list of applied modifiers for breakdown UI).
    """
```

Dove `AppliedModifier` è un dataclass/dict `{source: str, ability: str, kind: str, value: int}` usato dal frontend per il breakdown view.

#### 1.3 Nuovi / estesi endpoint API

| Metodo | Path | Payload/Query | Comportamento |
|---|---|---|---|
| `POST` | `/characters` | `{name, first_class?: {class_name, hit_die, subclass?}}` | Se `first_class` passato, dopo la creazione crea anche il class record con `level=1` e chiama auto-HP (con CON default 10 → mod 0 → HP = hit_die). Backward compat: payload legacy `{name}` → HP=0 come oggi. |
| `PATCH` | `/characters/{id}/xp` | `{add?: int, set?: int}` | Quando un `CharacterClass.level` incrementa (single-class auto-sync), invoca `hit_points_for_level(hit_die, current_con_mod, new_level)` e incrementa `character.hit_points` + `character.current_hit_points` di quel delta. Response include `hp_gained: int \| null`. |
| `POST` | `/characters/{id}/classes` | `{class_name, hit_die, ...}` | Se è la **prima** classe (count=0) e `character.hit_points == 0`, auto-HP con formula level-1 (HD_max + CON_mod corrente). Altrimenti behavior invariato — nessun auto-HP, anche in caso di multiclassing manuale. Il flow multiclasse con level-up vero sarà gestito da Gruppo G; nel frattempo il pulsante "Ricalcola HP" permette di allineare. |
| `PATCH` | `/characters/{id}/hp/recalc` | (body vuoto) | Invoca `total_base_hp(classes, con_mod)` e imposta `hit_points = result`. `current_hit_points = min(current, hit_points)` se ridimensiona verso il basso; `current += delta` se ridimensiona verso l'alto (per non perdere HP correnti). Endpoint idempotente. |
| `PATCH` | `/characters/{id}/ability_scores/{ability}` | `{value: int}` | Esistente; ora invoca anche hook CON: se `ability == constitution`, calcola `delta_mod = new_mod - old_mod`; `character.hit_points += delta_mod * total_level`; `character.current_hit_points += delta_mod * total_level`. Nessun effetto se `delta_mod == 0`. |
| `POST` | `/characters/{id}/spells/{spell_id}/roll_damage` | `{casting_level?: int, extra_dice?: str, is_critical?: bool}` | Parsa `spell.damage_dice`. Se `is_critical`, raddoppia i dadi (non il modificatore piatto). Aggiunge `extra_dice` se valido (regex `^\d+d\d+([+-]\d+)?$`). Ritorna `{rolls: int[], total: int, half_damage: int, damage_type: str, breakdown: str}`. Validate `casting_level >= spell.level`. Error 400 se parse fallito. Registra nella rolls_history del character. |
| `PATCH` | `/characters/{id}/items/{id}` | (body esistente, accetta `item_metadata` esteso) | Sui cambi a `is_equipped` o a `ability_modifiers`, se un modifier tocca CON, ricalcola HP (delta_mod × total_level). |

#### 1.4 Response `AbilityScore` estesa

L'esistente `AbilityScore` response aggiunge due campi opzionali:

```json
{
  "id": 1,
  "name": "dexterity",
  "value": 16,         // effective (base + modifiers), invariato
  "base_value": 14,    // NEW: valore base senza modifiers
  "modifier": 3,        // already computed from effective value
  "modifiers_applied": [
    { "source": "Cloak of Dexterity", "kind": "relative", "value": 2, "item_id": 42 }
  ]
}
```

Backward compat: client vecchi ignorano i nuovi campi; gli esistenti continuano a leggere `value` come valore effettivo.

Il recompute di `value` ed `modifiers_applied` avviene on-read (server resolve → lista items equipped → `effective_ability_score()`). Nessuna denormalizzazione, nessun invalidation cache.

#### 1.5 Hooks — Item equip/unequip + ability_modifiers edit

Quando `is_equipped` cambia o `ability_modifiers` di un item equipped cambiano, `api/routers/items.py` chiama un helper `recompute_hp_if_con_affected(character)`:

```python
def recompute_hp_if_con_affected(char: Character) -> None:
    eq_items = [i for i in char.items if i.is_equipped]
    old_eff_con = <pre-change snapshot>
    new_eff_con = effective_ability_score("constitution", char.base_con, eq_items)[0]
    delta_mod = modifier_from(new_eff_con) - modifier_from(old_eff_con)
    if delta_mod != 0:
        char.hit_points += delta_mod * char.total_level
        char.current_hit_points = max(0, char.current_hit_points + delta_mod * char.total_level)
```

Il pre-change snapshot va preso prima dell'update del metadata. Lato API: pattern read-modify-write dentro la stessa transazione.

#### 1.6 Validation

- `ability_modifiers[i].ability`: deve essere uno dei 6 slug validi → altrimenti 400.
- `ability_modifiers[i].kind`: deve essere `"absolute"` o `"relative"` → altrimenti 400.
- `ability_modifiers[i].value`: integer, nessun range hard (supporta sia +20 che -5 relativo).
- `hit_die` in `first_class`: integer in `{4, 6, 8, 10, 12}` (i 5 hit die D&D 5e) → altrimenti 400.
- `casting_level` in roll_damage: `spell.level ≤ casting_level ≤ 9` → altrimenti 400.
- `extra_dice`: regex `^\d+d\d+([+-]\d+)?$` (es. `2d6`, `1d8+3`, `3d10-1`) → altrimenti 400.

### 2. Frontend

#### 2.1 Character creation — automation lazy

Il form in `CharacterSelect.tsx` resta "solo nome" (HP=0). L'auto-HP scatta implicitamente in due punti successivi:

- **Add class**: quando l'utente aggiunge la prima classe (POST `/classes`), se `character.hit_points == 0` il backend calcola HP iniziale. `CharacterSelect` invia quindi anche `hit_die` (già fa).
- **Set ability score CON**: quando l'utente salva CON per la prima volta dopo il default 10, il hook CON change (§1.5) applica `delta_mod * total_level` sugli HP. Nessuna UI dedicata.

Motivo: evitare un creation wizard multi-step che aggiungerebbe friction senza vantaggio reale — i giocatori compilano lo stesso CON + class subito dopo.

#### 2.2 Level-up HP — toast + HPGauge animation

In `Experience.tsx` (mutation `/xp`):
- Response `hp_gained: int \| null` → se presente, mostra toast "+N HP" (usa `sonner` già esistente) per 2s.
- TanStack Query invalidate → HPGauge anima verso nuovo `hit_points` (framer-motion already supportato).
- History entry server-side "Level up: Fighter 5, +6 HP" (usa l'infrastruttura esistente di storico eventi — già traccia level up).

#### 2.3 `AbilityModifiersEditor` component

Nuovo file `webapp/src/pages/inventory/AbilityModifiersEditor.tsx`:

Props:
```ts
interface AbilityModifiersEditorProps {
  modifiers: AbilityModifier[]
  onChange: (next: AbilityModifier[]) => void
}
interface AbilityModifier {
  ability: 'strength' | 'dexterity' | 'constitution' | 'intelligence' | 'wisdom' | 'charisma'
  kind: 'absolute' | 'relative'
  value: number
}
```

Render:
- Titolo sezione "Modificatori caratteristiche" (i18n key `character.inventory.item.modifiers.title`)
- Per ogni modifier, una riga con:
  - Select ability (6 opzioni localizzate)
  - Toggle `absolute` / `relative` (visualmente `=` o `+/-`)
  - Input numerico (accetta negativi solo se `relative`)
  - Bottone "✕" remove
- Bottone "+ Aggiungi" sotto

Integrato in `InventoryItemForm.tsx` (o componente equivalente) come sezione dopo i campi type-specific. Presente per tutti i tipi (weapon, armor, shield, tools, consumable, wondrous, other).

Il valore serializza in `item_metadata.ability_modifiers`.

#### 2.4 Display ability effettivi

- **Hero section (`CharacterMain.tsx`)**: la griglia ability mostra il `value` effettivo. Se `modifiers_applied.length > 0`, un piccolo chip in basso-destra della cella "↑" (filtro oro) indica modifiche. Hover/tap opzionale mostra il breakdown (fuori scope per ora — in Group A le celle ability navigano a `/stats`).
- **Stats page (`/stats`)**: per ciascuna ability, sotto il valore grande, un blocco espandibile "Dettaglio" che mostra:
  ```
  Base: 14
  + Cloak of Dexterity: +2 (equipped)
  = 16 (mod +3)
  ```
  Usa `modifiers_applied` dal response API. Se vuoto, il blocco non si espande.

#### 2.5 Spell damage roll — `SpellItem.tsx`

Nell'item espanso della pagina `/spells`:

- Nuovo pulsante inline **"Roll Damage"** solo se `spell.damage_dice != null`. Stile: ghost button gold. Icona `Dices` da lucide.
- Click apre un bottom sheet (`<Sheet>` pattern già esistente nel repo):
  - Title "Tiro danni: {spell.name}"
  - Campo "Livello di casting" con `[-]` / `[+]` stepper, default = `spell.level`, range `[spell.level, 9]`.
  - Input text "Dadi extra" (regex hint, placeholder `"0d6"`)
  - Checkbox "Critico" — visibile solo se `spell.attack_save === 'ATK'` (o null/assente, quando è un attack roll)
  - Pulsante "Rolla"
- Al click Rolla: `POST /spells/{id}/roll_damage`, sheet content cambia in risultato:
  - "3d6 + 2 = [roll1, roll2, roll3] + 2 = 14"
  - Grid 2-col: "⚔ Pieno: 14" / "🛡 Dimezzato: 7" (il dimezzato appare solo se `attack_save != 'ATK'` e != null)
  - Pulsante "Chiudi" / "Nuovo tiro"
- Storico: salvato automaticamente via `rolls_history` del character (backend).

#### 2.6 Spell slot click — `SpellSlots.tsx` rewrite

Visual:
- Disponibile (`used <= i < total`) = gemma outline-only (vuota), gold border.
- Usato (`i < used`) = gemma filled gold.
- Inversione rispetto al design attuale.

Handler:

```tsx
const handleClick = (i: number) => {
  if (i < slot.used) {
    haptic.light()
    updateSlot.mutate({ slotId: slot.id, used: Math.max(0, slot.used - 1) })
  } else {
    haptic.medium()
    updateSlot.mutate({ slotId: slot.id, used: Math.min(slot.total, slot.used + 1) })
  }
}
```

Nessun long-press, nessun pulsante separato di undo. Click su gemma pieno (index < used) libera l'ultima; click su gemma vuota (index >= used) consuma la prima disponibile. Edge case: tutti usati + click su pieno → used--; tutti vuoti + click su vuoto → used++. Il caso "tutti usati + click su vuoto" non esiste (non ci sono gemme vuote).

Il pulsante "Reset" (→ used=0) resta invariato.

#### 2.7 Settings — pulsante "Ricalcola HP"

In `webapp/src/pages/character/Settings.tsx` (creare se non esiste, altrimenti integrare in pagina settings esistente). Aggiunge un pulsante danger-tone "Ricalcola HP dalla formula" con dialog di conferma:
> "Ricalcolerà gli HP massimi secondo la formula D&D 5e (fisso). Continuare?"

Su conferma: `PATCH /characters/{id}/hp/recalc` → TanStack query invalidation → HPGauge aggiorna.

Affiancato a un toggle: "HP automatici: [on/off]" che scrive `character.settings.hp_auto_calc`. Off disabilita sia l'auto-calc al level-up che il hook CON.

### 3. i18n

Nuove chiavi in `it.json` + `en.json`:

```json
{
  "character": {
    "inventory": {
      "item": {
        "modifiers": {
          "title": "Modificatori caratteristiche",
          "add": "Aggiungi modificatore",
          "ability": "Caratteristica",
          "kind": {
            "absolute": "Assoluto",
            "relative": "Relativo"
          },
          "value": "Valore",
          "remove": "Rimuovi modificatore"
        }
      }
    },
    "spells": {
      "roll_damage": {
        "title": "Tiro danni: {{name}}",
        "casting_level": "Livello di casting",
        "extra_dice": "Dadi extra",
        "extra_dice_placeholder": "es. 1d6",
        "critical": "Critico (raddoppia i dadi)",
        "roll_button": "Rolla",
        "full_damage": "Pieno",
        "half_damage": "Dimezzato",
        "close": "Chiudi",
        "reroll": "Nuovo tiro"
      }
    },
    "settings": {
      "hp": {
        "recalc": "Ricalcola HP dalla formula",
        "recalc_confirm_title": "Conferma ricalcolo",
        "recalc_confirm_body": "Ricalcolerà gli HP massimi secondo la formula D&D 5e (fisso). Continuare?",
        "auto_calc_toggle": "HP automatici",
        "auto_calc_on": "Attivi",
        "auto_calc_off": "Disattivati"
      }
    },
    "hero": {
      "ability_effective_badge_aria": "{{name}} modificato da equipaggiamento"
    },
    "xp": {
      "hp_gained_toast": "+{{hp}} HP"
    }
  }
}
```

Traduzioni EN analoghe con testi inglesi (es. "Ability modifiers", "Roll Damage", "Full"/"Half", "Recalculate HP from formula", "Auto HP", "+{{hp}} HP").

### 4. Accessibilità

- `AbilityModifiersEditor` rows: label semantico con `<label>` per ciascun select/input; button remove ha `aria-label`.
- Spell damage sheet: `role="dialog"`, `aria-modal="true"`, focus trap sui field interni.
- Spell slot gems: ciascuna è `<button>` con `aria-label={\`Livello {level} slot {i+1}/{total} ${i < used ? 'usato' : 'disponibile'}\`}` e `aria-pressed={i < used}`. Screen reader annuncia stato + effetto al click.
- Recalc HP button: conferma tramite dialog accessibile (pattern esistente nel repo).
- Ability effective badge: `title` + `aria-label` localizzati.

### 5. Edge cases

- **HP < 1 al level-up**: clamp a 1 HP per livello (PHB `max(1, die + con_mod)`).
- **Stacking assoluti**: multipli `=X` → applica max. No somma.
- **Base > assoluto**: se base 22 e assoluto 21, effective = 22 (max).
- **CON change con item equipped modificano CON**: il delta è calcolato su CON effettivo (base+items), non solo base.
- **Spell senza damage_dice**: pulsante Roll Damage nascosto.
- **Spell senza attack_save (auto-hit, es. Magic Missile)**: dimezzato non mostrato.
- **Casting level invalido**: 400 server, toast error client.
- **Extra dice parse error**: 400 server, toast error client.
- **Spell slot click con tutti usati**: click su qualsiasi gemma (tutte piene) → used--. Sempre undo-possibile.
- **Spell slot click con tutti vuoti**: click → used++. Non esiste mai stato "nessuna azione possibile".
- **Recalc HP con multiclass**: `total_base_hp()` somma per-classe. First class owns level 1 (max formula); altre classes tutti level 2+ formula.
- **Item modifier con ability key ignota**: scartato server-side (log warning, no errore al client).
- **Character.settings.hp_auto_calc == false**: tutti i hook (level-up auto, CON change, item equip) NON toccano HP. Il pulsante recalc in settings resta attivo (trigger manuale).
- **`ability_modifiers[]` vuoto o assente**: nessun modifier, `modifiers_applied: []`, `value == base_value`.

### 6. Backward compatibility

- `POST /characters` payload: `first_class` opzionale. Client vecchi (solo name) continuano a funzionare. HP=0 legacy.
- `PATCH /xp` response: `hp_gained` nuovo campo opzionale. Client vecchi ignorano.
- `AbilityScore` response: `base_value`, `modifiers_applied` nuovi. Client vecchi usano solo `value` e `modifier` — invariati.
- `item_metadata.ability_modifiers`: campo nuovo, parse defensivo (assente → nessun modifier).
- `Character.settings.hp_auto_calc`: campo nuovo opzionale, default `true`.
- Endpoint esistenti (`/hp`, `/spells/use`, `/spell_slots`, `/classes`, `/items`): signature invariata per i client vecchi.

## Dipendenze con altri gruppi

- **Gruppo A** (UX polish hero — merged): nessuna dipendenza.
- **Gruppo C** (concentrazione): nessuna dipendenza — il Roll Damage è danno in uscita verso nemici, mentre il TS su concentrazione di Gruppo C si lega al flow "subisci danni" in `/hp`. Flussi opposti.
- **Gruppo F** (§1.8 XP button + level-up UX): Gruppo B espone già l'auto-HP nel `/xp`. Quando Gruppo F aggiungerà il pulsante LEVEL UP dedicato, invocherà lo stesso endpoint — niente altro.
- **Gruppo G** (§2 multiclasse): la formula HP di `total_base_hp()` già accetta multiclasse per-classe. Quando Gruppo G aggiungerà la modale "scegli classe da salire", il payload `/xp` specificherà la classe scelta e il backend userà `hit_die` di quella classe. Design già compatibile.

Gruppo B può essere mergeato standalone.

## Implementazione — note operative

- **Build webapp**: come Gruppo A, `cd webapp && npm run build:prod` rigenera `docs/app/` per GitHub Pages. PR include sia `webapp/src/**` che `docs/app/**`.
- **Branch**: `feat/character-mechanics-gruppo-b` (già creata, basata su `main` post-merge Gruppo A).
- **Migrations**: nessuna (campi JSON già esistenti).
- **Testing**: verifica manuale via `npm run dev` + uvicorn. Testare su:
  - Character nuovo creato con primo class → HP = hit_die.
  - Level up single-class → HP aumenta di `(HD/2 + 1) + CON_mod`.
  - Cambio CON → HP retroattivo aggiornato.
  - Item equipped con `+2 DEX` → ability DEX effettiva +2.
  - Item equipped con `=21 STR` mentre base STR = 14 → effective STR = 21.
  - Item rimosso → effective torna al base.
  - Due item `+1 DEX` → DEX +2.
  - Due item `=19 STR` e `=21 STR` → STR = 21.
  - Roll damage Fireball casting level 3 → 8d6; casting level 5 + extra_dice `2d6` → 10d6.
  - Spell slot: click su vuoto → used++; click su pieno → used--.
  - Recalc HP button → HP riallineati alla formula.
- **Commit granularity**: un commit per sezione — compute layer, API endpoints, auto-HP hook, item modifiers UI, spell damage UI, spell slot rewrite, recalc settings, i18n, rebuild.

## Criteri di successo

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
- [ ] Nessuna regressione su flow esistenti: hp page, rest (short/long), inventory toggle equip, spell use (slot consume), spell slot reset.
