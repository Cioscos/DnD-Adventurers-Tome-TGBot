# Copertura test — "blindatura" dell'app

Questa cartella è il **deliverable condiviso** dell'iniziativa di blindatura: traccia quali unità
FE/BE hanno test associati e i finding di compatibilità FE↔API. È mantenuta dal comando locale
**`/blinda-test`** (non versionato; vive in `.claude/commands/`).

## Come funziona

Il comando, ad ogni run:
1. costruisce/aggiorna il grafo di conoscenza graphify su `webapp/src api core` (incrementale);
2. enumera le unità testabili (componenti/pagine/lib/hooks/store FE; endpoint/service/model BE);
3. verifica la compatibilità FE↔API (firme di `webapp/src/api/client.ts` vs schemi Pydantic / route);
4. genera un **lotto** di test mancanti — **Vitest + React Testing Library** per il FE,
   **pytest** per il BE — e aggiorna questo report + `coverage-ledger.json`.

Va **rilanciato** finché i residui arrivano a 0.

- I test FE vengono eseguiti automaticamente (`npm --prefix webapp run test`).
- I test BE vengono **solo generati**: eseguili tu su **Windows** con `uv run pytest` (regola WSL: mai `uv` da WSL).

## Stato copertura

> Aggiornato da `/blinda-test`. Ultimo lotto: **2026-06-09 (lotto 2)** (branch `chore/blinda-test-batch-1`).
> Il grafo graphify è stato costruito su `webapp/src api core` (3468 nodi, 9200 archi); al lotto 2
> `--update` è stato un no-op (zero modifiche ai sorgenti dal build — i 797 "cambiati" segnalati erano
> file fuori scope `.claude/.github/docs` che `detect_incremental` cammina sull'intero root).
> I "totali" sono inventario su filesystem; le "coperte" sono le unità mappate nel ledger.

| Ambito | Totali (≈) | Coperte (ledger) | Residue (≈) |
|---|---|---|---|
| FE (components 92 · pages 75 · lib 20 · hooks 5 · store 5) | 197 | 8 | 189 |
| BE (endpoint 102 · funzioni service 31 · model/enum 22) | 155 | 10 (+ motore homebrew, vedi nota) | ~145 |

> **Nota copertura BE pre-esistente:** oltre alle 5 unità mappate nel ledger, il repo aveva già
> una suite consistente — l'intero **motore homebrew** (`tests/services/homebrew/*`,
> `tests/integration/homebrew/*`, `tests/e2e/homebrew/*`) e varie regressioni
> (`tests/integration/test_hp_heal_regression.py`, `test_conditions_regression.py`,
> `test_use_consumable.py`, `test_carry_capacity_override.py`, ecc.). Non sono ancora enumerate
> unità-per-unità nel ledger; lo saranno nei prossimi lotti per affinare il diff.

### Lotto 2026-06-09 (8 unità, focus logica D&D 5e ad alto rischio)

**FE — Vitest, verdi (41 test, 5 file):**
- `lib/dnd.ts` — `profBonus`, `mod`
- `lib/xpThresholds.ts` — `levelFromXp`, `getNextLevelThreshold`, `quickXpAmounts`
- `lib/classProgression.ts` — `progressionKey`, `progressionRows`, `localizeFeatures` (+ contract su `class-progression.json`)
- `lib/unarmedStrike.ts` — `martialArtsDie`, `unarmedDamageDice` (+ contract con `core/game/attacks.py`)
- `lib/equipmentSlots.ts` — `ITEM_TYPE_TO_SLOTS`, `slotsAllowedFor`, `isSlotAllowed`, `isTwoHanded`, `handsConflict` (+ contract con `EQUIPMENT_SLOT_COMPAT`)

**BE — pytest, `be-pending` (da eseguire su Windows):**
- `routers/hp.py::POST /characters/{id}/death_saves/roll` → `tests/integration/test_death_save_roll.py`
- `routers/hp.py::POST /characters/{id}/rest` → `tests/integration/test_rest.py`
- `services/spell_slots.py::recalc_spell_slots` → `tests/services/test_recalc_spell_slots.py`

### Lotto 2026-06-09 #2 (8 unità, focus endpoint HP/morte ad alto rischio + slot CA + lib/store FE)

