---
name: fe-playwright-audit
description: >-
  Audit end-to-end del frontend (React Mini App in webapp/) guidato da Playwright MCP,
  con analisi VISIVA di ogni schermata e verifica dell'aderenza al design system.
  Usa SEMPRE questa skill quando l'utente chiede di "testare il frontend / la webapp /
  la Mini App", fare un "audit FE", "verificare visivamente le pagine", "controllare che
  il FE rispetti il design / DESIGN.md", "cercare elementi decentrati / disallineati /
  fuori posto / overflow / layout rotto", o testare un flusso specifico della webapp
  (hp, ac, spells, inventory, dice, ecc.) — anche se non nomina esplicitamente Playwright.
  Accetta in input la viewport (mobile / desktop / entrambe) e lo scope (tutti i flussi o
  un flusso preciso). Produce SOLO un report di segnalazioni nella cartella della skill;
  NON applica fix.
---

# FE Playwright Audit

Questa skill ispeziona il frontend D&D (`webapp/`, Telegram Mini App React) navigandolo
davvero con Playwright MCP, scatta screenshot **a pagina intera** di ogni stato, li
analizza visivamente per trovare problemi grafici, verifica l'aderenza al design system
(`DESIGN.md`) e produce un **report di sole segnalazioni** pronto per essere risolto da
altri agenti. **Non esegue fix.**

## Principi non negoziabili

1. **Screenshot sempre full-page.** Ogni `browser_take_screenshot` usa `fullPage: true`.
   Un finding visivo vale solo se lo screenshot mostra l'intera pagina, non il viewport
   ritagliato — altrimenti elementi fuori posto in fondo alla pagina restano invisibili.
2. **Analisi visiva obbligatoria di ogni screenshot.** Dopo OGNI screenshot, guarda
   davvero l'immagine restituita e ragiona su cosa non va (vedi sezione "Analisi visiva").
   Non collezionare screenshot da analizzare dopo: analizzali subito, finché hai in mente
   cosa stavi testando.
3. **Solo segnalazioni, nessun fix.** Il deliverable è un report. I findings devono essere
   abbastanza dettagliati da permettere a un altro agente di risolverli senza altro contesto
   (file sospetto + fix proposto + screenshot).
4. **Mai `uv`/`uv sync`/`uv run` da WSL** (vedi `CLAUDE.md`): corrompe la `.venv` Windows.
   Se serve l'API e non è avviata, chiedila all'utente da PowerShell. `npm`/`npx` da WSL OK.
5. **Interazione incrementale, mai azioni concatenate alla cieca.** Non inviare mai al MCP
   una sequenza tipo "inserisci valore + clicca Salva" in un colpo solo. Ogni azione è
   atomica: prima **aspetti che il FE abbia finito di renderizzare** (`browser_wait_for`),
   POI agisci su un singolo controllo, POI **verifichi il risultato** (via
   `browser_evaluate`/JS + `browser_snapshot` + screenshot) PRIMA di passare all'azione
   successiva. Questo è ciò che permette di osservare animazioni, toast e validazione degli
   input — comportamenti che spariscono o vengono saltati se input e submit avvengono
   insieme. Vale per ogni form: digiti il valore → guardi cosa succede (errori di
   validazione, stato del bottone, feedback inline) → solo allora premi Salva → guardi il
   toast/animazione di conferma.

## Passo 0 — Parsing input

Dal prompt dell'utente estrai due parametri:

- **Viewport**: `mobile` (390×844) | `desktop` (1440×900) | `both`. **Default `both`.**
  Parole come "mobile/telefono/cellulare" → mobile; "desktop/PC" → desktop; nessun accenno → both.
- **Scope**: tutti i flussi (default) oppure uno/più flussi specifici. Mappa i termini
  dell'utente alle aree di `references/flows.md` (es. "punti ferita/HP" → area `hp`,
  "incantesimi" → `spells`, "inventario" → `inventory`, "tiri" → `skills`/`saves`, ecc.).
  Se lo scope è ambiguo (es. "magia" potrebbe essere spells o slots), chiedi conferma.

Annota i parametri scelti all'inizio del report.

## Passo 1 — Leggi i riferimenti di design

Prima di toccare il browser, carica in contesto:

- `references/design-checklist.md` (in questa skill) — le 8 regole nominate tradotte in
  controlli verificabili da uno screenshot.
