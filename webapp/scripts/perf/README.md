# Perf harness: misure automatiche della Mini App

L'harness pilota la Mini App da solo, sulla **WebView di Telegram Android**
(`device`, default) o su **Chrome locale con CPU rallentata** (`local`), e misura
i frame **solo mentre esegue i gesti**. Gli scenari sono di **sola lettura**:
aprono, chiudono, navigano e scorrono, ma non tirano dadi, non salvano e non
cambiano toggle. Girano sui tuoi dati reali senza modificarli.

File:
- `run.mjs`: CLI, connessione, misure, report e confronto.
- `scenarios.mjs`: i gesti.
- `run.test.mjs`: test delle parti pure, da lanciare con `node --test scripts/perf/run.test.mjs`.

I risultati vanno in `results/` (gitignorata).

## Setup device (una tantum, da Windows)

1. Installa adb: `winget install Google.PlatformTools`, poi riapri il terminale.
2. **Telegram**: Impostazioni → tap ripetuti sul numero di versione finché si
   apre il menu debug → **Enable WebView Debug**. Poi **chiudi e riapri**
   Telegram, togliendolo anche dalle app recenti.
3. **Telefono**: Opzioni sviluppatore → **Debug wireless** (telefono e PC sulla
   stessa Wi-Fi) → "Associa dispositivo con codice" →
   `adb pair <ip>:<porta-pairing> <codice>`.
   Se `pair` risponde `unknown host service`, un vecchio server adb di un altro
   programma è ancora attivo: chiudilo con `adb kill-server` e riprova.
4. Dopo il pairing il telefono si ricollega da solo (mDNS). Se non lo fa, usa
   `adb connect <ip>:<porta>` con la porta mostrata nella schermata Debug wireless.
   Verifica con `adb devices`.

Se adb vede più dispositivi, l'harness sceglie da solo quello con la WebView in
debug: non serve impostare `ANDROID_SERIAL`.

## Uso

Apri la Mini App **su un personaggio**, tieni il telefono sbloccato e la Mini App
in primo piano, poi:

```powershell
cd webapp
node scripts/perf/run.mjs --label baseline                         # tutti gli scenari
node scripts/perf/run.mjs --label check --scenario help-sheet-hub  # solo alcuni
node scripts/perf/run.mjs --compare results/<dirA> results/<dirB>  # confronto → <dirB>/comparison.md

# Locale (Chrome installato, headless, 375×667, CPU 6x) con dev server e API locali avviati:
node scripts/perf/run.mjs --mode local --url "http://localhost:5173/#/char/<id>" --label local
```

Gli id degli scenari sono in `scenarios.mjs`. Quando cambiano le etichette
it/en dei pulsanti usati (guida, PF, aggiungi oggetto), vanno aggiornati lì.

## Come leggere il report

- **Frame p50/p95/max**: intervallo fra due `requestAnimationFrame`
  consecutivi durante il gesto. A 120 Hz un frame pieno dura circa 8 ms, a 60 Hz
  circa 16 ms.
- **Scatti**: frame oltre 33 ms, cioè uno scatto visibile. È il numero da far scendere.
- **LoAF**: frame bloccati per più di 50 ms (API `long-animation-frame`). Per i 3
  peggiori il report mostra la quota stile+layout e gli **script responsabili**:
  `invoker` e `sourceURL`. In produzione il bundle è minificato e i nomi non si
  leggono, ma il file indica comunque la libreria o il chunk. `n/d` significa
  che la WebView non supporta l'API.
- **Trace**: `<scenario>.trace.json` si apre così com'è in Chrome DevTools →
  Performance → "Load profile", per il flame chart completo.

## Troubleshooting

- `Nessuna WebView in debug trovata`: la Mini App è chiusa, WebView Debug è
  spento (o Telegram non è stato riaperto), oppure adb non è connesso.
- `WebView trovata ma non risponde`: il telefono è bloccato o Telegram è in
  background (la WebView congelata non risponde al CDP). Sbloccalo e riporta la
  Mini App in primo piano.
- `ERRORE: …` su uno scenario: in genere un pulsante non trovato (etichetta
  cambiata) o nessun personaggio aperto. Gli altri scenari girano comunque.
