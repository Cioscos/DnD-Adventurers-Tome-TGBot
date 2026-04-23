# Design — Gruppo D: Widget Dadi Overlay

**Data:** 2026-04-23
**Stato:** design validato, pronto per plan
**Branch:** `feat/dice-overlay-gruppo-d`
**Sezioni `istruzioni.md` coperte:** §1.3 (Widget Dadi Overlay) + §1.6 (animazione 3D rispetta setting nei Tiri Salvezza e altrove).

---

## 1. Scope

Gruppo D introduce un widget overlay globale per tirare dadi rapidamente da qualunque pagina del personaggio o della sessione di gioco, e connette l'animazione 3D esistente (già presente nella pagina `/dice`) anche alle altre pagine che tirano dadi (Tiri Salvezza, Abilità, Tiro Salvezza Morte, Danni Incantesimo), rispettando il setting `animate3d` nelle impostazioni.

### Out of scope
- Nessuna modifica al motore 3D (`DiceScene`, `physics`, `materials`) — già supporta multi-gruppo.
- Pagina `/char/:id/dice` resta invariata (roller completo dedicato).
- Nessun nuovo endpoint `/dice/roll` — multi-kind gestito con N chiamate parallele client-side.

---

## 2. Decisioni chiave (brainstorm)

| Tema | Scelta | Motivo |
|---|---|---|
| Multi-kind | Selezione mista: contatori indipendenti per d4/d6/d8/d10/d12/d20/d100 | `istruzioni.md` §1.3 "selezionando un dado si incrementa il contatore per quella tipologia" |
| Formato risultato | Breakdown per gruppo, niente totale aggregato | Tiri eterogenei; totale aggregato è fuorviante |
| Visibilità FAB | Tutte le pagine `/char/:id/*` eccetto `/char/:id/dice` + `/session/:id` | Utile ovunque tranne dove ridondante; coerente sessione live |
| Scope animazione §1.6 | Saving Throws + Skills + Death Save + Spell Damage | §1.6 menziona Tiri Salvezza ma la coerenza richiede ogni tiro rispetti il setting |
| Persistenza counters | Reset dopo ogni Lancia | Stato minimo, UX pulita |

### Interazioni UI
- Tap singolo su pulsante kind → `count++`.
- Long-press 500ms su pulsante kind → reset solo quel kind.
- Tap FAB chiuso → apre sidebar.
- Tap FAB aperto → chiude sidebar (counters preservati).
- Tap fuori sidebar → chiude sidebar (counters preservati).
- Post-Lancia → chiude sidebar, reset counters, mostra result overlay 3s.

---

## 3. Architettura

### 3.1 Montaggio in App.tsx

Il widget non ha bisogno di context condiviso (stato tutto locale, nessun consumer esterno), quindi montato come componente singolo dentro `DiceAnimationProvider`:

```tsx
<ModalProvider>
  <DiceAnimationProvider>
    <Suspense fallback={…}>
      <Routes>…</Routes>
    </Suspense>
    <DiceOverlay />    {/* montato una volta; legge route + store */}
  </DiceAnimationProvider>
</ModalProvider>
```

Niente nuovo provider / context. `DiceOverlay` usa `useDiceAnimation()` per animare, `useLocation()` per route, `characterStore` per `activeCharId` fallback in session.

### 3.2 Resolver `charId` e visibilità

Il widget risolve `charId` e visibilità leggendo `useLocation().pathname`:

```
if matchPath('/char/:id/dice', pathname) → hidden
if matchPath('/char/:id/*', pathname)    → charId = :id, visible
if matchPath('/session/:id', pathname)   → charId = characterStore.activeCharId, visible if != null
else                                      → hidden
```

### 3.3 Stato interno (React useState / useReducer)

```ts
type DicePool = Partial<Record<DiceKind, number>>   // {d6: 2, d20: 1}
type RollGroup = { kind: DiceKind; notation: string; rolls: number[]; total: number }

const [open, setOpen] = useState(false)           // sidebar expanded
const [pool, setPool] = useState<DicePool>({})    // counters
const [isRolling, setIsRolling] = useState(false) // in-flight
const [results, setResults] = useState<RollGroup[] | null>(null)
const [resultVisible, setResultVisible] = useState(false)
```

Timer 3s per auto-dismiss result, cleanup su unmount.

---

## 4. Layout visivo

```
                    ┌────┐
                    │ d4 │
                    ├────┤
                    │ d6 │
                    ├────┤
                    │ d8 │
                    ├────┤
                    │d10 │     sidebar vertical
                    ├────┤     (appare sopra FAB)
                    │d12 │
                    ├────┤
                    │d20 │
                    ├────┤
                    │d100│
                    └────┘
        ┌────────┐  ┌────┐
        │ LANCIA │  │ FAB│     Lancia a sinistra (se pool non vuoto)
        └────────┘  └────┘

       ───────────────────
       │  2d6 [3+4] = 7   │   result overlay bottom-center
       │  1d8 [5]    = 5  │   auto-dismiss 3s
       ───────────────────
```

