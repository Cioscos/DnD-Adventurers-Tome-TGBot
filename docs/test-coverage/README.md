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

> Aggiornato da `/blinda-test`. Ultimo lotto: **2026-06-09 (lotto 12)** (branch `chore/blinda-test-batch-1`).
> Il grafo graphify resta su `webapp/src api core` (3468 nodi / 9200 edge). Al lotto 12 — come ai lotti 8-11 — solo
> **2 file in-scope** risultavano modificati dopo il build del grafo (`api/routers/characters.py`,
> `api/routers/items.py`) — entrambi **edit interni** dei bug-fix (init `char.classes=[]`; riordino reset CA),
> **nessun endpoint/firma/schema nuovo** ⇒ la superficie API mappata è ancora accurata. `--update` avrebbe
> riprodotto i falsi positivi "deleted" del mismatch manifest↔scope; merge **saltato**, `graph.json` lasciato
> **intatto e queryabile** (replica delle decisioni dei lotti 8-10). I "totali" sono inventario su filesystem;
> le "coperte" sono le unità mappate nel ledger.

| Ambito | Totali | Coperte (ledger) | Residue |
|---|---|---|---|
| FE (components 89 · pages 72 · lib 20 · hooks 5 · store 5 + coperte) | 197 | 40 | 157 |
| BE (endpoint 102 · service 31 · core/game 2 · model/enum 22) | 157 | 113 (**tutte be-green** dopo il run del lotto 11) | 44 |

> **Back-fill copertura BE pre-esistente (lotto 8):** il diff dei lotti 1-7 ignorava la suite pytest
> **già presente** nel repo, che copriva molte unità "residue" → falsi negativi. Al lotto 8 sono state
> **mappate nel ledger (be-green)** 49 unità coperte da test esistenti (suite a `519 passed / 0 failed`):
> l'intero **motore homebrew** (24 funzioni in `tests/services/homebrew/*` + 13 endpoint router in
> `tests/integration/homebrew/test_routers_homebrew.py`), `effects.apply_heal`/`apply_conditions`
> (`test_hp_heal_regression.py`/`test_conditions_regression.py`/`test_use_consumable.py`) e il CRUD/GET
> character (`POST/GET/PATCH /characters`, `PATCH …/conditions|inspiration|skills`, GET
> abilities/items/spells). La copertura BE ledger è così salita da 45 → 99 senza generare test nuovi.

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

> **Run di conferma BE (2026-06-09, Windows): `519 passed, 0 failed` in ~90s.** Eseguito `uv run pytest`
> sull'intera suite dopo il lotto 7: tutti i `be-pending` accumulati (5 file del lotto 6 + 3 del lotto 7:
> `test_abilities_crud.py`, `test_item_crud.py`, DELETE in `test_spell_crud.py`) **passano** → portati a
> `be-green`. Da 477/0 → 519/0 (+42 test), nessuna regressione. I 276 warning residui sono
> `DeprecationWarning` benigni (`datetime.utcnow()`), non fallimenti. Ledger ora **0 be-pending**.

### Lotto 2026-06-09 #8 (back-fill copertura pre-esistente + fetta verticale currency contract-verified)

Run dominato dal **back-fill**: il diff dei lotti precedenti non considerava i pytest **già nel repo**,
quindi decine di unità coperte risultavano "residue". Mappate **49 unità be-green** dai test esistenti
(vedi nota in "Stato copertura") → copertura BE ledger 45 → 99 senza riscrivere nulla. In più, lotto di
**8 nuove unità** ordinate per rischio, con una **fetta verticale** BE↔FE sulla valuta (oracolo D&D 5e
delle conversioni monetarie + pagina FE che lo consuma, contratto codificato).

**FE — Vitest, verdi (20 test, 4 file · suite totale 158 test / 22 file):**
- `lib/roman.ts` — `toRoman` (1-9 → I-IX; fallback al numero fuori 1-9, es. livello 20). Puro.
- `lib/silhouette.ts` — `silhouetteUrl`: fallback `class_race_gender → class_race → class_gender → class`,
  mappatura nomi classe IT→EN (`Mago`→`wizard`), classe di livello più alto in multiclasse, `null` senza
  classe canonica o senza entry nel manifest. Manifest mockato per testare la logica di risoluzione.