**FE — Vitest, verdi (17 test, 3 file · suite totale 58 test / 8 file):**
- `lib/conditions.ts` — `CONDITION_ICONS` (14 condizioni 5e + spossatezza), `formatCondition` (ramo exhaustion-con-livello / slug)
- `lib/resourceDiff.ts` — `diffResourceMaxes` (solo delta `max_uses` positivi su Ability `is_class_feature`)
- `store/characterStore.ts` — `setActiveCharId` (azzera `activeScreen` solo al cambio id), `setActiveScreen`, `setLocale`, derivazione locale

**BE — pytest, `be-pending` (da eseguire su Windows):**
- `routers/hp.py::PATCH /characters/{id}/hp` → `tests/integration/test_hp_update.py` (temp HP, clamp 0, accrual fallimenti a 0, +2 critico, morte istantanea overflow, reset cura, clamp set_*)
- `routers/hp.py::PATCH /characters/{id}/death_saves` → `tests/integration/test_death_saves_update.py` (SUCCESS x3 stabile, FAILURE x3 morto, STABILIZE 1 HP, RESET, inerte da morto)
- `routers/hp.py::POST /characters/{id}/revive` → `tests/integration/test_death_saves_update.py` (rianima 1 HP + reset; no-op se vivo)
- `routers/hp.py::POST /characters/{id}/hit_dice/spend` → `tests/integration/test_hit_dice_spend.py` (cura roll+CON clampata; 404 classe ignota; 400 count<1)
- `services/equipment.py::swap_slot_occupant` → `tests/services/test_swap_slot_occupant.py` (displacement atomico, filtri slot/self/equipped)

## Finding compatibilità FE↔API

Le unità FE di questo lotto sono **lib pure** (nessuna chiamata diretta `api.*`): la verifica di
compatibilità ha riguardato i **contratti FE↔BE** che esse mirrorano. Tutti **allineati** — nessun
mismatch 🔴/🟠. I contratti sono stati codificati come assert nei test (un drift futuro li fa fallire):

| Contratto FE | Oracolo BE | Esito |
|---|---|---|
| `lib/equipmentSlots.ts` · `ITEM_TYPE_TO_SLOTS` | `api/services/equipment.py` · `EQUIPMENT_SLOT_COMPAT` | ✅ allineato |
| `lib/unarmedStrike.ts` · `martialArtsDie` | `core/game/attacks.py` · `martial_arts_die` | ✅ allineato |
| `lib/classProgression.ts` · `CLASS_NAME_TO_PROGRESSION_KEY` | chiavi di `webapp/src/data/class-progression.json` | ✅ tutte e 12 le classi presenti |

**Lotto 2:** anche le 3 unità FE di questo lotto sono **pure** (nessuna chiamata `api.*` diretta:
`conditions.ts`/`resourceDiff.ts` consumano tipi, `characterStore.ts` è stato UI client). Contratto
verificato: FE `Ability` ↔ BE `AbilityRead` (`api/schemas/common.py`) — i campi consumati da
`diffResourceMaxes` (`id`/`name`/`max_uses`/`is_class_feature`) esistono tutti nel serializer ⇒ **allineato**,
nessun mismatch 🔴/🟠. Il ramo `exhaustion`-come-`int` di `formatCondition` combacia con la scrittura
intera fatta da `POST /rest` (`conditions["exhaustion"] = new_exh`). Il **primo giro di compat HTTP reale**
(componenti che chiamano `api.*`) resta da fare — vedi residui.

## Prossimi residui per rischio (per il lotto successivo)

1. `routers/hp.py::POST /hp/recalc` — ricalcolo HP da formula `total_base_hp` (clamp current su Δmax)
2. `routers/spell_slots.py` — endpoint slot manuali (use/restore)
3. `services/character_response.py::build_character_response` — serializer (CA, HP effettivi, slot): oracolo centrale
4. `routers/items.py::PATCH /characters/{id}/items/{item_id}` — endpoint slot-aware che invoca `swap_slot_occupant` (giro end-to-end CA)
5. FE: `lib/sessionHelpers.ts`, `hooks/useLongPress.ts`, e altre `lib/*` ancora scoperte
6. **Componenti FE che chiamano davvero l'API** (HeroScreen, HPGauge, ecc.) → primo vero giro di compat FE↔API HTTP (mock `api.*` + contract test sulla shape della risposta BE)

## File

- `coverage-ledger.json` — mappa unità → test + stato (`fe-green` / `be-pending` / `be-green`).
- `README.md` — questo report umano.