- `DESIGN.md` (root del progetto) — fonte di verità per palette, tipografia, componenti.
- `docs/webapp-audit/00-index.md` — mappa delle route e convenzione del formato findings.

## Passo 2 — Precheck dello stack dev

La webapp gira contro l'API locale. Verifica che entrambi rispondano **senza avviare `uv`**:

```bash
# API FastAPI
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/docs
# Vite dev server
curl -s -o /dev/null -w "%{http_code}" http://localhost:5173/
```

- **API non raggiungibile** (`000`/connessione rifiutata): **chiedi all'utente** di avviarla
  da PowerShell — non puoi farlo tu da WSL. Suggerisci il comando con il prefisso `!`:
  `! uv run uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload`.
  Ricorda che il dev bypass (`DEV_USER_ID` in `.env`) salta l'auth Telegram: nessun init-data
  necessario in locale.
- **Vite non raggiungibile**: puoi avviarlo tu da WSL (è permesso) — proponi/esegui
  `cd webapp && npm run dev` in background, poi attendi che `:5173` risponda. Controlla che
  `webapp/.env.local` punti a `http://127.0.0.1:8000`.

Non procedere finché entrambi non rispondono `200`/`3xx`.

## Passo 3 — Prepara la cartella di sessione

Tutta la sessione di test (report + screenshot) vive in **un'unica cartella di sessione**
dentro questa skill, nominata con data e ora **human-readable**:

```
reports/<YYYY-MM-DD_HH-MM>-<viewport>/
```

Esempio: `reports/2026-05-29_19-07-mobile/` (per `both` usa il suffisso `both`:
`reports/2026-05-29_19-07-both/`). Genera il timestamp una sola volta a inizio run e
riusalo per tutta la sessione — non ricalcolarlo a ogni screenshot, altrimenti gli artefatti
finiscono in cartelle diverse. Ricavalo con:

```bash
date '+%Y-%m-%d_%H-%M'
```

Dentro la cartella di sessione crea una sottocartella `screens/`. Tutti gli screenshot vanno
lì con nomi parlanti: `<area>-<step>-<viewport>.png` (es. `hp-damage-applied-mobile.png`).
Il `report.md` (Passo 5) va nella radice della stessa cartella di sessione. Nessun artefatto
deve essere scritto fuori da questa cartella.

## Passo 4 — Esegui la matrice di test

Apri `references/flows.md` e segui le aree comprese nello scope. Regole di esecuzione:

- Se viewport = `both`: esegui **l'intera matrice per `desktop`, poi di nuovo per `mobile`**.
  Fra i due giri fai `browser_resize` e ricarica la pagina.
- Imposta la viewport con `browser_resize` (desktop `1440×900`, mobile `390×844`) **prima**
  di iniziare ogni giro.
- **Passata "schermo molto piccolo" (stress responsive).** Oltre ai giri standard, ripeti
  almeno le schermate/i flussi più densi (HeroScreen, equipaggiamento, modali di level-up,
  form con molti campi) a una viewport **molto stretta**: `320×568` (small phone) e, come
  caso limite, `280×600` (es. fold richiuso / device piccolissimi). Scopo: capire se i
  componenti si adattano davvero o se servono modifiche mirate. Distingui sempre nel report
  fra **(a)** un componente che si rompe a larghezze ragionevoli (≥320px) — finding reale da
  fixare — e **(b)** un degrado solo a larghezze estreme/irrealistiche (<300px) — comportamento
  al limite, da segnalare come 🟡 informativo, non bloccante. Annota la larghezza esatta a cui
  il layout inizia a cedere (breakpoint di rottura).
- **Fixture via UI**: se lo scope è "tutti i flussi", il primo passo è creare il personaggio
  di test **attraverso l'interfaccia** (flusso `character-create` in flows.md) — la creazione
  è essa stessa un test, e il char creato alimenta tutti i flussi successivi. Se lo scope è
  un singolo flusso, usa un char_id esistente passato dall'utente, oppure creane uno minimale
  via UI per avere su cosa lavorare.