- `store/unitSettings.ts` — store zustand (default `imperial`, `setSystem`) + helper di conversione su
  **fattore griglia D&D** (5 ft = 1.5 m, 1 lb = 0.5 kg): `feetToDisplay`/`displayToFeet`/`formatLength`,
  `lbToDisplay`/`displayToLb`/`formatWeight*`, round-trip puliti (30 ft ⇄ 9 m, 225 lb ⇄ 112.5 kg).
- `pages/Currency.tsx` — skeleton in pending; **read contract** (totale oro dalla shape `CurrencyRead`);
  **write contract** modalità `add` (PATCH current+delta per moneta) e `set` (monete non toccate restano al
  valore corrente); **convert** posta `(source, target, amount)` all'endpoint. Mock api/router/i18n/
  framer-motion + Sheet open-aware.

**BE — pytest, `be-pending` (da eseguire su Windows):**
- `services/equipment.py::slot_allowed_for_type` → `tests/services/test_slot_allowed.py` — mapping puro
  `item_type`→slot D&D (arma=mani, armatura=corpo, scudo=off-hand, accessori=collo/mantello/anelli,
  gear=testa/mani/piedi/munizioni); tipo ignoto → nessuno slot; ogni slot in `EQUIPMENT_SLOT_COMPAT` è un enum reale.
- `routers/currency.py::GET …/currency` → `tests/integration/test_currency.py` — crea il wallet vuoto (tutti 0 + `id`).
- `routers/currency.py::PATCH …/currency` → `test_currency.py` — set monete, campi non passati restano, clamp `max(0,·)` su negativi.
- `routers/currency.py::POST …/currency/convert` → `test_currency.py` — **tassi ufficiali** (1 gp = 10 sp);
  conversione "verso l'alto" restituisce il resto in copper senza distruggere valore (5 sp → 0 gp + 50 cp);
  400 su fondi insufficienti / source==target / amount≤0 / moneta sconosciuta.

> **Run di conferma BE (2026-06-09, Windows): `547 passed, 0 failed` in ~85s** (`uv run pytest`, log
> `pytest-all-be.log`). I 2 file `be-pending` del lotto 8 — `test_slot_allowed.py` (19 test) e
> `test_currency.py` (9 test) — **passano**: +28 test rispetto a 519/0, nessuna regressione, portati a
> `be-green`. Ledger ora **0 be-pending** (22 fe-green + 98 be-green). I 283 warning residui sono
> `DeprecationWarning` (`datetime.utcnow()`) e `ResourceWarning` ("Event loop is closed" in teardown
> aiosqlite) benigni, non fallimenti.

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

**Lotto 8 — pagina valuta + fetta verticale BE↔FE.** Verificati i metodi `api.currency.*` /
`api.characters.get` invocati da `Currency.tsx` contro route + schemi Pydantic e i campi letti dalla
risposta. Tutti **allineati**, nessun mismatch 🔴/🟠 — il contratto è codificato sia nel test FE
(risposte mockate con la shape esatta di `CurrencyRead`) sia nei pytest BE della stessa fetta:

| Metodo FE (`client.ts`) | Endpoint BE | Esito |
|---|---|---|
| `api.characters.get` → legge `char.currency.{copper,silver,electrum,gold,platinum}` | `get_character` → `CurrencyRead` (id + 5 monete) | ✅ allineato |
| `api.currency.update` → `PATCH …/currency` `{platinum,gold,electrum,silver,copper}` (int) → `CurrencyRead` | `update_currency` / `CurrencyUpdate` (tutti opzionali, BE clampa `max(0,·)`) | ✅ allineato |
| `api.currency.convert` → `POST …/currency/convert` `{source,target,amount}` → `CurrencyRead` | `convert_currency` / `CurrencyConvert` | ✅ allineato (400 su input invalido) |

Le altre 3 unità FE del lotto (`lib/roman.ts`, `lib/silhouette.ts`, `store/unitSettings.ts`) sono **pure**
(nessuna `api.*`); `silhouette.ts` mirrora i nomi-classe/razza/genere → slug, `unitSettings.ts` converte
solo al confine di display/input (il DB resta in unità canoniche piedi/libbre).

### Lotto 2026-06-09 #9 (8 unità: chiusura blocco `core/db/models.py` + 2 FE mutation pages magia/progressione)

