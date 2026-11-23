# Prompt dello scompositore

Zone `regola:` → blocchi di al massimo 25 carte per agente. Zone `flusso:` → un agente per al massimo 2 pagine. Le fonti da
assegnare le elenca `inventario fonti <zona>`. Ogni agente scrive un proprio file `<zona>--<parte>.json` (zona con `-` al posto
di `:` e `/`) con una lettera propria per gli id. Alla fine rilancia `fonti`: ciò che manca si riassegna.

Parte comune, poi quella del tipo di zona.

---

Per la zona `{zona}` della D&D Mini App (`{repo}`) scrivi che cosa deve essere vero. Altri lo proveranno caso per caso, in ordine
di rischio e in più giri: **non c'è un tetto**, un caso scritto e non provato oggi resta in coda, uno non scritto è perso.

- Fonti assegnate a te, tutte da trattare: `{fonti}`
- File da scrivere, e nessun altro: `{file}`. Id da `{lettera}01` in poi; se il file esiste, completalo senza cambiare gli id.

Ogni affermazione ha i casi con valore di partenza ed esito atteso espliciti:
- formula: un valore comune, il minimo, il massimo, zero, il valore che cambia il segno, subito prima e subito dopo una soglia
  o un arrotondamento;
- minimo o massimo scritto: il caso oltre; non scritto: il caso che lo dimostra;
- cambiamento di stato: tutto ciò che deve essere vero dopo, per ogni modo di arrivarci;
- un valore che dipende da un altro: cosa succede **quando l'altro cambia**, in più e in meno, con risorse piene e in parte spese;
- risorsa: ultima rimasta, esaurita, recupero, restituzione se l'azione viene annullata, anche quando la paga un altro;
- la stessa fonte in un'altra edizione, se differisce.

`rischio`: 1 numero o stato sbagliato che un giocatore incontra in una sessione normale, dati persi o visibili a chi non deve; 2 caso
meno comune; 3 raro o minore. `voce` fra: contratto, normale, limiti, ripetizione, annullamento, persistenza, permessi,
edizioni, interazione, regola. `copre`: le fonti trattate, con la stringa esatta ricevuta. Nessun testo copiato dai manuali.

```json
{"{lettera}01": {"voce": "limiti", "testo": "Riassunto breve con parole tue", "fonte": "2014 · Carta · pag. 97", "rischio": 1,
          "copre": ["carta:2014/classes/x.md#Titolo esatto"], "casi": {"a": "CAR 16: 4 usi", "b": "CAR 8: 0 usi"}}}
```

Alla fine esegui `uv run python -m tests.caccia.inventario verifica --contiene "{zona}"` (deve dire «Nessun errore») e `fonti "{zona}"`: nessuna
delle tue fonti deve comparire. Ritorna solo: numero di affermazioni e casi, e i punti ambigui come domande.

## Zona `regola:`

Non aprire codice né test: l'atteso nasce dalle carte (e da `tests/caccia/decisioni.md`, che prevale). Una carta alla volta, frase per
frase e cella per cella delle tabelle: ogni frase che cambia un numero, una durata, una condizione, un'eccezione, un ordine o
un bersaglio è un'affermazione. Poi le interazioni con le altre carte assegnate. Una carta senza effetti che un'app possa
mostrare o calcolare (solo narrativa) ha un'affermazione con rischio 3 e il caso `a` messo in `esenti`
(`"esenti": {"a": "motivo"}`).

## Zona `flusso:`

Qui non si ripetono le regole delle carte (le provano le zone `regola:`): si scrive ciò che deve essere vero dell'**app**. Apri i
componenti delle pagine assegnate e quelli che importano solo per elencare che cosa la pagina mostra e quali azioni offre; apri i
nomi degli endpoint per le azioni. L'atteso non viene dal codice ma da `tests/caccia/decisioni.md`, `CLAUDE.md` e da ciò che un
giocatore o un master darebbe per scontato. Per ogni dato mostrato e ogni azione, un'affermazione:
- dato: formato con valori negativi, zero, massimi, subito prima e dopo un limite, assenti, molto lunghi; coerenza con lo
  stesso dato altrove e con ciò che dice il server; arrotondamenti che non anticipano un traguardo non raggiunto;
- azione: doppio tocco, richiesta ripetuta, annullamento di ogni effetto (anche su altre schede), chiudere a metà, ricaricare,
  errore di rete o rifiuto del server, dati non validi, campi che non spettano a chi scrive o che deve decidere il server;
- utenti: chi vede e chi può, per proprietario, altro giocatore, master, estraneo; che cosa vedono gli altri subito dopo;
- combinazioni: due effetti insieme, due bersagli, lo stesso effetto due volte, prima e dopo un riposo o la fine di una serata.
