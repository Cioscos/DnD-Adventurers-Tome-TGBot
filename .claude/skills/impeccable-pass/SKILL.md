---
name: impeccable-pass
description: Passata impeccable componente-per-componente della Mini App (webapp/), guidata da un ledger-coda persistente e dalla conoscenza dell'audit FE più recente disponibile. Usa SEMPRE questa skill quando l'utente invoca /impeccable-pass o chiede di "continuare il design pass", "dare una passata impeccable ai componenti", "migliorare design/UX dei componenti", "lavorare il prossimo batch del ledger". Lavora a batch di PAGINA (non di file), instrada ogni problema sul comando impeccable giusto (critique, polish, clarify, harden, adapt, layout, animate, ...), applica i fix, verifica via Playwright a 375×667 e spunta il ledger. Una PR per giro con label release:patch.
user-invocable: true
argument-hint: "[id batch es. B4, oppure vuoto = primo batch non completato]"
---

# Impeccable Pass — design pass incrementale per componenti

Migliora design e UX di ogni componente della webapp lavorando a **batch di pagina** su una
coda persistente (`ledger.md` in questa cartella). Ogni invocazione lavora 1+ batch e spunta
il ledger: procedura e stato vivono su disco, quindi sopravvivono a `/clear` e compaction.

La skill è autoconsistente: **nessun percorso qui dentro è obbligatorio**. Ogni fonte di
conoscenza viene scoperta a runtime e, se manca, la skill indica quale altra skill eseguire
per generarla; in assenza totale procede comunque in modalità code-first.

## Passo 0 — Risoluzione dinamica delle fonti di conoscenza

1. **Ledger (coda di lavoro)**: `ledger.md` in questa cartella.
   - Se esiste: è la coda. Lavora il batch passato come argomento, altrimenti il primo `☐`.
   - Se NON esiste: fai il bootstrap. Estrai le route da `webapp/src/App.tsx`, raggruppa le
     pagine in 10-15 batch tematici (hub, equip, HP, tiri, magia, zaino, crescita, diario,
     dadi, impostazioni, homebrew, sessione) + 2-3 batch trasversali (modali/overlay,
     copy/i18n, stati di errore) + un batch finale di re-audit. Per mappare i componenti a
     ogni pagina usa la skill `graphify-nav` se disponibile, altrimenti gli import dei file
     pagina. Semina ogni batch con i findings dell'audit più recente (punto 2). Scrivi il
     ledger e committalo insieme al primo batch.
2. **Conoscenza d'audit (riusala, non rifarla)**: cerca i report più recenti, in ordine:
   - `ls -dt .claude/skills/fe-playwright-audit/reports/*/` → la cartella più recente che
     contiene `report.md` (findings), ed eventuali `component-coverage.md` (dove si osserva
     ogni componente) e `screens/` (screenshot full-page già scattati).
   - Analogo per `.claude/skills/fullstack-functional-audit/reports/*/` se esiste (oracoli
     funzionali: utile per non scambiare un comportamento corretto per un difetto UX).
   - Per il batch corrente leggi SOLO le sezioni e gli screenshot pertinenti.
   - Se non esiste alcun report, o quello più recente è più vecchio dell'ultimo tag di
     release (`git describe --tags --abbrev=0`): segnala all'utente che la conoscenza è
     assente o stantia e **suggerisci di eseguire prima `/fe-playwright-audit`** (scope =
     aree del batch). Se l'utente preferisce procedere subito, lavora code-first e scatta
     tu gli screenshot che servono.
3. **Contesto impeccable**: invoca la skill `impeccable` (Skill tool) e completa i suoi gate
   di setup: il suo loader risolve `PRODUCT.md` e `DESIGN.md` a root. Se `PRODUCT.md` manca,
   la skill impeccable stessa instrada su `teach`: seguila e poi riprendi da qui. Non
   dipendere da percorsi di installazione di impeccable: è la skill a conoscere i propri
   script e reference.
4. **Stack dev**: `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/docs` e
   `http://localhost:5173/`. API giù → chiedi all'utente di avviarla da PowerShell
   (`! uv run uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload`). Vite puoi
   avviarlo tu da WSL. **MAI `uv` da WSL** (corrompe la `.venv`, vedi CLAUDE.md).
5. **Branch**: mai su main. Un branch per giro (es. `feat/impeccable-pass-<giro>`).

## Routing: il comando impeccable giusto per ogni situazione

Per ogni problema individuato nel batch, carica il reference del comando impeccable che lo
possiede e seguine il flusso (un comando può coprire più findings; non improvvisare un
processo se esiste il comando dedicato):

