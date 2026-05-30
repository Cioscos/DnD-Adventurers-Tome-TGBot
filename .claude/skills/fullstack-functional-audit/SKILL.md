---
name: fullstack-functional-audit
description: >-
  Audit FUNZIONALE end-to-end full-stack della D&D Mini App (FE React in webapp/ + API FastAPI
  in api/ + core in core/), guidato da Playwright MCP. Per OGNI pagina non si limita a guardare
  la UI: legge il codice FE, traccia le chiamate API, legge il router/service BE e ne ricava
  l'oracolo di correttezza (incluse le regole D&D 5e), poi guida la UI e ASSERISCE valore reale
  vs atteso. Costruisce un grafo vivo delle dipendenze funzionali fra pagine e produce un report
  fixabile da un altro agente. USA SEMPRE questa skill quando l'utente chiede di "testare
  funzionalmente la webapp / l'app", "verificare che i calcoli / le regole D&D siano corretti",
  "fare un audit full-stack / funzionale", "controllare FE + API + BE insieme", "esplorare tutta
  l'app / tutti i sottomenu senza saltarne", "trovare regressioni funzionali", "verificare le
  dipendenze fra pagine (es. cambio CON -> HP, equip -> CA, riposo -> slot)", o testare la
  correttezza di un flusso (hp, death saves, riposo, attacco, incantesimi, slot, level-up, ecc.).
  Accetta in input cosa testare (include) e cosa NON testare (exclude). Produce SOLO segnalazioni
  in un report nella cartella della skill; NON applica fix. Per problemi PURAMENTE visivi/di
  design (allineamenti, overflow, palette, animazioni) usa invece `fe-playwright-audit`.
---

# Full-stack Functional Audit

Questa skill verifica la **correttezza funzionale** della Mini App D&D attraversandola davvero con
Playwright MCP, ma trattando ogni pagina come una fetta verticale **FE → API → BE**: legge il codice,
ricava cosa *dovrebbe* succedere (l'oracolo), poi confronta col comportamento reale. Il deliverable è
un **report di sole segnalazioni** abbastanza dettagliato da permettere a un altro agente di risolverle
senza altro contesto. **Non esegue fix.**

È la sorella funzionale di `fe-playwright-audit` (che è visiva/design-first). Le due sono complementari:
se trovi un problema **puramente** estetico (allineamento, overflow, palette, motion) annotalo come 🟡 e
rimanda a `fe-playwright-audit`; qui il focus è **logica, dati, contratti API e regole D&D 5e**.

## Principi non negoziabili

1. **Niente viene dimenticato — è il requisito #1.** La copertura non si fida di liste statiche (che
   invecchiano: CLAUDE.md dichiara "No test suite" ma i test esistono eccome). Al Passo 1 **derivi
   l'inventario dalla sorgente** e tieni un *Coverage Ledger*: la skill non è conclusa finché resta una
   sola riga `pending`. Le esclusioni da scope restano nel ledger marcate `excluded-by-scope` col motivo
   — mai sparizioni silenziose.
2. **Ogni pagina è una fetta verticale.** Prima di toccare il browser su una pagina, leggi il suo codice
   FE, traccia le `api.*` che chiama, e leggi il BE che le serve. L'oracolo nasce dal codice, non da
   intuizione. Vedi `references/oracles.md`.