- Gli URL usano HashRouter: `http://localhost:5173/#/<route>` (es. `#/char/12/hp`).
- **Stress di contenuto (dati estremi).** Lo stress di viewport non basta: i layout cedono
  anche per contenuto. Almeno una volta per le schermate dense, popola/scegli dati al limite:
  nome personaggio molto lungo (e con caratteri accentati/emoji), lista incantesimi piena,
  molte condizioni attive insieme, statistiche a 3 cifre, HP 0/negativi, inventario lungo
  vs vuoto. Cerca troncamenti senza ellissi, a-capo brutti, overflow, card deformate. È il
  complemento della passata "schermo molto piccolo".
- **Copertura degli stati (empty / loading / error / popolato).** Per ogni area testa
  deliberatamente più stati, non solo quello "felice": stato **vuoto** (inventario/incantesimi
  senza dati → c'è un empty-state curato o un buco?), stato di **caricamento** (lo skeleton
  appare e poi sparisce davvero?), stato di **errore** (cosa mostra la UI se l'API fallisce a
  metà flusso — simulalo con `browser_network_request`/route abort o con un id inesistente —
  messaggio d'errore leggibile? retry? schermata bianca?), e stato **popolato**. Empty-state
  mancanti/brutti e errori non gestiti sono findings reali.
- **i18n (it/en).** Ripeti almeno le schermate dense cambiando lingua (it ↔ en). Le stringhe
  inglesi/italiane hanno lunghezze diverse: cerca overflow, troncamenti, a-capo o bottoni che
  cambiano dimensione solo in una delle due lingue, e chiavi i18n non tradotte (testo grezzo
  tipo `char.hp.title`). La lingua si forza da `localStorage`/store locale (`locale` nello
  Zustand store) via `browser_evaluate`, poi ricarica.
- **Routing e pulsante indietro.** Verifica la navigazione, non solo le singole pagine:
  deep-link diretto a una route profonda (es. apri `#/char/:id/spells` da URL pulito →
  carica senza crash?), **back del browser**/`browser_navigate_back` e il **BackButton di
  Telegram** (`window.Telegram.WebApp.BackButton`) — tornano allo stato/scroll giusto o
  perdono lo stato del carousel/modale? Chiudere un modale col back non deve uscire dalla
  pagina; aprire un modale dovrebbe poter essere chiuso col back. Segnala route che vanno in
  404/schermata bianca, redirect inattesi, e history "intrappolata".

### Ciclo per ogni pagina/stato (ripetilo ad ogni passo della matrice)

1. `browser_navigate` all'URL (o interagisci per arrivare allo stato), poi `browser_wait_for`
   il contenuto chiave così lo screenshot non cattura uno skeleton di caricamento.
2. `browser_take_screenshot` con `fullPage: true`, salvato in `screens/`.
3. **Analizza lo screenshot** (sezione sotto) e annota i findings.
4. `browser_console_messages` → ogni errore JS è un finding 🔴.
5. `browser_network_requests` → ogni chiamata API fallita (4xx/5xx non attesa) è 🔴.
6. Esegui le interazioni previste dal flusso **una alla volta, in modo incrementale**
   (mai input + submit nello stesso colpo — vedi principio 5). Per ogni form/azione segui
   questo sotto-ciclo:
   1. **Digita/seleziona un solo valore** (`browser_type`, `browser_select_option`, ecc.).
      NON cliccare ancora Salva/Conferma.
   2. **Verifica lo stato intermedio**: `browser_evaluate` per leggere via JS il valore del
      campo, eventuali messaggi di errore di validazione (`.error`, `aria-invalid`,
      `[role=alert]`, testo helper), e lo stato `disabled` del bottone di submit; poi
      `browser_snapshot` + screenshot. Annota come reagisce la validazione (input invalido →
      errore mostrato? bottone disabilitato? bordo rosso? messaggio corretto?).
   3. **Solo ora** esegui il submit (`browser_click` su Salva/Conferma).
   4. **Cattura il feedback post-submit**: il toast spesso è effimero — usa
      `browser_wait_for` sul testo del toast e scatta lo screenshot **mentre è visibile**,
      poi un secondo screenshot dopo che è sparito per verificare la transizione di uscita.
      Verifica via JS che lo stato sia stato persistito (valore aggiornato, modale chiuso).
   Copri esplicitamente i **casi di validazione**: valore vuoto, fuori range, formato
   sbagliato — ognuno è uno step a sé con la sua verifica. Lo stesso pattern vale per
   drag del carousel, apertura/chiusura modali e ogni interazione con feedback animato.
7. **Robustezza dell'interazione.** Dopo le azioni che modificano dati, verifica due cose:
   - **Persistenza al reload**: ricarica la pagina (`browser_navigate` allo stesso URL o
     reload) e controlla via JS/screenshot che il valore sia davvero persistito lato API,
     non solo aggiornato in modo ottimistico nella UI (round-trip reale).
   - **Race condition / doppio submit**: clicca il bottone di submit due volte in rapida
     successione (o spamma un'azione) e osserva se compaiono toast duplicati, chiamate API
     doppie (`browser_network_requests`), stati incoerenti o crash. Il bottone dovrebbe
     disabilitarsi/debounce durante l'invio.

## Analisi visiva (il cuore della skill)

Per ogni screenshot full-page, ispeziona davvero l'immagine e cerca:

- **Allineamento/centratura**: elementi decentrati rispetto al loro contenitore, colonne
  disallineate, label scollegate dal proprio campo, icone non centrate nei bottoni.
- **Overflow**: scroll orizzontale, contenuto che esce dai bordi del contenitore o dello
  schermo, card più larghe del viewport mobile.
- **Sovrapposizioni**: testo/elementi che si accavallano, toast che coprono UI critica,
  modali che escono dallo schermo o non stanno nei 390px su mobile.
- **Troncamenti**: testo tagliato con/ senza ellissi, label che vanno a capo male, numeri
  troncati.
- **Spaziatura/ritmo**: padding incoerenti, gap irregolari, elementi appiccicati ai bordi,
  spazi vuoti innaturali.
- **Deformazioni**: bottoni/chip/avatar schiacciati o stirati, immagini con aspect-ratio
  rotto, icone sproporzionate.
- **Stati rotti**: empty state mancante o brutto, skeleton che non sparisce, layout che
  collassa quando i dati sono pochi o tanti.

Poi incrocia con `references/design-checklist.md` (Gold Leaf, Two Inks, Semantic Triad,
Inscription, Tabular Numerics, No Gradient Text, Warm-Shadow, Halo-as-Signal).

### Analisi delle animazioni e transizioni

Le animazioni si valutano solo se le **catturi durante l'esecuzione**, non a regime — per
questo l'interazione incrementale (principio 5) è indispensabile: agisci, poi scatta subito
mentre la transizione è in corso. Per ogni interazione con feedback animato (toast, modali
con framer-motion, transizioni del carousel, slot incantesimi, barre HP/XP, chip di stato):

- **Cattura il movimento**: dopo aver innescato l'azione, scatta uno screenshot *durante* la
  transizione (subito dopo il click) e uno a transizione conclusa. Per i toast effimeri,
  cattura sia l'entrata (toast visibile) sia l'uscita.
- **Cerca bug di rendering evidenti**: flash/flicker iniziale, elemento che "salta" alla
  posizione finale senza interpolare (animazione no-op — sintomo classico del `domAnimation`
  al posto di `domMax`, vedi `CLAUDE.md`/`main.tsx`), scatti o stutter, layout shift mentre
  l'elemento entra/esce, doppio render, elemento che resta a metà transizione, z-index che
  fa apparire l'animazione dietro altri elementi, transizione che parte da uno stato visivo
  sbagliato.
- **Toast**: appare e scompare con la sua animazione? non copre UI critica mentre è visibile?
  l'uscita è fluida o sparisce di colpo? si accavallano se ne lanci più d'uno?
- **Modali/carousel**: l'apertura/chiusura e lo snap del drag sono fluidi e finiscono nello
  stato corretto, senza overshoot rotto o rimbalzi anomali?
- **Verifica tecnica**: usa `browser_evaluate` per leggere classi/`style`/`transform` durante
  la transizione e capire se l'animazione è davvero applicata; controlla `browser_console_messages`
  per warning di framer-motion. Un'animazione che non parte affatto è un finding 🟠 (o 🔴 se
  rompe l'usabilità).

### Comportamento a schermo molto piccolo (adattività al limite)

Restringendo progressivamente la viewport (vedi la passata di stress nel Passo 4), osserva
come reagiscono i componenti e **identifica il breakpoint di rottura** — la larghezza esatta
oltre la quale il layout cede. Riduci a step (`browser_resize` a 360 → 320 → 300 → 280px) e
fra uno step e l'altro scatta screenshot full-page + `browser_snapshot`. Cerca:

- **Overflow orizzontale**: comparsa di scroll-x, card/righe più larghe del viewport, numeri
  o chip che spingono fuori il contenitore (usa `browser_evaluate` per leggere
  `document.documentElement.scrollWidth > clientWidth`).
- **Reflow vs rottura**: il contenuto va a capo in modo ordinato (grid che collassa a 1
  colonna, label sopra al campo) oppure si accavalla/tronca/sovrappone? La paper-doll
  dell'equipaggiamento e le statistiche affiancate sono i punti più fragili.
- **Touch target che si rimpiccioliscono** sotto i 44×44 quando lo spazio si riduce.
- **Testo che diventa illeggibile** o numeri tabellari che perdono l'allineamento.
- **Modali**: continuano a starci dentro la larghezza, o i bottoni di azione escono/si
  impilano male?

**Classifica sempre il giudizio**, perché è la domanda dell'utente:

- Rottura a larghezze **realistiche per il pubblico** (≥320px, device Telegram comuni) →
  finding reale 🟠: il componente va modificato (proponi la fix: grid responsive, `min-width`
  da rimuovere, `flex-wrap`, `clamp()` sul font, ecc.).
- Degrado solo a larghezze **estreme/irrealistiche** (<300px) → 🟡 informativo: è un
  comportamento al limite, non bloccante; segnala il breakpoint ma chiarisci che non
  richiede intervento prioritario.

**Scope accessibilità** (da `CLAUDE.md`): SEGNALA contrasto colore, touch target <44×44,
testo troppo piccolo da leggere a distanza di braccio, focus da tastiera non visibile
(desktop), chip icon-only senza affordance di scoperta. NON segnalare problemi
screen-reader/ARIA/gerarchia heading/alt/focus-order.

## Passo 5 — Genera il report

Scrivi `report.md` nella radice della cartella di sessione creata al Passo 3
(`reports/<YYYY-MM-DD_HH-MM>-<viewport>/report.md`). **Solo segnalazioni, nessun fix.**
Severità: 🔴 bug funzionale/crash · 🟠 regressione visiva o layout rotto · 🟡 nit
UX/mobile/contrast (opzionale) · 🟢 ok.

Usa ESATTAMENTE questa struttura:

```markdown
# Audit FE — <scope> — <viewport(s)>

> Data: <YYYY-MM-DD HH:MM> · Tool: Playwright MCP · Base URL: http://localhost:5173
> Viewport: Desktop 1440×900 / Mobile 390×844 · Char fixture: <id> (creato via UI)
> Severità: 🔴 bug · 🟠 regressione/layout · 🟡 nit · 🟢 ok

## Conteggi
| Severità | Desktop | Mobile |
|----------|---------|--------|
| 🔴 | n | n |
| 🟠 | n | n |
| 🟡 | n | n |
| 🟢 | n | n |

## Matrice
| ID | Area | Test | Desktop | Mobile | Note / evidenza |
|----|------|------|---------|--------|-----------------|
| HP1 | hp | Applica danno | 🟢 | 🔴 — toast fuori schermo | screens/hp-damage-mobile.png |

## Findings
### #1 — <titolo sintetico> [🔴]
- **Area / route:** hp · `#/char/:id/hp`
- **Viewport:** Mobile
- **Sintomo:** <cosa si vede di sbagliato>
- **Passi per riprodurre:** <1. … 2. …>
- **File sospetto (best guess):** `webapp/src/pages/hp/...`
- **Fix proposto:** <indicazione azionabile>
- **Screenshot:** screens/hp-damage-mobile.png

## Findings visivi / design
<elementi decentrati, disallineati, overflow, violazioni delle regole nominate di
DESIGN.md — ognuno con il PNG full-page di riferimento. Stessa scheda dei Findings.>
```

Regole del report:
- Per viewport singola, ometti la colonna inutile nella matrice (o segna `—`).
- Una scheda per ogni cella non-🟢. Ogni scheda deve essere **autosufficiente**: chi la
  risolve non deve rileggere lo screenshot per capire il problema.
- Tieni i 🟡 separati/elencabili: utili ma non bloccanti.

## Chiusura

A fine run, riepiloga all'utente: percorso del report, conteggi per viewport, i 3 findings
più gravi, e che gli screenshot full-page sono in `screens/`. Ricorda che è un report di
sole segnalazioni — i fix vanno affidati ad altri agenti (es. via `impeccable` per i visivi).
