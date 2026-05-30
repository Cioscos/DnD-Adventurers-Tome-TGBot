# Matrice di test FE — flussi per area

Una sezione per area. Per ognuna: route HashRouter, azioni da eseguire via Playwright MCP,
e cosa verificare (funzionale + visivo). Esegui solo le aree nello scope richiesto.
Per ogni passo applica il ciclo screenshot full-page + analisi visiva descritto in `SKILL.md`.

Nelle route, `:id` è l'id del personaggio fixture. Base: `http://localhost:5173/#`.

Termini → area (per il parsing dello scope): "punti ferita/HP/danno/cura/riposo" → `hp`;
"classe armatura/CA/AC" → `ac`; "abilità/skill check" → `skills`; "tiri salvezza" → `saves`;
"incantesimi/spell" → `spells`; "slot" → `slots`; "inventario/oggetti/equip/attacco" →
`inventory`; "monete/valuta" → `currency`; "caratteristiche/stat" → `stats`; "capacità/feature
di classe" → `abilities`; "classe/multiclasse" → `class`; "esperienza/XP/livello" → `xp`;
"identità/razza/background" → `identity`; "homebrew/regole custom" → `homebrew`; "condizioni" →
`conditions`; "dadi/dice" → `dice`; "note" → `notes`; "mappe" → `maps`; "cronologia/log" →
`history`; "impostazioni/settings" → `settings`; "sessione/GM/multiplayer" → `session`.

---

## character-list — Lista personaggi (`/`)

- Apri `/`. Verifica: lista delle schede personaggio (o empty state se DB vuoto), bottone di
  creazione visibile e raggiungibile.
- Visivo: card allineate in griglia/lista, niente overflow, gold solo su affordance primaria,
  empty state curato (non un vuoto sgraziato).

## character-create — Creazione personaggio via UI (wizard 2-step) ⭐ FIXTURE

> Questo flusso crea il personaggio fixture usato da tutti gli altri. Eseguilo per primo
> quando lo scope è "tutti i flussi".

- Dalla lista, avvia la creazione. **Step 1**: digita un nome (es. `FE-Audit-<viewport>`),
  procedi. **Step 2**: seleziona una classe (es. `wizard` per coprire la magia; oppure prova
  anche la classe custom con hit die personalizzato).
- Verifica: validazione (nome vuoto → errore, niente avanzamento), il char compare nella lista,
  redirect all'hub `/char/:id`. Annota l'`:id` creato.
- Visivo: stepper leggibile, griglia classi senza sovrapposizioni, label in Cinzel, input
  con underline che si scalda all'oro al focus (regola Inputs di DESIGN.md).

## character-main — Hub carousel (`/char/:id`)

Carousel a 3 schermate swipeable (`<CharacterSwiper>`, framer-motion `drag="x"`).

- **Screen 0 — HeroScreen**: nome, classe/razza, AC, HP, XP, stat, condizioni, capacità
  passive, riepilogo spell slot, anteprima progressione. Verifica numeri tabulari (mono,
  allineati) e hero numbers HP/AC con glow corretto (emerald ≥75%, gold 25–75%, crimson ≤25%).
- **Screen 1 — EquipmentScreen (PaperDoll vitruviano)**: 11 slot (head, neck, cloak, body,
  hands, ring1, ring2, feet, main_hand, off_hand, ammunition). Verifica silhouette centrata,
  slot allineati, placeholder leggibili.
- **Screen 2 — MenuScreen**: griglia di navigazione (Combat/Magic/Skills/Equipment/Character/Tools).
- Interazione: fai swipe (drag) tra le schermate (`browser_drag` su desktop / gesti su mobile)
  e verifica snap, niente scroll-trap, swipe orizzontale che non confligge con lo scroll verticale.
- Screenshot full-page di ciascuna delle 3 schermate.

## hp — Punti Ferita (`/char/:id/hp`)