3. **Asserzione, non osservazione.** Un test funzionale vale solo se confronti un valore **reale**
   (letto da `browser_evaluate` o dalla risposta di rete) con uno **atteso** (l'oracolo). "Il numero è
   cambiato" non basta: verifica che sia il numero *giusto* secondo la regola D&D.
4. **Interazione incrementale, mai azioni concatenate alla cieca.** Agisci su un singolo controllo →
   aspetti il render (`browser_wait_for`) → leggi lo stato (rete + JS) → asserisci → solo allora prosegui.
   Questo eredita il principio 5 di `fe-playwright-audit`: senza di esso perdi validazione, toast e stati
   intermedi.
5. **Le dipendenze cross-page si verificano davvero.** Quando un'azione muta un campo che un'altra pagina
   legge (es. CON → `hit_points`), non ti fidi: vai sulla pagina dipendente e verifichi che rifletta il
   cambio. Ogni dipendenza scoperta diventa un arco del grafo vivo.
6. **Solo segnalazioni, nessun fix.** Il deliverable è un report. Ogni finding è autosufficiente: FE file
   + endpoint + BE `file:riga` + atteso-vs-reale + fix proposto + evidenza.
7. **Mai `uv`/`uv sync`/`uv run` da WSL** (vedi `CLAUDE.md`): corrompe la `.venv` Windows. `npm`/`npx`
   da WSL sono OK. Se serve far girare pytest, lo chiedi all'utente da PowerShell.

## Passo 0 — Parsing input (include / exclude)

Dal prompt estrai lo scope:

- **Include** ("testa solo X", "verifica il flusso degli incantesimi"): limita le aree a quelle citate.
- **Exclude** ("non testare le sessioni", "salta le mappe"): escludi quelle aree.
- Mappa i termini dell'utente alle aree usando la tabella termini→area di
  `.claude/skills/fe-playwright-audit/references/flows.md` (riusala, non duplicarla).
- Default: **tutte** le aree (incluse `/session/*`, che la skill sorella lascia opzionali — qui le
  consideri salvo esclusione esplicita).
- Se lo scope è ambiguo, chiedi conferma.

Annota lo scope a inizio report. **Anche con scope ristretto, l'intero inventario va nel Coverage Ledger**:
ciò che è fuori scope si marca `excluded-by-scope`, non sparisce.

## Passo 1 — Deriva l'inventario e costruisci il Coverage Ledger

Apri `references/coverage-map.md` e segui la procedura di derivazione. In sintesi:

1. **Route**: estrai ogni `<Route path=…>` da `webapp/src/App.tsx`.
2. **Superficie API**: estrai ogni `api.<namespace>.<metodo>` da `webapp/src/api/client.ts`.
3. **Cross-check** con `docs/webapp-audit/00-index.md` (23 aree documentate).
4. **Confronto col seed** in `coverage-map.md`: se trovi route/endpoint che il seed non elenca → l'app è
   cambiata: aggiorna il ledger e **segnala il drift** (potenziale superficie non documentata). Se il seed
   ha voci non più presenti nel codice → segnala la rimozione.

Scrivi `coverage.md` (template in `coverage-map.md`): una riga per ogni **route** e per ogni **metodo API**,
colonna stato `pending | tested | excluded-by-scope | blocked` + colonna note. Questo file è la prova
anti-skip: a fine run non deve avere righe `pending`.

## Passo 2 — Precheck dello stack

La webapp gira contro l'API locale. Verifica che entrambi rispondano **senza avviare `uv`** (riusa la
procedura di `fe-playwright-audit`):

```bash
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/docs   # API FastAPI
curl -s -o /dev/null -w "%{http_code}" http://localhost:5173/       # Vite dev server
```

- **API giù** (`000`/rifiutata): **chiedi all'utente** di avviarla da PowerShell — non puoi da WSL.
  Suggerisci col prefisso `!`: `! uv run uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload`.
  Il dev bypass (`DEV_USER_ID` in `.env`) salta l'auth Telegram: nessun init-data in locale.
- **Vite giù**: puoi avviarlo tu da WSL — `cd webapp && npm run dev` in background, poi attendi `:5173`.
  Controlla che `webapp/.env.local` punti a `http://127.0.0.1:8000`.

Carica in contesto, prima di procedere: `references/oracles.md`, `docs/webapp-audit/known-issues.md`,
`docs/webapp-audit/findings-tracker.md`, `docs/webapp-audit/fixture-character.md`, e
`docs/webapp-audit/dependency-graph.json` se esiste (il grafo vivo da arricchire).

## Passo 3 — Prepara la cartella di sessione

```
reports/<YYYY-MM-DD_HH-MM>-<scope>/
├── report.md
├── coverage.md
└── screens/
```

`<scope>` è `full` per l'audit completo, altrimenti un tag breve (`hp`, `spells`, ...). Genera il
timestamp **una volta sola** a inizio run (`date '+%Y-%m-%d_%H-%M'`) e riusalo. Tutti gli artefatti di
sessione vivono qui; l'unica eccezione è il grafo vivo (Passo 6), che vive in `docs/webapp-audit/`.