Chiuso il residuo prioritario #1 — **l'intero `core/db/models.py`** (model/enum) — in un solo file pytest
**puro** (transient, niente DB/async): la matematica D&D 5e che vive direttamente sui modelli. In parallelo,
2 FE mutation pages alto-rischio ancora scoperte (slot incantesimi + esperienza/level-up).

**FE — Vitest, verdi (16 test, 2 file · suite totale 174 test / 24 file):**
- `pages/SpellSlots.tsx` — skeleton; render `available/total` + livello romano dalla shape `SpellSlotRead`;
  cast gemma libera → `update{used+1}` (clamp `total`) / click gemma usata → `update{used-1}` (clamp 0);
  `TotalEditor` blur → `update{total}`; add livello mancante → `add(level, total=1)`; remove → DELETE;
  reset-all via `ConfirmSheet` → `resetAll`→`CharacterFull`. **Auto mode** (`settings.spell_slots_mode`,
  default `'auto'`): `AutoModeBanner` + nessuna affordance manuale. `toRoman` reale, resto mockato.
- `pages/Experience.tsx` — skeleton; livello da `levelFromXp(experience_points)` (900→3); add → `updateXP{add}`,
  set (toggle) → `updateXP{set}`; CTA level-up → `updateXP{set: XP_THRESHOLDS[level]=2700}`; **toast level-up**
  quando `newLevel>oldLevel`; **toast hp_gained** quando `response.hp_gained>0`. `xpThresholds`+`resourceDiff`
  reali; sotto-componenti pesanti (`ClassTabs`/`ProgressionPreview`/`LevelUpModal`/`StatPill`/`Ornament`) mockati.

**BE — pytest `tests/services/test_models.py`, `be-green`** (eseguito su Windows 2026-06-09 — **tutti passati**):
- `core/db/models.py::Character` — `ac`, `total_level`, `proficiency_bonus` (tabella 5e completa con boundary),
  `class_summary`, `recalculate_encumbrance`, `recalculate_carry_capacity` (STR×15, default 150, rispetta override).
- `…::SpellSlot` — `available` clamp 0, `use_slot` (incr + `ValueError` se esaurito), `restore_slot` floor 0, `restore_all`.
- `…::Currency` — `RATES` ufficiali, `total_in_copper`, `convert` (esatto / resto value-preserving / fondi insufficienti no-op).
- `…::Ability` — `use` (decr / `ValueError` a 0 / no-op passiva), `restore` (reset a max / no-op senza max).
- `…::AbilityScore` — `modifier` floor-division (1→-5 … 30→10).
- `…::enums` — integrità membri+valori dei 6 enum + str-mixin (vedi `[[reference_sqlalchemy_enum_passthrough]]`).

**Lotto 9 — compat FE↔API.** Verificati i metodi `api.spellSlots.*` / `api.characters.updateXP` invocati da
`SpellSlots.tsx`/`Experience.tsx` contro route + schemi Pydantic. Tutti **allineati**, nessun mismatch 🔴/🟠;
i payload inviati e le shape lette sono codificati come assert (un drift fa fallire):

| Metodo FE (`client.ts`) | Endpoint BE | Esito |
|---|---|---|
| `spellSlots.add` → `POST …/spell_slots` `{level,total,used:0}` → `SpellSlotRead` | `add_spell_slot` / `SpellSlotCreate` | ✅ allineato |
| `spellSlots.update` → `PATCH …/spell_slots/{id}` `{total?,used?}` → `SpellSlotRead` | `update_spell_slot` / `SpellSlotUpdate` | ✅ allineato |
| `spellSlots.remove` → `DELETE …/spell_slots/{id}` (204) | `delete_spell_slot` | ✅ allineato |
| `spellSlots.resetAll` → `POST …/spell_slots/reset` → `CharacterFull` | `reset_spell_slots` | ✅ allineato |
| `characters.updateXP` → `PATCH …/xp` `{add?,set?}` → `CharacterFull` (`hp_gained`) | `update_xp` / `XPUpdate` | ✅ allineato |

Lette dal FE e confermate nello schema: `spell_slots[].{id,level,total,used,available,is_pact}` (`SpellSlotRead`),
`settings.spell_slots_mode` (source-of-truth in `settings`, vedi `[[project_spell_slots_mode_source]]`),
`experience_points`/`hp_gained`/`abilities` (`CharacterFull`). Le unità BE del lotto sono **pure** (nessuna `api.*`):
sono l'oracolo D&D 5e sotto le derivate (mod/PB/HP/CA/slot/valuta) lette altrove.