### Posizionamento (Tailwind)
- FAB: `fixed bottom-4 right-4 z-[55] w-14 h-14 rounded-full`.
- Sidebar: `absolute bottom-full right-0 mb-2 flex flex-col gap-1`. Motion: `scaleY 0→1` origin bottom + stagger children.
- Lancia: `absolute right-full top-0 mr-2`. Motion: scale/slide in from right.
- Result overlay: `fixed bottom-24 left-1/2 -translate-x-1/2 z-[55] max-w-xs`. Framer fade+translateY.

### Z-index
- FAB + Sidebar + Result: `z-[55]`.
- `DiceAnimationProvider` scene overlay: `z-[60]` (già esistente) — durante animazione copre e disabilita il widget naturalmente.
- Modali (`Sheet`, `RollResultModal`): `z-50`.
- Ordine finale: modal < widget < scena 3D.

---

## 5. Data flow

### 5.1 Trigger Lancia

1. User tap Lancia → `setIsRolling(true)`, disabilita FAB/sidebar/Lancia.
2. `entries = Object.entries(pool).filter(([_, n]) => n > 0)` → lista `[kind, count][]`.
3. `Promise.all(entries.map(([kind, count]) => api.dice.roll(charId, count, kind)))` → N `DiceRollResult`.
4. Costruisci `groups: [{ kind, results: r.rolls }, …]` per `dice.play({ groups, interGroupMs: 150 })`.
5. `await dice.play(...)` (no-op se setting 3D off).
6. `setResults([{ kind, notation: r.notation, rolls: r.rolls, total: r.total }, …])`.
7. Reset: `setPool({})`, `setOpen(false)`, `setIsRolling(false)`, `setResultVisible(true)`.
8. `setTimeout(() => setResultVisible(false), 3000)`.
9. `queryClient.invalidateQueries(['dice-history', charId])`.

### 5.2 Error handling

- Se una delle N chiamate rigetta: `Promise.all` fallisce.
- Catch → `haptic.error()`, mostra toast (usare i18n `character.dice_overlay.roll_failed`), abort animazione, `setIsRolling(false)`. Counters preservati (utente può riprovare).
- Risultati parziali delle chiamate riuscite vengono scartati — semplice, consistente.

### 5.3 History

Backend `POST /dice/roll` salva automaticamente ogni chiamata in `dice_history`. N chiamate parallele → N entries distinte (una per kind). Coerente con `Dice.tsx` attuale (che fa singola chiamata per singolo kind).

---

## 6. Integrazione animazione in altre pagine (§1.6)

Pattern uniforme in ciascuna pagina: prima di mostrare il modal/result, chiamare `dice.play()`. Se setting 3D off o reduced-motion → `play` è no-op, comportamento invariato.

### 6.1 `SavingThrows.tsx`
```ts
const dice = useDiceAnimation()
const rollMutation = useMutation({
  mutationFn: (ability) => api.characters.rollSavingThrow(charId, ability),
  onSuccess: async (result, ability) => {
    await dice.play({ groups: [{ kind: 'd20', results: [result.die] }] })
    setRollResult({ result, title: … })
    haptic.success()
  },
})
```

### 6.2 `Skills.tsx`
Identico a SavingThrows, sostituendo `rollSavingThrow` con `rollSkill`.

### 6.3 `HP.tsx` — death save
Prima di `setDeathSaveResult(result)`:
```ts
await dice.play({ groups: [{ kind: 'd20', results: [result.roll] }] })
```
(Verificare in plan il field esatto della response death-save.)

### 6.4 `SpellDamageSheet.tsx`
Richiede **estensione response backend** `RollDamageResult`.

**Modifica `RollDamageResult` (Pydantic + TS):**
```python
class RollDamageResult(BaseModel):
    rolls: list[int]           # legacy piatto, invariato
    total: int                 # invariato
    half_damage: int           # invariato
    damage_type: str | None    # invariato
    breakdown: str             # invariato
    casting_level: int         # invariato
    is_critical: bool          # invariato
    # nuovi:
    main_kind: str             # es. "d6"
    main_rolls: list[int]      # es. [3, 5]
    extra_kind: str | None     # es. "d4" o None
    extra_rolls: list[int]     # [] se niente extra
```

Il backend popola i nuovi campi con dati già disponibili (`sides` → `f"d{sides}"`, `main_rolls`, `extra_sides`, `extra_rolls`).