- Verifica HP corrente/max, barra, hit dice, pulsanti danno/cura, riposo breve/lungo.
- Interazioni: applica danno (HP scende, glow vira a crimson sotto soglia), cura (sale, glow
  emerald), porta HP a 0 (banner ember + death saves), tira un death save (modale risultato),
  riposo breve (HitDiceModal → spendi hit dice), riposo lungo (ripristino + reset death saves
  + concentrazione interrotta).
- Visivo: banner 0-HP con `ember`/`halo-danger` (un solo halo per schermata), toast non fuori
  schermo su mobile, numeri tabulari.

## ac — Classe Armatura (`/char/:id/ac`)

- Verifica breakdown AC (base/scudo/magic override), eventuale `HomebrewBreakdownRow`.
- Interazioni: modifica override magico; (incrocio con inventory) equipaggia armatura/scudo e
  verifica che l'AC si aggiorni — nota: è un bug noto storico (vedi `docs/webapp-audit/known-issues.md`).
- Visivo: righe del breakdown allineate, numeri mono.

## skills — Abilità (`/char/:id/skills`)

- 18 skill con tiro d20. Verifica lista, indicatori di competenza/expertise (long-press),
  esecuzione di uno skill check → RollResultModal con bonus/totale, crit/fumble evidenziati.
- Visivo: righe leggibili, modale centrato, niente troncamenti dei nomi skill.

## saves — Tiri Salvezza (`/char/:id/saves`)

- Verifica i 6 tiri salvezza, competenze, esecuzione tiro → modale. Testa il reroll con
  ispirazione (bug noto: il modale potrebbe non aggiornarsi).
- Visivo: come skills.

## conditions — Condizioni (`/char/:id/conditions`)

- 14 condizioni standard + Spossatezza (0–6). Applica/rimuovi una condizione, apri il dettaglio
  (ConditionDetailModal), regola il livello di spossatezza.
- Se è installata una regola homebrew di condizione (es. Sanguinamento), testa CustomConditionCard
  + CTA turn-start.
- Visivo: chip condizioni leggibili, colore semantico accoppiato a icona+label.

## dice — Dice roller (`/char/:id/dice`)

- d4/d6/d8/d10/d12/d20. Componi un pool, lancia → DicePoolResultModal con singoli dadi + totale,
  animazione su critico. Testa "post-to-chat" se presente. Svuota la history.
- Visivo: dadi/pool allineati, modale risultato centrato, easing elastico ammesso SOLO qui.

## spells — Incantesimi (`/char/:id/spells`)

- CRUD incantesimi (impara/modifica), ricerca fuzzy, lancio (CastSpellModal → scegli livello
  slot, gestione concentrazione). Verifica che la concentrazione attivi `halo-arcane`.
- Visivo: lista leggibile, modale che sta nello schermo su mobile, accenti arcane solo per la magia.

## slots — Slot Incantesimi (`/char/:id/slots`)

- Slot per livello: consuma/ripristina, riposo. Verifica conteggi tabulari e ripristino al riposo.
- Visivo: contatori allineati, superfici `arcane` per gli slot.

## inventory — Inventario (`/char/:id/inventory`)