### Lotto 2026-06-09 #10 (8 unità: chiusura famiglia FE "stats/condizioni" + bulk saving_throws + router history)

Chiuse le **4 FE mutation pages della famiglia stats/condizioni** ancora scoperte (AbilityScores/SavingThrows/
Skills/Conditions): tutte invocano `api.*` con mutation reali, quindi la compat FE↔API passa dal contratto
statico al payload HTTP effettivo. In parallelo, BE: l'unico endpoint bulk delle proficiency ancora scoperto
(`PATCH /saving_throws`, legato alla compat di `SavingThrows.tsx`) + **chiusura completa di `routers/history.py`**
(3 endpoint).

**FE — Vitest, verdi (26 test, 4 file · suite totale 200 test / 28 file):**
- `pages/AbilityScores.tsx` — skeleton; read contract sui valori; `handleSave` con **doppia guard** (fuori
  1..30 → niente PATCH; valore invariato → chiude senza PATCH); save valido → `updateAbilityScore(id,ability,value)`;
  **CON che cambia `hit_points` → toast hp_recalc**. Card/EditModal mockati per esporre le affordance.
- `pages/SavingThrows.tsx` — skeleton; total = `mod + (PB se proficient) + homebrew` (STR proficient → +4,
  contract); toggle proficiency con `stopPropagation` (fuori dal path roll) → `updateSavingThrows` **merge**;
  roll su click Surface → `rollSavingThrow(id,ability,undefined)` (animate3d=false) → `RollResultModal`;
  reroll ispirazione → `(...,true)`, **409 → toast.error**.
- `pages/Skills.tsx` — skeleton; **expert doubling** `mod + 2×PB` (athletics expert L5 → +9) + passiva percezione;
  tap cicla livello (`expert→false`) → `updateSkills{[key]:next}`; **long-press → picker Sheet** → `updateSkills{[key]:value}`;
  roll → `rollSkill(id,key,undefined)`, reroll **409 → toast.error**. `useLongPress` mockato (onClick=tap/
  onContextMenu=longpress; il timing è coperto da `[[reference_uselongpress_cancel_then_end]]` in `useLongPress.test.ts`).
- `pages/Conditions.tsx` — skeleton; toggle standard → `updateConditions` merge; `setExhaustion` cumulativo;
  **reset-all** (ConfirmSheet) → `{exhaustion:0 + 14 keys false}`; **`deriveAppliableCustoms`/`collectApplyConditionKeys`**
  (walk ricorsivo su `if`/`match`): regola enabled con `apply_condition` annidato → `applyCustom` →
  `{custom:bleeding:{rule_id,params:{}}}`; `removeCustom` → `{custom:bleeding:false}` (merge non poppa);
  **turnStart** → `showHomebrewNotifications` se `notifications>0`, altrimenti `toast.info`.

**BE — pytest, `be-pending` (da eseguire su Windows):**
- `routers/characters.py::PATCH …/saving_throws` → `tests/integration/test_saving_throws_bulk.py` — bulk
  `SavingThrowsUpdate` (`dict[str,bool]`): **MERGE** (`current.update`, mai replace) → chiavi non inviate
  preservate, flip a false, aggiunta nuova chiave mantiene STR/CON seedate dal Guerriero; response `CharacterFull`; 404.
- `routers/history.py::GET …/history` → `tests/integration/test_history.py` — ordine `timestamp` desc (newest-first),
  shape `HistoryEntryRead` `{id,timestamp,event_type,description}` (**omette `meta`**); ownership 404 (assente) / 403 (altro owner).
- `routers/history.py::GET …/history/retention-preview` → `test_history.py` — `would_purge_events = max(0,total-events)`;
  `would_purge_days` = righe con `timestamp < utcnow-days` (confronto stringa ISO); query bounds `events`/`days` → 422 a 0.
- `routers/history.py::DELETE …/history` → `test_history.py` — wipe completo (204), GET successiva → `[]`; 404 assente.

> **Run di conferma BE (2026-06-09, Windows): verde.** Eseguiti su Windows `test_saving_throws_bulk.py` (5 test)
> e `test_history.py` (10 test) — **tutti passati**, nessuna regressione. I 4 `be-pending` del lotto 10 portati a
> `be-green`. Ledger ora **0 be-pending** (28 fe-green + 108 be-green).

