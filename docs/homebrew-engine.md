# Motore Regole Homebrew — note di architettura e versioning

Complemento al [Ricettario](homebrew-recipes.md): qui stanno le note **per manutentori e
autori avanzati** sul comportamento del motore (`api/services/homebrew/`), non coperte
dall'editor. Allineato con le fasi di hardening dell'audit (fasi 1–7).

## Versioning del DSL (#41)

Il DSL è bloccato a `version: Literal[1]` (`api/services/homebrew/dsl.py`). Ogni regola
salvata porta `version=1`. **Bumpare a una v2 NON è retro-compatibile da solo**: il
dispatcher ri-valida ogni regola con `RuleDSL.model_validate` a ogni evento e, se la
validazione fallisce, disabilita la regola (`enabled=False`) e logga una voce di storia.
Se si passasse a `Literal[2]` (o a uno schema diverso) **senza migrare le DSL già in DB**,
tutte le regole `version=1` verrebbero auto-disabilitate al primo evento.

**Strategia richiesta prima di introdurre v2** (una delle due):

- **Union discriminato per versione** con upgrade automatico in lettura: `RuleDSL` diventa
  `Annotated[Union[RuleDSLv1, RuleDSLv2], Field(discriminator="version")]` e una funzione
  `upgrade(dsl) -> dsl_v2` normalizza le v1 al volo prima dell'esecuzione.
- **Migrazione one-shot** delle `homebrew_rules.dsl` in DB (in `core/db/engine.py`, accanto
  alle altre migrazioni idempotenti), riscrivendo le v1 nel nuovo formato e bumpando
  `version`.

In ogni caso: bumpare `version` **richiede** una di queste strategie, mai da solo.

## Validazione e limiti di sicurezza

- **Validazione ricorsiva** (fase 4, #8): i rami annidati `match.cases`, `if.then`,
  `if.else` sono validati ricorsivamente a *parse-time* via `parse_action`, non solo gli
  effetti top-level.
- **Cap difensivi per trigger** (fase 7, #45): profondità di annidamento ≤ `10` e numero
  totale di azioni ≤ `200` per trigger (`_MAX_NESTING_DEPTH` / `_MAX_TRIGGER_ACTIONS` in
  `dsl.py`). Limiti generosi: nessuna regola reale li raggiunge; servono solo a respingere
  alberi patologici (stack overflow / trigger lentissimi).
- **Anti-ricorsione a runtime**: l'unico vero vettore di ricorsione è il *re-emit* di
  eventi (`damage_character` / `heal_character` riemettono `damage_taken` /
  `dropped_to_zero`). È protetto da `MAX_DEPTH` (8) più uno stack dei `rule_id` già
  attraversati (`dispatcher.py`). `match` / `if` NON incrementano la profondità: restano
  nello stesso trigger e non ri-dispacciano eventi.

## Risorse custom e riposo

- `restoration_type` (`long_rest` / `short_rest` / `none` / `manual`) è **azionato
  automaticamente al riposo** (fase 3, D3), con la stessa semantica delle Ability: un
  riposo lungo ricarica anche le risorse `short_rest`.
- È persistito per **nome** del membro enum (es. `LONG_REST`), coerente con `Ability` e con
  la heal-migration di `engine.py` (vedi nota su SQLAlchemy `Enum` pass-through).
- I contatori (`HomebrewResource`) sono materializzati a install/create della regola dalle
  `ResourceDef` dichiarate. La materializzazione è **additiva**: un edit del DSL non rimuove
  mai una risorsa (per non perdere il `current` del giocatore). Per eliminare una risorsa
  orfana usare `DELETE /characters/{id}/homebrew/resources/{resource_id}` (fase 5, #31).

## Default delle property degli oggetti

I default `hb_<key>` delle property di una regola *item-scoped* sono materializzati:

- all'**install/create** della regola, su tutti gli item che matchano il filtro `subject`;
- alla **creazione di un nuovo item** che matcha (`_apply_item_property_defaults` in
  `api/routers/items.py`, fase 3 #32).

Solo le chiavi mancanti vengono impostate: i valori già presenti non vengono sovrascritti.

## Semantica degli eventi

- **`manual_trigger`** è scopato alla **sola regola** il cui id è nell'URL
  `manual-trigger/{rule_id}` (fase 5, #19): attivare manualmente una regola non fa più
  scattare le altre regole con trigger manuale. Il `rule_id` resta nel payload, quindi le
  regole che si auto-filtravano con `$event.rule_id` continuano a funzionare.
- **`event.amount`** su `damage_taken` è il **danno nominale (lordo)**: prima
  dell'assorbimento dei PF temporanei e prima del clamp a 0 — coerente tra il percorso HP
  primario (`hp.py`) e il re-emit homebrew (`actions.py`) (fase 5, #29/#46). Il danno
  **effettivo** ai PF si ricava da `current_hp_before - current_hp_after`, sempre presenti
  nel payload.

## Tono semantico dei badge (#47)

Le property a elenco possono dichiarare `tone_by_value` (mappa valore → `danger` /
`success` / `neutral`) per il colore del badge nelle superfici di gioco. In assenza di
mapping si applica l'euristica `tonePerValue` (token bilingui + nome chiave contenente
`quality`/`condition`/`state`).

## Auto-disable best-effort (#30)

Quando il dispatcher incontra una regola con DSL non valido la disabilita
(`enabled=False`) e accoda una voce di storia, ma **non committa**: la persistenza dipende
dal commit del router chiamante. In caso di rollback la disabilitazione si perde, ma è
innocuo — la regola invalida viene ri-valutata e ri-disabilitata al prossimo evento
(idempotente). Non si fa un commit dedicato perché `dispatch` condivide la sessione del
router e committerebbe stato di business ancora in volo.
