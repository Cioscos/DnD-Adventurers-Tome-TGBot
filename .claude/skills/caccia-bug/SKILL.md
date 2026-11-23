---
name: caccia-bug
description: >-
  Caccia ai bug funzionali della D&D Mini App (FE React, API FastAPI, core) e agli scostamenti di comportamento dal
  manuale D&D 2014/2024, con una pipeline fissa: regressione del catalogo, scelta delle zone, caccia, conferma
  indipendente e, su scelta dell'utente, risoluzione. Ogni bug confermato diventa un test permanente (pytest, Vitest,
  Playwright), così i giri successivi non ripartono da zero. USA SEMPRE questa skill quando l'utente chiede di "cercare
  bug", "andare a caccia di bug", "fare un audit funzionale / full-stack", "testare funzionalmente l'app", "verificare
  che l'app si comporti come il manuale", "controllare FE + API + BE insieme", "lanciare la regressione", "blindare
  l'app dai bug", o di correggere un bug del catalogo ("risolvi CB-012"). Per leggere il codice accanto alle carte dei
  manuali usa rules-conformance-team; per una partita simulata party-playtest; per difetti visivi fe-playwright-audit.
---

# Caccia ai bug

Sei il **coordinatore**. Prepari, assegni, fai confermare e salvi. La caccia e la conferma le fanno subagenti diversi: chi
ha trovato un bug è il meno adatto a dubitarne.

Le vecchie skill davano esiti diversi a ogni giro perché reinventavano il piano e non lasciavano controlli. Qui il catalogo
è fatto di test nel repository, e uno script senza modello decide copertura e zone. Se ti accorgi che stai improvvisando
un piano, torna allo script.

## Modi

- `caccia` (predefinito): passi 0-7, poi 8-9 se l'utente sceglie dei bug. Opzioni: zone da includere o escludere, edizione,
  `zone=N` (predefinito 8).
- `regressione`: solo il passo 2 e un resoconto. Non crea branch e non scrive nulla nel repository.
- `risolvi CB-…`: passi 8-9 sui controlli indicati.

## Vincoli

- Python solo da Windows con `uv run`. Mai `data/dnd_bot.db`, mai la porta 8000, mai messaggi Telegram.
- I manuali (`docs/superpowers/rules/{2014,2024}/`) sono locali. Nel repository si citano edizione, carta e pagina, mai il
  testo. Se mancano, dillo: le regole restano fuori dal giro e non vanno date per coperte.
- `git add` solo dei file toccati. Push e PR solo dopo il sì dell'utente, con l'account indicato in `CLAUDE.md`. Senza
  autorizzazione ti fermi al commit locale.
- Regole mancanti del tutto = `mancante`: si annotano, non sono bug.

## 0. Ambito e branch

