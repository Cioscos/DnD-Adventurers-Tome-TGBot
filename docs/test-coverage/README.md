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

> Aggiornato da `/blinda-test`. Ultimo lotto: **2026-06-09 (lotto 7)** (branch `chore/blinda-test-batch-1`).
> Il grafo graphify resta su `webapp/src api core` (3468 nodi / 9200 archi). Al lotto 7 `--update`:
> dal build del grafo (01:54) gli unici sorgenti in-scope cambiati erano i 2 router BE già noti
> (`api/routers/characters.py`, `api/routers/items.py`, fix dei lotti precedenti). Un `--update`
> precedente era rimasto a metà con un `.graphify_incremental.json` fuori scope (829 file: `bot/`,
> `docs/app`, `.claude/`); è stato scartato. Provando a fondere i 2 file via `build_merge`, la **guardia
> anti-collasso** di graphify ha rifiutato (il dedup fuzzy avrebbe portato 3468→2868 nodi), quindi
> `graph.json` è rimasto **intatto e queryabile**: i 2 router cambiati sono comunque letti direttamente
> come oracolo nella verifica compat. I "totali" sono inventario su filesystem; le "coperte" sono le
> unità mappate nel ledger.

| Ambito | Totali (≈) | Coperte (ledger) | Residue (≈) |
|---|---|---|---|
| FE (components 92 · pages 75 · lib 20 · hooks 5 · store 5) | 197 | 18 | ~179 |
| BE (endpoint 102 · funzioni service 31 · model/enum 22) | 155 | 45 (32 be-green + 13 be-pending; + motore homebrew, vedi nota) | ~110 |

> **Nota copertura BE pre-esistente:** oltre alle unità mappate nel ledger, il repo aveva già
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

### Lotto 2026-06-09 #3 (8 unità, primo giro compat FE↔API HTTP + serializer centrale)

**FE — Vitest, verdi (25 test, 3 file · suite totale 83 test / 11 file):**
- `lib/sessionHelpers.ts` — `getMyRole` (gm > player > none, guardie su null) + `formatUptime` (Xm / Xh Ym, ISO o `Date`, clamp negativi). Contratto FE↔BE su `gm_user_id`/`participants[].user_id`/`created_at` codificato negli assert.
- `hooks/useLongPress.ts` — tap vs long-press vs move-cancel (>12px) + ramo `onProgress` (ring poll ~30Hz, `Date` mockato). **Regressione** `[[reference_uselongpress_cancel_then_end]]` codificata: `pointercancel` pre-soglia + `touchend` stray non ritocca `onClick`; doppia consegna pointer+touch = singolo `onClick`.
- `components/ui/HPGauge.tsx` — presentazionale puro: 10 celle segmentate, `pulse-danger` a ≤25%, no-crash con `max=0`, modalità non-segmentata, overlay temp. `framer-motion` mockato (`m.*` + `useReducedMotion` → niente `matchMedia` in jsdom).

**BE — pytest, `be-pending` (da eseguire su Windows):**
- `routers/hp.py::POST /characters/{id}/hp/recalc` → `tests/integration/test_hp_recalc.py` (formula `total_base_hp`; max↓ clampa current, max↑ somma delta, 0 classi → 0/0; shape `CharacterFull`)
- `routers/spell_slots.py::PATCH /characters/{id}/spell_slots/{slot_id}` → `tests/integration/test_spell_slots.py` (cast `used↑`/refund `used↓`, total-only, 404, `available`)
- `routers/spell_slots.py::POST /characters/{id}/spell_slots/reset` → `tests/integration/test_spell_slots.py` (azzera tutti gli `used`)
- `services/character_response.py::build_character_response` → `tests/integration/test_character_response.py` (ac_breakdown + `ac=base+shield+magic`, default homebrew, risoluzione ability con modificatore item)
- `routers/items.py::PATCH /characters/{id}/items/{item_id}` → `tests/integration/test_item_equip_ac.py` (equip/unequip armor+shield → CA, displacement resetta CA occupante, slot incompatibile 422)