**Lotto 10 — compat FE↔API.** Verificati i metodi `api.characters.*` / `api.homebrew.*` invocati dalle 4 pagine
contro route + schemi Pydantic. Tutti **allineati**, nessun mismatch 🔴/🟠; i payload inviati e le shape lette
sono codificati come assert (un drift fa fallire):

| Metodo FE (`client.ts`) | Endpoint BE | Esito |
|---|---|---|
| `characters.updateAbilityScore` → `PATCH …/ability_scores/{name}` `{value}` → `CharacterFull` | `update_ability_score` / `AbilityScoreUpdate` | ✅ allineato |
| `characters.updateSavingThrows` → `PATCH …/saving_throws` `{saving_throws}` → `CharacterFull` | `update_saving_throws` / `SavingThrowsUpdate` (`dict[str,bool]`) | ✅ allineato |
| `characters.rollSavingThrow` → `POST …/saving_throws/{a}/roll` `{die?,with_inspiration}` o vuoto → `RollResult` | `roll_saving_throw` / `D20RollSubmission` | ✅ allineato |
| `characters.updateSkills` → `PATCH …/skills` `{skills}` → `CharacterFull` | `update_skills` / `SkillsUpdate` | ✅ allineato |
| `characters.rollSkill` → `POST …/skills/{k}/roll` `{die?,with_inspiration}` o vuoto → `RollResult` | `roll_skill` / `D20RollSubmission` | ✅ allineato |
| `characters.updateConditions` → `PATCH …/conditions` `{conditions}` → `CharacterFull` | `update_conditions` / `ConditionsUpdate` | ✅ allineato |
| `homebrew.turnStart` → `POST …/homebrew/turn-start` → `{notifications:[…]}` | `turn_start` (shape `notifications`, NON `homebrew_notifications`) | ✅ allineato (gestito manualmente nel FE) |

Nota: `rollSkill`/`rollSavingThrow` con `die` assente e `with_inspiration=false` inviano **body `undefined`**
(`die != null || withInspiration` falso) → il server tira lato suo. Coerente con `D20RollSubmission` (tutti i
campi opzionali). Le 4 pagine leggono `ability_scores[].{name,value,modifier}`, `saving_throws`/`skills` (dict),
`saves_homebrew_modifiers`/`skills_homebrew_modifiers`, `total_level`, `heroic_inspiration`, `conditions` — tutti
presenti in `CharacterFull`.

### Lotto 2026-06-09 #11 (9 unità: chiusura FE magia/abilità/multiclasse + dice/characters BE)

Chiuse le **3 FE mutation pages più grandi ancora scoperte** (`Spells.tsx` 641 · `Abilities.tsx` 779 ·
`Multiclass.tsx` 209) + la **modale di level-up multiclasse** (`LevelUpModal.tsx`): tutte invocano `api.*`
con mutation reali (cast/concentrazione/CRUD incantesimi; usi/ripristino abilità + risorse homebrew;
rimozione classe; **distribuzione livelli multiclasse**). In parallelo, chiusura dei buchi BE rimasti su
`dice.py` e sulla collection character (list/delete).

**FE — Vitest, verdi (34 test, 4 file · suite totale 234 test / 32 file):**
- `pages/Spells.tsx` — skeleton; render incantesimi raggruppati + gemme-slot (`SpellSlotRead`); **cast leveled
  non-danno con concentrazione** → `spells.use(id, spellId, slotLevel)` poi `updateConcentration`; **cast leveled
  con danno** → defer alla `SpellDamageSheet` (slot **non** consumato, `data-slot` corretto); **cantrip con danno**
  → damage sheet a slot 0; **cantrip concentrazione** → `updateConcentration` senza slot; gemma usata→`update{used-1}`
  / disponibile→`update{used+1}` (clamp); toggle concentrazione da riga → `updateConcentration`; remove → `spells.remove`;
  **add contract** → `spells.add` con payload trimmato (`level` numerico, vuoti→`undefined`, `is_pinned:false`);
  **createSlot in auto** → `characters.update{settings.spell_slots_mode:'manual'}` poi `spellSlots.add(level,1)` + toast.