## Passo 4 — Loop full-stack per ogni nodo in scope

Ripeti questo ciclo per **ogni** pagina/area non esclusa. Se lo scope è "tutte le aree", il primo nodo è
`character-create`: crea la fixture via UI (o riusa "Effervescent Barto" id=3 se presente — vedi
`fixture-character.md`) perché alimenta i flussi successivi.

1. **Leggi FE.** Apri `webapp/src/pages/<X>.tsx` (e i sub-componenti in `webapp/src/pages/<area>/`).
   Elenca: le chiamate `api.*`, i controlli UI che le scatenano, le `queryKey` di TanStack Query, e gli
   aggiornamenti ottimistici (`qc.setQueryData`) — un update ottimistico può mascherare un BE rotto, da
   smascherare col reload (punto 6).
2. **Traccia API.** Mappa ogni `api.x.y()` → endpoint (metodo + path) via `webapp/src/api/client.ts`.
3. **Leggi BE e ricava l'oracolo.** Dal path risali a `api/routers/<…>.py` → `api/services/…` /
   `core/game/…`. Determina l'**output atteso** (specie i calcoli D&D), citando `file:riga`. Per le regole
   note usa `references/oracles.md` come mappa già pronta; per il resto leggi il codice.
4. **Guida la UI e asserisci** (incrementale, principio 4):
   - Naviga (`#/char/:id/<route>`), `browser_wait_for` il contenuto chiave.
   - Esegui una singola azione (digita/clicca un controllo).
   - **Leggi il valore reale**: `browser_network_requests` (la risposta JSON dell'endpoint è la verità
     lato BE) + `browser_evaluate` (cosa mostra la UI).
   - **Confronta col l'oracolo**: il valore mostrato e quello restituito coincidono con l'atteso D&D?
     Discrepanza UI≠BE → bug FE; BE≠regola → bug BE; entrambi sbagliati → bug BE non corretto dalla UI.
   - Copri gli **stati**: empty (lista vuota → empty-state o buco?), loading (skeleton sparisce?), error
     (id inesistente o `browser_network_request` abort → messaggio leggibile o schermata bianca?).
   - Copri la **validazione**: input vuoto / fuori range / formato errato → ognuno è uno step con la sua
     asserzione (errore mostrato? bottone disabilitato? il BE rifiuta con 4xx?).
5. **Registra le dipendenze.** Se l'handler BE muta campi che altre pagine leggono (vedi la matrice in
   `references/dependency-graph.md`), aggiungi l'arco al grafo e **programma il check cross-page**: vai
   sulla pagina dipendente e verifica che rifletta il cambio (es. dopo `rest('long')` apri `/slots` e
   verifica `used=0`; dopo cambio CON apri `/hp` e verifica il nuovo max).
6. **Robustezza.** Dopo le mutazioni: (a) **persistenza al reload** — ricarica e verifica via rete/JS che
   il valore sia persistito lato API, non solo ottimistico; (b) **doppio submit** — clicca due volte
   rapidamente e osserva chiamate API doppie / stati incoerenti (`browser_network_requests`).
7. **Emetti findings e aggiorna il ledger.** Scrivi le segnalazioni nel formato standard. **Cross-check**
   con `known-issues.md`/`findings-tracker.md`: se è un bug noto `VERIFIED` ancora presente → marcalo
   `REGRESSED` (non come nuovo); se è davvero nuovo → nuova scheda. Marca la riga del Coverage Ledger
   `tested` (route **e** ogni endpoint toccato).

> **Console & network sempre attivi.** A ogni pagina: `browser_console_messages` (ogni errore JS è 🔴) e
> `browser_network_requests` (ogni 4xx/5xx inatteso è 🔴).

## Passo 5 — Suite esistenti (ground-truth)

Le suite già nel repo sono un oracolo di verità complementare alla lettura del codice:

- **Homebrew (Playwright, eseguibile da WSL).** Per l'area homebrew:
  `cd webapp && npx playwright test -c playwright.homebrew.config.ts` — incorpora gli esiti (pass/fail) nel
  report. Questi spec coprono event/action coverage, template, modificatori passivi, filtri, error case e
  transizioni di stato (`webapp/tests/e2e-playwright/homebrew/`).
