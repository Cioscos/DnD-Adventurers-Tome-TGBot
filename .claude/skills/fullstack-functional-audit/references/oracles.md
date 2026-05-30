# Oracoli di correttezza — regole D&D 5e + tracing FE→API→BE

Questo file è la mappa per il **Passo 4.3** (ricavare l'oracolo) e **4.4** (asserire). Un oracolo è
"cosa *dovrebbe* restituire il BE / mostrare la UI" secondo il codice e le regole D&D 5e. Le citazioni
`file:riga` sono ancorate al codice al momento della scrittura della skill: se non combaciano, il codice
è cambiato — ri-leggi e aggiorna (e valuta se il cambiamento è esso stesso un finding).

## Ricetta di tracing FE→API→BE

Per ogni pagina, prima di interagire:

1. **FE** — apri `webapp/src/pages/<X>.tsx`. Trova le `useMutation`/`useQuery` e annota: quale `api.*`
   chiamano, quale controllo UI le scatena, quale `queryKey` invalidano, se fanno update ottimistico
   (`qc.setQueryData`). L'update ottimistico è importante: nasconde i bug BE finché non ricarichi.
2. **API** — in `webapp/src/api/client.ts` trova il metodo: ti dà **metodo HTTP + path**. La base URL è
   `VITE_API_BASE_URL` (locale `http://127.0.0.1:8000`); ogni request porta l'header `X-Telegram-Init-Data`.
3. **BE** — dal path risali al router in `api/routers/`. Il prefisso `/characters` è comune; cerca la
   funzione handler. Da lì segui le chiamate a `api/services/…` e `core/game/…`. La risposta è quasi
   sempre `CharacterFull` costruita da `api/services/character_response.py:build_character_response`.
4. **Oracolo** — determina l'output atteso (specie i calcoli sotto). Asserisci la **risposta di rete**
   (verità BE) e separatamente la **UI** (`browser_evaluate`). Tre tipi di bug:
   - UI ≠ rete → bug FE (render/ottimistico).
   - rete ≠ regola D&D → bug BE.
   - UI = rete ma entrambi ≠ regola → bug BE non mascherato.

## Auth in locale

`Depends(get_current_user)` (`api/auth.py`) verifica l'HMAC dell'initData Telegram, ma con `DEV_USER_ID`
impostato in `.env` salta la verifica e usa quell'id. Ogni router fa ownership check (`char.user_id ==
user_id`, altrimenti 403). In locale quindi le chiamate funzionano senza initData.

## Regole D&D 5e — dove vivono e cosa asserire

### HP e danno/cura (`api/routers/hp.py`)
- `update_hp()` — `hp.py:101`. Op: DAMAGE / HEAL / SET_MAX / SET_CURRENT / SET_TEMP.
  - **Temp HP assorbe il danno per primo**, poi gli HP correnti.
  - **Cura cappata** al max effettivo (base + bonus homebrew); non supera il massimo.
  - **HP risale da 0 → reset automatico dei death saves** (`hp.py:192` ca.). Asserisci: porta a 0, poi
    cura → `death_saves` azzerati.
  - **HP scende a 0** → emette evento homebrew "dropped_to_zero"; **non** inizializza death saves da solo.
  - Se subisci danno mentre concentri → vedi Concentrazione.

### Death saves (`api/routers/hp.py`)
- `roll_death_save()` — `hp.py:381`. Regole D&D 5e (asserisci ogni ramo):
  - **nat 20** → rivive con **1 HP** + **reset** dei death saves (`hp.py:393` ca.).
  - **nat 1** → **2 fallimenti**.
  - **10+** → 1 successo; **2-9** → 1 fallimento.
  - **3 successi** → stabile; **3 fallimenti** → morto.
- `update_death_saves()` — `hp.py:337`. Tracking manuale: SUCCESS/FAILURE/STABILIZE/RESET. STABILIZE a
  0 HP → stabile (e tipicamente 1 HP secondo la UI). Asserisci i conteggi.

### Riposo (`api/routers/hp.py`)
- `rest()` — `hp.py:213`.
  - **Lungo**: HP a max, **temp_hp azzerato**, **concentrazione interrotta** (`concentrating_spell_id =
    None`), **tutti gli spell slot** `used=0`, ripristina abilities/class-resource con `restoration_type`
    **long_rest OR short_rest**, **death saves resettati**. Asserisci ciascuno aprendo le pagine
    dipendenti (slots, abilities, hp, spells).
  - **Breve**: interrompe la concentrazione, ripristina **solo gli slot pact** (Warlock) e le risorse
    `short_rest`; gli HP si curano spendendo hit dice.
- `spend_hit_dice()` — `hp.py:294`. Cura = somma di `1d<hit_die> + CON_mod` per dado, **min 1** per dado.
  Asserisci che gli HP salgano del valore corretto e che gli hit dice spesi vengano scalati.

### HP massimi e formula (`api/routers/stats.py`, `core/game/stats.py`)
- `update_ability_score()` — `stats.py:57`. Se la caratteristica è **constitution** e l'auto-calc è
  attivo (`settings`): `delta = nuovo_mod - vecchio_mod`; `hit_points += delta * total_level`; clamp di
  `current_hit_points` (`stats.py:69-103`). Asserisci: cambia CON, verifica il nuovo HP max = vecchio +
  delta_mod × livello_totale, e il toast "HP massimi aggiornati: X → Y".
- `hit_points_for_level(hit_die, con_mod, level)` — `core/game/stats.py:36`. **Livello 1**: `hit_die +
  con_mod`. **Livello 2+**: `(hit_die // 2 + 1) + con_mod`. Min 1 per livello.
- `total_base_hp(classes, con_mod)` — `core/game/stats.py:58`. La **prima classe** usa la formula L1; le
  altre classi (anche al loro L1) usano la formula L2+.
- `recalc_hp()` — `hp.py:446`. Ricalcolo esplicito (Settings → "Ricalcola"). Asserisci che riallinei HP
  max alla formula.

### Classe armatura (`core/db/models.py`, `api/routers/items.py`, `api/routers/stats.py`)
- **AC totale** = `base_armor_class + shield_armor_class + magic_armor` — proprietà `Character.ac`
  (`models.py:202-203`).
- **Equip armatura/scudo** in `update_item()` (`items.py:146`): se `item_type == "armor"` e **non**
  `base_armor_class_override` → `base_armor_class = item_metadata.ac_value` (10 se non equip)
  (`items.py:197-199`); se shield e non override → `shield_armor_class = ac_bonus` (`items.py:200-201`).
- **Occupante spostato** (`swap_slot_occupant`): se l'item displaced era armatura/scudo, il suo contributo
  AC viene azzerato (`items.py:203-208`).
- `update_ac()` — `stats.py:109`: edit manuale imposta i flag override (preserva l'edit dell'utente
  attraverso l'equip). `reset_ac_override()` — `stats.py:128`: ricalcola da equipped body/off_hand.
- ⚠️ **Bug noto storico (F01)**: l'override manuale di AC.Base ha priorità sull'auto-calc da equip. Vedi
  `known-issues.md`: se ancora presente → conferma; se risolto e ricompare → `REGRESSED`.

### Equipaggiamento slot-aware (`api/services/equipment.py`, `api/routers/items.py`)
- `EQUIPMENT_SLOT_COMPAT` — `equipment.py:13`: weapon→{MAIN_HAND, OFF_HAND}, armor→{BODY}, shield→
  {OFF_HAND}, accessory→{NECK, CLOAK, RING1, RING2}, gear→{HEAD, HANDS, FEET, AMMUNITION}.
- `swap_slot_occupant()` — `equipment.py:29`: equipaggiare un item in uno slot occupato **disequipaggia
  atomicamente** il precedente (clear `is_equipped` + `equipment_slot`). Asserisci: equip A in main_hand,
  poi B in main_hand → A risulta non equipaggiato.
- Item con >1 slot compatibile (es. arma versatile) devono chiedere lo slot prima del PATCH (bug noto F07).
- **CON da item equipaggiato** → ricalcolo HP: `effective_con_mod(char)` (`_helpers.py:82`) include i
  modificatori degli item equipaggiati; equipaggiare un item che cambia CON ricalcola gli HP se l'auto-calc
  è attivo.

### Attacco con arma (`api/routers/items.py`)
- `attack_with_weapon()` — `items.py:285`.
  - **To-hit** = `1d20 + ability_mod + proficiency_bonus`; arma **finesse** usa `max(STR, DEX)`.
  - **Danno** = dadi arma + `ability_mod + bonus`; **critico** (nat 20) = **raddoppia il numero di dadi**
    (non i bonus); **fumble** (nat 1) = 0 danni.
  - **Ispirazione**: con `with_inspiration=true` consuma `heroic_inspiration` (toggle a false); se non
    disponibile, attesa 409. Asserisci to-hit/danno separati e il consumo dell'ispirazione.

### Incantesimi e concentrazione (`api/routers/spells.py`, `api/routers/_helpers.py`)
- `use_spell()` — `spells.py:149`: consuma lo slot del livello scelto (`available > 0`); se la spell è
  `is_concentration` → `concentrating_spell_id = spell_id` (`spells.py:178`). I cantrip (livello 0) non
  consumano slot.
- `update_concentration()` — `spells.py:184`: imposta/azzera manualmente la concentrazione.
- `concentration_save()` — `spells.py:200` + `roll_concentration_save()` (`_helpers.py:119`): DC =
  `max(10, danno // 2)`; nat 20 = pass automatico, nat 1 = fail automatico; **fail → azzera**
  `concentrating_spell_id`. Asserisci la DC e l'effetto sul campo.
- `roll_spell_damage()` — `spells.py:218`: scaling per `casting_level`; **critico = raddoppia i dadi**;
  half damage = `(total + 1) // 2` (arrotondato per eccesso).

### Slot incantesimi (`api/routers/spell_slots.py`, `api/services/spell_slots.py`)
- CRUD + `resetAll`. In **modalità automatica** (`settings['spell_slots_mode']`, default 'auto')
  `recalc_spell_slots()` (`api/services/spell_slots.py`) è autoritativa: riconcilia gli slot con le
  tabelle D&D, preserva `used` clampato al nuovo `total`, rimuove slot non più autorizzati. ⚠️ La mode
  vive in `settings`, **non** nella colonna del modello (vedi memoria progetto). Asserisci che il riposo
  ripristini `used=0` e che i conteggi per livello siano corretti.

### Skill, tiri salvezza, competenza (`core/db/models.py`, `api/routers/characters.py`)
- `proficiency_bonus` = `2 + (total_level - 1) // 4`, min +2 — proprietà (`models.py:210`).
- `roll_skill()` — `characters.py:471`: bonus = `ability_mod + (PB se competente, 2×PB se esperto)`;
  totale = `d20 + bonus`. Asserisci crit/fumble evidenziati e il bonus corretto.
- `roll_saving_throw()` — `characters.py:530`: bonus = `ability_mod + (PB se competente)`.
- Reroll con ispirazione: bug noto F03 (il modale poteva non aggiornarsi). Verifica che il valore mostrato
  cambi dopo il reroll.

### XP e level-up (`api/routers/characters.py`)
- `update_xp()` — `characters.py:405`: per un personaggio mono-classe, derivare il livello dalla soglia
  XP, aggiornare `class.level`, ricalcolare risorse, **HP** (somma `hit_points_for_level` per ogni
  livello guadagnato, se auto-calc), e **slot** (`recalc_spell_slots` in modalità auto). Multiclasse: il
  level-up può richiedere la distribuzione via `/classes` (per design — F02). Asserisci HP/slot/risorse.

### Creazione personaggio (`api/routers/characters.py`)
- `create_character()` — `characters.py:184`: crea Character (ability scores + currency a cascata); se
  fornita la classe iniziale, calcola gli HP L1 (`hit_die + con_mod`) e seed degli slot. Asserisci il
  redirect a `/char/:id`, gli HP L1 corretti, e la validazione (nome vuoto → niente avanzamento).

### Eventi homebrew (vari router)
Diversi handler emettono eventi che le regole homebrew possono intercettare: `dropped_to_zero` (danno a
0), `long_rest_taken`, `ability_used` (decremento usi), `spell_cast` (incremento slot usato),
`attack_rolled`. Se sono installate regole homebrew, asserisci che le notifiche/effetti scattino. La
suite Playwright homebrew (Passo 5) copre questa area in profondità.

## Note su currency, conditions, identity, notes, maps, history, dice, settings
Per queste aree l'oracolo è meno "matematico" ma vale comunque il principio asserzione-non-osservazione:
- **currency** (`api/routers/currency.py`): aggiungere/togliere e **convertire** rispetta i tassi (RATES
  nel modello Currency). Asserisci che la conversione conservi il valore equivalente.
- **conditions**: 14 condizioni + Spossatezza 0-6. Asserisci persistenza e (bug noto F04) che la history
  mostri `livello 0 → N`, non `False → N`.
- **history** (`api/routers/history.py`): max 50 entry; asserisci che gli eventi recenti compaiano e che
  il serializer non produca `False`/`None` grezzi.
- **dice** (`api/routers/dice.py`): la history è in `char.rolls_history`; `clearHistory` la svuota;
  `postToChat` invia al chat privato via Bot API.
- **notes / maps**: upload multipart (`requestFormData`); asserisci persistenza e che i file siano
  serviti correttamente (`fileUrl`/`voiceUrl` autorizzati).
- **settings**: tema/lingua/retention/ricalcolo; asserisci che il cambio lingua aggiorni le stringhe e che
  "Ricalcola" riallinei gli HP.
