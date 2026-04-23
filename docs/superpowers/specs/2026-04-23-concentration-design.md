# Gruppo C — Rework concentrazione (design)

**Gruppo roadmap:** C — `istruzioni.md` §1.4 + §1.5.
**Data:** 2026-04-23.
**Branch:** `feat/concentration-gruppo-c` (creato da `main`).
**Dipendenze:** nessuna bloccante. Infrastruttura esistente: `char.concentrating_spell_id`, `Spell.is_concentration`, endpoint `POST /concentration/save`.

---

## 1. Obiettivo

Rimuovere il flow manuale del tiro salvezza (TS) su concentrazione e triggerarlo automaticamente quando il personaggio subisce danni. Mostrare il risultato in modo chiaro all'utente. Semplificare la sezione concentrazione nel menù Incantesimi per mostrare solo lo spell attivo + descrizione.

Fonte: `istruzioni.md` §1.4 (Menù Punti Ferita) + §1.5 (Menù Incantesimi — parte concentrazione).

**Nota semantica:** il TS su concentrazione si fa quando il personaggio SUBISCE danni (difensivo). Il flow si aggancia a `/hp` op DAMAGE, NON al Roll Damage offensivo di Gruppo B.

## 2. Scope

### In-scope

- Backend `api/routers/hp.py` op DAMAGE: auto-triggerare concentration save quando `char.concentrating_spell_id` è impostato.
- Refactor backend: estrarre `_roll_concentration_save(char, damage, session)` helper condiviso tra la nuova logica auto e l'endpoint esistente `POST /concentration/save`.
- Schema `CharacterFull`: nuovo campo opzionale `concentration_save: ConcentrationSaveResult | null`, popolato nella response di `/hp` op DAMAGE.
- FE `HP.tsx`: rimuovere input+button TS manuale; mostrare panel risultato quando `mutation.data.concentration_save` è presente.
- FE `Spells.tsx`: rimuovere il blocco TS manuale; aggiungere `spell.description` nella sezione concentrazione attiva; mantenere bottone Stop.
- i18n keys aggiuntive IT/EN.

### Fuori scope

- Endpoint `POST /concentration/save` resta disponibile (backwards compat, testing, eventuali flow futuri manuali).
- Altri effetti che rompono concentrazione (long rest, short rest, HP=0) — già implementati, nessuna modifica.
- Check su Roll Damage offensivo (Gruppo B) — non riguarda il caster, fuori dal task.

## 3. Decisioni

### 3.1 Orchestrazione auto-TS

Atomic lato backend. L'endpoint `/hp` op DAMAGE, se `char.concentrating_spell_id != None` e `char.current_hit_points > 0` dopo il danno, chiama `_roll_concentration_save` e include il risultato nella response. Nessuna orchestrazione FE a due step.

### 3.2 Helper `_roll_concentration_save`