### Lotto 2026-06-09 #4 (8 unità, focus combattimento/magia ad alto rischio D&D 5e)

**FE — Vitest, verdi (21 test, 2 file · suite totale 104 test / 13 file):**
- `lib/relativeTime.ts` — `formatRelative` (oggi/ieri/`Intl` day‑week 2–30 gg/data assoluta same‑year vs altro anno), `formatAbsolute`, `dayKey` (YYYY‑MM‑DD zero‑pad), `dayHeader`. Rami locale‑aware pinnati contro le stesse `Intl` API; `now` fisso → bucket deterministici; date costruite/lette in locale → TZ‑independent; verificata la non‑mutazione di `now`/`date` nel diff.
- `lib/spellSrd.ts` — `lookupSrdSpell` (chiave canonica + alias, case‑insensitive, `trim`, `null` su vuoto/ignoto, chiavi `_` ignorate) + `srdSpellNames` (ordinate, escluse le metadata). JSON `spells-srd` mockato con `vi.mock` hoisted → testa la **logica** di indicizzazione indipendente dai dati reali.

**BE — pytest, `be-pending` (da eseguire su Windows):**
- `routers/spells.py::POST …/spells/{id}/use` → `tests/integration/test_spell_use.py` (slot `used+1`/`available`, concentrazione attivata/None, 400 slot assente/esaurito, 404 spell)
- `routers/spells.py::POST …/spells/{id}/roll_damage` → `tests/integration/test_spell_roll_damage.py` (RNG eliminato via `main_rolls`/`extra_rolls`: crit raddoppia il **numero** di dadi, `half_damage` round‑up, bonus piatto una volta, extra_dice, 400 lunghezza/range/casting_level/no‑damage)
- `routers/spells.py::POST …/concentration/save` (→ `_helpers.roll_concentration_save`) → `tests/integration/test_concentration_save.py` (DC=`max(10, danno//2)`, nat20/nat1, `die+CONmod>=DC`, perdita concentrazione + clear verificato via GET)
- `routers/items.py::POST …/items/{id}/attack` → `tests/integration/test_weapon_attack.py` (to‑hit `d20+mod+PB`, crit raddoppia danno, fumble azzera, melee/ranged/finesse, ispirazione consumo/409, 400 non‑arma, 404)
- `routers/items.py::POST …/attack/unarmed` → `tests/integration/test_unarmed_attack.py` (flat‑1 non‑monaco NON raddoppiato dal crit; dado arti marziali monaco `1d6` a L5 + crit raddoppia; ispirazione 409)
- `routers/classes.py::PATCH …/classes/distribute` → `tests/integration/test_classes_distribute.py` (multiclasse: `classes_mismatch`/`sum_exceeds_target` 400, scaling HP a ratio `10+6+5=21`, `hp_gained`)

### Lotto 2026-06-09 #5 (8 unità BE, focus progressione/attributi derivati & tiri d20 ad alto rischio)

Lotto **interamente BE** (`be-pending`): tutta la logica D&D 5e ancora scoperta era lato server (la
matematica derivata di `core/game/stats.py` e i ripple attributi→HP/CA/carico, XP→livello, multiclasse,
tiri d20). I residui FE rimasti sono ormai presentazionali/UI-state (rischio basso). Suite FE invariata
e ri-verificata verde di non-regressione: **104 test / 13 file**.

