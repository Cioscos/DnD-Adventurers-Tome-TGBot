# Product

## Register

product

## Users

Giocatori di D&D 5e al tavolo, dal vivo, con il telefono in mano (Telegram Mini App, viewport di riferimento 375×667). Consultano la scheda tra un turno e l'altro, spesso in penombra e a braccio teso; il tempo di attenzione disponibile è di pochi secondi e l'interfaccia compete con la conversazione al tavolo, non con altre app. Il GM è un utente secondario (sessioni multiplayer: incontri, turni, consegna oggetti), servito dalla stessa app senza una modalità dedicata. Pubblico vedente: l'accessibilità screen-reader è fuori scope per scelta esplicita (vedi CLAUDE.md).

## Product Purpose

Gestione completa della scheda personaggio D&D 5e durante il gioco dal vivo: HP, CA, tiri, incantesimi, slot, inventario, condizioni, riposi, level-up, sessioni di gruppo. Sostituisce la scheda cartacea e il companion digitale generico. Il successo si misura in velocità di consultazione: trovare CA, HP o un bonus in 1-2 secondi, eseguire l'operazione di gioco (danno, tiro, slot) in meno di tre tocchi, fidarsi del numero mostrato perché le regole 5e sono applicate correttamente dal backend.

## Brand Personality

Epica, leggibile, calma (in quest'ordine di priorità, come da DESIGN.md: quando confliggono vince la leggibilità). Voce da manoscritto miniato: solenne ma mai pomposa, tematica ma al servizio del gioco. L'atmosfera da codex è un moltiplicatore d'immersione, non un costo accettabile sulla velocità.

## Anti-references

- **D&D Beyond** per l'estetica (neon rosso su nero puro, chrome da dashboard): resta però il riferimento di categoria per completezza dei flussi di scheda, da eguagliare in UX senza imitarne la pelle.
- **Roll20 / "WordPress 2014"**: chrome datato, righe-tabella, dropdown non trattati.
- **SaaS-cream**: card neutre + accento blu + rounded-2xl ovunque; non è un B2B tool.
- **Gacha mobile**: particelle, celebrazioni, monete finte, FOMO.
- **AI-slop default**: hero-metric card, gradient text, griglie di card identiche, glassmorphism riempitivo.

## Design Principles

1. **Il numero prima dell'ornamento.** Ogni schermata ha uno o due valori che il giocatore cerca (CA, HP, bonus): devono leggersi in 1,5 secondi a braccio teso. L'ornamento si concentra dove l'occhio atterra e sparisce dalle superfici di lettura.
2. **Meno tocchi del tavolo fisico.** Un'operazione di gioco (danno, tiro salvezza, spendere uno slot) deve costare meno gesti che farla con matita e dado: massimo tre tocchi, feedback immediato, undo o conferma dove si può perdere qualcosa.
3. **Vocabolario coerente, memoria muscolare.** Stessi pattern ovunque: conferma a destra, annulla a sinistra, stessi sheet, stessi chip, stesse soglie colore (emerald/gold/crimson). In sessione non si rilegge l'interfaccia, la si usa al buio.
4. **Pattern nativi Telegram.** L'app vive dentro Telegram: gesti, BackButton, haptics e fluidità devono comportarsi come il client che la ospita, non come un sito incorporato.
5. **Fiducia nei numeri.** Le regole 5e calcolate dal backend sono la fonte di verità; la UI non nasconde mai il breakdown (d20 + modificatori, componenti CA) perché la verificabilità è ciò che fa abbandonare la scheda cartacea.

## Accessibility & Inclusion

Scope deliberato (CLAUDE.md): niente requisiti screen-reader/ARIA/heading-hierarchy. In scope, come requisiti reali del tavolo: contrasto leggibile in penombra e in light mode "pergamena" (≥4.5:1 sul body), touch target ≥44×44 per azioni distruttive e ≥40px altrove, testo leggibile a distanza di braccio, focus visibile da tastiera su desktop, colore sempre accoppiato a icona+label per i daltonici, `prefers-reduced-motion` rispettato (segnale via colore+icona+copy).
