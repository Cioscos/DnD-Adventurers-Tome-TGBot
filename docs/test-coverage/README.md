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

> Aggiornato da `/blinda-test`. Ultimo lotto: **2026-06-09** (branch `chore/blinda-test-batch-1`).
> Il grafo graphify è stato costruito su `webapp/src api core` (3468 nodi, 9200 archi).
> I "totali" sono inventario su filesystem; le "coperte" sono le unità mappate nel ledger.

| Ambito | Totali (≈) | Coperte (ledger) | Residue (≈) |
|---|---|---|---|
| FE (components 92 · pages 75 · lib 20 · hooks 5 · store 5) | 197 | 5 | 192 |
| BE (endpoint 102 · funzioni service 31 · model/enum 22) | 155 | 5 (+ motore homebrew, vedi nota) | ~150 |

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

## Finding compatibilità FE↔API

Le unità FE di questo lotto sono **lib pure** (nessuna chiamata diretta `api.*`): la verifica di
compatibilità ha riguardato i **contratti FE↔BE** che esse mirrorano. Tutti **allineati** — nessun
mismatch 🔴/🟠. I contratti sono stati codificati come assert nei test (un drift futuro li fa fallire):

| Contratto FE | Oracolo BE | Esito |
|---|---|---|
| `lib/equipmentSlots.ts` · `ITEM_TYPE_TO_SLOTS` | `api/services/equipment.py` · `EQUIPMENT_SLOT_COMPAT` | ✅ allineato |
| `lib/unarmedStrike.ts` · `martialArtsDie` | `core/game/attacks.py` · `martial_arts_die` | ✅ allineato |
| `lib/classProgression.ts` · `CLASS_NAME_TO_PROGRESSION_KEY` | chiavi di `webapp/src/data/class-progression.json` | ✅ tutte e 12 le classi presenti |

## Prossimi residui per rischio (per il lotto successivo)

1. `routers/hp.py` — `PATCH /hp` (op damage/heal/set + accrual death save a 0), `hit_dice/spend`, `PATCH /death_saves`, `POST /revive`, `POST /hp/recalc`
2. `routers/spell_slots.py` — endpoint slot manuali (use/restore)
3. `services/equipment.py::swap_slot_occupant` — displacement atomico + reset CA
4. `services/character_response.py::build_character_response` — serializer (CA, HP effettivi, slot)
5. FE: `lib/conditions.ts`, `lib/resourceDiff.ts`, `lib/sessionHelpers.ts`, `store/characterStore.ts`, `hooks/useLongPress.ts`
6. Componenti FE che chiamano davvero l'API (HeroScreen, HPGauge, ecc.) → primo vero giro di compat FE↔API HTTP

## File

- `coverage-ledger.json` — mappa unità → test + stato (`fe-green` / `be-pending` / `be-green`).
- `README.md` — questo report umano.
