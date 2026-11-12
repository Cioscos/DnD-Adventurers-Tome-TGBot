# Esecuzione delegata: un subagente per test

Il coordinatore spende token solo per piano, fixture, dispatch e report. Ogni test del piano lo esegue un
subagente nuovo, modello `sonnet`, che non eredita la conversazione e riporta l'esito in una riga del ledger.

## Regole

- **Uno per test.** Ogni ID del `piano-test.md` (A1, B3, E7…) = un subagente nuovo. Mai riusare un
  subagente per il test successivo: il contesto accumulato è proprio il costo da evitare.
- **Modello esplicito:** `model: "sonnet"` in ogni dispatch (subagente `general-purpose`).
- **In sequenza, mai in parallelo.** Tutti i subagenti condividono lo stesso browser del server Playwright
  MCP: due test insieme si rubano le schede e lo stato del DB. Un test alla volta, nell'ordine del piano.
- **Il coordinatore non legge snapshot, screenshot o log del browser.** Legge solo la riga del ledger e,
  se l'esito non è 🟢, la scheda del finding. Il subagente risponde al coordinatore con una sola riga.
- **Stato condiviso solo via file.** Id di personaggi, campagne e serate stanno in `fixture.md`. Un test
  che crea qualcosa che servirà dopo (un personaggio, una serata) lo aggiunge a `fixture.md`.
- **Il piano si adatta, non si forza.** Se un test scopre un vincolo dell'app che rende impossibile un
  test successivo così com'è scritto, il coordinatore aggiunge al brief di quel test un paragrafo
  «Adattamento del coordinatore» invece di riscrivere il piano.
- **Dipendenze:** se un test dipende da uno precedente non 🟢 o `bloccato`, il coordinatore lo marca
  `bloccato` nel ledger senza dispatch, citando il test da cui dipende.

## Brief per test (`briefs/<ID>.md`)

Il coordinatore lo genera copiando dal piano, senza riassumere:

```markdown
# Test <ID> — <titolo>
Azione: <dal piano>
Atteso: <dal piano, con fonte: manuale p. X / file:riga>
Personaggi e utenti: <da fixture.md>
Dipende da: <ID precedenti o nessuno>
```

## Prompt di dispatch (testo fisso, cambiano solo i percorsi)

```
Sei un tester. Esegui UN solo test funzionale della Mini App D&D con gli strumenti mcp__playwright__*.
1. Leggi, in quest'ordine: <dir>/briefs/<ID>.md (il test), <dir>/fixture.md (ambiente, utenti, id),
   e la sezione "Passo 4" di .claude/skills/fullstack-functional-audit/SKILL.md (il metodo).
   Regole del manuale: docs/superpowers/rules/{2014,2024}/ (cerca con grep, non leggere tutto).
2. Prima del browser, leggi il codice FE/API/BE coinvolto quanto basta per l'oracolo (file:riga).
3. Le AZIONI del test si fanno dalla UI, come un giocatore; l'API diretta solo per leggere lo stato
   (o, se la UI non lo permette, dichiarandolo nel ledger).
   Apri una scheda tua (browser_tabs new) con l'URL dell'utente indicato; chiudila alla fine.
   Preferisci browser_find e browser_evaluate a snapshot interi; salva screenshot solo come evidenza
   di un esito non 🟢, in <dir>/screens/<ID>-*.png.
4. Non modificare codice, non toccare la porta 8000 né data/dnd_bot.db, niente uv. Non chiudere le
   serate della fixture. Se il test cambia lo stato di un personaggio (PF, slot, risorse, condizioni),
   riportalo com'era alla fine, salvo che il brief dica altro.
5. Appendi UNA riga a <dir>/ledger-test.md:
   | <ID> | <area> | <atteso> | <reale> | 🟢/🟡/🟠/🔴/bloccato | <evidenza> |
   Se l'esito non è 🟢, appendi anche la scheda del finding (formato "Findings" del Passo 7 della
   skill) in <dir>/findings/<ID>.md.
   Se hai creato entità che servono ai test successivi, aggiungile a <dir>/fixture.md.
6. Rispondi con una sola riga: "<ID> <esito> — <motivo in max 15 parole>".
```

## Ledger (`ledger-test.md`)

```markdown
# Ledger test — <run>
| ID | Area | Atteso | Reale | Esito | Evidenza |
|----|------|--------|-------|-------|----------|
```

Il run è finito quando ogni ID del piano ha una riga. Il coordinatore poi scrive `report.md` dal ledger
(Passo 7) e aggiorna `coverage.md` con le route/endpoint toccati citati nelle righe.
