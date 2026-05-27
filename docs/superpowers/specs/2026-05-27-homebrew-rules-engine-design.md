# Homebrew Rules Engine — Design Spec

**Data:** 2026-05-27
**Branch:** `feat/homebrew-rules-engine`
**Stato:** Approvato (post brainstorming) — pronto per writing-plans
**Scope:** MVP — vincolato form-based, single-character, eseguito automaticamente

---

## 1. Sommario esecutivo

Aggiungere alla mini app un **motore di regole homebrew** che permette al giocatore di esprimere meccaniche custom della propria campagna (es. "Qualità & Usura" del master) senza modificare il codice della webapp.

Le regole vivono in JSON-DSL (vocabolario chiuso, validato Pydantic), si attaccano a un personaggio, e si attivano automaticamente quando il backend rileva eventi di gioco rilevanti (nat-1 in attacco, critico subito, scendere a 0 PF, level-up, ecc.). L'utente le costruisce e gestisce tramite una UI in linguaggio naturale; mai vede JSON.

Una libreria di **template installabili** (`Qualità & Usura`, `Sanguinamento`, `Arma incantata +1d6`, `Punti Fortuna`) copre l'80% dei casi reali senza richiedere costruzione da zero.

---

## 2. Goals / Non-goals

### Goals
- Supportare 4 categorie di meccaniche homebrew: modificatori su oggetti, condizioni custom su PG, risorse/contatori custom, modificatori passivi statici.
- 15 eventi e 16 azioni iniziali nel vocabolario.
- Esecuzione automatica con notifica all'utente.
- UI 100% in linguaggio naturale, zero identifiers tecnici visibili.
- 4 template pre-confezionati come default UX.
- Test e2e Playwright per ogni combinazione evento×azione, con report nel formato compatibile con `/audit-loop`.

