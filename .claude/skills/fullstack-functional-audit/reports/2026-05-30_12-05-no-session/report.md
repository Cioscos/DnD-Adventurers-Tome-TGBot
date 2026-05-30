# Audit funzionale full-stack — no-session

> Data: 2026-05-30 12:05 · Tool: Playwright MCP + lettura codice FE/API/BE
> Stack: API http://127.0.0.1:8000 · Vite http://localhost:5173 · Fixture: **id=4 "AuditFS Chierico"** (creata in questo run; "Effervescent Barto" id=3 non esiste più)
> Severità: 🔴 bug/contratto · 🟠 errore non bloccante · 🟡 nit (→ fe-playwright-audit) · 🟢 ok

## Copertura
- Scope: tutte le aree TRANNE sessione multiplayer (`/session*`, esclusa dall'utente).
- Dettaglio in `coverage.md`.

## Matrice oracoli verificati (🟢 ok salvo finding citato)
| Area | Test funzionale | Atteso (oracolo) | Reale | Esito |
|------|-----------------|------------------|-------|-------|
| character-create | Chierico L1 | HP 8 (d8+CON0), slot L1=2, TS prof wis+cha, "Chierico 1" | identico | 🟢 |
| character-main | hero snapshot | HP/AC/XP/slot/progressione Chierico | corretto (progressione L1 Divine Domain, L2 Channel Divinity) | 🟢 |
| hp | temp assorbe danno | TEMP5 −4 → temp1 HP8 | temp1 HP8 | 🟢 |
| hp | death save d18/d1/d9/d20 | success/2fail/fail/revive1HP+reset | identico | 🟢 |
| hp | riposo lungo | HP=max, temp0, slot used0, death reset, conc null | identico | 🟢 |
| hp | hit dice 1d8 | heal=max(1,1d8+CON0); HP 2→4 | rolls[2] heal2 HP4 | 🟢 |
| hp | submit Conferma | 1 PATCH | **2 PATCH + history duplicata** | 🔴 #1 |
| xp | level-up → L2 | XP300 L2, HP+5(=13), slot L1 2→3, +Channel Divinity 1/short | identico | 🟢 |
| xp | submit Applica | 1 PATCH | **2 PATCH** (valore mascherato) | 🟠 #2 |
| stats | CON 10→14 auto-HP | HP +delta_mod×liv = +4 (13→17) | 17, 1 PATCH (guard ok) | 🟢 (F02 ok) |
| stats | validazione range | 35→400, 0→400, 30/14→200 | identico | 🟢 |
| inventory | equip armatura | base_ac 10→16, slot body auto | identico | 🟢 (F01 ok) |
| inventory | equip arma versatile | slot picker main/off (F07) | picker presente | 🟢 (F07 ok) |
| inventory | equip scudo + swap | AC+2=18; equip main_hand displaces Spada | identico (Spada slot=null) | 🟢 |
| inventory | attacco Pugnale/Spada | to-hit d20+STR0+PB2; danno 1d8+0 | to-hit 7+2=9, dmg 1d8=2 | 🟢 |
| ac | edit Magia +1 | AC 18→19, no override flag | 19, 1 PATCH (no double) | 🟢 |
| spells | use Bless L1 | slot used0→1, conc=Bless | identico | 🟢 |
| spells | cantrip "Usa" | nessun consumo slot → apre tiro danni | dialog danni (FE non chiama /use) | 🟢 |
| spells | roll_damage Guiding Bolt | 4d6; crit→8d6; half=(tot+1)//2 | 4d6=16 half8; crit 8d6=21 half11 | 🟢 |
| spells | concentration_save dmg20 | DC=max(10,10)=10, bonus CONmod+2, fail→clear | DC10 total6 fail lost_conc | 🟢 |

## Findings

### #1 — Doppio submit su pagina HP: ogni "Conferma" applica la mutazione due volte [🔴]
- **Area / route:** hp · `#/char/4/hp`
- **Catena FE→API→BE:** `webapp/src/pages/hp/HpOperationForm.tsx:102` (`<Input onCommit={onApply}>`) **+** `:109` (`<button onClick={onApply}>`) → `webapp/src/pages/HP.tsx:121` `handleApply` → `PATCH /characters/{id}/hp` → `api/routers/hp.py:100 update_hp`
- **Regola / oracolo:** una singola conferma HP deve produrre **una** mutazione e **una** entry di cronologia.
- **Atteso vs reale:** atteso 1 `PATCH /hp` per click; **reale 2 PATCH identici** per ogni click di "Conferma" (verificato: indici rete 14+15 SET_TEMP, 16+17 DAMAGE, 18+19 HEAL, 20+21 DAMAGE — sempre a coppie). La cronologia mostra ogni evento **duplicato**: `GET /characters/4/history` → `["Danni: -3 HP (8 → 6)","Danni: -3 HP (8 → 6)","Cura: +2 HP (8 → 8)","Cura: +2 HP (8 → 8)","Danni: -4 HP (8 → 8)","Danni: -4 HP (8 → 8)"]`.
- **Root cause:** cliccando "Conferma" dopo aver digitato, il blur dell'`<Input>` chiama `onCommit`→`handleApply` **e** il click del bottone chiama `onClick`→`handleApply`. Il guard `if (hpMutation.isPending) return` (HP.tsx:122) è inefficace: `isPending` è stato React asincrono, entrambe le chiamate partono nello stesso tick. È **lo stesso bug F17** già risolto in `AbilityScores.tsx` (che usa un `savingRef` sincrono, vedi commento a riga 29) ma **non applicato** a `HpOperationForm`. NB: `Input.tsx:108-109` documenta esplicitamente che il doppio onCommit "caused duplicate submissions (e.g. heal applied twice)".
- **Impatto:** cronologia HP raddoppiata; gli eventi homebrew `damage_taken`/`dropped_to_zero`/`hp_healed` vengono **dispatchati due volte** (`hp.py:134,145,163`) → regole homebrew si attivano due volte; doppio carico API. Attualmente i valori HP restano corretti **solo per fortuna** (le due richieste corrono sullo stesso snapshot e scrivono lo stesso valore: last-writer-wins). Se le due richieste si serializzassero (lock/timing DB diverso) → **danno/cura applicati due volte**. Le pagine sicurezza-critiche (HP a 0 → death saves) sono le più esposte.
- **Passi per riprodurre:** 1. `/char/4/hp` · 2. modalità DANNI · 3. digita `3` nell'input · 4. clicca "Conferma" · 5. `GET /characters/4/history` → due entry identiche; `browser_network_requests` filtro `/hp` → 2 PATCH.
- **Fix proposto:** applicare a `HpOperationForm`/`HP.tsx` lo stesso `savingRef` sincrono di `AbilityScores.tsx:29` (flip immediato a inizio `handleApply`, reset in onSuccess/onError); oppure rimuovere `onCommit={onApply}` dall'Input e affidarsi solo al click del bottone (ma si perde l'invio con Enter); oppure de-dup a livello di Input (non chiamare onCommit su blur se il blur è causato dal click sul bottone di submit).
- **Evidenza:** rete indici 14-21 (coppie identiche), `GET /characters/4/history` (entry duplicate).