Frontend:
```ts
const groups = [{ kind: data.main_kind as DiceKind, results: data.main_rolls }]
if (data.extra_kind && data.extra_rolls.length) {
  groups.push({ kind: data.extra_kind as DiceKind, results: data.extra_rolls })
}
await dice.play({ groups, interGroupMs: 150 })
setResult(data)
```

**Compatibilità:** i campi sono aggiuntivi, mai letti dal codice esistente → zero breaking change client-side pregresso.

---

## 7. File impattati

### Nuovi
- `webapp/src/components/DiceOverlay.tsx` (~250 LOC): FAB + sidebar + Lancia + result overlay.

### Modificati
- `webapp/src/App.tsx` — monta `<DiceOverlay />` dentro `DiceAnimationProvider` accanto a `<Routes>`.
- `webapp/src/pages/SavingThrows.tsx` — `await dice.play(...)` in `onSuccess`.
- `webapp/src/pages/Skills.tsx` — idem.
- `webapp/src/pages/HP.tsx` — idem su `rollDeathSave`.
- `webapp/src/pages/spells/SpellDamageSheet.tsx` — `await dice.play(...)` con `main_kind`/`extra_kind`.
- `webapp/src/types/index.ts` — estendere `RollDamageResult`.
- `api/routers/spells.py` — popolare nuovi campi response.
- `webapp/src/locales/it.json` + `en.json` — chiavi `character.dice_overlay.*` (aria-label FAB, label Lancia, toast errore).

### Invariati
- `DiceAnimationProvider`, `DiceScene`, `useDiceAnimation` — già adeguati.
- `api/routers/dice.py` — multi-kind via N chiamate parallele.
- `Dice.tsx` — pagina roller invariata.

---

## 8. Edge cases

1. Setting 3D off / reduced motion → `dice.play` no-op, overlay funziona identico senza anim.
2. Pool vuoto → Lancia button non appare.
3. Tap multipli durante roll → `isRolling` blocca input.
4. Path `/char/:id/dice` → widget hidden; ricompare immediatamente cambiando route (via `useLocation`).
5. Path `/session/:id` con `activeCharId = null` → widget hidden.
6. Errore su una delle N chiamate → tutti i risultati scartati, counters preservati, toast errore.
7. Unmount durante timer 3s → `clearTimeout` in cleanup `useEffect`.
8. Scena 3D copre widget durante anim → UX corretta (impossibile interagire), nessuna logica extra.
9. `/history` → entries multiple per lancio multi-kind, accettabile (ogni kind ha sua notation leggibile).
10. Haptic: `haptic.light()` su increment counter, `haptic.medium()` su Lancia, `haptic.error()` su fallimento.

---

## 9. i18n keys nuove

```json
"dice_overlay": {
  "open": "Apri lanciatore",
  "close": "Chiudi lanciatore",
  "roll": "Lancia",
  "roll_failed": "Errore durante il lancio",
  "clear_kind": "Resetta"
}
```

Sotto `character` in `it.json` + `en.json`.

---

## 10. Dipendenze / rischi

- **Nessuna dipendenza bloccante** verso altri gruppi.
- **Collisione visuale** col chip velocità hero (Gruppo A) nullificata: hero chip è `absolute bottom-3 right-3` **dentro** l'hero card, widget è viewport-fixed → piani diversi, nessuna sovrapposizione reale.
- **Performance**: `DiceAnimationProvider` fa lazy-load di `DiceScene` al primo `play()`. Widget stesso è leggero (no three.js finché non tira).
- **Rischio basso**: estensione `RollDamageResult` è additiva, compat assicurata.

---

## 11. Acceptance criteria

- [ ] FAB visibile su tutte le pagine `/char/:id/*` eccetto `/dice` + su `/session/:id` se `activeCharId != null`.
- [ ] Sidebar verticale sopra FAB, 7 dadi (d4→d100) con badge counter.
- [ ] Long-press pulsante kind resetta quel kind.
- [ ] Lancia button a sinistra del FAB, appare solo con almeno 1 counter > 0.
- [ ] Multi-kind rolla tutti in parallelo, anima multi-group 3D se setting on.
- [ ] Result overlay bottom-center mostra breakdown per kind, niente totale aggregato, auto-dismiss 3s.
- [ ] Counters reset post-Lancia.
- [ ] Ogni roll salvato in dice_history (verificabile da `/history`).
- [ ] Setting `animate3d` off → no anim, result appare immediatamente.
- [ ] SavingThrows, Skills, Death Save, Spell Damage animano con setting on.
- [ ] Nessuna regressione pagina `/dice`.

---

## 12. Domande aperte

Nessuna. Tutte le decisioni sono state prese durante brainstorming.
