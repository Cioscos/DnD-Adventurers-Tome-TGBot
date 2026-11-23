# Prompt del cacciatore

Riempi i segnaposto e invia il testo sotto la riga.

---

Cerchi bug in una zona della D&D Mini App, nella cartella `{repo}`. Non correggi: scrivi controlli eseguibili.

- Zona: `{zona}`. File: `{file}`. Carte del manuale: `{carte}`.
- Pagine e carte ancora senza controlli, da cui partire: `{fonti}`.
- Id che puoi usare: `{id}`. File di test che puoi scrivere, e nessun altro: `{file_test}`.
- Già noti, da non segnalare di nuovo: `{noti}`.

**Da dove viene l'atteso.** In ordine: decisione dell'utente (`tests/caccia/decisioni.md`), carta del manuale dell'edizione
giusta (`docs/superpowers/rules/`), comportamento dichiarato in `CLAUDE.md` o nel changelog, invariante ovvio (una richiesta
ripetuta non spende due volte). Non ricavarlo dal codice che stai provando: un test che ricopia il codice è verde anche
quando il codice è sbagliato. Il codice ti serve per sapere come chiamare l'app e dove rischia. Fonte ambigua → niente
controllo, riportala come domanda con i passi. Regola non implementata affatto → `mancante`, niente controllo.

**Metodo.** Di ogni formula prova anche minimo, massimo, il valore che cambia segno e quelli attorno a una soglia; di ogni
cambiamento di stato rileggi tutto ciò che deve cambiare, non solo lo status. Un comportamento che ti sorprende è un rosso se una
fonte o un invariante lo contraddice, anche se l'app potrebbe averlo fatto apposta: a decidere è la conferma. `DOMANDE` è per
ciò che nessuna fonte tratta. Per ciascuna delle dieci voci scrivi l'atteso con la fonte, poi il controllo, poi eseguilo. Parti dalle
combinazioni (due effetti insieme, due classi, due utenti, prima e dopo un riposo): lì i test esistenti coprono meno.

| Voce | Che cosa provare |
|---|---|
| contratto | metodo e percorso che il frontend chiama esistono; i campi inviati sono accettati; quelli letti ci sono nella risposta, anche null o liste vuote |
| normale | il percorso comune dall'inizio alla fine, con i numeri giusti |
| limiti | zero, massimo, negativo, livello 1 e 20, arrotondamenti, risorse esaurite, testo lungo, accenti |
| ripetizione | doppio invio, stessa richiesta due volte, due richieste insieme: nessun effetto o spesa doppia |
| annullamento | annullare, eliminare, rimuovere, disequipaggiare: tutto torna com'era, niente effetti orfani |
| persistenza | rileggere dopo la modifica; stato ancora giusto dopo riposo, fine combattimento, export e import |
| permessi | un altro utente, un giocatore al posto del master, dati altrui nelle risposte |
| edizioni | stesso caso 2014 e 2024: ciascuna segue la propria carta |
| interazione | un cambiamento qui si riflette nelle altre zone, e viceversa |
| regola | una carta alla volta, numeri e condizioni |

**Come si scrive.** pytest su API vera (`client`, `come_utente(id)`, `dadi(3, 5)` da `tests/caccia/conftest.py`; i dadi vanno
fissati quando contano, l'ora si sostituisce nel modulo che la legge). Vitest per la logica o i componenti del frontend
(`renderWithProviders`). Playwright solo per ciò che si vede unicamente nella UI (ricaricamento, doppio tocco, cache fra
pagine); fixture in `webapp/tests/e2e-playwright/caccia/fixtures.ts`: scrivilo, non eseguirlo.

```python
@pytest.mark.caccia(id="CB-012", fonte="2024 · Monaco · pag. 101", zona="{zona}", voce="limiti",
                    copre=["POST /characters/{char_id}/rest", "carta:2024/classes/monk.md#Titolo esatto della carta"])
async def test_…(client): ...
```
```ts
// caccia: {"id": "CB-013", "fonte": "…", "zona": "{zona}", "voce": "normale", "copre": ["route:/char/:id/hp"]}
test('…', …)
```

Un comportamento per controllo. Nei metadati solo letterali scritti per esteso (niente costanti, f-string o concatenazioni), su una riga in TypeScript, subito sopra `test(` o `it(`. Niente
`skip`, `only` o `xfail`. Nessun testo copiato dai manuali. Esegui `uv run pytest <tuo file> -q` e
`npx vitest run <tuo file>` da `webapp/`, e alla fine
`uv run python -m tests.caccia.inventario verifica --contiene <tuo file>`: deve dire «Nessun errore». Per Playwright usa solo
ruoli e testi letti nel componente o in `locales/it.json`. Un rosso vale solo se fallisce l'asserzione sull'atteso: un errore di preparazione
è un difetto del tuo test. Prima di riportarlo, ripeti i passi da capo.

Non modificare codice dell'app, non fare commit, non usare la porta 8000 né `data/dnd_bot.db`. La ricerca di altri test,
commit o report per indovinare i bug non serve: prova l'app.

**Ritorno, in questo formato:**

```
VOCI: contratto=fatta(CB-…) … | voce=non_applicabile(motivo)
ROSSI: id | fonte (edizione, carta, pagina) | passi numerati riproducibili | atteso | osservato | gravità 🔴/🟠/🟡
VERDI: id e comportamento, una riga ciascuno
PLAYWRIGHT DA ESEGUIRE: file
DOMANDE: comportamento osservato | passi | perché ti pare strano | fonte più vicina
MANCANTE: …
```

Gravità: 🔴 dati persi o esposti, crash, risultato sbagliato in un caso comune; 🟠 risultato sbagliato in un caso raro; 🟡
minore. Se una voce è applicabile ma non l'hai provata, scrivi `non_fatta`: la zona resterà in coda.
