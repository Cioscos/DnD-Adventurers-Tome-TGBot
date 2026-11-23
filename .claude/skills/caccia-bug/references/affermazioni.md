# Prompt dello scompositore

---

Per una zona della D&D Mini App (`{repo}`) scrivi che cosa deve essere vero, **prima** che qualcuno guardi il codice. Altri lo
proveranno caso per caso.

- Zona: `{zona}` (pagine: `{route}`; endpoint: `{endpoint}`). Carte: `{carte}`.
- File da scrivere, e nessun altro: `{affermazioni}`. Se esiste, completalo senza cambiare gli id già usati.

**Fonti.** `tests/caccia/decisioni.md`, le carte in `docs/superpowers/rules/2014/` e `2024/` (zona di flusso: leggi i capitoli di `general.md`
e le carte che trattano quel flusso, in entrambe le edizioni), `CLAUDE.md`, gli invarianti che un giocatore o un master darebbe
per scontati. Non aprire codice né test: l'atteso deve nascere dalle fonti. Puoi vedere solo i nomi degli endpoint.

**Come.** Leggi ogni carta frase per frase: ogni frase che cambia un numero, una durata, una condizione, un'eccezione o un
ordine è un'affermazione. Vale anche ciò che avviene **dopo**: che cosa si azzera, finisce o torna com'era. Per ogni
affermazione i casi, con valore ed esito atteso espliciti:
- formula: un valore comune, il minimo, il massimo, e il valore che cambia il segno o scatta l'arrotondamento (un
  modificatore: +3, 0 e −1; un livello: subito prima e subito dopo la soglia);
- «minimo 1», «almeno», «fino a»: il caso sotto la soglia; e se la carta **non** scrive un minimo, il caso che lo dimostra;
- transizione: lo stato completo dopo (ogni contatore e condizione), da tutti i modi per arrivarci;
- edizioni diverse: un caso per ciascuna;
- risorsa: ultima rimasta, esaurita, recupero;
- azione nell'app: doppio tocco o richiesta ripetuta, annullamento, permessi di un altro utente, rilettura, dato inviato non
  valido, effetto su ciò che si mostra altrove (ordini, totali, elenchi), dato libero usato per altro (percorsi, nomi).

Priorità alle combinazioni e a ciò che un giocatore incontra. Tetto: 50 casi; se non bastano, tieni i più rischiosi e riporta
le frasi rimaste fuori.

```json
{"A01": {"voce": "limiti", "testo": "Riassunto breve con parole tue", "fonte": "2014 · Carta · pag. 97",
         "casi": {"a": "CAR 16: 4 usi", "b": "CAR 8: 0 usi"}}}
```

`voce` fra: contratto, normale, limiti, ripetizione, annullamento, persistenza, permessi, edizioni, interazione, regola. Id `A01`, `A02`…; casi
`a`, `b`… Nessun testo copiato dai manuali.

Alla fine: numero di affermazioni e casi, frasi rimaste fuori, punti ambigui della fonte (come domande).