- **Backend (pytest, NON da WSL).** Non puoi lanciare `pytest` da WSL (vincolo `uv`). Individua i test
  rilevanti per l'area in scope sotto `tests/` e **chiedi all'utente** di eseguirli da Windows, suggerendo
  col prefisso `!` (es. `! uv run pytest tests/integration -k hp -q`). Incorpora l'output. Se l'utente
  declina, prosegui con l'oracolo da codice e annotalo nel report.

## Passo 6 — Aggiorna il grafo vivo

Il grafo delle dipendenze funzionali è un artefatto **persistente e committato** in
`docs/webapp-audit/dependency-graph.json` (+ `dependency-graph.md` con diagramma Mermaid). Segui
`references/dependency-graph.md`: fai **merge idempotente** degli archi scoperti (non duplicare archi
esistenti; aggiungi solo i nuovi e arricchisci `evidence`), poi rigenera il `.md`. Se i file non esistono
ancora, creali dalla matrice seed in `references/dependency-graph.md`.

## Passo 7 — Genera il report

Scrivi `report.md` nella cartella di sessione. **Solo segnalazioni, nessun fix.** Severità:
🔴 bug funzionale / contratto rotto / crash · 🟠 regressione o comportamento errato non bloccante ·
🟡 nit (UX/visivo → rimanda a `fe-playwright-audit`) · 🟢 ok.

Struttura:

```markdown
# Audit funzionale full-stack — <scope>

> Data: <YYYY-MM-DD HH:MM> · Tool: Playwright MCP + lettura codice FE/API/BE
> Stack: API http://127.0.0.1:8000 · Vite http://localhost:5173 · Fixture: <id>
> Severità: 🔴 bug/contratto · 🟠 errore non bloccante · 🟡 nit (→ fe-playwright-audit) · 🟢 ok

## Copertura
- Route testate: X/Y · Endpoint testati: A/B
- Escluse da scope: <lista con motivo>   ← prova anti-skip
- Dettaglio completo in coverage.md

## Matrice
| ID | Area | Test funzionale | Atteso (oracolo) | Reale | Esito | Evidenza |
|----|------|-----------------|------------------|-------|-------|----------|
| HP1 | hp | death save nat 20 | revive 1 HP + reset saves | rivive ma saves non azzerati | 🔴 | screens/hp-deathsave.png |

## Findings
### #1 — <titolo> [🔴]
- **Area / route:** hp · `#/char/:id/hp`
- **Catena FE→API→BE:** `webapp/src/pages/HP.tsx` (deathRollMutation) → `POST /characters/{id}/death_saves/roll` → `api/routers/hp.py:381` `roll_death_save()`
- **Regola D&D / oracolo:** nat 20 → rivive con 1 HP e azzera i death saves (`hp.py:393-400`)
- **Atteso vs reale:** atteso `death_saves={0,0,false}`; risposta API restituisce `successes=2`
- **Passi per riprodurre:** 1. … 2. …
- **Fix proposto:** <azionabile>
- **Evidenza:** screens/hp-deathsave.png + estratto risposta rete

## Regressioni di bug noti
<bug del findings-tracker marcati VERIFIED ma di nuovo presenti → REGRESSED, con ID originale>

## Suite esistenti
<esiti pytest / playwright homebrew incorporati, o nota che non sono stati eseguiti>

## Grafo dipendenze
<archi nuovi aggiunti a docs/webapp-audit/dependency-graph.json in questo run>
```

Regole del report:
- Una scheda per ogni finding non-🟢. Ogni scheda è **autosufficiente**: chi la risolve non deve
  rileggere lo screenshot né ri-tracciare il codice per capire il problema.
- I 🟡 visivi vanno elencati a parte e rimandati a `fe-playwright-audit` (non sono il focus).
- Aggiorna `docs/webapp-audit/findings-tracker.md` solo nella colonna `Status` per i bug noti
  riconfermati/regrediti — mai rinumerare.

## Chiusura

Riepiloga all'utente: percorso del report, copertura (route/endpoint testati e cosa è stato escluso e
perché), i 3 findings più gravi, gli archi nuovi nel grafo vivo, e gli esiti delle suite. Ricorda che è
un report di sole segnalazioni — i fix vanno affidati ad altri agenti.