**Preliminare:** spostare la classe `ConcentrationSaveResult` da `api/routers/spells.py` (dov'è definita localmente a line 197) a `api/schemas/common.py` (o `api/schemas/character.py`), così che sia importabile sia da `CharacterFull` sia dai router. Aggiornare gli import in `spells.py` e in `webapp/src/api/client.ts` (tipo omologo già presente a line 67).

Estratto da `api/routers/spells.py` (lines ~210-250 della route esistente). Firma:

```python
def _roll_concentration_save(
    char: Character,
    damage: int,
    session: AsyncSession,
) -> ConcentrationSaveResult:
    """Roll a CON save vs DC=max(10, damage//2). Nat20 auto-pass, nat1 auto-fail.

    Side effects:
    - Clears char.concentrating_spell_id on failure (lost_concentration).
    - Appends a history entry describing the roll.

    Returns the ConcentrationSaveResult with die, bonus, total, success, lost_concentration, dc.
    """
```

`api/routers/spells.py` `POST /concentration/save` diventa un thin wrapper che chiama l'helper. Stessa logica di prima.

### 3.3 Modifica `/hp` op DAMAGE

In `api/routers/hp.py` dopo la sottrazione HP e l'history entry del danno:

```python
if body.op == HPOp.DAMAGE:
    amount = body.value
    if char.temp_hp > 0:
        absorbed = min(char.temp_hp, amount)
        char.temp_hp -= absorbed
        amount -= absorbed
    old = char.current_hit_points
    char.current_hit_points = max(0, char.current_hit_points - amount)
    _add_history(session, char.id, "hp_change",
                 f"Danni: -{body.value} HP ({old} → {char.current_hit_points})")

    # Auto concentration save — only if still conscious and concentrating
    conc_result = None
    if (
        char.concentrating_spell_id is not None
        and char.current_hit_points > 0
    ):
        conc_result = _roll_concentration_save(char, body.value, session)
```

Edge case HP→0: codice esistente (linea 162) azzera `concentrating_spell_id` e registra history entry "Concentrazione persa (HP a 0)". In quel caso NON rolliamo auto-TS (concentrazione già persa per RAW su HP=0).

Propagazione della `conc_result` al response: dopo la normale preparazione di `CharacterFull` alla fine della route, se `conc_result` è valorizzata, setta `result.concentration_save = conc_result`.

### 3.4 Schema `CharacterFull`

In `api/schemas/character.py`, aggiungere campo:

```python
from api.schemas.common import ConcentrationSaveResult  # if not already imported

class CharacterFull(...):
    ...
    concentration_save: Optional[ConcentrationSaveResult] = None
```

**Importante:** il campo è transient (non è una property del `Character` model). Viene popolato dopo `CharacterFull.model_validate(char)` esplicitamente nel route handler. Stesso pattern di `hp_gained` già in uso.

Serializzazione JSON: `null` se assente, oggetto `{die, bonus, total, is_critical, is_fumble, description, dc, success, lost_concentration}` se presente.

### 3.5 FE HP.tsx

**Rimuovo:**
- `concSaveMutation` (lines ~92-103).
- `concSaveResult` state + `setConcSaveResult`.
- `concDamageInput` state + damage input field.
- Sezione TS manuale (lines ~415-440).

**Aggiungo:**
- `autoConcSave: ConcentrationSaveResult | null` state (default `null`).
- `hpMutation.onSuccess` estratto: se `(updated as any).concentration_save` → `setAutoConcSave(...)`, + toast warning se `lost_concentration`.
- Panel JSX condizionale `{autoConcSave && (...)}` che mostra: DC, `d20={die} + {bonus} = {total}`, SUCCESSO/FALLIMENTO colorato, eventuale "Concentrazione persa!" bold, dismiss button.

Panel visibile finché user dismissa (niente auto-hide: su fail l'utente deve vederlo chiaramente).

Banner "concentrazione attiva" esistente (linea 178 ~`isConcentrating`) resta — informa lo stato, non innesca UI manuale.

### 3.6 FE Spells.tsx

**Rimuovo:**
- `concSaveMutation` locale.
- Stati `concDamageInput`, `concSaveResult`.
- Sezione TS manuale (lines ~294-330): damage input + save button + result panel.

**Modifico sezione concentrazione attiva (lines ~221-245):**
- Mostra nome spell (come ora) + `spell.description` sotto, `text-sm text-dnd-text font-body leading-relaxed`.
- Stop button resta (bottone `danger` con icona `X`, rimane a destra).

**Mantengo:**
- `concentrationMutation` per toggle start/stop manuale.
- Toggle on cast (line ~118).
- Lista spell con modalità "start/stop concentration" esistente.

### 3.7 i18n keys

`webapp/src/locales/it.json` (+4 chiavi):
```json
"character.hp.concentration_lost": "Concentrazione persa!",
"character.hp.save_success": "Successo",
"character.hp.save_fail": "Fallimento",
"common.dismiss": "Chiudi"
```

`webapp/src/locales/en.json`:
```json
"character.hp.concentration_lost": "Concentration lost!",
"character.hp.save_success": "Success",
"character.hp.save_fail": "Failure",
"common.dismiss": "Dismiss"
```

Verificare se `common.dismiss` già esiste; in tal caso non duplicare.

## 4. Edge cases

- **HP drop a 0 con DAMAGE:** backend skippa auto-TS (concentrazione persa per RAW su HP=0). `concentration_save = null` nella response. History entry dedicato "Concentrazione persa (HP a 0)" già esistente.
- **Char non concentrato:** `concentration_save = null`, FE nessun panel.
- **TEMP HP assorbe tutti i danni (amount effettivo 0):** auto-TS comunque triggerato basato su `body.value` (danno incoming). DC = `max(10, body.value // 2)`. RAW-aligned.
- **Damage = 0 esplicito:** `body.value == 0` è comunque processato; DC = 10 (floor). Scenario raro, accettabile.
- **Multiple DAMAGE rapidi:** ogni chiamata è atomic; TS indipendenti. OK.
- **Nat20 / Nat1:** gestiti dal helper (invariato).
- **Panel dismiss:** user dismissa esplicitamente (click "Chiudi"). Nessun auto-hide.

## 5. Testing (verifica manuale)

Nessun test suite (CLAUDE.md). Checklist:

1. Char concentrato su spell X, damage 10, HP > 10 → HP bar scende, panel TS compare con risultato. Success → panel gold, concentrazione mantenuta. Fail → panel crimson, `concentrating_spell_id=null`, toast "Concentrazione persa!".
2. Char non concentrato, damage 10 → HP scende, panel TS assente.
3. Damage enorme che porta HP=0 → HP=0, `concentrating_spell_id=null`, panel TS assente, history entry HP=0 presente.
4. TEMP HP 10 assorbe tutti i 10 danni → damage effettivo 0, TS comunque triggerato su body.value=10, DC=10.
5. Spells.tsx sezione concentrazione attiva → mostra spell name + description. Stop button interrompe.
6. Spells.tsx: nessun damage input né bottone TS manuale.
7. HP.tsx: nessun damage input dedicato a TS, nessun bottone TS. Pannello TS appare solo post-DAMAGE auto.
8. Nat20 → panel success, crit indicator.
9. Nat1 → panel fail, fumble indicator, concentrazione persa.

## 6. File impattati

| File | Action | Responsibility |
|------|--------|----------------|
| `api/routers/spells.py` | Modify | Estrarre `_roll_concentration_save` helper; route `/concentration/save` diventa wrapper. |
| `api/routers/hp.py` | Modify | op DAMAGE chiama helper se concentrating + HP>0; popola `concentration_save` in response. |
| `api/schemas/character.py` | Modify | Campo opzionale `concentration_save: ConcentrationSaveResult | None`. |
| `webapp/src/api/client.ts` | Modify | Estendere tipo `CharacterFull` con `concentration_save?: ConcentrationSaveResult | null`. |
| `webapp/src/pages/HP.tsx` | Modify | Rimuovere TS manuale, aggiungere panel auto. |
| `webapp/src/pages/Spells.tsx` | Modify | Rimuovere TS manuale, aggiungere descrizione spell nella sezione concentrazione. |
| `webapp/src/locales/it.json` | Modify | +4 chiavi (verifica `common.dismiss`). |
| `webapp/src/locales/en.json` | Modify | +4 chiavi. |
| `docs/app/` | Modify (generated) | Rebuild pre-PR. |

## 7. Dipendenze e roadmap

- **Gruppo B** (meccaniche): riuso `CharacterFull` con campo transient (stesso pattern di `hp_gained`).
- **Gruppo F/G**: nessun impatto.
- **Gruppo D** (dadi overlay): futuro potrebbe visualizzare auto-TS come animazione dadi 3D. Non in scope C.

Post-merge:
- Tabella roadmap Gruppo C: `⬜ Pending` → `✅ Done (PR #<n> merged → main)`.
- Sezione `## Gruppo C`: `⬜` → `✅`.
- Ordine consigliato: `→ C →` diventa `→ ✅ C →`.