- CRUD oggetti tipizzati; equip slot-aware (equipaggiando si sposta l'occupante precedente);
  attacco con arma → WeaponAttackModal (to-hit + danno separati). Se ci sono regole homebrew,
  verifica PropertyBadge sugli item.
- Visivo: card oggetto allineate, chip/badge senza sovrapposizioni, modale attacco centrato.

## currency — Monete (`/char/:id/currency`)

- 5 monete (platino/oro/argento/rame...). Aggiungi/togli, eventuale conversione.
- Visivo: totali in numeri tabulari allineati in colonna.

## stats — Caratteristiche (`/char/:id/stats`)

- 6 caratteristiche + modificatori. Modifica un punteggio, verifica ricalcolo modificatore.
  Nota bug noto: HP max non sempre si auto-aggiorna al cambio CON (mitigato da Settings → Ricalcola).
- Visivo: griglia stat allineata, modificatori mono.

## abilities — Abilità Speciali (`/char/:id/abilities`)

- Feature di classe / passive. Apri il dettaglio (PassiveAbilityDetailModal). Se c'è una risorsa
  homebrew (es. Punti Fortuna), testa CustomResourceCounter (+/−, ripristino al riposo).
- Visivo: card capacità leggibili, contatori allineati.

## class — Classe / Multiclasse (`/char/:id/class`)

- Gestione classi, risorse, trigger level-up. Aggiungi una classe (multiclass) → LevelUpModal
  (scelta classe da livellare, tabella progressione).
- Visivo: tabella progressione leggibile, modale che sta nello schermo.

## xp — Esperienza (`/char/:id/xp`)

- Tracker XP, soglie, level-up → LevelUpModal. Aggiungi XP fino al threshold.
- Visivo: barra XP, numeri tabulari, call-out level-up con `amber`/pulse (non oro primario).

## identity — Identità (`/char/:id/identity`)

- Nome, razza, background, allineamento, ecc. Modifica e salva un campo.
- Visivo: form con label Cinzel, input underline-focus oro, nessun em dash nei testi.

## homebrew — Regole custom (`/char/:id/homebrew`, `/new`, `/:ruleId`)

- Hub: empty state, libreria template (Qualità&Usura, Sanguinamento, Arma incantata, Punti
  Fortuna), installa/abilita/disabilita/elimina una regola, toast.
- RuleEditor (`/new`): sezioni Identity/Subject/Properties/Tables/PassiveModifiers/Triggers+
  EffectChain. Crea una regola semplice, salva, verifica persistenza; testa validazione (nome
  vuoto / DSL malformato → 422, niente salvataggio).
- Visivo: editor usabile su mobile (niente overflow orizzontale, sezioni raggiungibili),
  RuleCard ordinate.

## notes — Note (`/char/:id/notes`)

- Note testuali (markdown) + note vocali (upload/playback). Crea/modifica/elimina una nota.
- Visivo: editor leggibile, player audio non deformato.

## maps — Mappe (`/char/:id/maps`)

- Upload immagine/zona, gestione zone, visualizzazione mappa.
- Visivo: anteprime con aspect-ratio corretto, niente immagini stirate.

## history — Cronologia (`/char/:id/history`)

- Log dei cambiamenti (max 50). Verifica che gli eventi recenti compaiano; svuota se previsto.
- Visivo: righe con timestamp mono allineati, niente troncamenti incoerenti.

## settings — Impostazioni (`/char/:id/settings`)

- Tema (dark/light), lingua (it/en), retention policy, eventuale "Ricalcola". Cambia tema e
  lingua e verifica che la UI risponda.
- Visivo: **in light mode** ricontrolla contrasto e ornamenti (la pergamena va trattata con lo
  stesso rigore del dark, non è un flip). Toggle/select non deformati.

## session — Sessioni multiplayer (`/session`, `/session/join`, `/session/:id`) — OPZIONALE

> Fuori scope di default (richiede 2 utenti simulati). Includi solo se l'utente lo chiede.

- Crea sessione, join via codice, room live (feed + messaggi), GrantItemModal lato GM.
- Visivo: feed leggibile, layout room senza overflow.

---

## Modali trasversali (verifica ovunque compaiano)

RollResultModal, DicePoolResultModal, WeaponAttackModal, CastSpellModal, HitDiceModal,
LevelUpModal, PassiveAbilityDetailModal, ConditionDetailModal, GrantItemModal.

Per ogni modale: entrata/uscita, tap-outside ed ESC che chiudono (mai trap), `rounded-3xl`
con corner flourish, backdrop con blur (unico glassmorphism ammesso), accent border del colore
giusto, **niente overflow oltre lo schermo su mobile (390px)**, niente doppio halo.
