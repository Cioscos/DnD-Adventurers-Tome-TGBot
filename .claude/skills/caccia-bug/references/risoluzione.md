# Risoluzione

Solo i bug scelti dall'utente. Raggruppali per causa e procedi una causa alla volta: con più cause aperte non si distingue
quale correzione ha reso verde un controllo.

a. **Causa.** Trova dove nasce, non dove si vede. Elenca tutti i chiamanti del codice da cambiare, l'altra edizione e il
   frontend che legge quel dato.
b. **Rosso.** Togli `xfail` (o `test.fails`, `test.fail`) ed esegui: deve fallire per il motivo scritto nel report. Se fallisce
   per altro, il controllo va corretto prima.
c. **Correzione minima alla radice.** Se tocca lo schema del database, i dati già salvati o la UX, chiedi prima all'utente. Non
   cambiare il controllo per farlo passare.
d. **Verde.** Il controllo, poi i test dei file toccati. Un test esistente che diventa rosso perché asseriva il bug si aggiorna
   solo citando la fonte; se due fonti si contraddicono, chiedi.
e. **Revisione.** Un subagente che non ha scritto il fix riceve diff, fonte e controllo, e risponde a tre domande: il
   comportamento ora segue la fonte? che cosa può essersi rotto? lo stesso errore c'è altrove? Le conferme fuori dalla
   causa tornano al passo 5 della skill come bug nuovi, non si correggono di passaggio.
f. **Commit** per causa: `fix: <cosa> (CB-012)`, con la fonte nel corpo e il co-autore richiesto dalla sessione.

Dopo due tentativi falliti annulla le sole modifiche del tentativo, rimetti `xfail`, e riferisci che cosa hai capito. Non
ripristinare file con modifiche di altri.
