# Animation Opportunities — Mini App

**Generato:** 2026-05-26 via audit Playwright + lettura DESIGN.md + censimento `framer-motion` esistente.
**Scope:** webapp/src — solo motion. Nessuna proposta che richieda refactor strutturale.
**Vincoli (DESIGN.md):**

- Easing parchment `cubic-bezier(0.22, 1, 0.36, 1)` (`ease.inkSpread` o `pageTransition`).
- Spring presets in `@/styles/motion.ts`: `press`, `drift`, `snappy`, `elastic`, `swipe`. Niente `outBack` fuori dal dice roller.
- Halo signal-only: max 1 halo attivo per schermata.
- `prefers-reduced-motion` → collapse a istantaneo (`useReducedMotion()` già diffuso).
- No viewport shake, no flash schermo, no particles-on-tap (registro gacha vietato).
- Numerics: `font-variant-numeric: tabular-nums`. Le count-up devono usare mono.

---

## Già coperto (non riproporre)

| Componente | Animazione esistente |
|------------|---------------------|
| `Layout.tsx` | header drift-in + breadcrumb collapse on scroll |
| `PageTransition.tsx` | fade+y route change con `spring.drift` |
| `CharacterSwiper` | drag-x + spring snap |
| `ResultDialog` / `ModalProvider` | scale+y+opacity con `spring.swipe`, corner flourish statici |
| `RollResultModal` | flourish con `spring.elastic` (eccezione dice) |
| `HPGauge` | width + `animate-pulse-danger` su critico |
| `Button` | `whileTap` press |
| `DiceOverlay` | spring 320/26, cup→reveal |
| `Surface` interactive | press scale 0.98 |
| Pulse loops CSS | `animate-pulse-gold`, `animate-pulse-danger`, `animate-gold-shimmer` |
| Glows HP | `hp-glow-emerald/gold/crimson` (filter drop-shadow) |

---

## Tier 1 — Momenti firma (impatto narrativo alto)

### A. Level-up "Sali di Livello" (XP page)

**Dove:** `webapp/src/pages/Experience.tsx` → bottone primary `+ Sali di Livello`.
**Oggi:** click → numero LIV cambia istantaneo, niente cerimonia per quello che è il momento più epico fuori dal combattimento.
**Proposta:**

1. Click → pulse-gold halo sulla card "LIV" (3 cicli, già CSS-ready).
2. Numero livello: **count-up con `useSpring`** (mono, stiffness 100 damping 30, ~600ms).
3. Burst di 4 flourish glyphs dagli angoli della card (scale 0→1 + rotate -8→0, stagger 60ms, `spring.swipe`) — riusa gli SVG già definiti per dialog corners.
4. Ornament line `◈—◈` sotto LIV draws left-to-right (`scaleX 0→1`, `transformOrigin: 'left'`, 400ms `ease.inkSpread`).
5. XP bar: width interp con `spring.drift` invece di snap.

Tutto opt-in dietro `useReducedMotion`. Rispetta "No Gradient Text" (numero solid gold-bright, niente shimmer sul digit).

### B. Death-save roll reveal (HP=0)

**Dove:** `webapp/src/pages/HP.tsx` → sezione `Tiri vs Morte` quando `current_hp === 0`.
**Oggi:** la modal di reroll/ispirazione esiste ma il risultato del d20 appare instantaneo.
**Proposta:** flip 3D del d20 — `rotateY: [0, 720, 720]` (~700ms `ease.inkSpread`) → atterraggio scale `[1, 1.08, 1]` → tinta glow finale:
- `nat 20` → emerald glow pulse 2 cicli + bordo `border-dnd-emerald-bright` 1s.
- `nat 1` → crimson `halo-danger` + numero shake locale (`x: [-2,2,-1,1,0]` 220ms) **sul digit** (non viewport).
- altrimenti → fade gold standard.

L'eccezione "spring.elastic per dice" autorizza il rimbalzo finale; nessuna alterazione del viewport.

### C. HP threshold color transition

**Dove:** `webapp/src/pages/HP.tsx` + `HPGauge.tsx`.
**Oggi:** classi `.hp-glow-emerald/gold/crimson` switchano via condizionale → cambio di filter istantaneo, lacerante quando un colpo critico fa passare 80% → 20%.
**Proposta:** wrappare il container in un `m.div` che anima la custom prop `--hp-glow-color` con `MotionValue<string>` (motion supporta string interp su rgba) o, più semplice, mantenere 3 layer sovrapposti con `opacity` cross-fade 300ms `ease.inkSpread`. Niente snap.
Bonus: il numero HP set in mono usa `AnimatedNumber` count su damage/heal (vedi pattern §F).