- `pages/Abilities.tsx` — skeleton; raggruppamento class-features/custom; **add wizard 2-step** con
  `detectRestoration` end-to-end ("Action Surge"→`short_rest`) → `abilities.add` (`is_active:!is_passive`, `uses==max_uses`);
  **pallini ≤10**: pip acceso (usato)→`update{uses+1}` (ripristina) / spento→`update{uses-1}` (spende); delete custom →
  `abilities.remove`; **feature di classe bloccata** → solo `update{description}` via sheet description-only; **risorse
  homebrew** inc/dec/restore → `homebrew.patchResource` (clamp `max(0,·)`/`min(max,·)`).
- `pages/Multiclass.tsx` — skeleton; livello totale da `levelFromXp` (lib reale, non mockata); banner level-up
  solo se `targetLevel > Σlivelli` con classi presenti; card classe (nome/sottoclasse/`d{hit_die}`/livello); apri
  "gestisci classi"; empty state; **rimozione classe** via `ConfirmSheet` → `classes.remove(charId, classId)`.
- `pages/multiclass/LevelUpModal.tsx` — selettore per-classe (default = prima classe); **confirm** → `classes.distribute`
  con **+1 alla classe selezionata, le altre invariate**; cambio selezione redirige il +1; toast level-up + **toast
  `hp_gained`** quando >0 + confetti (non-reducedMotion) + `onClose`; **classe a livello 20 → confirm disabilitato**,
  nessuna `distribute`. `classProgression` reale (bridge IT/EN).

**BE — pytest, `be-green`** (eseguiti su Windows 2026-06-09 — **tutti passati**):
- `routers/characters.py::GET /characters` → `tests/integration/test_characters_list_delete.py` —
  lista `CharacterSummary` **solo del proprietario**, ordinata per id, shape completa, `total_level`/`class_summary`
  riflettono la classe iniziale; esclude i personaggi di altri owner (inseriti via session factory).
- `routers/characters.py::DELETE /characters/{id}` → `test_characters_list_delete.py` — 204 + GET
  successiva 404, rimozione mirata dalla lista, 404 ignoto, **403 owner diverso**.
- `routers/dice.py::POST …/dice/post-to-chat` → `tests/integration/test_dice_post_to_chat.py` —
  ownership prima del token (404/403), **503 senza `BOT_TOKEN`**, happy-path con `httpx.AsyncClient` **monkeypatchato**
  (asserisce `chat_id`=utente autenticato, `parse_mode=Markdown`, testo single `🎲 d20: *18*` vs multi `🎲 2d6: 3 + 5 = *8*`),
  **502** se Telegram risponde non-2xx.

> **Run di conferma BE (2026-06-09, Windows): verde.** I 3 file `be-pending` del lotto 11
> (`test_characters_list_delete.py`, `test_dice_post_to_chat.py`) sono stati eseguiti su Windows con
> `uv run pytest` — **tutti passati**, nessuna regressione → portati a `be-green`. Ledger ora **0 be-pending**
> (32 fe-green + 113 be-green).

> **Back-fill copertura BE pre-esistente:** `routers/dice.py::GET …/dice/history` e `DELETE …/dice/history` erano già
> coperti da `tests/integration/test_dice_result.py` (`test_history_records_roll_then_clears`, verde nel run 547/0) ma
> mai mappati → mappati ora come **be-green** senza rigenerare nulla.

**Lotto 11 — compat FE↔API.** Verificati i metodi `api.*` (`webapp/src/api/client.ts`) invocati dalle 4 unità FE
contro route + schemi Pydantic. Tutti **allineati**, nessun mismatch 🔴/🟠; i payload inviati e le shape lette sono
codificati come assert (un drift fa fallire):