### #2 — Doppio submit su Esperienza (XP): bottone "Applica" invia due PATCH [🟠]
- **Area / route:** xp · `#/char/4/xp`
- **Catena FE→API→BE:** `webapp/src/pages/Experience.tsx:293` (`<Input onCommit={handleApply}>`) **+** `:299` (`<button onClick={handleApply}>`) → `Experience.tsx:141 handleApply` → `mutation.mutate({add|set})` → `PATCH /characters/{id}/xp` → `api/routers/characters.py:405 update_xp`
- **Root cause:** identico a #1 (blur onCommit + click onClick), **nessun guard** `savingRef` né ref sincrono in `handleApply`.
- **Atteso vs reale:** atteso 1 `PATCH /xp` per click; **reale 2 PATCH** (verificato: indici rete 12+13 da un singolo click "Applica" su valore 100).
- **Impatto:** il valore XP risultante è rimasto **corretto** (XP=100, non 200) perché le due richieste corrono sullo stesso snapshot (`characters.py:415` legge `experience_points` pre-update da entrambe → last-writer-wins). MA: (a) `update_xp` NON scrive history quindi nessuna entry duplicata visibile; (b) **rischio latente**: se le richieste si serializzassero → `+2N` XP e possibile doppio level-up; (c) al level-up concorrente l'inserimento di `ClassResource` (`characters.py:431-433`, guard `existing_names` interno alla singola richiesta) potrebbe creare **risorse di classe duplicate**. Severità 🟠 perché oggi il valore è mascherato e non c'è dup visibile, ma è lo stesso difetto strutturale di #1.
- **Passi per riprodurre:** 1. `/char/4/xp` · 2. modalità "+ Aggiungi XP" · 3. digita un valore · 4. clicca "Applica" · 5. `browser_network_requests` filtro `/xp` → 2 PATCH.
- **Fix proposto:** come #1 (guard sincrono in `handleApply`, sul modello `AbilityScores.tsx:29`).
- **Nota positiva:** il level-up tramite i bottoni dedicati (onClick-only, es. "Porta al livello 2") è single-fire e **funziona correttamente** — vedi oracolo verificato (XP 300→L2, HP +5, slot L1 2→3, +risorsa "Incanalare la Divinità").