---

## Tier 2 — Momenti di significato

### D. Equipment slot — equip drop

**Dove:** `webapp/src/components/character/EquipItemPicker.tsx` + `EquipmentSlotCell.tsx`.
**Oggi:** scelta da picker → modal chiude → slot riempito istantaneo. Nessuna continuità spaziale.
**Proposta:** quando l'utente conferma equip:

1. `layoutId={\`equip-\${itemId}\`}` sull'icona dentro picker E sul cell target.
2. AnimatePresence chiude il picker; framer-motion fa volare l'icona da picker → cella (~400ms `spring.drift`).
3. Cella target accende `halo-gold` per 600ms poi torna a rest.

Se l'oggetto displace un occupante, il vecchio fade-out e scale-down a 0.8 mentre il nuovo arriva (cross-dissolve 200ms). Honors swap-slot logic backend già lì.

### E. AC value reattivo

**Dove:** `webapp/src/pages/ArmorClass.tsx` + crest AC sull'Hero screen.
**Oggi:** AC totale è un numero statico mono.
**Proposta:** AC value wrappato in `<AnimatedNumber value={ac}>` con `useSpring(stiffness 140, damping 24)`. Quando il backend ricalcola CA dopo equip armor/scudo, il numero scrubba i digit. Su delta positivo: brief `text-dnd-emerald-bright` flash 400ms. Su delta negativo: brief `text-dnd-crimson-bright` flash. Ritorno a gold standard.

### F. Inventory item add

**Dove:** `webapp/src/pages/Inventory.tsx`.
**Oggi:** lista cambia, oggetto compare. Bar carico cambia istantaneo.
**Proposta:**

1. Nuovo item: `<m.li layoutId={item.id} initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }}>` con `spring.swipe`.
2. Lista riordinata: framer-motion `layout` prop sui `<m.li>` → riarrangiamento smooth.
3. Carry bar: width via `m.div animate={{ width: \`\${pct}%\` }} transition={spring.drift}` invece di width inline.
4. Bar lampeggia gold-bright se l'oggetto porta carico > 70%, crimson se > 100% (encumbered).

### G. Concentration breathing

**Dove:** `webapp/src/pages/Spells.tsx` → chip dell'incantesimo concentrato.
**Oggi:** la chip è statica anche se la concentration è il singolo stato più dinamico di una battaglia magica.
**Proposta:** `m.div animate={{ boxShadow: ['0 0 0 2px rgba(155,89,182,.18)', '0 0 22px rgba(155,89,182,.45)', '0 0 0 2px rgba(155,89,182,.18)'] }}` loop 2.8s `ease.inOut`. Pausa loop quando la pagina perde focus (`document.visibilityState`). Halo-arcane è già un token DESIGN — questo lo rende **vivente** invece di decorativo. Mai più di una chip respira per volta (rispetta "no 2 halos at once").

### H. Death-save banner enter

**Dove:** `webapp/src/pages/HP.tsx` → blocco `Tiri vs Morte` quando current=0.
**Oggi:** appare in flusso, nessuna enfasi.
**Proposta:** `<AnimatePresence>` con `initial={{ y: 24, opacity: 0 }} animate={{ y: 0, opacity: 1 }}` `spring.swipe`. All'apparizione, bordo `border-dnd-crimson/40` accende con `boxShadow` halo-danger per 1.2s poi rest. Solo prima apparizione (memo flag), non a ogni mount.

---

## Tier 3 — Polish silenzioso (1-2 righe ciascuno)

### I. Character cards stagger (CharacterSelect)
`webapp/src/pages/CharacterSelect.tsx`: `motion.ul` con `staggerChildren: stagger.list (0.045)`. Card item: `fadeUp` variant. Initial only.

### J. Stats grid stagger (Hero screen)
`webapp/src/components/character/...HeroScreen`: 6 `StatPill` con stagger 0.04, `spring.drift`. Una volta per mount del personaggio.

### K. Skill proficiency ring draw
`webapp/src/pages/Skills.tsx`: cerchio `<circle>` con `pathLength` animato `0→1` (300ms `ease.out`) al toggle. Su expert (long-press), secondo ring concentrico draw 0→1 + breve `halo-gold` 400ms.

### L. Long-press expert progress
Long-press handler già esistente: aggiungere `<m.circle pathLength>` come progress indicator riempito durante il press (700ms threshold). Visivo dell'intent prima del commit. Su release prematura → `pathLength` ritorna a stato attuale.

### M. Empty state idle bob
Inventario vuoto, Spells vuoti, Conditions/Maps vuoti: icona principale `m.div animate={{ y: [0, -4, 0] }} transition={{ repeat: Infinity, duration: 3.2, ease: 'easeInOut' }}`. Stop quando reduced-motion. Marca la pagina viva senza chiasso.