| Metodo FE (`client.ts`) | Endpoint BE | Esito |
|---|---|---|
| `spells.add` → `POST …/spells` `Partial<Spell>` → `Spell` | `add_spell` / `SpellCreate` | ✅ allineato (payload trimmato, `level` numerico, `is_pinned:false`) |
| `spells.use` → `POST …/spells/{id}/use` `{slot_level}` → `CharacterFull` | `use_spell` / `SpellUseRequest` | ✅ allineato |
| `spells.updateConcentration` → `PATCH …/concentration` `{spell_id}` → `CharacterFull` | `update_concentration` / `ConcentrationUpdate` | ✅ allineato |
| `spells.remove` → `DELETE …/spells/{id}` (204) | `delete_spell` | ✅ allineato |
| `spellSlots.update`/`add` → `PATCH …/spell_slots/{id}` · `POST …/spell_slots` | `update_spell_slot` / `add_spell_slot` | ✅ allineato (riuso lotto 3/9) |
| `characters.update` → `PATCH …/characters/{id}` `{settings}` → `CharacterFull` | `update_character` / `CharacterUpdate` | ✅ allineato (switch auto→manual) |
| `abilities.add`/`update`/`remove` → `POST/PATCH/DELETE …/abilities[/{id}]` | `*_ability` / `AbilityCreate`·`AbilityUpdate` | ✅ allineato (`uses`/`description`-only/`max_uses`) |
| `homebrew.listResources`/`patchResource` → `GET/PATCH …/homebrew/resources[/{id}]` `{current}` | `list_resources` / `patch_resource` | ✅ allineato |
| `classes.remove` → `DELETE …/classes/{id}` → `CharacterFull` | `remove_class` | ✅ allineato (riuso lotto 6) |
| `classes.distribute` → `PATCH …/classes/distribute` `{classes:[{class_id,level}]}` → `CharacterFull` (`hp_gained`) | `distribute_class_levels` / `ClassDistribute` | ✅ allineato (riuso lotto 4) |

Note di contratto codificate: `LevelUpModal` invia un payload `distribute` che **incrementa di 1 solo la classe selezionata**
(le altre col loro livello corrente) — l'oracolo dello scaling HP a ratio è già coperto BE (`test_classes_distribute.py`).
`Spells.tsx` legge `settings.spell_slots_mode` (source-of-truth in `settings`, vedi `[[project_spell_slots_mode_source]]`);
in **auto** la creazione slot dalla modale di cast passa prima da `characters.update` per portare il personaggio in manuale.
`Abilities.tsx` consuma `Ability`/`AbilityRead` (`uses`/`max_uses`/`is_class_feature`/`source_class_id`) e le risorse
homebrew (`HomebrewResource`: `id`/`current`/`max`) — tutti presenti nei serializer.

### Lotto 2026-06-09 #12 (8 unità: chiusura blocco FE `pages/hp/*` — HP/morte/death-save/hit-dice/concentrazione)

Chiuso **l'intero sotto-albero `pages/hp/*`** (8 componenti presentazionali sotto la pagina HP, già coperta al lotto 2):
era il **massimo rischio D&D 5e FE rimanente** — è la UI di danno/cura, tiri salvezza morte, morte istantanea, riposo
breve (dadi vita) e concentrazione. Lotto **FE-only**: nessun pytest nuovo (i residui BE sono ormai periferici, vedi sotto).

**FE — Vitest, verdi (37 test, 8 file · suite totale 271 test / 40 file):**
- `pages/hp/HpOperationForm.tsx` — form HP controllato (harness stateful): selettore 5 operazioni
  (damage/heal/set_current/set_max/set_temp), shortcut rapidi con **segno op-dipendente** (− per damage, + per heal),
  **toggle colpo critico mostrato solo a 0 HP in damage** (regola crit-while-dying, `aria-pressed` che alterna),
  confirm disabilitato finché non si digita un valore.
- `pages/hp/DeathSaves.tsx` — tracker tiri salvezza morte: titolo/etichette pallini, roll (`onRoll`, disabled mentre
  rolling), override manuali reset/success/failure/stabilize → `onAction(action)`, **pulse "urgent"** del gruppo
  fallimenti quando `failures>=2`.
- `pages/hp/HitDiceModal.tsx` — modale riposo breve: empty state senza classi, lista classi con `d{hit_die}`,
  stepper +/- (clamp `>=0`), **roll disabilitato a 0 dadi** → `onSpend(classId, count)`, confirm-rest/cancel.
- `pages/hp/DeadState.tsx` — stato Morto: causa `death_saves`/`massive_damage`, **revive dietro `ConfirmSheet`**
  (`onRevive` solo su conferma, **non** su annulla).
- `pages/hp/InstantDeathDialog.tsx` — dialog morte istantanea (danno massiccio): `null` se `!open`; accent crimson +
  pulse quando aperto; forwarding `onClose`.

