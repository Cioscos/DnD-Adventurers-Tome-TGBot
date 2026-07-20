# Perf harness — trace CDP della Mini App

Misura le performance reali della webapp: sulla **WebView di Telegram Android**
(modalità `device`) o su **Chrome locale con CPU throttling** (modalità `local`).
Ogni run produce trace Chrome per scenario + `report.md` con long task, FPS,
paint full-screen e bucket main-thread. Cartella `results/` gitignorata.

## Setup device (una tantum)

1. **Telegram**: Impostazioni → tap ripetuti sul numero di versione finché non
   si apre il menu debug → attiva **Enable WebView Debug**. Riavvia Telegram.
2. **Telefono**: Opzioni sviluppatore → attiva **Debug wireless** (Android 11+;
   telefono e PC sulla stessa Wi-Fi).
3. **WSL**: `sudo apt install adb`
4. **Pairing (solo la prima volta)**: sul telefono "Accoppia dispositivo con
   codice" → `adb pair <ip>:<porta-pairing>` col codice mostrato.
5. **Ogni sessione**: `adb connect <ip>:<porta-debug>` (porta della schermata
   Debug wireless, diversa da quella di pairing). Verifica con `adb devices`.

Fallback USB se la Wi-Fi è instabile: usbipd-win (`winget install usbipd`,
`usbipd bind --busid <X>`, `usbipd attach --wsl --busid <X>`, e `adb kill-server`
sul lato Windows).

## Uso

```bash
# Baseline completa sul device (Mini App già aperta in Telegram):
node scripts/perf/run.mjs --mode device --label baseline

# Solo alcuni scenari:
node scripts/perf/run.mjs --mode device --label baseline --scenario overlay-modal --scenario swiper-hub

# Modalità locale (throttling 6x, viewport 375×667) contro il dev server:
node scripts/perf/run.mjs --mode local --url http://localhost:5173 --label local-check

# Confronto fra due run:
node scripts/perf/compare.mjs results/baseline-<ts> results/after-<ts>
```

Gli scenari (tranne `smoke`) sono manuali: il CLI dice quale gesto eseguire e
delimita la trace con INVIO. Elenco scenari in `scenarios.mjs`.

## Come leggere il report

- **Long task**: task main-thread >50 ms — durante un'animazione significano
  frame persi certi. `causa` è l'evento interno più lungo.
- **FPS medi / Dropped est.**: stima da `DrawFrame` sulla durata della trace
  (approssimazione: non usa PipelineReporter).
- **Paint full-screen**: repaint con clip ≥90% del viewport — durante
  un'animazione di overlay è la firma del flicker da `backdrop-filter`.
- **Bucket**: somma per categoria senza sottrarre l'annidamento (uno script che
  contiene un Layout conta in entrambi).

## Troubleshooting

- `Nessuna WebView in debug trovata` → Mini App chiusa, WebView Debug spento, o
  adb non connesso.
- Più socket WebView → l'harness prende l'ultimo; chiudi le altre app con
  WebView o passa `--port` dopo un forward manuale del socket giusto.
- `connectOverCDP` rifiutato → il forward punta a una WebView morta: riapri la
  Mini App e rilancia.
