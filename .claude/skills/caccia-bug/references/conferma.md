# Prompt del confermatore

---

Qualcuno sostiene che la D&D Mini App (`{repo}`) abbia questo difetto. Il tuo compito è provare a smentirlo.

- Fonte dell'atteso: `{fonte}`
- Passi: `{passi}`
- Atteso dichiarato: `{atteso}`. Osservato: `{osservato}`

1. Rileggi tu la fonte (`tests/caccia/decisioni.md`, `docs/superpowers/rules/<edizione>/…`, `CLAUDE.md`): l'atteso segue davvero
   da lì, per quell'edizione, e nessuna eccezione o decisione dell'utente lo cambia?
2. Ripeti i passi con uno script tuo, usa e getta, in `{cartella_temporanea}`: API vera tramite ASGI e database temporaneo,
   come in `tests/integration/conftest.py`; per la UI, Vitest o la lettura del componente con la richiesta reale. Non
   aprire i file `tests/caccia/test_cb_*` né `webapp/tests/**/caccia/`.
3. Guarda il codice solo per capire se il risultato dipende da una preparazione irrealistica (dato che l'app non permette,
   passo saltato, dado non fissato).

Non modificare nulla nel repository, non usare la porta 8000 né `data/dnd_bot.db`.

Rispondi con: `confermato | scartato | domanda`, cosa hai eseguito, atteso e osservato da te, e il punto della fonte (edizione,
carta, pagina). `domanda` solo se la fonte è ambigua, con le letture possibili. Se non riesci a riprodurlo, è `scartato`.
Aggiungi, se lo vedi, il punto del codice da cui nasce: serve a unire i duplicati.
