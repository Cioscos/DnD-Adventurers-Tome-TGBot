# Modello del report

```markdown
# Caccia ai bug — <data ora>

Branch: … · Commit esaminato: … · Manuali: presenti | assenti (regole non cacciate)
Regressione: <n> verdi, <n> xfail, <n> rossi · Zone: <guardate>/<totali>, restano <per motivo>

## Bug confermati
### CB-012 — <titolo> 🔴|🟠|🟡
- Zona, voce, endpoint o pagina:
- Fonte: edizione · carta · pagina (o decisione)
- Passi:
- Atteso / reale:
- Riprodurre: `uv run pytest tests/caccia/test_cb_x.py::test_… --runxfail`
- Causa probabile: file:riga
- Conferma: chi, come
- Stato: aperto | corretto (<commit>)

## Regressioni e controlli cambiati
## Scartati (con il motivo)
## Domande e decisioni
## Zone guardate
| Zona | Motivo | Voci fatte | Non applicabili (perché) | Non fatte |
## Zone rimaste
## Mancante (regole non implementate, non bug)
```

«Coperto» significa che esiste un controllo eseguito. Una voce letta nel codice ma non provata è «non fatta».