### Non-goals (esplicitati come deferral)
- **Editor a grafo visuale** (tipo n8n / Blender). Resta form-based + card.
- **Pattern interattivi pre-roll** (Fortunato, Auto-10 d20, Maestro d'Armi Possenti opt-in, advantage/disadvantage dinamici al roll-time). Richiedono un secondo asse architetturale ("hook pre-dado") da affrontare in v2.
- **Sharing / import / export** di regole tra utenti.
- **Marketplace / community** template.
- **Multi-utente / GM role**. Le regole sono per-character.
- **Effects asincroni o delayed** (es. "tra 2 turni applica X").
- **Versionamento storico** delle regole (solo campo `version` integer monotonico).

---

## 3. User stories

### US-1 — Installa una regola dalla libreria
> "Ho ricevuto dal master la house rule Qualità & Usura. Apro la pagina Homebrew, vedo nella libreria 'ricette pronte' una card 'Qualità & Usura', clicco 'Installa'. Da quel momento, i miei item di tipo weapon/armor/shield hanno le caratteristiche `Qualità` (default: Ordinaria) e `Stato` (default: Integro), modificabili sulla card dell'item."

### US-2 — Effetto automatico al fumble
> "Sono in combattimento, attacco con la mia spada (qualità Pessima, stato Integro). Tiro un nat-1. Il backend automaticamente: tira 1d20 sulla tabella usura, ottiene 7 → cella `D` per la riga `pessima`. La spada diventa Danneggiata. Mi appare un modal: '⚠️ Spada lunga danneggiata!'. La voce è loggata in History."

### US-3 — Effetto a catena (depth)
> "Stessa spada, ora Danneggiata. Tiro un altro nat-1. Lookup → `D`. La regola legge che la spada era già Danneggiata, quindi la passa a Distrutta, la disequipaggia automaticamente, modal '💥 Spada distrutta!'."

### US-4 — Risorsa custom restore-by-dice
> "Possiedo una Bacchetta Pirotecnica (template installato). Ha 7 cariche custom. Le consumo una a una. All'alba (riposo lungo), il backend tira 1d6+1 e ripristina quel numero di cariche, capped a 7."

### US-5 — Bonus passivo statico
> "Indosso uno Scudo Espressivo (regola: '+1 AC mentre equipaggiato'). Apro la pagina Armor Class: vedo `AC totale: 17`, con breakdown 'Base 10 + Destrezza 3 + Scudo 2 + Modificatori homebrew: +1 (Scudo Espressivo)'."

---

## 4. Architettura ad alto livello

```
┌──────────────────────────────────────────────────────────────────────┐
│                       FRONTEND (webapp/)                             │
│  ┌─────────────────────────────┐  ┌──────────────────────────────┐   │
│  │ /char/:id/homebrew          │  │  Display integrato:          │   │
│  │  • Lista regole + library   │  │  • Inventory → property badge│   │
│  │  • Editor sezioni collap.   │  │  • Conditions → custom sect. │   │
│  │  • Plain-language only      │  │  • Abilities → custom resrc. │   │
│  │                             │  │  • AC/HP/Skill/Save breakdown│   │
│  │                             │  │  • Toast + modal su firing   │   │
│  └─────────────────────────────┘  └──────────────────────────────┘   │
└─────────────────────────┬────────────────────────────────────────────┘
                          │  X-Telegram-Init-Data (auth)
                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         BACKEND (api/)                               │
│                                                                      │
│   items.py    hp.py    multiclass.py    abilities.py    spell_*.py   │
│      │          │            │               │               │       │
│      └──┬───────┴────────────┴───────────────┴───────────────┘       │
│         │ await dispatch(session, char, event_type, payload)         │
│         ▼                                                            │
│  ┌────────────────────────────────────────────────────────────┐      │
│  │       api/services/homebrew/dispatcher.py                  │      │
│  │  • carica rule attive per character                        │      │
│  │  • filtra per event_type                                   │      │
│  │  • depth limit (anti-loop)                                 │      │
│  │  • cycle detection (anti rule-A→B→A)                       │      │
│  └─────────────────────────┬──────────────────────────────────┘      │
│                            ▼                                         │
│  ┌────────────────────────────────────────────────────────────┐      │
│  │       api/services/homebrew/engine.py  (RuleEngine)        │      │
│  │  • valuta filters (8 operator)                             │      │
│  │  • esegue effects (14 actions, vocabolario chiuso)         │      │
│  │  • tabelle lookup                                          │      │
│  │  • passive_modifiers query (per stat calcoli)              │      │
│  └─────────────────────────┬──────────────────────────────────┘      │
│                            ▼                                         │
│  ┌────────────────────────────────────────────────────────────┐      │
│  │  api/services/homebrew/dsl.py  (Pydantic strict schemas)   │      │
│  └────────────────────────────────────────────────────────────┘      │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐      │
│  │           api/services/homebrew/templates.py               │      │
│  │   4 template hardcoded: Qualità & Usura, Bleeding,         │      │
│  │   Arma incantata +1d6, Punti Fortuna                       │      │
│  └────────────────────────────────────────────────────────────┘      │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐      │
│  │           api/routers/homebrew.py                          │      │
│  │   CRUD /characters/{id}/homebrew/rules + templates + state │      │
│  └────────────────────────────────────────────────────────────┘      │
└──────────────────────────────────────────────────────────────────────┘
```

### Componenti nuovi
- **`core/db/models.py`** → `+ HomebrewRule`, `+ HomebrewResource` (additivi)
- **`api/services/homebrew/dsl.py`** → schemi Pydantic strict per il DSL
- **`api/services/homebrew/dispatcher.py`** → entry point `dispatch(session, char, event_type, payload, depth=0)`
- **`api/services/homebrew/engine.py`** → `RuleEngine`: eval filtri, esegui effetti, lookup tabelle
- **`api/services/homebrew/templates.py`** → 4 template hardcoded
- **`api/services/homebrew/passive.py`** → helper `get_passive_modifiers(char, target_path) → list[int]`
- **`api/routers/homebrew.py`** → CRUD endpoints
- **`api/schemas/homebrew.py`** → Pydantic schemas API-facing

### Estensioni router esistenti
Ogni handler che produce un evento rilevante chiama `await dispatch(...)`. Vedi sezione 12 (Integration points).

### Componenti frontend nuovi
- **`webapp/src/pages/Homebrew.tsx`** → lista + libreria template + editor inline
- **`webapp/src/pages/homebrew/RuleEditor.tsx`** → editor sezioni collassabili
- **`webapp/src/pages/homebrew/templates/`** → componenti card per ogni template
- **`webapp/src/components/homebrew/EffectChain.tsx`** → render del flusso step-by-step in linguaggio naturale
- **`webapp/src/components/homebrew/PropertyBadge.tsx`** → badge per property custom su item
- **`webapp/src/components/homebrew/CustomConditionCard.tsx`**
- **`webapp/src/components/homebrew/CustomResourceCounter.tsx`**
- **`webapp/src/lib/homebrew/i18n-dsl.ts`** → mapping DSL ↔ linguaggio naturale (i18n)

### Estensioni pagine esistenti
- `Inventory.tsx` → mostra `<PropertyBadge>` sotto al nome dell'item, se ha homebrew property
- `Conditions.tsx` → sezione "Personalizzate" sotto le 14 standard
- `Abilities.tsx` → sezione "Risorse Custom" sotto le Class Resources
- `ArmorClass.tsx`, `HP.tsx`, `Skills.tsx`, `SavingThrows.tsx` → breakdown include riga "Modificatori homebrew"

---

## 5. Modello dati

### Nuove tabelle (additive, via `_MIGRATIONS` in `core/db/engine.py`)

```python
class HomebrewRule(Base):
    __tablename__ = "homebrew_rules"
    id:           Mapped[int]            = mapped_column(Integer, primary_key=True)
    character_id: Mapped[int]            = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"))
    name:         Mapped[str]            = mapped_column(String(100), nullable=False)
    description:  Mapped[Optional[str]]  = mapped_column(Text)
    enabled:      Mapped[bool]           = mapped_column(Boolean, default=True)
    dsl:          Mapped[dict]           = mapped_column(JSON, nullable=False)
    version:      Mapped[int]            = mapped_column(Integer, default=1)
    template_id:  Mapped[Optional[str]]  = mapped_column(String(50))  # null se custom
    created_at:   Mapped[str]            = mapped_column(String(50))
    updated_at:   Mapped[str]            = mapped_column(String(50))

    character:    Mapped["Character"]    = relationship(back_populates="homebrew_rules")
    resources:    Mapped[list["HomebrewResource"]] = relationship(
        back_populates="rule", cascade="all, delete-orphan"
    )

class HomebrewResource(Base):
    __tablename__ = "homebrew_resources"
    id:               Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_id:          Mapped[int] = mapped_column(ForeignKey("homebrew_rules.id", ondelete="CASCADE"))
    character_id:     Mapped[int] = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"), index=True)
    key:              Mapped[str] = mapped_column(String(60), nullable=False)
    name:             Mapped[str] = mapped_column(String(100), nullable=False)
    current:          Mapped[int] = mapped_column(Integer, default=0)
    max:              Mapped[int] = mapped_column(Integer, default=0)
    restoration_type: Mapped[str] = mapped_column(Enum(RestorationType), default=RestorationType.NONE)

    rule:             Mapped["HomebrewRule"]  = relationship(back_populates="resources")

    __table_args__ = (UniqueConstraint("character_id", "key"),)
```

### Relazioni aggiunte a `Character`
```python
homebrew_rules: Mapped[list["HomebrewRule"]] = relationship(
    back_populates="character", cascade="all, delete-orphan"
)
homebrew_resources: Mapped[list["HomebrewResource"]] = relationship(
    "HomebrewResource",
    primaryjoin="HomebrewResource.character_id == Character.id",
    cascade="all, delete-orphan",
    viewonly=False,
)
```

### Riuso campi JSON esistenti (NIENTE schema change)
- **Custom property su Item** → `Item.item_metadata` (già `Text` JSON). Chiavi con prefisso `hb_*`. Esempio: `item.metadata["hb_quality"] = "pessima"`, `item.metadata["hb_damage_state"] = "danneggiata"`.
- **Custom condition su Character** → `Character.conditions` (già `JSON dict`). Chiavi con prefisso `custom:`. Esempio: `char.conditions["custom:bleeding"] = {"rule_id": 42, "params": {"die": "1d4"}}`.

### Tabelle di lookup
Vivono **dentro al `dsl` della regola**, non in DB separato. Sono parte integrante della definizione della regola.

---

## 6. Specifica del DSL

Schema versionato (`version` integer top-level). MVP = `version: 1`.

```json
{
  "version": 1,
  "subject": {
    "type": "item" | "character" | "ability",
    "filter": {
      "item_types": ["weapon", "armor", "shield"]   // se type=item
    }
  },
  "properties": [
    {
      "key": "quality",
      "type": "enum",
      "values": ["pessima", "ordinaria", "buona", "straordinaria"],
      "default": "ordinaria",
      "label_i18n": { "it": "Qualità", "en": "Quality" },
      "value_labels_i18n": {
        "pessima": { "it": "Pessima", "en": "Poor" },
        ...
      }
    },
    {
      "key": "damage_state",
      "type": "enum",
      "values": ["integra", "danneggiata", "distrutta"],
      "default": "integra",
      "label_i18n": { "it": "Stato", "en": "State" },
      "value_labels_i18n": { ... }
    }
  ],
  "tables": [
    {
      "id": "tabella_usura",
      "row_axis": "quality",
      "col_axis": "d20_result",
      "col_bins": [[1,1],[2,3],[4,9],[10,15],[16,20]],
      "cells": {
        "pessima":      ["X","X","D","D","S"],
        "ordinaria":    ["X","D","D","S","S"],
        "buona":        ["D","D","S","S","S"],
        "straordinaria":["D","S","S","S","S"]
      }
    }
  ],
  "passive_modifiers": [
    {
      "when": { "path": "$subject.is_equipped", "op": "eq", "value": true },
      "target": "character.ac",
      "value": 1,
      "label_i18n": { "it": "Scudo Espressivo", "en": "Shield of Expression" }
    }
  ],
  "triggers": [
    {
      "event": "attack_rolled",
      "filters": [
        { "path": "$event.is_fumble", "op": "eq", "value": true },
        { "path": "$subject", "op": "has_property", "value": "quality" }
      ],
      "effects": [ /* vedi azioni sezione 8 */ ]
    }
  ]
}
```

### Filter operators (8)
`eq` · `neq` · `lt` · `lte` · `gt` · `gte` · `in` · `has_property`

### Path resolver
- `$event.X` → campo del payload evento (es. `$event.to_hit_die`, `$event.was_critical_hit`)
- `$subject.X` → property dell'item/character/ability soggetto (es. `$subject.quality`, `$subject.is_equipped`, `$subject.name`)
- `$character.X` → campo sul Character (es. `$character.current_hit_points`)
- `$<var>` → risultato di uno step precedente con `store_as` (es. `$wear_roll`)

---

## 7. Vocabolario eventi (15)

### Auto-fired (13)
| Evento | Emesso da | Payload chiave |
|---|---|---|
| `attack_rolled` | `items.py:attack_with_weapon` | `to_hit_die`, `to_hit_total`, `is_critical`, `is_fumble`, `damage_total`, `item_id` |
| `damage_taken` | `hp.py:update_hp` (`op=DAMAGE`) | `amount`, `was_critical_hit`, `current_hp_before`, `current_hp_after`, `temp_hp_absorbed` |
| `dropped_to_zero` | derivato in `hp.py` quando `current_hp_after==0 and current_hp_before>0` | `damage_amount`, `from_critical` |
| `hp_healed` | `hp.py:update_hp` (`op=HEAL`) | `amount`, `current_hp_before`, `current_hp_after` |
| `long_rest_taken` | `hp.py:rest` (kind=long) | `restored_resources` |
| `short_rest_taken` | `hp.py:rest` (kind=short) | `restored_resources` |
| `spell_cast` | `spell_slots.py:use_slot` | `slot_level`, `spell_id` |
| `ability_used` | `abilities.py:use_ability` | `ability_id` |
| `item_equipped` | `items.py:update_item` (when `is_equipped` flips to true) | `item_id`, `slot` |
| `item_unequipped` | come sopra (flip false) | `item_id` |
| `level_up` | `multiclass.py` (when class level increases) | `class_name`, `new_level`, `old_level`, `total_level_new` |
| `resource_changed` | `change_resource` action o edit manuale resource custom | `key`, `before`, `after`, `rule_id` |
| `resource_depleted` | derivato (`resource_changed` con `after==0`) | `key`, `rule_id` |

### Manuali (2)
| Evento | Trigger UI | Payload |
|---|---|---|
| `turn_started` | bottone "Inizio turno" sulla pagina Conditions (visibile se almeno una custom condition è attiva) | (nessuno) |
| `manual_trigger` | bottone "Attiva ora" sulla card della regola | `rule_id` |

### Cambio API rilevante per gli eventi
- `HPUpdate` Pydantic schema (in `api/schemas/hp.py`) → aggiungere campo `was_critical_hit: bool = False`. Il frontend `HP.tsx` mostra checkbox nel modal di danno.
- `multiclass.py` endpoint level-up → emit `level_up` dopo successful commit.

---

## 8. Vocabolario azioni (16)

### Effetti dati / control flow
| Azione | Parametri | Descrizione |
|---|---|---|
| `roll_dice` | `notation: str`, `store_as: str` | Tira (es. `1d20`, `2d6+3`). Risultato in variabile per step successivi |
| `lookup_table` | `table: str (table_id)`, `row: path`, `col: path`, `store_as: str` | Lookup in tabella DSL. `col_bins` mapping automatico |
| `match` | `value: path`, `cases: {value: [effects]}` | Switch — esegue il branch corrispondente |
| `if` | `cond: filter`, `then: [effects]`, `else: [effects]` | Condizionale |

> NB: la sequenza è implicita ovunque nel DSL — una lista di effetti `[a, b, c]` è sempre eseguita in ordine. Non esiste un'action `sequence` esplicita.

### Mutazione subject
| Azione | Parametri | Descrizione |
|---|---|---|
| `set_property` | `target: "subject"\|"character"`, `key: str`, `value: any` | Set property custom (item_metadata o conditions[custom:X]) |
| `inc_property` | `target`, `key`, `delta: int\|dice` | Increment numeric property (dice supported) |
| `unequip` | `target: "subject"` | Force-unequip item (solo se subject è item equipaggiato) |

### Mutazione character
| Azione | Parametri | Descrizione |
|---|---|---|
| `damage_character` | `amount: int\|dice`, `type: damage_type?`, `was_critical: bool=false` | Applica danno (chiama internamente la stessa logica di `hp.py:update_hp DAMAGE`, riemette eventi a depth+1) |
| `heal_character` | `amount: int\|dice` | Cura |
| `change_resource` | `key: str`, `delta: int\|dice` | Mod resource custom (negativo = consumo) |
| `restore_resource` | `key: str`, `amount: int\|dice\|"max"` | Set / restore resource (es. `1d6+1` cariche, capped a max) |
| `apply_condition` | `key: str`, `params: dict?` | Applica condizione (standard o custom:X) |
| `remove_condition` | `key: str` | Rimuovi |
| `apply_modifier_once` | `target: stat_path`, `delta: int\|dice`, `label: str` | Bonus retroattivo permanente (es. Robusto: +2*livello PF subito) |

### Utility
| Azione | Parametri | Descrizione |
|---|---|---|
| `notify` | `severity: "info"\|"warning"\|"error"\|"success"`, `message: str (template con $-resolver)` | Toast/modal UI |
| `add_history` | `description: str (template)`, `meta: dict?` | Entry in `character_history` con `event_type="homebrew"` |

---

## 9. Modificatori passivi

### Target supportati (MVP)
- `character.ac` — sommato a `Character.ac` computed property
- `character.hit_points_max` — sommato a `Character.hit_points`
- `character.speed` — sommato a `Character.speed`
- `character.skill.<skill_slug>` — bonus check (mostrato in `Skills.tsx`)
- `character.saving_throw.<ability_slug>` — bonus al TS (mostrato in `SavingThrows.tsx`)

### **NON** supportato in MVP
- Advantage/disadvantage dinamici al roll-time (richiederebbero consultazione frontend)
- Modifier sulle ability scores (FOR/DES/...)
- Modifier sul proficiency bonus
- Modifier sul damage dei weapon (richiede integrazione in `WeaponAttackModal`, deferred)

### Computazione
Helper `get_passive_modifiers(session, char, target_path: str) → int` in `api/services/homebrew/passive.py`. Carica le regole `enabled=true` del char, per ognuna scorre `passive_modifiers`, valuta `when` filter, somma le `value` matching il `target`. Cache per request (memoize su char_id+target_path).

Punti di integrazione:
- `Character.ac` (property `@property` sincrona in `core/db/models.py`) → **lasciato invariato**. La somma del modificatore homebrew avviene a livello di schema Pydantic. Estendiamo `CharacterFull` in `api/schemas/character.py` aggiungendo:
  - `ac_homebrew_modifier: int = 0` (calcolato in router via `get_passive_modifiers(session, char, "character.ac")`)
  - `ac_breakdown: AcBreakdown` con `{base, shield, magic, homebrew}` (nuovo nested schema)
  - Il campo legacy `ac: int` viene calcolato come `base + shield + magic + homebrew` (somma totale, backward compatible per i client che leggono solo `ac`)
- Analogamente per HP max, Speed, Skill, Save.

---

## 10. UI Design

### Entry point: `/char/:id/homebrew`
Layout:
- **Top bar:** "Regole Homebrew" + bottone `+ Nuova regola`
- **Sezione "Attive":** card per ogni regola attiva (nome, descrizione 1 riga, icona, toggle enable/disable, ##triggers)
- **Sezione "Disattivate":** stesse card, opacità ridotta
- **Sezione "Ricette pronte all'uso" (libreria template):** grid di 4 card (Qualità & Usura, Sanguinamento, Arma incantata +1d6, Punti Fortuna), bottone "+ Installa"

### Editor (stessa pagina, modale o sotto-route `/char/:id/homebrew/:rule_id`)
**Sezioni collassabili in ordine:**
1. **Identità** — nome (testo), descrizione (textarea), icona (picker), toggle attiva
2. **Si applica a** — radio "Oggetti / Personaggio / Capacità speciali" + filtri tipo (multi-chip)
3. **Caratteristiche aggiunte** — lista di property card (Aggiungi/Modifica/Rimuovi). Ogni card: nome label (i18n), tipo (enum/numero/booleano), valori possibili (se enum), valore iniziale
4. **Tabelle di lookup** — opzionale, riservato a regole avanzate; lista di tabelle editabili come grid HTML
5. **Modificatori passivi** — lista; ogni voce: "Quando ... allora ... applica modificatore a ..."
6. **Quando si attiva** — lista trigger; ogni trigger: dropdown evento (in linguaggio naturale), filtri opzionali aggiunti come chip ("Solo se è un 1 fallimento critico")
7. **Cosa succede** — flusso step numerati (vedi sotto)

### "Cosa succede" — Effect Chain
Render dei `triggers[].effects` come **card numerate consecutive**:
- Card 1: 🎲 "Tira 1d20, chiamiamolo *nome_user_friendly*"
- Card 2: 📊 "Guarda nella tabella *X*, riga *Y*, colonna *Z*, chiamiamolo *nome*"
- Card 3 (decision): "In base al risultato di *nome*" + branch cards indentati per ogni case (X/D/S nel master rule), con sub-card per `if/else` nested.

Ogni card ha:
- Icona azione
- Descrizione plain-language (generata da `i18n-dsl.ts` mapping)
- Pulsanti "Modifica" / "Rimuovi" / "Sposta su" / "Sposta giù"

### Mapping `i18n-dsl.ts` (esempi)
```ts
const EVENT_LABEL_IT: Record<EventType, (filters?) => string> = {
  attack_rolled: (f) => f?.is_fumble
    ? "Quando tiro 1 (fallimento critico) attaccando"
    : f?.is_critical ? "Quando tiro 20 (critico) attaccando" : "Quando tiro un attacco",
  damage_taken: (f) => f?.was_critical_hit
    ? "Quando subisco un colpo critico"
    : "Quando subisco danno",
  dropped_to_zero: () => "Quando vengo portato a 0 PF in un colpo",
  ...
};

const ACTION_LABEL_IT = {
  roll_dice: (p) => `🎲 Tira ${p.notation}` + (p.store_as ? `, chiamiamolo "${p.store_as}"` : ""),
  lookup_table: (p) => `📊 Guarda nella tabella "${p.table}" alla riga ${p.row} colonna ${p.col}` + (p.store_as ? `, chiamiamolo "${p.store_as}"` : ""),
  set_property: (p) => `Imposta ${p.key} di ${p.target == "subject" ? "questo oggetto" : "il personaggio"} a "${p.value}"`,
  ...
};
```

### Display custom states (integrato nelle pagine esistenti)

| Pagina | Estensione |
|---|---|
| `Inventory.tsx` | Sotto al nome dell'item, `<PropertyBadge>` per ogni `metadata["hb_*"]`. Esempio: chip "Pessima" + chip "Danneggiato" |
| `Conditions.tsx` | Sezione "Personalizzate" sotto le 14 standard. Card con icona regola, parametri (es. dado), pulsante "Rimuovi" |
| `Abilities.tsx` | Sezione "Risorse Custom" sotto le Class Resources. Counter con +/− e "Recupera" |
| `ArmorClass.tsx` | Breakdown include riga "Modificatori homebrew: +X (Nome regola)" |
| `HP.tsx`, `Skills.tsx`, `SavingThrows.tsx` | idem |

### Notifiche al firing
Riuso del `ResultDialog` / `ModalProvider` esistenti. Format:
- Icona (dalla regola sorgente)
- Titolo: nome regola + emoji severity
- Body: messaggio (testo del DSL action `notify` con $-resolver applicato)
- Auto-close 5s (override per `severity=error`)

---

## 11. API endpoints (`api/routers/homebrew.py`)

| Method | Path | Descrizione |
|---|---|---|
| `GET` | `/characters/{char_id}/homebrew/rules` | Lista regole del PG |
| `GET` | `/characters/{char_id}/homebrew/rules/{rule_id}` | Single rule |
| `POST` | `/characters/{char_id}/homebrew/rules` | Create rule (body: DSL Pydantic-validated) |
| `PATCH` | `/characters/{char_id}/homebrew/rules/{rule_id}` | Update rule (DSL + meta) — incrementa `version` |
| `DELETE` | `/characters/{char_id}/homebrew/rules/{rule_id}` | Cancella rule + risorse collegate |
| `POST` | `/characters/{char_id}/homebrew/rules/{rule_id}/enable` | Toggle enabled true/false |
| `GET` | `/characters/{char_id}/homebrew/templates` | Lista template disponibili (4 hardcoded) |
| `POST` | `/characters/{char_id}/homebrew/templates/{template_id}/install` | Installa template come nuova rule (clone del DSL) |
| `GET` | `/characters/{char_id}/homebrew/resources` | Lista resource custom del PG (con stato `current/max`) |
| `PATCH` | `/characters/{char_id}/homebrew/resources/{resource_id}` | Modifica `current` (manuale) |
| `POST` | `/characters/{char_id}/homebrew/manual-trigger/{rule_id}` | Trigger manuale (per regole con `manual_trigger` event) |
| `POST` | `/characters/{char_id}/homebrew/turn-start` | Trigger `turn_started` event |

Tutte protette da `Depends(get_current_user)` + ownership check via `_get_owned`.

---

## 12. Integration points — emit `dispatch(...)`

| File | Endpoint | Eventi emessi |
|---|---|---|
| `api/routers/items.py:attack_with_weapon` | `POST /characters/{c}/items/{i}/attack` | `attack_rolled` |
| `api/routers/items.py:update_item` | `PATCH /characters/{c}/items/{i}` | `item_equipped` / `item_unequipped` (su flip `is_equipped`) |
| `api/routers/hp.py:update_hp` | `PATCH /characters/{c}/hp` | `damage_taken`, `dropped_to_zero` (derivato), `hp_healed` |
| `api/routers/hp.py:rest` | `POST /characters/{c}/rest` | `long_rest_taken` / `short_rest_taken` |
| `api/routers/spell_slots.py:use_slot` | `POST /characters/{c}/spell_slots/{lvl}/use` | `spell_cast` |
| `api/routers/abilities.py:use_ability` | `POST /characters/{c}/abilities/{a}/use` | `ability_used` |
| `api/routers/classes.py` o multiclass endpoint | quando `CharacterClass.level` incrementa | `level_up` |
| `api/routers/homebrew.py:patch_resource` | `PATCH /homebrew/resources/{r}` | `resource_changed` + `resource_depleted` se appropriate |

Dispatch signature:
```python
async def dispatch(
    session: AsyncSession,
    char: Character,
    event_type: EventType,
    payload: dict,
    *,
    depth: int = 0,
    triggered_rule_stack: tuple[int, ...] = (),
) -> list[RuleFiringResult]:
    """Restituisce la lista di firing risultati (per UI: notifiche, history)."""
```

---

## 13. Persistence & Migrations

### Migrations (`core/db/engine.py` → `_MIGRATIONS` tuple)

```sql
-- Migration N+1
CREATE TABLE homebrew_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    enabled BOOLEAN NOT NULL DEFAULT 1,
    dsl JSON NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    template_id VARCHAR(50),
    created_at VARCHAR(50) NOT NULL,
    updated_at VARCHAR(50) NOT NULL
);

CREATE INDEX idx_homebrew_rules_character_enabled
    ON homebrew_rules(character_id, enabled);

CREATE TABLE homebrew_resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id INTEGER NOT NULL REFERENCES homebrew_rules(id) ON DELETE CASCADE,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    key VARCHAR(60) NOT NULL,
    name VARCHAR(100) NOT NULL,
    current INTEGER NOT NULL DEFAULT 0,
    max INTEGER NOT NULL DEFAULT 0,
    restoration_type VARCHAR(20) NOT NULL DEFAULT 'none',
    UNIQUE(character_id, key)
);

CREATE INDEX idx_homebrew_resources_character ON homebrew_resources(character_id);
```

Idempotenti (controllo `IF NOT EXISTS` o try/except in `_MIGRATIONS` come gli altri).

### Backward compat
- Characters senza regole = zero overhead. Nessuna regola = `dispatch()` no-op (return early se 0 regole attive).
- `Item.item_metadata` chiavi `hb_*` ignorate da tutti gli altri router. Solo l'engine le legge/scrive.
- `Character.conditions` chiavi `custom:*` ignorate dalle 14 condition base. Solo l'engine le tocca.

---

## 14. Rischi e mitigazioni

### R1 — Recursive rule firing (loop)
**Rischio:** rule A chiama `damage_character`, che emette `damage_taken`, che triggera rule A o B che chiama altro... loop infinito.
**Mitigazione:**
- `dispatch(depth=N)`. Per ogni call ricorsiva interna (es. da un'action `damage_character`), `depth+=1`. Se `depth > 8` → skip + log warning in CharacterHistory.
- `triggered_rule_stack: tuple[int, ...]` — se lo stesso `rule_id` è già nello stack → skip silenzioso (cycle detection).

### R2 — Race condition (richieste concorrenti)
**Rischio:** due endpoint paralleli leggono `Item.metadata["hb_damage_state"]`, entrambi scrivono → last-write-wins, stato perso.
**Mitigazione:**
- Dispatcher prende lock pessimistico `SELECT ... FOR UPDATE` sulla `Character` row a inizio esecuzione. Pattern già usato nel codebase per ownership check + write.

### R3 — DSL malformato in DB (edit manuale, vecchio schema)
**Rischio:** un futuro update del DSL schema rende vecchie regole illegali → engine crasha.
**Mitigazione:**
- Pydantic strict validation al `POST/PATCH /homebrew/rules`.
- Runtime: se DSL fallisce parse → regola skippata + entry in history `⚠️ Regola X disattivata: DSL incompatibile`. Mai HTTP 500.
- Campo `version` integer sul DSL per migrazioni schema future. Lo schema validator accetta solo `version` correnti.

### R4 — Performance (molte regole su character)
**Rischio:** char con 20 regole, ogni endpoint che emette evento scansiona 20 regole.
**Mitigazione:**
- Dispatcher carica solo `enabled=true` con index `(character_id, enabled)`.
- Filtra per `event_type` IN PYTHON dopo load (parse DSL solo 1 volta).
- Cache passive_modifiers per request (in-memory dict).
- Soft limit: warning se char ha >50 regole attive.

### R5 — Effetti irreversibili in dev (test)
**Rischio:** un test e2e applica `apply_modifier_once(+50 HP)` e il fixture char rimane storpiato per i test successivi.
**Mitigazione:**
- Fixture character ricreato fresh all'inizio di ogni test (`test:homebrew:audit` runner).
- Snapshot pre-run + restore post-run.

---

## 15. Strategia di Testing

### Livello 1 — Unit tests
**File:** `tests/services/homebrew/test_engine.py`, `test_dsl.py`, `test_passive.py`

Coverage:
- Ogni filter operator (8): input → output deterministico
- Ogni action (14): mock `random.randint` per determinismo. Asserisci sul side effect (DB row, history entry).
- Lookup table edge cases: `col_bins` boundary, missing row/col, fallback
- `match` / `if` con tutti i rami (cases vuoti, default mancante, deeply nested)
- DSL Pydantic validation: ogni campo invalido → ValidationError
- Path resolver: `$event`, `$subject`, `$character`, `$<var>` con paths nested

**Target:** 95%+ coverage su `api/services/homebrew/*`.

### Livello 2 — Integration tests
**File:** `tests/integration/homebrew/test_dispatcher.py`

Coverage:
- 1 rule + 1 event → asserisci side effect + return value
- Recursion depth limit: rule auto-ricorsiva → si ferma a depth 8 con log
- Cycle detection: rule A → rule B → rule A → skip silenzioso
- Passive modifiers: Character.ac response include `hb_modifier_total: +X`
- Multiple rule firing su stesso event: ordering (per `id` ASC), accumulo effetti
- Disabled rule = no firing
- Malformed DSL in DB = rule disabilitata automaticamente con history entry

### Livello 3 — E2E template tests
**File:** `tests/e2e/homebrew/test_template_*.py`

Una suite per template (4 totali):
- `test_template_quality_wear.py` — installa, modifica qualità su item, tira nat-1 deterministico (seeded), asserisci damage_state cambia, history, notify
- `test_template_bleeding.py` — applica condition custom:bleeding, premi "Inizio turno", asserisci HP diminuito di 1d4 (seeded)
- `test_template_enchanted_weapon.py` — installa, equipaggia weapon, tira attacco, asserisci damage_total include +1d6 fuoco extra
- `test_template_luck_points.py` — installa, consuma resource, riposo lungo, asserisci restore

### Livello 4 — Playwright E2E matrix (output `docs/homebrew-audit/`)
**File:** `tests/e2e-playwright/homebrew/*.spec.ts`

Coverage matrix (~70 tests):
- **15 eventi:** 1 test per evento. Trigger via API o UI, asserisci dispatcher chiamato.
- **16 azioni:** 1 test per azione in isolamento (escluso `sequence` che è implicito nella lista `effects`).
- **4 template:** lifecycle completo (install + interaction + uninstall).
- **5 passive modifier targets:** AC/HP/Speed/Skill/Save bonus correttamente sommato e visibile in UI.
- **8 filter operators:** uno per operator.
- **~10 error cases:** DSL malformato, regola disabilitata, depth limit, race, missing subject, recursion.
- **State transitions:** per ogni property enum N-stati, N(N-1) transizioni testate.

**Runner CLI:** `npm run test:homebrew:audit`. Workflow:
1. Snapshot DB
2. Crea fixture character (dedicated, separato da `webapp-audit/fixture-character.md`)
3. Esegue tutti gli spec sequenzialmente
4. Per ogni test produce un finding entry in `docs/homebrew-audit/NN-area.md`
5. Aggrega 🔴/🟠/🟡 in `docs/homebrew-audit/known-issues.md`
6. Diff vs `.previous.md` (baseline precedente)
7. Restore DB snapshot
8. Exit code = 0 se nessuna nuova issue, !=0 altrimenti

**Output format del report — IDENTICO a `docs/webapp-audit/known-issues.md`:**

```markdown
# Known Issues — Homebrew Engine Audit YYYY-MM-DD

## Conteggi
| Severità | Conteggio |
|---|---|
| 🔴 Bug funzionale | N |
| 🟠 Regressione visiva | N |
| 🟡 UX | N |
| 🟢 Nice-to-have | N |

---

## 🔴 BUG FUNZIONALI

### #1 — <Titolo del test fallito>
**Area:** `NN-area.md`
**Evento:** `attack_rolled` con `is_fumble=true`
**Sintomo:** <descrizione del comportamento osservato>
**Root cause:** <ipotesi dal trace dell'esecuzione>
**Fix proposto:** <suggerimento concreto>
```

**Severity assignment automatica:**
- 🔴 = assertion fallita sul state core (DB property, HP, condition)
- 🟠 = state corretto ma display UI non aggiornato (mismatch frontend vs API)
- 🟡 = tempi >2s, manca toast/feedback, micro-interazioni
- 🟢 = tutto verde ma annotazioni discovery (es. "manca animazione")

Il file `known-issues.md` è l'**input per `/audit-loop`** — stesso formato del `docs/webapp-audit/` esistente. `/audit-loop` può iterare fix → re-run → diff.

**Directory structure prodotta:**
```
docs/homebrew-audit/
├── 00-index.md
├── fixture-character.md         # stato del PG fixture
├── known-issues.md              # roll-up findings (input per /audit-loop)
├── 01-event-coverage.md         # 15 findings
├── 02-action-coverage.md        # 14 findings
├── 03-templates.md              # 4 findings (template lifecycle)
├── 04-passive-modifiers.md      # 5 findings
├── 05-filters.md                # 8 findings
├── 06-error-cases.md            # ~10 findings
└── 07-state-transitions.md      # findings per ogni property enum
```

---

## 16. Out of scope (esplicitato per writing-plans)

Confermato durante brainstorming come **deferred a v2**:
- Editor a grafo visuale (n8n-style)
- Pattern interattivi pre-roll: Fortunato (reroll d20), Auto-10 (Amuleto Orologeria), Maestro d'Armi Possenti (opt-in -5/+10), advantage/disadvantage dinamici
- Sharing / import / export di regole tra utenti
- Marketplace / community template
- Multi-utente / GM role
- Effetti asincroni / delayed
- Audit log dettagliato per ogni firing (basta `CharacterHistory`)
- Modifiers su ability scores, proficiency bonus, weapon damage rolls

---

## 17. Acceptance criteria (per writing-plans)

Il piano di implementazione è completo quando:

1. **Backend**
   - 2 nuove tabelle create via migration
   - `api/services/homebrew/` modulo completo con dispatcher, engine, dsl, templates, passive
   - 6 router esistenti (items, hp, spell_slots, abilities, classes/multiclass, homebrew stesso) emettono `dispatch(...)` su 8 endpoint complessivi
   - 12 endpoint API CRUD su `/characters/{id}/homebrew/*`
   - 4 template hardcoded e installabili

2. **Frontend**
   - Nuova route `/char/:id/homebrew` con lista + libreria + editor
   - 7 sezioni collassabili nell'editor, tutte in linguaggio naturale
   - Display custom states integrato in Inventory/Conditions/Abilities/AC/HP/Skills/Saves
   - i18n IT (default) + EN per tutte le label DSL→UI

3. **Test**
   - 95%+ coverage unit + integration su `api/services/homebrew/*`
   - 4 e2e template tests passano
   - Playwright matrix completa (~70 test) eseguibile via `npm run test:homebrew:audit`
   - `docs/homebrew-audit/known-issues.md` generato con 0 🔴 al primo run

4. **End-to-end manuale (sanity)**
   - Installo Qualità & Usura → modifico spada a qualità Pessima → tiro attacco con `--seed=fumble` → vedo spada Danneggiata
   - Installo Sanguinamento → premo "Inizio turno" → HP scende di 1d4
   - Installo Punti Fortuna → resource visibile in Abilities → consumo 1 → riposo lungo → restore

---

## 18. Open questions (per writing-plans / implementation)

- **Q1:** Per i template hardcoded, è preferibile un file Python (`templates.py` con dict) o JSON sotto `api/services/homebrew/templates/*.json`?
- **Q2:** L'editor di tabelle DSL (sezione 4 dell'editor UI) deve essere visibile sempre o solo in "modalità avanzata"? (Inclination: collassato default, toggle "Mostra impostazioni avanzate")
- **Q3:** Per `apply_modifier_once` (Robusto-style), il delta diventa parte di `Character.hit_points` permanente o vive in `passive_modifiers` come "static-once"? (Inclination: scrive direttamente sulla colonna, perché è retroattivo e permanente)
- **Q4:** Quando un PG viene clonato (feature non ancora in app), le regole homebrew vengono clonate? (Probabilmente sì, ma fuori scope)

---
*Fine spec — pronto per writing-plans skill.*