### N. Dice tile flip (Dice page)
`webapp/src/pages/Dice.tsx`: tap su d4/d6/d8/d10/d12/d20/d100 → `rotateY 0→180` 280ms `ease.inkSpread`, mid-flip swap del number, poi il risultato sale a `DiceOverlay`. Eccezione dice-roller autorizzata.

### O. Pool chip selected lift
`webapp/src/pages/Dice.tsx`: chip `2D6/3D6/4D6KH3` selezionata → `y: -2`, halo gold subtle, 200ms `ease.out`. De-selected → ritorno a rest.

### P. Stepper count transition
Numero dadi `webapp/src/pages/Dice.tsx` + ogni `+/-` ovunque: il digit centrale wrapped in `AnimatedNumber` con `useSpring` (stiffness 200, damping 28). Sostituisce sostituzione di stringa con scrubbing.

### Q. Currency add
`webapp/src/pages/Currency.tsx`: ogni count di monete in `AnimatedNumber`. Tap su `+1 PA` → conio "click" haptic + digit scrubs. Niente coin-rain (registro gacha vietato esplicitamente).

### R. Carry capacity bar
Vedi §F.3 — vale anche da solo come quick win indipendente da F.

### S. HP gauge segment cascade
`webapp/src/components/ui/HPGauge.tsx`: oggi width transition unica. Proposta: se HP cala da N a M, animare segment-by-segment con stagger 25ms (`for (i=N; i>M; i--) cascadeSegment(i)`). Su heal, cascade reverse. Sentire il danno arrivare uno scatto alla volta. Reduced-motion → snap.

### T. Conditions chip activation
`webapp/src/pages/Conditions.tsx`: tap su condizione attivante → bordo `border-dnd-crimson/0 → /50` interp 250ms `ease.inkSpread` + brief `halo-danger` 600ms. Disattivazione: cross-fade neutro.

### U. Hero screen ornament line draws in
`webapp/src/pages/CharacterMain.tsx` mount: la riga ornament header (la sequenza `◈—◈` sopra le sezioni) → `scaleX 0→1`, `transformOrigin 'left'`, 400ms `ease.inkSpread`. Mount-only.

### V. Modal corner flourish stagger
`webapp/src/components/ui/ResultDialog.tsx`: i 4 SVG corner pop assieme col container. Proposta: scale 0→1 + rotate ±4→0, stagger 70ms (TL→TR→BR→BL clockwise), `spring.swipe`. Sigilla la dialog come timbro a 4 colpi.

### W. Tablist breadcrumb slide-in
`webapp/src/components/Layout.tsx` breadcrumb mount: ogni chip `(prev) ◈ (current) ◈ (next)` slide-in da `x: -8` con stagger 50ms. Solo prima apparizione, non al collapse/expand toggle (che è già curato).

### X. Floating dice FAB attention
Sul personaggio: il FAB dadi (`DiceOverlay` trigger) è sempre visibile e silenzioso. Quando l'utente è inattivo da > 30s in pagine "actionable" (HP, Combat, Skills), il FAB inizia un `breathe` loop (scale 1→1.04→1, 2s, `ease.inOut`, 3 cicli poi pausa 12s, repeat). Disabilitato se `useReducedMotion` o se un modal è aperto. Halo-gold mai (è già il FAB primario; halo va riservato a "agisci qui adesso" puntuale).

---

## Quick-win order consigliato

Se vogliamo iterare a piccoli step, l'ordine massimo-ROI/minimo-rischio:

1. **§F.3 Carry bar smooth + §S HP segment cascade** — 1 commit, due barre.
2. **§P AnimatedNumber helper** — componente riusabile in §A/§E/§Q/§R.
3. **§A Level-up choreography** — usa §P, è il momento più richiamato dall'UX.
4. **§G Concentration breathing** — singolo componente, valore percepito altissimo in sessione live.
5. **§D Equip drop layoutId** — richiede coordinare picker + cell; pianificare su branch dedicato.

Tutto il resto: polish da PR seguenti, nessun blocchere.

---

## Anti-pattern da evitare (promemoria DESIGN)

- Niente `outBack` / `elastic` su layout (solo dice).
- Niente shimmer su testo body o numeri (`No Gradient Text Rule`).
- Niente particles, coin rain, level-up confetti.
- Niente full-screen flash su damage, niente shake del viewport.
- Niente "tinted-card grid + gradient text" reflex.
- Max **1 halo attivo** per schermata: se §G concentration respira e §H banner pulsa, scegliere il più semantico.