| Situazione nel batch | Comando impeccable |
|---|---|
| Valutare una pagina/feature con scoring euristico, capire cosa non va | `critique` |
| Drift dal design system, rifiniture, allineamenti, stati interattivi mancanti | `polish` |
| Label, copy, messaggi d'errore, terminologia incoerente, em dash | `clarify` |
| Stati edge: errori API, vuoti, loading, contenuti estremi, i18n robusta | `harden` |
| Problemi responsive/viewport (320-375px, fold, tablet) | `adapt` |
| Spaziatura, ritmo, gerarchia visiva sbagliata | `layout` |
| Tipografia: scale, line-height, font usati fuori ruolo | `typeset` |
| Colore: monocromia, semantica violata, contrasto | `colorize` |
| Motion: transizioni mancanti/rotte, micro-interazioni | `animate` |
| Pagina sovraccarica o urlata | `distill` / `quieter` |
| Pagina piatta o anonima che merita carattere | `bolder` / `delight` |
| Empty state e primo utilizzo | `onboard` |
| Jank, re-render, animazioni costose | `optimize` |
| Score complessivo (baseline e re-audit di fine giro) | `audit` |
| Il fix rivela token/componenti da promuovere a sistema | `extract`, poi `document` per aggiornare DESIGN.md |
| Iterazione visiva dal vivo su un elemento conteso | `live` |

Regola pratica per batch: apri con `critique` sulla pagina, instrada i findings sui comandi
sopra, chiudi con `polish` come passata finale.

## Il loop per batch (ripetibile, ~4-6 batch per sessione)

1. **Critique a doppia lente** (reference `critique` + le 8 regole nominate di DESIGN.md):
   - **Codice**: leggi i file del batch cercando il drift che gli screenshot non mostrano
     (side-stripe, `bg-black`/`#fff`/`#000`, halo decorativi, token hard-coded, easing
     elastici fuori dal dice-roller, em dash nel copy, stati interattivi mancanti).
   - **Screenshot**: parti da quelli dell'audit più recente se esistono; scatta i nuovi
     stati mancanti. Gerarchia, leggibilità a braccio teso, light mode con pari rigore.
2. **Triagia e instrada**: conforme / fix (applicalo col comando impeccable competente) /
   miglioria UX oltre la conformità (applicala se nello spirito di PRODUCT.md: "il numero
   prima dell'ornamento", max 3 tocchi, memoria muscolare) / rimanda (annota nel ledger).
3. **Fix**: riusa i componenti condivisi (Sheet, ConfirmSheet, EmptyState, chip); mai
   one-off nuovi se esiste l'equivalente nel design system.
4. **Verifica** via Playwright MCP a **375×667** (+ 320×568 sulle schermate dense):
   screenshot prima/dopo, console pulita, interazione incrementale (un'azione → osserva →
   la successiva). `tsc --noEmit` + `npm run lint` a fine batch.
5. **Spunta il ledger**: stato → `✅` (o `◐` con nota), 1 riga di esito nel Diario.
   Committa codice + ledger insieme (`fix(design): batch <id> — <sintesi>`).

## Gotcha operativi (verificali, non assumerli: l'app evolve)

- Lo scroll delle pagine è su `<main>` (pattern Layout), non sul body.
- L'API locale può rispondere in 2-3s: dopo una mutazione attendi ≥3s prima di leggere.
- I click via `evaluate` JS bypassano overlay e hit-testing: per i click usa i ref dello
  snapshot Playwright. I toast durano ~4s: catturali con click+poll nello stesso evaluate.
- Tema: localStorage `dnd-theme-settings` (`{"state":{"mode":"dark"},"version":0}`);
  `auto` in browser puro = light. Run canonica in dark, ricontrolla i fix anche in light.
- Fixture: serve un personaggio ricco di stato (multiclasse, condizioni, item equipaggiati,
  spell con concentrazione). Se non c'è, crealo via UI (la creazione è essa stessa un test).
  Per le sessioni multiplayer: secondo utente in un tab con `?dev_user=<id>` (richiede
  `DEV_USER_ID` in `.env`).
- Il full-page screenshot NON cattura i contenitori a scroll interno: scatta top + bottom.

## Regole di consegna

- **Scope accessibilità** da CLAUDE.md: niente findings screen-reader/ARIA; sì contrasto,
  touch target, leggibilità a braccio teso, focus visibile.
- Conferma a DESTRA, annulla a sinistra, ovunque.
- Una PR per giro: voce changelog bilingue + bump `package.json`/`pyproject.toml` + label
  `release:patch` (o `minor` se il giro introduce UX nuova). PR serializzate: il
  changelog-check confronta con l'ultimo tag. Prima del commit dei sorgenti webapp:
  `cd webapp && npm run build:prod`.
- A fine giro esegui `audit` (impeccable) e annota lo score nel ledger accanto alla
  baseline precedente; se manca una baseline, quella di questo giro lo diventa.
- Se trovi un bug funzionale (non di design), NON fixarlo qui: annotalo nel ledger in
  "Fuori scope" e segnalalo all'utente (per i sospetti usa `/fullstack-functional-audit`).