Albero tracciato pulito, altrimenti chiedi. Ogni caccia stacca un branch nuovo `fix/caccia-<YYYY-MM-DD_HH-MM>`: da `main`, o
dal branch di una caccia precedente non ancora unita (`git branch --no-merged main --list "fix/caccia-*" "feat/caccia-bug"`;
se sono più d'uno, chiedi quale). Senza fix scelti il branch resta aperto, senza PR né release. `risolvi` lavora sul branch
che contiene quei controlli, o su uno nuovo se sono già in `main`.

Crea `docs/superpowers/caccia/<YYYY-MM-DD_HH-MM>/` (locale) per report e materiale.

## 1. Inventario

```
uv run python -m tests.caccia.inventario verifica
uv run python -m tests.caccia.inventario elenco
```

Prima aggiorna il grafo con la skill `graphify` (`--update`), se c'è. Se `verifica` segnala un endpoint, una route, un file
o una carta senza zona, aggiungilo alla zona giusta in `tests/caccia/zone.json` prima di proseguire: ciò che non ha zona
non verrebbe mai cacciato.

## 2. Regressione

```
uv run pytest tests/caccia -n auto -q
cd webapp && npm run test:caccia
uv run python -m tests.caccia.inventario verifica
```

Ogni rosso passa dalla conferma (passo 5) e ha tre esiti possibili:
- **regressione** → va all'utente al passo 7; mai un xfail automatico, nasconderebbe un difetto nuovo;
- **cambiamento voluto** → solo con una decisione dell'utente, scritta in `tests/caccia/decisioni.md`; poi si aggiorna la fonte;
- **controllo sbagliato** → si corregge, o si ritira mettendo l'id in `ritirati` di `stato.json`.

Un xfail che passa è rosso: qualcuno ha corretto il bug. Dopo la conferma si toglie il segno. I rossi non fermano la caccia.

## 3. Zone

```
uv run python -m tests.caccia.inventario scegli --max 8 [--includi 'flusso:*'] [--escludi …] [--edizione 2024]
```

Usa l'elenco così com'è e riferisci quante zone restano. Annota `git rev-parse HEAD`: è il commit esaminato.

## 4. Caccia

**4a. Affermazioni.** Un subagente per zona (`general-purpose`, modello `sonnet`) con `references/affermazioni.md`: scompone le
fonti in affermazioni con casi e valori limite, **senza leggere il codice**, in `tests/caccia/affermazioni/<zona>.json` (zona
con `-` al posto di `:` e `/`). Se il file c'è già, lo completa. È ciò che rende il giro ripetibile: senza, ogni cacciatore
sceglie i valori a istinto e il caso che rivela il bug resta fuori.

**4b. Caccia.** Con `references/caccia.md`, un subagente per ogni gruppo di al massimo 25 casi da provare
(`uv run python -m tests.caccia.inventario casi <zona>`): una zona grande ha più cacciatori, con i casi divisi per affermazione.
Per ogni cacciatore prepara:
- la riga di `zone.json`, i file che corrispondono ai suoi glob e l'elenco dei suoi casi;
- un blocco di 100 id consecutivi, a partire da `prossimo-id` (gli id non usati restano vuoti);
- i file di test che può scrivere: `tests/caccia/test_cb_<zona>.py`, `webapp/tests/unit/caccia/<zona>.test.tsx`,
  `webapp/tests/e2e-playwright/caccia/<zona>.spec.ts`, con la zona senza `:` e `/` e un suffisso `_2`, `_3`
  per i cacciatori oltre il primo. Sono solo suoi, così i paralleli non collidono;
- i problemi già noti e ancora aperti nella zona, da `docs/superpowers/rules-audit/`, `docs/superpowers/playtest/` e dal
  catalogo. Quelli risultati corretti che ricompaiono sono regressioni.

I cacciatori scrivono i controlli Playwright ma non li eseguono: le porte sono fisse. Li lanci tu, uno alla volta:
`npx playwright test -c playwright.caccia.config.ts <file>`. Un rosso prima dell'asserzione (selettore che non trova
nulla, timeout) è un difetto del controllo: rimandalo al suo autore con `SendMessage`.

Non accettare la consegna se `uv run python -m tests.caccia.inventario verifica --contiene <file>` segnala errori o se `casi <zona>`
elenca ancora casi suoi: rimandala indietro.

## 5. Conferma

Per ogni rosso **e per ogni domanda**, un subagente nuovo con `references/conferma.md` (segnalazioni della stessa zona insieme,
al massimo 6): riceve solo fonte, passi e risultato osservato. Una domanda che la fonte o un invariante decide diventa bug
o scartata; arriva all'utente solo se resta davvero ambigua. Non passargli
il test né il ragionamento del cacciatore. Unisci i duplicati che hanno la stessa causa. `domanda` → `AskUserQuestion`, con
edizione, pagina, comportamento attuale e opzioni; la risposta va in `decisioni.md`.

## 6. Consolidamento

Per ogni zona, a conferma finita:
1. bug confermati: `@pytest.mark.xfail(strict=True, reason="CB-012 …")`, `test.fails` (Vitest) o `test.fail` (Playwright);
   scartati: via il controllo, o corretto se l'atteso era sbagliato. Restano i verdi che proteggono un comportamento;
2. esegui i controlli della zona e `verifica`: verdi o xfail;
3. segna la zona, con una voce per ciascuna delle dieci:
   `uv run python -m tests.caccia.inventario segna <zona> <commit> --voci contratto=fatta normale=fatta … regola=non_applicabile`
4. commit di soli controlli e stato: `test(caccia): <zona>`.

Un caso non provabile va in `esenti` dell'affermazione, con il motivo. `segna` rifiuta anche i casi senza controllo.
Lo stato si salva solo qui: una zona interrotta, o il cui agente è fallito, resta in coda. `segna` rifiuta una voce `fatta`
senza controllo: non aggirarlo scrivendo test vuoti, dichiara la voce `non_applicabile` con il motivo nel report.

Scrivi il report con `references/report.md`.

## 7. Scelta dell'utente

Mostra l'elenco (id, gravità, atteso e reale in una riga, fonte) e chiedi quali correggere. Di' anche le zone guardate, quelle
rimaste e i `mancante`. Nessuna correzione prima della risposta.

## 8. Risoluzione

Segui `references/risoluzione.md`, una causa alla volta.

## 9. Chiusura

Una volta sola: `uv run pytest -n auto -q` e `npm run test:caccia`. Se è cambiato `webapp/`: `npm run lint`, `npx vitest run`,
`npm run check:layout` se è cambiata la UI, `npm run build:prod` se è cambiato `webapp/src/`. Poi changelog e versione secondo
`CLAUDE.md`, riepilogo, e chiedi se fare push e PR con la label di release. I bug non scelti restano xfail.
