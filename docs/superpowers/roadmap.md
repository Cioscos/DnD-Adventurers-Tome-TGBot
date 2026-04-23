# Roadmap — Decomposizione di `istruzioni.md` in 8 sottoprogetti

**Sorgente originale:** `istruzioni.md` (radice del repo, gitignorato).
**Ultima revisione:** 2026-04-23.
**Stato globale:** Gruppi A, B, C, D, F, G completati e mergeati; E, H pending.

Questo documento è la mappa maestra dei sottoprogetti. Ogni gruppo è un ciclo indipendente `brainstorming → spec → plan → implementazione → PR`. Lo scope, le dipendenze e l'ordine consigliato sono sotto.

---

## Decomposizione — i 8 gruppi

| # | Gruppo | Sezioni `istruzioni.md` | Status | Branch |
|---|---|---|---|---|
| A | UX polish hero section | §5 integrale + §1.1 (solo XP bar) | ✅ Done (PR #67 merged → main) | `feat/ux-polish-hero-section` |
| B | Meccaniche personaggio | §1.1 (meno XP bar) + §1.2 | ✅ Done (PR #68 merged → main) | `feat/character-mechanics-gruppo-b` |
| C | Rework concentrazione | §1.4 + §1.5 | ✅ Done (PR #72 merged → main) | `feat/concentration-gruppo-c` |
| D | Widget dadi overlay | §1.3 + §1.6 | ✅ Done (PR #73 merged → main) | `feat/dice-overlay-gruppo-d` |
| E | Privacy identità | §1.7 + §4 | 🟡 Parziale (base già fatto pre-roadmap) | — |
| F | XP + Level-up button | §1.8 | ✅ Done (PR #69 merged → main) | `feat/xp-level-up-gruppo-f` |
| G | Multiclasse | §2 (tutto) | ✅ Done (PR #70 merged → main) | `feat/multiclass-gruppo-g` |
| H | Chat/cronologia integrata | §3 | ⬜ Pending | — |

---

## Gruppo A — UX polish hero section ✅

**Sezioni coperte:** `§5 Hero section UX` integrale + `§1.1 XP bar` (estratto dal §1.1 perché visuale).

**Sub-punti di `istruzioni.md`:**

- **Hero section – XP**: sostituire il valore numerico con una barra progressiva (§5).
- **Breadcrumb cliccabile**: prev/next del page carousel nell'header Layout diventano cliccabili (§5 — testo chiarito dall'utente: la parte "rimuovere il testo" riferita alle chip, non al breadcrumb).
- **Velocità**: icon-only floating bottom-right dell'hero card, tap reveals `30 ft` inline per 2s (§5).
- **Spossatezza**: descrizioni dei 6 livelli mostrate in toggle dal pulsante Info (§5 — originariamente sempre visibile, cambiato in post-review dall'utente).
- **Condizioni hero**: chip icon-only con icona specifica per condizione, tap apre `ConditionDetailModal` (§5).
- **Abilità passive hero**: chip invariate (icon+nome), tap apre nuovo `PassiveAbilityDetailModal` (§5 — estensione).
- **Caratteristiche cliccabili**: celle STR/DEX/CON/INT/WIS/CHA navigano a `/stats` (§5).
- **Classe Armatura**: Base full-width + Scudo/Magia su due colonne (§5 — solo pagina `/ac`; hero emblem invariato).
- **Layout shield AC**: spostato da `absolute top-right` a flex row con HP+XP bar a sinistra e shield centrato verticalmente (iterazione post-merge).

**Decisioni chiave:**
- Chip icon-only differenziate: velocità tap = reveal valore 2s; condizioni tap = apre modale dettaglio.
- XP bar variant "D": `LIV N` + `current/threshold`, sostituito da bottone LEVEL UP inline quando `levelFromXp(xp) > char.total_level` (multiclass pending).
- Level 20 → mostra "MAX" invece di numeri.
- `pr-24` rimosso dopo il refactor layout AC (shield non più absolute).

**Componenti creati:**
- `webapp/src/components/ui/HeroXPBar.tsx` (barra XP con level-up button)
- `webapp/src/pages/abilities/PassiveAbilityDetailModal.tsx`
- `webapp/src/lib/xpThresholds.ts` (estrazione da `Experience.tsx`)

**Spec & plan:**
- Spec: `docs/superpowers/specs/2026-04-22-ux-polish-hero-section-design.md`
- Plan: `docs/superpowers/plans/2026-04-22-ux-polish-hero-section.md`

**Dipendenze:** nessuna. Standalone.

---

## Gruppo B — Meccaniche personaggio ✅

**Sezioni coperte:** `§1.1 Meccaniche di Gioco` (meno XP bar già fatto in A) + `§1.2 Slot Incantesimi`.

**Sub-punti di `istruzioni.md`:**

- **Auto-HP alla creazione**: formula D&D 5e fixed — liv 1 = `HD_max + CON_mod`.
- **Auto-HP al level-up**: liv 2+ = `(HD/2 + 1) + CON_mod`, clampato a 1 HP/livello minimo.
- **Inventario modificatori caratteristiche**: assoluti (es. `=19`) + relativi (es. `+2`), solo 6 ability score, solo se `is_equipped`, stacking rule `max(base+sum(rel), max(abs))`, nessun cap (homebrew).
- **Dadi danno incantesimi**: pulsante "Rolla danni" inline + sheet con casting level + extra dice + critical toggle (attack spell) + risultato pieno/dimezzato.
- **Spell slots click bug fix**: click simmetrico use/un-use (click su vuoto → `used++`; click su pieno → `used--`).
- **Spell slots nuovo behavior**: visual invertito (disponibile=vuoto outline, usato=pieno gold).

**Estensioni decise durante l'implementazione:**
- **CON change hook**: al cambio CON gli HP max+current si aggiornano retroattivamente di `delta_mod * total_level`.
- **Flag `settings.hp_auto_calc`**: boolean default True per disattivare gli auto-hook (homebrew manuale).
- **`POST /hp/recalc` endpoint**: pulsante "Ricalcola HP" nelle settings per riallineare manualmente.
- **Tipo item "accessory"** (non in `istruzioni.md`): aggiunto perché gli item type esistenti (generic/weapon/armor/shield/consumable/tool) non coprivano accessori magici equipaggiabili (cinture, anelli, mantelli). Senza questo, l'AbilityModifiersEditor non era utile per gli oggetti magici tipici.
- **Spells page (collapsible + count)**: level header cliccabili per collapse/expand + conteggio incantesimi per livello + stesso click behavior symmetric delle gemme anche qui.
- **Toast "+N HP" al level-up**: feedback visuale quando l'XP mutation ritorna `hp_gained > 0`.

**Componenti creati:**
- `core/game/stats.py` — `hit_points_for_level`, `total_base_hp`, `effective_ability_score`, `AppliedModifier` dataclass
- `api/routers/_helpers.py` — `effective_con_mod(char)` condiviso
- `webapp/src/pages/inventory/AbilityModifiersEditor.tsx`
- `webapp/src/pages/spells/SpellDamageSheet.tsx`

**Spec & plan:**
- Spec: `docs/superpowers/specs/2026-04-23-character-mechanics-design.md`
- Plan: `docs/superpowers/plans/2026-04-23-character-mechanics.md`

**Dipendenze:** nessuna sulla parte implementata. Gruppo F estenderà il bottone LEVEL UP (già presente in HeroXPBar dal Gruppo A) per collegarlo al vero flow level-up. Gruppo G estenderà il level-up flow con la modale multiclasse — il backend di B è già pronto per questo (`total_base_hp` accetta multiclasse).

**Stato:** ✅ Mergeato in main via PR #68 (merge commit `f7b73b6`).
- Bug fix applicati durante verifica: `c54d0b3` (auto-HP persistence), `9f628fd` (accessory type), `171bc53` (Spells page collapsible).

---

## Gruppo C — Rework concentrazione ✅

**Sezioni coperte:** `§1.4 Menù Punti Ferita` + `§1.5 Menù Incantesimi` (parte concentrazione).

**Sub-punti di `istruzioni.md`:**

- **Menù Punti Ferita** (§1.4):
  - Se il personaggio è in concentrazione su un incantesimo: **non mostrare** la sezione concentrazione né il pulsante per il tiro salvezza su concentrazione.
  - Il tiro salvezza su concentrazione viene eseguito **automaticamente** all'inserimento dei danni subiti.
- **Menù Incantesimi** (§1.5):
  - Rimuovere la possibilità di calcolare manualmente il tiro salvezza su concentrazione.
  - Mostrare soltanto l'incantesimo attivo in concentrazione con la relativa descrizione.

**Nota semantica (chiarita dall'utente durante Gruppo B):** il TS su concentrazione si fa quando il personaggio SUBISCE danni (difensivo), non quando fa danni agli altri. Il flow si aggancia a `/hp` op DAMAGE, NON al Roll Damage del Gruppo B.

**Dipendenze:**
- Nessuna dipendenza bloccante. L'infrastruttura `char.concentrating_spell_id` + `Spell.is_concentration` esiste già.
- Nessuna dipendenza da B.

**Componenti impattati (preview):**
- `webapp/src/pages/HP.tsx` — rimuovere/nascondere pulsante TS manuale; aggiungere logica auto-TS su DAMAGE.
- `webapp/src/pages/Spells.tsx` — semplificare UI concentrazione (mostrare solo spell attivo + descrizione).
- Backend: `api/routers/hp.py` op DAMAGE potrebbe già fare il check; verificare.

---

## Gruppo D — Widget dadi overlay ⬜

**Sezioni coperte:** `§1.3 Widget Dadi (Overlay)` + `§1.6 Menù Tiri Salvezza` (solo il dettaglio animazione 3D).

**Sub-punti di `istruzioni.md`:**

- **Overlay globale (§1.3):**
  - Pulsante overlay fisso in basso a destra, sempre visibile.
  - Al click apre barra laterale che si estende dal bottone con tutti i tipi di dado selezionabili.
  - Selezionando un dado si incrementa il contatore per quella tipologia.
  - Accanto al pulsante principale appare a scomparsa un pulsante **"Lancia"** che avvia l'animazione 3D.
  - Risultato in overlay bottom che scompare dopo 3s.
  - Risultato sempre salvato in cronologia.
- **Animazione 3D (§1.6):**
  - Il tipo di animazione del dado deve rispettare l'**impostazione della visualizzazione 3D** configurata nelle impostazioni.
  - Applicabile anche alla pagina Tiri Salvezza.

**Infrastruttura esistente:** `webapp/src/dice/` contiene già `DiceScene.tsx`, `useDiceAnimation.ts`, engine Three.js + cannon-es. `Dice.tsx` è la pagina dedicata al dice roller. Questo gruppo estende l'accesso globale overlay.

**Dipendenze:**
- Nessuna bloccante.
- Collisione potenziale con il chip velocità floating bottom-right dell'hero (Gruppo A). Da gestire: l'overlay sta SOPRA l'hero, visibile su tutte le pagine.

**Componenti da creare (preview):**
- `webapp/src/components/DiceOverlay.tsx` — FAB + sidebar con contatori.
- Estensione a `SavingThrows.tsx` / altre pagine che rollano dadi.

---

## Gruppo E — Privacy identità 🟡 Parziale

**Sezioni coperte:** `§1.7 Identità del Personaggio` + `§4 Sessione di Gioco` (parte identità).

**Sub-punti di `istruzioni.md`:**

- **Identità (§1.7):**
  - Dividere info in **private** (tratti caratteriali, ideali, legami, difetti, background) e **pubbliche** (resto).
  - Spostare **Background** tra info private (nei tratti caratteriali).
  - Setting per nascondere/mostrare info private.
- **Sessione (§4):**
  - Un player può cliccare un altro player per vederne la sezione identità.
  - Se public-only → mostra solo le pubbliche.
  - Se ha reso pubbliche le private → mostra anche quelle.

**Stato parziale:** Prima dell'avvio del roadmap (ramo `feat/session-room-ux-privacy` mergeato in `ff7e0a1` e precedenti), sono state fatte:
- Redaction di info sensibili (HP exact, conditions) in session-room per non-GM non-owner.
- Click su participant row → view limitata.
- Whisper system GM↔player.

**Da verificare (gap possibile):**
- Effettiva split private/public di identità con toggle.
- Spostamento Background nel blocco privato.
- Click player in session per view identità completa (non solo HP/status).

**Raccomandazione:** audit del codice attuale (`Session.tsx`, `SessionRoom.tsx`, `Identity.tsx`, `Settings.tsx`) per capire quanto resta da fare. Può finire con spec+plan molto corti se la maggior parte è già in main.

**Dipendenze:** nessuna bloccante.

---

## Gruppo F — XP + Level-up button ✅

**Sezioni coperte:** `§1.8 Esperienza e Level Up`.

**Sub-punti di `istruzioni.md`:**

- **Aggiungere pulsante/funzione di level up nella schermata esperienza.**
- **I pulsanti per aggiungere quantità predefinite di XP devono scalare proporzionalmente agli XP necessari per il livello successivo.**

**Stato corrente:**
- Gruppo A ha aggiunto il bottone **LEVEL UP** inline nell'hero XP bar (`HeroXPBar`) che naviga a `/xp` quando `xpLevel > total_level`.
- Gruppo B ha aggiunto l'auto-HP al level-up XP.
- Gruppo F completa: bottone in pagina `/xp` (Experience.tsx) per trigger manuale + quick-XP buttons proporzionali.

**Sub-task concreti:**
1. Pulsante "LEVEL UP" in `Experience.tsx` (visibile quando `levelUpAvailable`).
2. Quick-XP buttons (oggi fissi 50/100/200/500) rimpiazzati da valori proporzionali (es. 10%, 25%, 50%, 100% degli XP necessari al prossimo livello).

**Dipendenze:**
- Usa `levelFromXp` + `XP_THRESHOLDS` di `lib/xpThresholds.ts` (Gruppo A → B riutilizza).
- Click su LEVEL UP: se single-class trigga auto-level via `PATCH /xp` (già fa). Se multiclass → delega a Gruppo G (modale scelta classe).

---

## Gruppo G — Multiclasse ✅

**Sezioni coperte:** `§2 Funzionalità Multiclasse` (entrambe le sottosezioni).

**Sub-punti di `istruzioni.md`:**

- **2.1 Comportamento al Level Up:**
  - Single-class: invariato.
  - Multiclass: al passaggio di livello appare una **modale** che chiede su quale classe salire.
  - **Struttura modale:**
    - In alto: prossimi sblocchi per classe attualmente selezionata.
    - In basso: un pulsante per ogni classe disponibile (prima classe pre-selezionata).
    - Click su bottone classe → aggiorna sblocchi mostrati in alto.
    - Pulsante Conferma per applicare la scelta.
    - *Esempio:* Chierico/Guerriero → 2 bottoni; Chierico pre-selezionato con sblocchi; click Guerriero → sblocchi Guerriero.

- **2.2 Menù della Classe:**
  - Sostituire "Aggiungi classe" con "**Modifica classe**".
  - "Modifica classe" permette di redistribuire i livelli tra classi esistenti, rispettando il livello totale:
    - Non superare il livello totale del personaggio.
    - Prima del conferma, somma dei livelli classi = livello totale.
  - **Livello personaggio slegato dal livello delle singole classi.**
  - *Esempio:* Liv 19 Chierico 18 / Guerriero 1 → possibile abbassare Chierico a 17 e alzare Guerriero a 2, somma = 19.

**Dati progressione classi richiesti:** il contenuto di `dnd5e_classi.md` (radice del repo, gitignorato) contiene le tabelle di sblocchi/caratteristiche per livello per ciascuna classe D&D 5e. Questo gruppo deve:
1. Caricare questi dati in un formato strutturato (JSON o Python dict).
2. Renderli accessibili via API o statico nel webapp.
3. Usare i dati per popolare il blocco "sblocchi" della modale level-up.

**Dipendenze:**
- Gruppo F (bottone LEVEL UP base) → Gruppo G (estende con scelta classe per multiclass).
- Gruppo B backend è già pronto (`total_base_hp` e `hit_points_for_level` gestiscono multiclasse correttamente).

**Task pesante.** Richiede:
- Data loading per 12+ classi D&D 5e (file JSON o module Python).
- Modale UI complessa con selettore classi + preview sblocchi.
- Endpoint `PATCH /classes` per redistribuzione livelli con validazione somma.
- Integrazione con flow XP per trigger modale su level-up multiclass.

---

## Gruppo H — Chat/cronologia integrata ⬜

**Sezioni coperte:** `§3 Cronologia`.

**Sub-punti di `istruzioni.md`:**

- Cronologia disponibile sia nel **Gestore Personaggio** (completa) che nella **Sessione di Gioco** (solo sessione corrente).
- Ogni player vede propria cronologia + altri.
- **Azioni di cura altrui** → mostrate in forma generica (es. *"Si è curato"*).
- **Master** vede cronologia completa di ogni personaggio, inclusi dettagli cure.
- Cronologia **integrata nella chat**: la sezione chat ha funzione duplice (chat + cronologia).

**Stato corrente:**
- Pagina `/history` esiste (`webapp/src/pages/History.tsx`) con cronologia eventi del personaggio.
- Chat in session-room esiste.
- Non integrata.

**Dipendenze:**
- Parte della logica privacy (redaction "si è curato" per cure altrui) riusa pattern di Gruppo E.
- Infrastruttura session chat di `SessionRoom.tsx` + session_messages table (già esistenti).

**Task concreti (preview):**
1. Merge chat + history in un'unica view per la session.
2. Filtro/transform eventi di cura per non-owner non-GM → "Si è curato" generico.
3. GM bypass: vede tutti i dettagli.
4. Gestore personaggio: cronologia completa invariata.

---

## Ordine consigliato

Fondazioni → feature grosse → integrazioni:

```
✅ A → ✅ B → ✅ F → ✅ G → ✅ C → ✅ D → E completion → H
```

**Razionale:**
- **A** (fatto) — UX polish, nessuna dipendenza.
- **B** (in corso) — meccaniche foundation. Altri gruppi riusano i suoi helper.
- **F** — piccolo, estende A+B.
- **G** — grosso, richiede F. Richiede caricamento dati da `dnd5e_classi.md` (lavoro una-tantum).
- **C** — isolato, può essere mergeato in parallelo con G se due sviluppatori.
- **D** — grosso ma isolato. Overlay globale.
- **E** — completamento parziale. Audit + eventuali gap.
- **H** — depende da E e da infrastruttura session chat.

**Alternativa più veloce** (se priorità è "feature visibili utente"):
```
B → D → G → C → F → H → E audit
```

---

## Come riusare questo roadmap

**Prima di iniziare un nuovo gruppo**, leggi la sua sezione qui + le spec dei gruppi già completati per:
1. Vedere le decisioni prese (convenzioni, pattern, file già esistenti da riutilizzare).
2. Capire se il tuo scope si sovrappone con qualcosa di già fatto.
3. Rispettare le dipendenze già note.

**Aggiorna questo file** quando:
- Un gruppo passa da ⬜ → 🟡 → ✅.
- Una decisione in-flight cambia scope o dipendenze.
- Un nuovo sottotema emerge (es. il tipo "accessory" emerso in B non era in `istruzioni.md` originale).

**Spec e plan** per ciascun gruppo vivono in `docs/superpowers/specs/` e `docs/superpowers/plans/`. Questo file è il master index.

---

## File correlati

- **Source of truth:** `istruzioni.md` (radice, gitignorato — contiene il testo originale dell'utente).
- **Dati D&D 5e:** `dnd5e_classi.md` (radice, gitignorato — tabelle progressione classi per Gruppo G).
- **Specs:**
  - `docs/superpowers/specs/2026-04-22-ux-polish-hero-section-design.md` — Gruppo A
  - `docs/superpowers/specs/2026-04-23-character-mechanics-design.md` — Gruppo B
- **Plans:**
  - `docs/superpowers/plans/2026-04-22-ux-polish-hero-section.md` — Gruppo A
  - `docs/superpowers/plans/2026-04-23-character-mechanics.md` — Gruppo B
