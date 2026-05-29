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

## Passo 3 — Prepara la cartella di report

Crea `reports/<YYYYMMDD-HHMM>-<viewport>/` dentro questa skill (per `both` usa il suffisso
`both`). Dentro, una sottocartella `screens/`. Tutti gli screenshot vanno lì con nomi
parlanti: `<area>-<step>-<viewport>.png` (es. `hp-damage-applied-mobile.png`).

## Passo 4 — Esegui la matrice di test

Apri `references/flows.md` e segui le aree comprese nello scope. Regole di esecuzione:

- Se viewport = `both`: esegui **l'intera matrice per `desktop`, poi di nuovo per `mobile`**.
  Fra i due giri fai `browser_resize` e ricarica la pagina.
- Imposta la viewport con `browser_resize` (desktop `1440×900`, mobile `390×844`) **prima**
  di iniziare ogni giro.
- **Fixture via UI**: se lo scope è "tutti i flussi", il primo passo è creare il personaggio
  di test **attraverso l'interfaccia** (flusso `character-create` in flows.md) — la creazione
  è essa stessa un test, e il char creato alimenta tutti i flussi successivi. Se lo scope è
  un singolo flusso, usa un char_id esistente passato dall'utente, oppure creane uno minimale
  via UI per avere su cosa lavorare.
- Gli URL usano HashRouter: `http://localhost:5173/#/<route>` (es. `#/char/12/hp`).

### Ciclo per ogni pagina/stato (ripetilo ad ogni passo della matrice)

1. `browser_navigate` all'URL (o interagisci per arrivare allo stato), poi `browser_wait_for`
   il contenuto chiave così lo screenshot non cattura uno skeleton di caricamento.
2. `browser_take_screenshot` con `fullPage: true`, salvato in `screens/`.
3. **Analizza lo screenshot** (sezione sotto) e annota i findings.
4. `browser_console_messages` → ogni errore JS è un finding 🔴.
5. `browser_network_requests` → ogni chiamata API fallita (4xx/5xx non attesa) è 🔴.
6. Esegui le interazioni previste dal flusso (click, type, fill, drag per il carousel,
   apri/chiudi modali) e ripeti screenshot+analisi sugli stati risultanti (es. dopo aver
   applicato danno, dopo aver lanciato un incantesimo, con un modale aperto).

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

**Scope accessibilità** (da `CLAUDE.md`): SEGNALA contrasto colore, touch target <44×44,
testo troppo piccolo da leggere a distanza di braccio, focus da tastiera non visibile
(desktop), chip icon-only senza affordance di scoperta. NON segnalare problemi
screen-reader/ARIA/gerarchia heading/alt/focus-order.

## Passo 5 — Genera il report

Scrivi `reports/<timestamp>-<viewport>/report.md`. **Solo segnalazioni, nessun fix.**
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