**FE contract-bearing (shape mockata = oracolo BE, un drift di schema fa fallire il test):**
- `pages/hp/DeathSaveResultDialog.tsx` — esito tiro morte (`POST …/death_saves/roll`): nat20→gold+pulse+revived,
  nat1+3 fallimenti→crimson+pulse+dead, success+3 successi→emerald+stable, failure→crimson. Contract con
  `api/schemas/common.py::DeathSaveRollResult`.
- `pages/hp/ConcentrationSaveDialog.tsx` — esito tiro concentrazione (`POST …/concentration/save`): accent
  critico→gold/successo→emerald/fallimento→crimson, pulse su critico|fumble, banner CRITICO/FUMBLE, nota `conc_lost`,
  segno bonus. Contract con `api/schemas/common.py::ConcentrationSaveResult` (RollResult + dc/success/lost_concentration).
- `pages/hp/HitDiceResultDialog.tsx` — esito spesa dadi vita (`POST …/hit_dice/spend`): `+healed`,
  `[rolls] +con_bonus (COS)`, `new_current_hp`. Contract con `api/routers/hp.py::HitDiceSpendResult`.

> **Lotto FE-only** — i `pages/hp/*` non chiamano `api.*` direttamente (sono guidati dalle callback della pagina HP,
> già testata al lotto 2). I 3 dialog di risultato **leggono** però le shape di risposta di 3 endpoint HP: i loro
> fixture codificano il contratto campo-per-campo verso gli schemi BE. **Nessun pytest nuovo** generato.

**Lotto 12 — compat FE↔API.** Verificate le 3 shape di risposta consumate dai dialog contro gli schemi Pydantic.
Tutte **allineate**, nessun mismatch 🔴/🟠:

| Shape FE (`@/api/client` / `@/types`) | Schema BE | Esito |
|---|---|---|
| `DeathSaveRollResult` (die/outcome/successes/failures/stable/revived/current_hp) | `common.py::DeathSaveRollResult` | ✅ allineato campo-per-campo |
| `ConcentrationSaveResult` (die/bonus/total/description?/dc/success/lost_concentration/is_critical/is_fumble) | `common.py::ConcentrationSaveResult` (`RollResult` + dc/success/lost_concentration) | ✅ allineato |
| `HitDiceSpendResult` (rolls/con_bonus/healed/new_current_hp) | `hp.py::HitDiceSpendResult` | ✅ allineato |

## Prossimi residui per rischio (per il lotto successivo)

1. **FE mutation pages restanti** (HP+`pages/hp/*`/ArmorClass/Currency/SpellSlots/Experience/AbilityScores/SavingThrows/
   Skills/Conditions/**Spells/Abilities/Multiclass/LevelUpModal** chiusi): `pages/Inventory.tsx` (743 righe — CRUD item,
   equip/slot, attacco), `multiclass/EditClassesModal.tsx` (add/update/distribute classi inline), `pages/Identity.tsx`
   (351 — patch identità), `pages/Settings.tsx` (568 — preferenze, slot mode, silhouette upload).
2. **Router ancora scoperti** (rischio D&D basso, ma flussi reali): `routers/sessions.py` (13 endpoint, sessioni di
   gioco) interamente; `routers/maps.py` (6, upload/serve), `routers/notes.py` (6, incl. voice), `routers/silhouette.py`
   (3); **modelli ORM** in `core/db/models.py` (Character/Item/Spell/Map/CharacterClass/… — gli enum sono già coperti).
   `routers/dice.py` e `routers/characters.py` list/delete **chiusi al lotto 11**.
3. FE `lib/*`/hooks/store residui (rischio basso): `rewardQueue.ts`, `eventMeta.ts`, `itemIcons.ts`,
   `celebrate.ts`, `inlineMarkdown.tsx`, `homebrew/i18n-dsl.ts`; hooks `useSwipeNavigation`/`useToast`/
   `useIntersection`/`useReducedMotion`; store `diceSettings`/`overlayStore`/`themeSettings`.
4. FE componenti presentazionali ad alto valore (no API): `components/character/SpellSlotsSummary.tsx`,
   `ProgressionPreview.tsx`, `components/ui/HeroXPBar.tsx`, `HPBar.tsx`, `pages/hp/DeathSaves.tsx`/`DeadState.tsx`.

## File

- `coverage-ledger.json` — mappa unità → test + stato (`fe-green` / `be-pending` / `be-green`).
- `README.md` — questo report umano.