### #3 — Rimozione classe (DELETE) ricalcola gli slot ma NON gli HP → HP "fantasma" [🟠]
- **Area / route:** class · `#/char/4/class` (azione "Remove" sulla card classe)
- **Catena FE→API→BE:** `webapp/src/pages/Multiclass.tsx` (Remove → confirm "Rimuovere la classe?") → `DELETE /characters/{id}/classes/{class_id}` → `api/routers/classes.py:155-167 remove_class`
- **Regola / oracolo:** con `settings.hp_auto_calc=true` (default), gli HP massimi derivano dalle classi/livelli (`total_base_hp`). Rimuovere una classe riduce i livelli → gli HP dovrebbero essere ricalcolati, coerentemente con `distribute` (`classes.py:219-232`, ricalcola HP via `total_base_hp`) e con `update_xp` (`characters.py:435-446`).
- **Atteso vs reale:** dopo aver rimosso **Mago** da un Chierico1/Mago1 (auto-calc ON), atteso HP max = `total_base_hp(Chierico L1, CON+2)` = **10**; **reale HP max = 16** (resta il valore multiclass). Gli **slot** invece vengono ricalcolati correttamente (3→2). `remove_class` chiama solo `recalc_spell_slots`, **mai** `total_base_hp`/aggiornamento `hit_points`.
- **Verifica estesa (richiesta utente):** rimuovendo **tutte** le classi → `classes:[]`, `total_level:0`, `class_summary:"Nessuna classe"`, `slots:[]`, `proficiency_bonus:2` (clamp min +2). La UI gestisce il caso senza crash (empty state pagina classe, hero "Nessuna classe", 0 errori console). **MA HP resta 16/16** → personaggio senza classi con HP fantasma.
- **Passi per riprodurre:** 1. personaggio multiclass o mono con auto-calc ON · 2. `/char/{id}/class` · 3. "Remove" su una classe → "Elimina" · 4. `GET /characters/{id}` → `hit_points` invariato mentre `spell_slots` ricalcolati.
- **Fix proposto:** in `remove_class`, dopo `session.delete(cls)`, replicare il blocco HP di `distribute` (`classes.py:219-232`): se `hp_auto_calc`, `char.hit_points = total_base_hp(char.classes, effective_con_mod(char))` (0 se nessuna classe) e clamp di `current_hit_points`. Gestire il caso `classes == []` (HP 0 o lasciare l'ultimo valore manuale).
- **Evidenza:** `GET /characters/4` post-remove (hp 16/16, slots ricalcolati); screens/history-... non applicabile.

### #4 — Hero mostra "LIV 2 / LEVEL UP" con 0 classi (total_level=0) [🟡 → cosmetico]
- **Area:** character-main hero · dopo rimozione di tutte le classi. L'XP bar mostra il livello derivato dagli XP (LIV 2) e il prompt "LEVEL UP" mentre `total_level=0`. È lo stato "livello pending da assegnare"; non è un crash ma è incoerente con "Nessuna classe". Valutare di mostrare LIV 0 / nascondere LEVEL UP quando non ci sono classi.

### #5 — Freccia "Indietro" usa la history (navigate(-1)): nessun ritorno diretto al menu del personaggio [🟡 → UX/navigazione]
- **Area:** navigazione globale · `webapp/src/components/Layout.tsx:34-36` (header di ogni sub-pagina)
- **Comportamento attuale:** la freccia "Indietro" chiama **`navigate(-1)`** (torna di un passo nello stack di navigazione del browser/HashRouter). Utile per disfare l'ultimo passo, ma da una pagina raggiunta con più navigazioni (es. Menu → Incantesimi → Slot via cross-link, oppure catene di breadcrumb Combat) un singolo tap **non riporta al menu principale** del personaggio (`/char/:id`): servono N tap.
- **Code smell correlato:** il prop **`backTo?: string` è dichiarato (`Layout.tsx:14`) ma inutilizzato** — `handleBack` lo ignora. **22 pagine** passano comunque `backTo={/char/${id}}` (intento originale: ritorno a route-padre fissa) che viene scartato. Inoltre **non esiste un bottone "Home"** nell'header delle sub-pagine (solo freccia + titolo + breadcrumb verso pagine sorelle dello stesso gruppo).
- **Impatto:** per tornare all'hub del personaggio da una pagina profonda l'utente deve premere Indietro più volte (o usare le briciole, che però collegano solo pagine sorelle, non l'hub). Frizione di navigazione segnalata dall'utente.
- **Fix proposto (uno dei due):**
  1. **Aggiungere un bottone "Home"** nell'header (accanto alla freccia) che fa `navigate(/char/${id})` — ritorno immediato al menu del personaggio, mantenendo la freccia history per il back puntuale; **oppure**
  2. **Cablare il prop `backTo` già esistente**: `handleBack = () => backTo ? navigate(backTo) : navigate(-1)`, così le 22 pagine che già lo passano tornerebbero al loro parent logico (l'hub) invece che allo stack. (Valutare quale dei due comportamenti è preferibile: history-back è comodo per i cross-link; un Home esplicito è più prevedibile.)
- **Severità:** 🟡 UX/navigazione (non blocca funzionalità). Candidabile a `fe-playwright-audit`.

### #6 — `PATCH /classes/distribute` omette dalla risposta le risorse di classe appena inserite [🟠]
- **Area / route:** class · `#/char/:id/class` (flusso "Gestisci classi" → Conferma, anche "Aggiungi la tua prima classe" con livelli pending)
- **Catena FE→API→BE:** `Multiclass.tsx`/EditClassesModal commit → `PATCH /characters/{id}/classes/distribute` → `api/routers/classes.py` (handler distribute, ~righe 219-239): inserisce i nuovi `ClassResource` via `session.add(...)`, poi `flush` + `recalc_spell_slots` + `build_character_response` — **senza** `_refresh_char_full`.
- **Atteso vs reale:** la risposta del distribute deve includere `classes[].resources` aggiornate (come fa `update_xp`, `characters.py:454`, e `create_character`, `characters.py:214`, che usano `_refresh_char_full` proprio per caricare i `ClassResource` appena inseriti). **Reale**: riprodotto deterministicamente — 0 classi → crea Monaco6/Ladro2: `distributeResponse → Monaco.resources = []` mentre un `GET /characters/{id}` successivo restituisce `Monaco.resources = [Punti Ki 6/6]`. Le righe nuove inserite nella stessa transazione non sono serializzate.
- **Sintomo UI osservato:** dopo il level-up multiclass (Monaco L6) la card classe **non mostra "Punti Ki 6/6"** finché non si ricarica la pagina (il FE aggiorna la cache dalla risposta del distribute, priva della risorsa). Dopo `location.reload()` la risorsa compare. Nessuna perdita dati (la risorsa è persistita correttamente).
- **Nota:** si manifesta solo quando il distribute **inserisce** una risorsa nuova; un distribute su risorse già esistenti (anche con `total` che cresce) le include regolarmente.
- **Passi per riprodurre:** 1. personaggio con 0 classi e XP da liv ≥2 · 2. "Gestisci classi" → aggiungi Monaco, livello 6 + Ladro 2 → Conferma · 3. card Monaco senza "Punti Ki" · 4. reload → "Punti Ki 6/6" compare. (Confermato anche via fetch: response distribute `resources:[]` vs GET `[Punti Ki 6/6]`.)
- **Fix proposto:** nel handler `distribute`, dopo l'inserimento dei `ClassResource`, sostituire `build_character_response(session, char)` con un re-fetch completo: `fresh = await _refresh_char_full(session, char_id, user_id)` poi `recalc_spell_slots(session, fresh)` + `build_character_response(session, fresh)` — esattamente il pattern di `update_xp` (`characters.py:448-460`).
- **Evidenza:** eval Playwright — `distributeResponseMonacoResources: []`, `freshGetMonacoResources: ["Punti Ki 6/6"]`, `mismatch: true`.

### #7 — Pulsante di chiusura (✕) dei toast con sfondo bianco in tema scuro [🟡 → contrasto/visivo, → fe-playwright-audit]
- **Area:** toast globali (sonner) · `webapp/src/components/ui/Toast.tsx:14-32`
- **Dettaglio:** il `<SonnerToaster>` tematizza il **corpo** del toast (`toastOptions.style` → bg `var(--dnd-surface-raised)`, testo `--dnd-text`, bordo `--dnd-border-strong`) ma **non** la crocetta di chiusura. Il prop `closeButton` (riga 19) abilita il pulsante di default di sonner, il cui stile usa le variabili interne di sonner (`--gray1`/`--gray4`…) → **sfondo chiaro/bianco**. In **tema scuro** il cerchietto bianco della ✕ stona con il fondo pergamena scuro (contrasto incoerente col design). Non esiste override CSS per `[data-close-button]` né `toastOptions.classNames`.
- **Impatto:** estetico/contrasto in tema scuro (la maggior parte dell'uso, session-mode in penombra). Non funzionale.
- **Fix proposto (uno dei due):**
  1. Tematizzare il close button via `toastOptions.classNames = { closeButton: 'dnd-toast-close' }` + CSS: `[data-sonner-toast] [data-close-button]{ background: var(--dnd-surface); border-color: var(--dnd-border-strong); color: var(--dnd-text); }` (anche hover); **oppure**
  2. passare alla `<SonnerToaster>` il `theme` allineato al tema attivo dell'app (auto/chiaro/scuro) così sonner deriva i grigi corretti — richiede di leggere il tema corrente dallo store (vedi Settings → Tema).
- **Severità:** 🟡 visivo/contrasto — di competenza di `fe-playwright-audit`.

## Matrice oracoli verificati (continua)
| Area | Test funzionale | Atteso | Reale | Esito |
|------|-----------------|--------|-------|-------|
| slots | Auto-mode UI | banner 2014, no editor manuale | conforme (R02/U047) | 🟢 |
| slots | resetAll (+confirm U048) | used→0 | 1:0/3 | 🟢 |
| slots | manual add + Livello 2 | crea slot L2 | 2:0/1 | 🟢 |
| skills | Percezione prof + passiva | bonus +2, passiva 12 | +2, 12 | 🟢 |
| skills | roll Percezione | d20+2, crit su nat20 | d20=20+2=22 CRIT | 🟢 |
| saves | bonus COS/SAG/CAR | COS +2(unprof), SAG/CAR +2(prof) | identico | 🟢 |
| saves | reroll ispirazione modale (F03) | modale aggiorna valore | 18→20 poi reroll d2→4 | 🟢 (F03 ok) |
| currency | convert 10 GP→SP | 100 SP (valore preservato) | 0 GP / 100 SP | 🟢 |
| abilities | decremento usi + restore long rest | 2→1, rest→2 | identico | 🟢 |
| conditions | Spossatezza 2 + Avvelenato (F04) | history "livello 0 → 2" | esatto (no False) | 🟢 (F04 ok) |
| dice | 4d6kh3 (F19/R04) | total top-3, notation "4d6kh3" | 13 (5+4+4), "4d6kh3" | 🟢 (F19/R04 ok) |
| dice | clearHistory (+confirm) | history svuotata | svuotata (ma 2 DELETE idempotenti) | 🟢 (vedi #1 nota) |
| history | serializzazione + F04 | stringhe leggibili, no False/None | pulita; HP entries duplicate | 🟢 (dup = #1) |
| identity | update Razza | persiste | race="Umano" | 🟢 |
| notes | add nota | persiste con timestamp | "Indizio Audit" salvata | 🟢 |
| maps | upload PNG + file serving | 201, file servito image/png | upload 201, file 200 69B | 🟢 |
| settings | toggle slot mode → MANUALE | settings['spell_slots_mode']='manual', slots page editor manuale | conforme | 🟢 |
| settings | recalc HP | allinea HP alla formula | 16→10 (Chierico L1) | 🟢 |
| class | multiclass distribute (Chierico1+Mago1) | HP 16, slot 1:3 (caster lvl 2), +Recupero Arcano | identico | 🟢 |
| class | remove classe | recalc HP+slot | slot ok, **HP NON ricalc** | 🟠 #3 |
| class | rimuovi tutte le classi | gestione robusta 0 classi | no crash, HP fantasma | 🟢/🟠 #3 |
| homebrew | listTemplates + installTemplate | regola installata | "Punti Fortuna" attiva | 🟢 |
| homebrew | RuleEditor render | builder DSL senza crash | conforme | 🟢 |
| homebrew | engine (suite Playwright) | 63 test | **63 passed** | 🟢 |

## Regressioni di bug noti
Tutti i bug noti `VERIFIED` ricontrollati in questo run risultano **ancora risolti** (nessuna regressione):
F01 (equip armatura→AC), F02 (HP auto-recalc su CON), F03 (reroll ispirazione nel modale), F04 (Spossatezza "livello 0→N"), F07 (slot picker arma versatile), F19+R04 (dice 4d6kh3 top-3/notation), F20 (no ClassTabs inerti), F21 (14 condizioni, no Rapide row), R01 (Ripristino "Lungo/Breve"), R02+U047/U048 (slot Auto-mode + confirm), U006/U023/U024 (ordine D&D stat + placeholder), U051 (velocità ≈ m), U053 (sticky save identity), U055 (risorse total>0), U062 (caption Spossatezza), U067 (dice timestamp). Nessun `REGRESSED`.

## Suite esistenti
- **Homebrew (Playwright, da WSL):** `npx playwright test -c playwright.homebrew.config.ts` → **63 passed (18.5s)**. Copre event/action coverage, modificatori passivi, filtri (eq/neq/lt/lte/gt/gte/in/has_property), error case (DSL malformata 422, regola disabilitata, cycle detection, filtri no-match), state transitions (integra→danneggiata→distrutta, bleeding HP floor a 0). Motore homebrew solido.
- **Backend (pytest):** NON eseguito (vincolo `uv` da WSL). Suggerito all'utente da Windows: `uv run pytest tests/integration -q`. Gli oracoli BE qui sono stati verificati via lettura codice + asserzione risposta di rete.

## Grafo dipendenze (archi promossi a `verified` in questo run)
- stats→hp (CON→hit_points), inventory→ac (equip armor/shield→base/shield AC), hp(rest long)→{hp,slots,abilities,deathsaves}, spells(use)→slots, spells(use)→spells(concentration), hp/spells(concentration_save su danno)→spells, xp→{hp,slots,class}, class(distribute)→{hp,slots}, settings(recalc)→hp, **settings(slot mode)→slots** (nuovo arco scoperto), character-create→{hp,slots}.
- Arco con comportamento anomalo: **class(remove)→hp** atteso ma NON implementato (Finding #3); class(remove)→slots verificato.

## Copertura
- **Route testate: 23/23 in scope** (3 `/session*` escluse da scope utente). Tutte le sub-route incl. homebrew/new.
- **Endpoint: ~78/78 in scope testati** (sessions.* esclusi). Dettaglio in `coverage.md`.
- Escluse: `/session`, `/session/join`, `/session/:id` + `sessions.*` — sessione multiplayer, esclusa esplicitamente dall'utente.

## Riepilogo findings
- 🔴 **#1** — Doppio submit pagina HP (Conferma): 2 PATCH + cronologia duplicata + doppio dispatch homebrew. Latente rischio danno doppio.
- 🟠 **#2** — Doppio submit XP (Applica): 2 PATCH (valore mascherato dalla race).
- 🟠 **#3** — Remove classe non ricalcola gli HP (HP fantasma; slot invece ricalcolati). Emerso su richiesta utente.
- 🟡 **#4** — Hero "LIV 2 / LEVEL UP" con 0 classi (cosmetico).
- 🟡 **#5** — Freccia "Indietro" = `navigate(-1)` (history), nessun ritorno diretto all'hub personaggio; prop `backTo` dead + nessun bottone Home. Aggiungere Home o cablare `backTo`.
- 🟠 **#6** — `PATCH /classes/distribute` omette dalla risposta le risorse di classe appena inserite (manca `_refresh_char_full`): la card multiclass non mostra le risorse nuove (es. Punti Ki) fino a reload. Persistenza ok.
- 🟡 **#7** — Crocetta di chiusura dei toast con sfondo bianco in tema scuro (`Toast.tsx`: close button non tematizzato) → contrasto incoerente col design. → fe-playwright-audit.
- Nota: doppio DELETE idempotente su dice clearHistory (innocuo, causa diversa da #1/#2 — non onCommit+onClick).

I 3 più gravi: #1 (HP), #3 (remove classe HP), #2 (XP). I fix vanno affidati ad altri agenti — questo è un report di sole segnalazioni.

## Stato fix
Branch: `fix/audit-funzionale-2026-05-30`. Ordine di lavorazione: #1, #3, #6, #2, #5, #7, #4.

- [x] #1 — Guard sincrono anti doppio-submit HP (`savingRef` in `HP.tsx`)
- [x] #3 — Remove classe: ricalcolo HP in `remove_class`
- [x] #6 — `distribute`: `_refresh_char_full` per serializzare le risorse nuove
- [x] #2 — Guard sincrono anti doppio-submit XP (`Experience.tsx`)
- [ ] #5 — Freccia Indietro: cablare il prop `backTo` in `Layout.tsx`
- [ ] #7 — Toast close button tematizzato in tema scuro
- [ ] #4 — Hero "LIV/LEVEL UP" con 0 classi (cosmetico)