**BE — pytest, `be-pending` (da eseguire su Windows):**
- `core/game/stats.py` (modulo PURO) → `tests/services/test_stats.py` — `ability_modifier` (floor-div, 1→-5), `hit_points_for_level` (L1=die+CON / L2+=die//2+1+CON, clamp 1, ValueError), `unarmored_defense_ac`, `total_base_hp` (id più basso possiede lo slot L1, ordinamento, CON per livello, vuoto→0), `effective_ability_score` (relativi sommati + assoluti come pavimento, JSON-string, ability/valori invalidi, `ValueError`)
- `routers/stats.py::PATCH …/ability_scores/{name}` → `tests/integration/test_ability_scores.py` — validazione 1–30, **CON↑/↓ → ripple HP** `delta_mod*total_level` (simmetrico), **STR → carico** (×15), non-CON non tocca HP
- `routers/stats.py::POST …/ac/unarmored-defense` → `tests/integration/test_unarmored_defense.py` — Difesa Senza Armatura `10+DEX+2a`, re-sync ai cambi DEX/2a, **clear del base override** (mutuo), disabilita→10, 400 ability invalida
- `routers/characters.py::PATCH …/xp` → `tests/integration/test_xp_levelup.py` — `set`/`add` clamp ≥0, monoclasse XP→livello→**+HP** (`hp_gained`), level-down **non** toglie HP, multiclasse **no auto-sync**
- `routers/classes.py::POST …/classes` → `tests/integration/test_add_class.py` — 1ª classe bootstrap HP + save proficiency; 2ª classe **no HP / no save** (regola multiclasse); default `hit_die`/`spellcasting` per classe predefinita; 404
- `routers/classes.py::PATCH …/classes/{id}` → `tests/integration/test_update_class.py` — edit grezzo level/subclass/hit_die **senza ripple HP** (`proficiency_bonus` sì), level-up **sincronizza feature** (Monaco→Punti Ki), 404
- `routers/characters.py::POST …/skills/{name}/roll` → `tests/integration/test_skill_roll.py` — d20 deterministico, `bonus = mod + 0/PB/2×PB(expert)`, crit/fumble, skill ignota 400, ispirazione 409/consumo
- `routers/characters.py::POST …/saving_throws/{ability}/roll` → `tests/integration/test_saving_throw_roll.py` — `bonus = mod + (PB se proficient)` (Guerriero seedato STR/CON), ability ignota 400, crit/fumble, ispirazione 409/consumo

### Lotto 2026-06-09 #6 (10 unità: primo giro FE-mutation reale + progressione/dadi/CA/incantesimi residui)

Primo lotto che testa **componenti/pagine FE che chiamano davvero `api.*` con mutation** (residuo
prioritario #1): la verifica di compatibilità FE↔API passa da "lib pure che mirrorano contratti" a
"endpoint HTTP realmente invocati dal FE". I residui ad alto rischio D&D ancora lato server (rimozione
classe, dadi generici, override CA, CRUD incantesimi, concentrazione) chiusi in parallelo.

**FE — Vitest, verdi (16 test, 3 file · suite totale 120 test / 16 file):**
- `components/WeaponAttackModal.tsx` — presentazionale (props `WeaponAttackResult`): colpo normale (emerald) / **critico** (gold + pulse + label "(critico)") / **fumble** (crimson, **blocco danno nascosto**); bottone reroll ispirazione (solo se `inspirationAvailable && !wasRerolled && handler`) + badge a `wasRerolled`. **Gap 🟠 codificato**: il tipo FE ha esattamente 10 campi e **omette `homebrew_notifications`** (il render non si rompe col campo extra a runtime).
- `components/DicePoolResultModal.tsx` — mutation reroll → **`api.dice.result`**; bottone solo su pool d20 puro; click → body `DiceResultRequestBody` **esatto** `{rolls:[{kind:'d20',value}], notation:'1d20', with_inspiration:true}` (`Math.random` pinnato, `animate3d=false` → niente canvas 3D), onSuccess locka il bottone, **409 → toast.error**.
- `pages/Actions.tsx` — skeleton in pending; lista **solo armi equipaggiate**; `api.items.attack(charId,itemId)` / `attackUnarmed(charId)` / **reroll con `with_inspiration=true`** (terzo arg); apre `WeaponAttackModal` col result intero.

**BE — pytest, `be-pending` (da eseguire su Windows):**
- `routers/classes.py::DELETE …/classes/{id}` → `tests/integration/test_delete_class.py` — scaling HP a ratio (parità con `distribute`): 21→16 a HP pieno, `round(7/21·16)=5/16` danneggiato, ultima classe → 0/0, 404
- `routers/dice.py::POST …/dice/result` → `tests/integration/test_dice_result.py` — il server **non tira**: range 400, `total` override (4d6kh3 = 15 non 16), notation inferita (`+3`/`-2`/`2d6`), ispirazione 409/consumo, history append + `GET`/`DELETE`
- `routers/stats.py::PATCH …/ac` + `POST …/ac/reset-override` → `tests/integration/test_ac_override.py` — override `base`/`shield` lock (clamp ≥0) vs `magic` senza flag; reset ricalcola da equip (base→10/shield→0), `magic` intatto
- `routers/spells.py::POST …/spells` + `PATCH …/spells/{id}` → `tests/integration/test_spell_crud.py` — create (solo `name`, default trucchetto) + `exclude_unset` partial + 404
- `routers/spells.py::PATCH …/concentration` → `tests/integration/test_concentration_manual.py` — set/clear/empty-body di `concentrating_spell_id`

> Mappata anche la copertura BE **pre-esistente** `tests/integration/test_carry_capacity_override.py`
> (`be-green`, verde nel run 477/0) per affinare il diff — non rigenerata.

### Lotto 2026-06-09 #7 (8 unità: chiusura FE mutation pages grandi + CRUD BE residui)

Chiuso il residuo prioritario #1: le **due pagine mutation più grandi** (`HP.tsx` 435 righe /
`ArmorClass.tsx` 357 righe), entrambe verdi e verificate. In parallelo, CRUD BE ancora scoperto
(abilities free-form, items create/delete, spells delete). Scoperto che `test_spell_slots.py`
copriva **già** POST/DELETE slot (mai mappati): mappati come `be-green` invece di rigenerarli.

**FE — Vitest, verdi (18 test, 2 file · suite totale 138 test / 18 file):**
- `pages/HP.tsx` — skeleton in pending; PF render `current`/`(hit_points + hp_max_homebrew_modifier)`;
  `handleApply` parse + guard (NaN/≤0 → niente PATCH) + **`was_critical_hit` true solo a 0 HP con crit attivo**;
  quick-apply `heal` + **undo toast**; **riposo corto** (`spendHitDice` poi `rest('short')` via HitDiceModal) /
  **lungo** (`rest('long')` via ConfirmSheet); sezione **morente** (DeathSaves: `rollDeathSave(id, undefined)`
  con reducedMotion, `updateDeathSaves(id, action)`); **morto** (DeadState → `revive`); **dialog concentrazione**
  (+ toast warning su `lost_concentration`) e **morte istantanea** (`is_dead && failures<3`). Mock di
  api/router/framer-motion/i18n + tutti i sottocomponenti `pages/hp/*`.
- `pages/ArmorClass.tsx` — skeleton; CA totale `= ac + ac_breakdown.homebrew` + breakdown `base+shield+magic`;
  Save **disabilitato finché non dirty**; PATCH `updateAC` con **solo i campi compilati** (vuoti → `undefined`);
  **preview live** del nuovo totale; **reset override** (`resetACOverride`); **Difesa Senza Armatura**
  (`setUnarmoredDefense` con `wisdom`/`constitution`/`null`); base input **disabilitato** quando unarmored attivo.

**BE — pytest, `be-pending` (da eseguire su Windows):**
- `routers/abilities.py::POST …/abilities` → `tests/integration/test_abilities_crud.py` — create 201, shape `AbilityRead`, default minimi, listata
- `routers/abilities.py::PATCH …/abilities/{id}` → `test_abilities_crud.py` (+ `test_ability_protection.py` per il lock, già verde) — uses↓=uso (dispatch `ability_used`, niente notifiche senza regole), uses↑=ripristino, rinomina/max_uses liberi su non-class-feature, 404
- `routers/abilities.py::DELETE …/abilities/{id}` → `test_abilities_crud.py` (+ `test_ability_protection.py`) — 204 + de-listata, 404
- `routers/items.py::POST …/items` → `tests/integration/test_item_crud.py` — create 201 (CharacterFull), **dedup generico per nome** (merge quantity), arma con slot, **slot incompatibile → 422**
- `routers/items.py::DELETE …/items/{id}` → `test_item_crud.py` — 200 (CharacterFull senza l'item), 404
- `routers/spells.py::DELETE …/spells/{id}` → coda di `test_spell_crud.py` — 204 + de-listato, 404

> Mappata copertura BE **pre-esistente** in `test_spell_slots.py` (`be-green`, run 477/0): `POST …/spell_slots`
> (create 201 + `available`) e `DELETE …/spell_slots/{id}` (204) — il lotto 3 aveva mappato solo PATCH/reset.

## Bug BE smascherati eseguendo i pytest (2026-06-09)

Primo `uv run pytest` su Windows dell'intera suite BE accumulata (mai eseguita prima per i lotti
`be-pending`): **429 passati / 48 falliti**. I 48 rossi sono **2 bug reali del BE** (1 che cascata su ~46
test), non 48 problemi distinti — i test erano corretti e hanno fatto il loro lavoro. `test_stats.py`
(matematica pura D&D) **31/31 verde**. Entrambi i bug **corretti** in questo branch; i test bloccati
restano `be-pending` finché un nuovo run su Windows non li conferma verdi.

| # | Sev | Bug | Dove | Fix applicato |
|---|---|---|---|---|
| 1 | 🔴 | `POST /characters` con `initial_class` → 500 `MissingGreenlet` (lazy-load di `char.classes` in contesto async). Il wizard (`CharacterSelect.tsx`) invia `initial_class` ⇒ **creare un personaggio con classe iniziale è rotto**. Cascata su ~46 test (ogni fixture che crea il char con classe). | `api/routers/classes.py:133` (`if cls not in char.classes`), invocato da `characters.py::create_character` che non inizializzava la collection | `create_character`: aggiunto `char.classes = []` in memoria (mirror dell'esistente `char.abilities = []`) |
| 2 | 🟠 | Swap armatura non aggiorna la CA base: equipaggiando un'armatura su uno slot già occupato, la CA base resta 10 invece dell'`ac_value` del nuovo pezzo (il reset dell'occupante spiazzato girava DOPO, clobberando il valore appena impostato). | `api/routers/items.py:200-213` (`update_item`) | Riordinato: reset CA dell'occupante spiazzato **prima** di applicare la CA del nuovo pezzo |

> Nota: i fix sbloccano anche test `be-pending` di lotti precedenti che fallivano sulla stessa causa
> (`test_hp_recalc`, `test_classes_distribute`, `test_unarmed_attack` monaco — bug #1; `test_item_equip_ac`
> displacement — bug #2).
>
> **Re-run di conferma (2026-06-09, dopo i 2 fix): `477 passed, 0 failed`** (da 429/48 → 477/0, nessuna
> regressione). Tutte le unità BE del ledger passano ⇒ portate da `be-pending` a `be-green`. I warning
> residui (`ResourceWarning` / "Event loop is closed" in teardown aiosqlite) sono rumore benigno, non fallimenti.

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
intera fatta da `POST /rest` (`conditions["exhaustion"] = new_exh`).

**Lotto 3 — primo giro di compat FE↔API HTTP reale.** Verificati i metodi `api.*` (`webapp/src/api/client.ts`)
che colpiscono gli endpoint di questo lotto contro route + schemi Pydantic. Tutti **allineati**, nessun
mismatch 🔴/🟠; i contratti di risposta sono codificati come assert nei test (un drift dello schema fa fallire):

| Metodo FE (`client.ts`) | Endpoint BE | Esito |
|---|---|---|
| `api.recalcHp` → `POST /characters/{id}/hp/recalc` (no body) → `CharacterFull` | `recalc_hp` | ✅ allineato |
| `api.spellSlots.update` → `PATCH …/spell_slots/{id}` `{total?,used?}` → `SpellSlot` | `update_spell_slot` / `SpellSlotUpdate` → `SpellSlotRead` (`available`,`is_pact`) | ✅ allineato |
| `api.spellSlots.resetAll` → `POST …/spell_slots/reset` → `CharacterFull` | `reset_spell_slots` | ✅ allineato |
| `api.items.update` → `PATCH …/items/{id}` `Partial<Item>` → `CharacterFull` | `update_item` / `ItemUpdate` | ✅ allineato |
| `getMyRole`/`formatUptime` ← `gm_user_id`/`participants[].user_id`/`created_at` | `GameSessionRead` (`api/schemas/session.py`) | ✅ allineato |

Nota: `HPGauge` (candidato del residuo "componenti che chiamano l'API") si è rivelato **presentazionale puro**
— riceve `current/max/temp` via props, nessuna chiamata `api.*`. La query graphify lo aveva solo accostato al
nodo `api` euristicamente. Testato come componente puro.

**Lotto 4 — endpoint combattimento/magia.** Verificati i metodi `api.*` (`webapp/src/api/client.ts`) contro
route + schemi Pydantic. Tutti **allineati** sui campi che il FE invia/legge; i contratti di risposta sono
codificati come assert nei pytest:

| Metodo FE (`client.ts`) | Endpoint BE | Esito |
|---|---|---|
| `api.spells.use` → `POST …/spells/{id}/use` `{slot_level}` → `CharacterFull` | `use_spell` / `SpellUseRequest` | ✅ allineato |
| `api.spells.rollDamage` → `POST …/roll_damage` `RollDamageRequest` → `RollDamageResult` | `roll_spell_damage` | ✅ allineato (anche i campi 3D `main_kind`/`extra_kind`) |
| `api.spells.concentrationSave` → `POST …/concentration/save` `{damage}` → `ConcentrationSaveResult` | `concentration_save` (estende `RollResult`) | ✅ allineato (`die/bonus/total/is_critical/is_fumble/dc/success/lost_concentration`) |
| `api.items.attack` / `attackUnarmed` → `POST …/attack[/unarmed]` `{with_inspiration?}` → `WeaponAttackResult` | `attack_with_weapon` / `attack_unarmed` / `AttackSubmission` | ✅ allineato sui campi letti |
| `api.classes.distribute` → `PATCH …/classes/distribute` `{classes:[{class_id,level}]}` → `CharacterFull` | `distribute_class_levels` / `ClassDistribute` (`level` `ge=1,le=20`) | ✅ allineato |

🟠 **Gap di tipizzazione (non funzionale)** — `WeaponAttackResult` (definito sia in `client.ts` sia in
`components/WeaponAttackModal.tsx`) **omette** il campo `homebrew_notifications` che il BE restituisce
(opzionale) su `…/attack` e `…/attack/unarmed`. **Nessun impatto runtime**: gli attacchi passano da
`useMutation` (verificato in `pages/Actions.tsx` e `pages/Inventory.tsx`) e l'interceptor globale
`MutationCache.onSuccess` in `main.tsx` legge `homebrew_notifications` **dinamicamente** (`'…' in data`),
non dal tipo statico — quindi le notifiche delle regole homebrew su attacco (es. "Qualità & Usura") vengono
comunque mostrate. Consigliato (cleanup, non urgente) aggiungere `homebrew_notifications?: { … }[]` al tipo per
allinearlo allo schema e renderlo introspezionabile.

**Lotto 5 — progressione/attributi & tiri d20.** Verificati i metodi `api.*` (`webapp/src/api/client.ts`)
che colpiscono gli endpoint del lotto contro route + schemi Pydantic. Tutti **allineati**; le shape di
risposta sono codificate come assert nei pytest (un drift dello schema fa fallire). `core/game/stats.py`
è puro (nessuna `api.*`): il contratto verificato è che è il modulo-oracolo sotto HP/CA/mod letti dal FE.

| Metodo FE (`client.ts`) | Endpoint BE | Esito |
|---|---|---|
| `api.stats.updateAbilityScore` → `PATCH …/ability_scores/{name}` `{value}` → `CharacterFull` | `update_ability_score` / `AbilityScoreUpdate` | ✅ allineato |
| `api.stats.setUnarmoredDefense` → `POST …/ac/unarmored-defense` `{ability}` (`wisdom`/`constitution`/`null`) → `CharacterFull` | `set_unarmored_defense` / `UnarmoredDefenseUpdate` (valida ∈ {wisdom,constitution}/null) | ✅ allineato |
| `api.stats.updateXP` → `PATCH …/xp` `{add?,set?}` → `CharacterFull` (`hp_gained`) | `update_xp` / `XPUpdate` | ✅ allineato |
| `api.classes.add` / `update` → `POST/PATCH …/classes[/{id}]` → `CharacterFull` | `add_class` / `update_class` / `CharacterClassCreate`·`CharacterClassUpdate` | ✅ allineato |
| `api.stats.rollSkill` / `rollSavingThrow` → `POST …/{skills\|saving_throws}/…/roll` `{die?,with_inspiration}` o vuoto → `RollResult` | `roll_skill` / `roll_saving_throw` / `D20RollSubmission` (`die` `ge=1,le=20`) | ✅ allineato (`die/bonus/total/is_critical/is_fumble/description`) |

Nota: `rollSkill`/`rollSavingThrow` con `die` assente serializzano `JSON.stringify({die: undefined, …})`
che **scarta** la chiave `die` → `D20RollSubmission.die` resta `None` (RNG server-side). Coerente.

**Lotto 6 — primo giro su componenti/pagine FE che chiamano DAVVERO `api.*` con mutation.** Non più
solo lib pure: qui il FE invoca endpoint HTTP reali. Verificati i metodi `api.*` (`webapp/src/api/client.ts`)
contro route + schemi Pydantic; i payload inviati e le shape lette sono codificati come assert (un drift fa fallire):

| Metodo FE (`client.ts`) | Endpoint BE | Esito |
|---|---|---|
| `api.dice.result` → `POST …/dice/result` `DiceResultRequestBody` → `DiceRollResult` | `post_dice_result` / `DiceResultRequest` | ✅ allineato (`rolls[].{kind,value}`, `notation`, `with_inspiration`, `total?`) |
| `api.items.attack` / `attackUnarmed` (`charId, itemId?, withInspiration=false`) → `WeaponAttackResult` | `attack_with_weapon` / `attack_unarmed` | ✅ allineato sui 10 campi letti |
| `api.characters.get` → `CharacterFull` (`items[].{item_type,is_equipped}`, `classes`, `heroic_inspiration`) | `get_character` | ✅ allineato |

🟠 **Gap di tipizzazione (ribadito, non funzionale)** — confermato e ora **codificato in un test**
(`WeaponAttackModal.test.tsx`): `WeaponAttackResult` (in `client.ts` **e** in `WeaponAttackModal.tsx`)
ha esattamente 10 campi e **omette `homebrew_notifications`** che il BE restituisce opzionale su
`…/attack` e `…/attack/unarmed`. Nessun impatto runtime (l'interceptor `MutationCache.onSuccess` in
`main.tsx` lo legge dinamicamente con `'…' in data`); il test asserisce sia l'assenza della chiave nel
tipo sia che il render regge col campo extra. Cleanup consigliato (non urgente): aggiungere
`homebrew_notifications?: { … }[]` al tipo.

🟢 **`api.dice.result` — il FE omette `source`/`label`/`modifier`** dal body del reroll: `DiceResultRequest`
li ha tutti con default (`source=None`, `modifier=0`), quindi il subset inviato dal `DicePoolResultModal`
(`rolls`/`notation`/`with_inspiration`) è accettato e il `source` finisce a `"manual"`. Coerente, nessun mismatch.

**Lotto 7 — pagine mutation HP & CA.** Verificati i metodi `api.characters.*` (`webapp/src/api/client.ts`)
invocati da `HP.tsx`/`ArmorClass.tsx` contro route + schemi Pydantic, e i campi letti dalla risposta contro
il tipo FE (`webapp/src/types/index.ts`) e il serializer BE. Tutti **allineati**, nessun mismatch 🔴/🟠:

| Metodo FE (`client.ts`) | Endpoint BE | Esito |
|---|---|---|
| `updateHp` → `PATCH …/hp` `{op, value, was_critical_hit}` → `CharacterFull` | `HpUpdate` (`was_critical_hit` default False) | ✅ allineato |
| `rest` → `POST …/rest` `{rest_type, hit_dice_used}` | `RestRequest` (`hit_dice_used` opzionale) | ✅ allineato |
| `revive` / `updateDeathSaves` / `rollDeathSave` / `spendHitDice` | `revive` / `death_saves` `{action}` / `death_saves/roll` `{die?}` / `hit_dice/spend` `{class_id, count}` | ✅ allineato |
| `updateAC` → `PATCH …/ac` `{base?, shield?, magic?}` | `ACUpdate` | ✅ allineato |
| `resetACOverride` / `setUnarmoredDefense` → `POST …/ac/reset-override` · `…/ac/unarmored-defense` `{ability}` | `reset_ac_override` / `set_unarmored_defense` (∈ wisdom/constitution/null) | ✅ allineato |

Campi **letti** dal FE confermati presenti sia nel tipo FE sia in `CharacterFull` (BE): `concentration_save`
(opzionale, `Optional[ConcentrationSaveResult]`, popolato solo dalla risposta di `PATCH /hp`),
`base_armor_class_override`/`shield_armor_class_override`, `unarmored_defense_ability`, `ac_breakdown.homebrew`,
`death_saves`, `is_dead`, `concentrating_spell_id`, `hp_max_homebrew_modifier`. Le shape sono codificate come
assert nei test FE (un drift le fa fallire).

## Prossimi residui per rischio (per il lotto successivo)

1. **FE mutation pages restanti** (HP/ArmorClass chiusi nel lotto 7): pagine D&D ad alto rischio ancora scoperte —
   `pages/SpellSlots.tsx` + `pages/Spells.tsx` (create/patch/delete slot e incantesimi, cast, concentrazione),
   `pages/Multiclass.tsx` + `multiclass/LevelUpModal.tsx`/`EditClassesModal.tsx` (add/update/delete/distribute classi, level-up),
   `pages/Abilities.tsx` (uses/ripristino), `pages/AbilityScores.tsx`/`SavingThrows.tsx`/`Skills.tsx`/`Conditions.tsx`/`Experience.tsx`.
2. `core/db/models.py` — enum/property ad alto rischio (test puro, niente DB): `Character.proficiency_bonus`/`total_level`,
   `SpellSlot.use_slot`/`available`, `is_dead`, enum `EquipmentSlot`/`RestorationType` (finora toccate solo indirettamente via endpoint).
3. `routers/characters.py` — create/patch/delete top-level (parz. in `test_character_patch_refresh`); `routers/sessions.py` (sessioni di gioco) interamente scoperto.
4. `services/equipment.py::slot_allowed_for_type`/`EQUIPMENT_SLOT_COMPAT` come unità mappata; `routers/maps.py` upload/serve.
5. FE `lib/*` ancora scoperte (rischio basso): `roman.ts`, `rewardQueue.ts`, `eventMeta.ts`, `itemIcons.ts`, `celebrate.ts`, `silhouette.ts`, `inlineMarkdown.tsx`, `homebrew/i18n-dsl.ts`; FE hooks/store: `useSwipeNavigation`, `useToast`, `unitSettings`, `diceSettings`

## File

- `coverage-ledger.json` — mappa unità → test + stato (`fe-green` / `be-pending` / `be-green`).
- `README.md` — questo report umano.
