---
name: impeccable-pass
description: Passata impeccable componente-per-componente della Mini App (webapp/), guidata dal ledger-coda e dalla conoscenza dell'audit FE del 2026-06-11. Usa SEMPRE questa skill quando l'utente invoca /impeccable-pass o chiede di "continuare il design pass", "dare una passata impeccable ai componenti", "migliorare design/UX dei componenti", "lavorare il prossimo batch del ledger". Lavora a batch di PAGINA (non di file), critica codice+screenshot, applica i fix, verifica via Playwright a 375×667 e spunta il ledger. Una PR per giro con label release:patch.
user-invocable: true
argument-hint: "[id batch es. B4, oppure vuoto = primo batch non completato]"
---

# Impeccable Pass — design pass incrementale per componenti

Migliora design e UX di ogni componente della webapp lavorando a **batch di pagina** su una
coda persistente (`ledger.md` in questa cartella). Ogni invocazione lavora 1+ batch e spunta
il ledger: la procedura sopravvive a `/clear` e compaction perché vive su disco.

## Setup (ogni invocazione, in quest'ordine)

1. **Contesto impeccable**: esegui `node /home/claudio-ubuntu/.claude/skills/impeccable/scripts/load-context.mjs`
   (fallback: `node .claude/skills/impeccable/scripts/context.mjs`). Deve trovare `PRODUCT.md`
   e `DESIGN.md` a root. Leggi poi i reference della skill impeccable:
   `reference/critique.md` + `reference/polish.md` + `reference/product.md`
   (in `/home/claudio-ubuntu/.claude/skills/impeccable/`).
2. **Coda**: leggi `ledger.md` (questa cartella). Se l'utente ha passato un id batch (es. `B4`)
   lavora quello; altrimenti il primo batch con stato `☐`.
3. **Conoscenza dell'audit** (riusala, non rifarla): nella cartella
   `.claude/skills/fe-playwright-audit/reports/2026-06-11_18-58-mobile/` trovi
   `report.md` (findings #1-#12, #V1-#V4), `component-coverage.md` (dove si osserva ogni
   componente) e `screens/` (~90 screenshot full-page 375×667 già scattati). Per il batch
   corrente leggi SOLO le sezioni e gli screenshot pertinenti.
4. **Stack dev**: `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/docs` e
   `http://localhost:5173/`. API giù → chiedi all'utente di avviarla da PowerShell
   (`! uv run uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload`). Vite puoi avviarlo
   tu da WSL. **MAI `uv` da WSL** (corrompe la .venv, vedi CLAUDE.md).
5. **Branch**: mai su main. Un branch per giro (es. `feat/impeccable-pass-<giro>`).

## Il loop per batch (ripetibile, ~4-6 batch per sessione)

Per il batch scelto dal ledger:

1. **Critique a doppia lente** (reference critique + le 8 regole nominate di DESIGN.md):
   - **Codice**: leggi i file del batch cercando il drift che gli screenshot non mostrano
     (side-stripe, `bg-black`/`#fff`, halo decorativi, token hard-coded, easing elastici,
     em dash nel copy, stati interattivi mancanti). Il code-scan ha già trovato violazioni
     invisibili a occhio: ripeti il metodo.
   - **Screenshot**: parti da quelli esistenti in `screens/`; scatta nuovi stati solo se
     mancano. Gerarchia, spaziatura, leggibilità a braccio teso, light mode.
2. **Triagia**: conforme / fix piccolo (falla subito) / migliora (proposta UX oltre la
   conformità, applicala se nello spirito di PRODUCT.md: "il numero prima dell'ornamento",
   max 3 tocchi, memoria muscolare) / rimanda (annota nel ledger con motivo).
3. **Fix**: applica. Riusa i componenti condivisi (Sheet, ConfirmSheet, EmptyState, chip);
   mai nuovi one-off se esiste l'equivalente nel design system.
4. **Verifica** via Playwright MCP a **375×667** (+ 320×568 sulle schermate dense):
   screenshot prima/dopo, console senza errori, interazione incrementale (un'azione → osserva
   → poi la successiva). `tsc --noEmit` + `npm run lint` a fine batch.
5. **Spunta il ledger**: stato → `✅` (o `◐` se parziale, con nota), aggiungi 1 riga di esito.
   Committa: codice + ledger insieme (`fix(design): batch <id> — <sintesi>`).

## Gotcha operativi (imparati nell'audit, non riscoprirli)

- Lo scroll delle pagine è su `<main>` (pattern Layout), NON sul body né su div.
- L'API locale risponde in ~2-3s: dopo ogni mutazione attendi ≥3s prima di leggere lo stato.
- I click via `evaluate` JS bypassano overlay e hit-testing: per i click usa SEMPRE i ref
  dello snapshot Playwright. I toast durano ~4s: catturali con click+poll nello stesso evaluate.
- Tema: localStorage `dnd-theme-settings` (`{"state":{"mode":"dark"},"version":0}`); `auto`
  in browser = light. Run canonica in dark, ricontrolla i fix di contrasto anche in light.
- Fixture: char id 9 (Chierico 1/Mago 2, ricco di stato) e id 10 per l'utente dev 777
  (sessioni: tab con `?dev_user=777`, sessione 48CLPK). Se mancano, ricreali via UI.
- Full-page screenshot NON cattura i contenitori a scroll interno: scatta top + bottom.
- ESC non chiude i ResultDialog finché il batch B1 non lo fixa: chiudi col tap-outside.

## Regole di consegna

- **Scope accessibilità** da CLAUDE.md: niente findings screen-reader/ARIA; sì contrasto,
  touch target, leggibilità, focus visibile.
- Conferma a DESTRA, annulla a sinistra, ovunque.
- Una PR per giro: voce changelog bilingue + bump `package.json`/`pyproject.toml` + label
  `release:patch` (o `minor` se il giro introduce UX nuova). PR serializzate: il
  changelog-check confronta con l'ultimo tag. Prima del commit dei sorgenti webapp:
  `cd webapp && npm run build:prod`.
- A fine giro aggiorna la baseline: ricalcola lo score impeccable audit (5 dimensioni 0-4)
  e annotalo in `ledger.md`; baseline di partenza 14/20, target ≥17/20.
- Se trovi un bug funzionale (non di design), NON fixarlo qui: annotalo nel ledger sezione
  "Fuori scope" e segnalalo all'utente.
