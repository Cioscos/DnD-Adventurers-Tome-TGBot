# Dice Overlay Widget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aggiungere un widget overlay globale per tirare dadi (multi-kind, bottom-right) visibile in tutte le pagine `/char/:id/*` (eccetto `/dice`) e in `/session/:id`; connettere l'animazione 3D esistente alle pagine SavingThrows, Skills, HP death save, SpellDamageSheet rispettando il setting `animate3d`.

**Architecture:** Componente singolo `DiceOverlay` montato una volta in `App.tsx` dentro `DiceAnimationProvider`. Stato tutto locale (useState). Resolver charId via `useLocation` + `matchPath` con fallback `activeCharId` dallo store per le route session. Roll multi-kind gestito client-side con N chiamate parallele a `POST /dice/roll`. Animazione tramite hook esistente `useDiceAnimation()`. Estensione additiva di `RollDamageResult` (backend + TS) per esporre `main_kind/main_rolls/extra_kind/extra_rolls` così la modale Rolla Danni può animare i dadi corretti.

**Tech Stack:** React 18, TypeScript, Tailwind, framer-motion, TanStack Query, Zustand (`characterStore.activeCharId`), FastAPI/Pydantic (backend), Three.js + cannon-es (già integrati via `DiceScene`).

**Branch:** `feat/dice-overlay-gruppo-d` (già creato).

**Note sul testing:** il repo non ha una suite di test (vedi CLAUDE.md: *"No test suite or linter is configured"*). Il ciclo di verifica per ogni task è: (1) `npx tsc --noEmit` sul webapp per il typecheck, (2) verifica manuale sul dev server (`uv run uvicorn api.main:app --reload` in una shell e `cd webapp && npm run dev` nell'altra), (3) commit. I passi di verifica manuale sono espliciti in ogni task.

**Convenzione commit:** conventional commits, scope `webapp` o `api` a seconda. Messaggio italiano ok dove già usato (vedi git log).

---

## Mappa dei file

### Nuovi
- `webapp/src/components/DiceOverlay.tsx` — widget (FAB + sidebar + Lancia + result toast). ~250 LOC.

### Modificati
- `webapp/src/App.tsx` — monta `<DiceOverlay />` accanto a `<Routes>` dentro `DiceAnimationProvider`.
- `webapp/src/locales/it.json`, `webapp/src/locales/en.json` — nuova sezione `character.dice_overlay.*`.
- `webapp/src/types/index.ts` — estendere `RollDamageResult`.
- `api/routers/spells.py` — popolare nuovi campi response `RollDamageResult` Pydantic.
- `webapp/src/pages/SavingThrows.tsx` — `await dice.play(...)` prima di `setRollResult`.
- `webapp/src/pages/Skills.tsx` — idem.
- `webapp/src/pages/HP.tsx` — `await dice.play(...)` su `rollDeathSave` mutation.
- `webapp/src/pages/spells/SpellDamageSheet.tsx` — `await dice.play(...)` usando `main_kind/extra_kind`.
- `docs/superpowers/roadmap.md` — aggiornare stato Gruppo D a ✅ alla fine.

---

## Task 1: Estendere `RollDamageResult` (backend + TS)

Il `SpellDamageSheet` (Task 11) richiede di sapere il kind dei dadi main ed extra per animarli separatamente. La response attuale ha un `rolls[]` piatto. Aggiungiamo campi additivi.

**Files:**
- Modify: `api/routers/spells.py`
- Modify: `webapp/src/types/index.ts:265-279`

- [ ] **Step 1: Leggi lo stato attuale della response**

Apri `api/routers/spells.py` attorno a riga 270-302 (funzione `roll_spell_damage`). Conferma che le variabili locali `sides`, `main_rolls`, `extra_sides`, `extra_rolls` sono già calcolate prima del `return RollDamageResult(...)`.

- [ ] **Step 2: Estendere il modello Pydantic `RollDamageResult`**

Cerca la definizione di `RollDamageResult` nel codice backend. Se sta in `api/schemas/spells.py` o simile, apri quel file. Altrimenti potrebbe essere inline in `api/routers/spells.py`.

Comando:
```bash
grep -rn "class RollDamageResult" api/
```

Aggiungi i campi (additivi, con default per safety):

```python
class RollDamageResult(BaseModel):
    rolls: list[int]
    total: int
    half_damage: int
    damage_type: str | None
    breakdown: str
    casting_level: int
    is_critical: bool
    # --- nuovi campi per animazione 3D ---
    main_kind: str           # es. "d6"
    main_rolls: list[int]    # solo dadi main (non-extra)
    extra_kind: str | None = None   # "d4" o None
    extra_rolls: list[int] = []     # [] se nessun extra_dice
```

- [ ] **Step 3: Popolare i nuovi campi in `roll_spell_damage`**

In `api/routers/spells.py`, nel blocco finale della funzione (attorno a riga 294-302), modifica la costruzione del return. Prima del return, calcola la stringa `main_kind`:

```python
main_kind = f"d{sides}"
extra_kind = f"d{extra_sides}" if extra_rolls else None

return RollDamageResult(
    rolls=main_rolls + extra_rolls,
    total=total,
    half_damage=half_damage,
    damage_type=spell.damage_type,
    breakdown=breakdown,
    casting_level=casting_level,
    is_critical=body.is_critical,
    main_kind=main_kind,
    main_rolls=main_rolls,
    extra_kind=extra_kind,
    extra_rolls=extra_rolls,
)
```

Assicurati che `is_critical` nella response rispecchi esattamente `body.is_critical` (bool, non None). Se il codice attuale non lo passa, aggiungilo.

- [ ] **Step 4: Estendere il tipo TS `RollDamageResult`**

Apri `webapp/src/types/index.ts` e localizza `RollDamageResult` (riga ~271). Sostituisci con:

```ts
export interface RollDamageResult {
  rolls: number[]
  total: number
  half_damage: number
  damage_type: string | null
  breakdown: string
  casting_level: number
  is_critical: boolean
  main_kind: string           // es. "d6"
  main_rolls: number[]        // solo dadi main
  extra_kind: string | null   // null se niente extra_dice
  extra_rolls: number[]       // [] se niente extra_dice
}
```

- [ ] **Step 5: Typecheck webapp**

```bash
cd webapp
npx tsc --noEmit
```

Expected: 0 errori (il campo è letto solo in Task 11; qui serve solo che la type aggiunta non rompa niente).

- [ ] **Step 6: Verifica manuale backend**

Chiedi all'utente di:
1. Riavviare `uvicorn` (con `--reload` dovrebbe essere automatico).
2. Aprire la webapp, andare su `Spells`, rollare danni di un incantesimo con `damage_dice = "2d6"` senza extra.
3. Aprire DevTools → Network → cliccare sulla risposta `roll_damage` → verificare che la response JSON contenga `main_kind: "d6"`, `main_rolls: [...]`, `extra_kind: null`, `extra_rolls: []`.
4. Rifare con un `extra_dice = "1d4"` inserito manualmente → response deve avere `extra_kind: "d4"`, `extra_rolls: [...]`.

Il comportamento visivo della modale non deve cambiare (i nuovi campi non sono ancora letti dal frontend).

- [ ] **Step 7: Commit**

```bash
git add api/routers/spells.py webapp/src/types/index.ts
# se hai modificato anche api/schemas/spells.py aggiungilo
git commit -m "$(cat <<'EOF'
feat(api): expose main_kind/main_rolls/extra_kind/extra_rolls in RollDamageResult

Needed by SpellDamageSheet to play per-kind 3D dice animations (Gruppo D §1.6).
Field additions are backward compatible — existing clients ignore them.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Aggiungere chiavi i18n `character.dice_overlay.*`

**Files:**
- Modify: `webapp/src/locales/it.json`
- Modify: `webapp/src/locales/en.json`

- [ ] **Step 1: Individuare la sezione `character` in it.json**

```bash
grep -n '"character":' webapp/src/locales/it.json
grep -n '"dice":' webapp/src/locales/it.json
```

Nota il range del blocco `character.dice` esistente (es. righe 210-228). La nuova sezione `dice_overlay` andrà subito dopo `dice` dentro `character`.

- [ ] **Step 2: Aggiungere chiavi in it.json**

Subito dopo la chiusura del blocco `character.dice` (ma ancora dentro `character`), aggiungi:

```json
"dice_overlay": {
  "open": "Apri lanciatore dadi",
  "close": "Chiudi lanciatore",
  "roll": "Lancia",
  "roll_failed": "Errore durante il lancio",
  "clear_kind": "Resetta",
  "rolling": "Sto lanciando…"
}
```

Ricorda la virgola dopo la parentesi precedente.

- [ ] **Step 3: Aggiungere chiavi in en.json**

Stesso punto in `webapp/src/locales/en.json`:

```json
"dice_overlay": {
  "open": "Open dice tray",
  "close": "Close dice tray",
  "roll": "Roll",
  "roll_failed": "Roll failed",
  "clear_kind": "Clear",
  "rolling": "Rolling…"
}
```

- [ ] **Step 4: Validare JSON**

```bash
cd webapp
node -e "require('./src/locales/it.json'); require('./src/locales/en.json'); console.log('ok')"
```

Expected: stampa `ok` (nessuna eccezione JSON.parse).

- [ ] **Step 5: Commit**

```bash
git add webapp/src/locales/it.json webapp/src/locales/en.json
git commit -m "$(cat <<'EOF'
feat(webapp): i18n keys for dice overlay widget

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `DiceOverlay` — scheletro con FAB + visibilità + resolver charId

Crea il componente con solo il FAB visibile (senza sidebar, senza lancio). Obiettivo: FAB appare/scompare correttamente in base alla route e `activeCharId`.

**Files:**
- Create: `webapp/src/components/DiceOverlay.tsx`
- Modify: `webapp/src/App.tsx:48-78`

- [ ] **Step 1: Creare `DiceOverlay.tsx` con FAB e visibility logic**

```tsx
import { useMemo } from 'react'
import { useLocation, matchPath } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Dices } from 'lucide-react'
import { useCharacterStore } from '@/store/characterStore'

function useOverlayVisibility(): { visible: boolean; charId: number | null } {
  const location = useLocation()
  const activeCharId = useCharacterStore((s) => s.activeCharId)

  return useMemo(() => {
    const path = location.pathname

    // Char pages: /char/:id/* EXCEPT /char/:id/dice
    const charDice = matchPath('/char/:id/dice', path)
    if (charDice) return { visible: false, charId: null }

    const charAny = matchPath('/char/:id/*', path) ?? matchPath('/char/:id', path)
    if (charAny) {
      const id = Number(charAny.params.id)
      return { visible: Number.isFinite(id), charId: Number.isFinite(id) ? id : null }
    }

    // Session room: /session/:id — uses activeCharId
    const session = matchPath('/session/:id', path)
    if (session && activeCharId != null) {
      return { visible: true, charId: activeCharId }
    }

    return { visible: false, charId: null }
  }, [location.pathname, activeCharId])
}

export default function DiceOverlay() {
  const { t } = useTranslation()
  const { visible } = useOverlayVisibility()

  if (!visible) return null

  return (
    <m.button
      type="button"
      aria-label={t('character.dice_overlay.open')}
      className="fixed bottom-4 right-4 z-[55] w-14 h-14 rounded-full
                 bg-gradient-to-br from-dnd-gold-deep to-dnd-gold-bright
                 border border-dnd-gold-dim shadow-halo-gold
                 flex items-center justify-center text-dnd-ink"
      whileTap={{ scale: 0.9 }}
      whileHover={{ scale: 1.05 }}
      initial={{ opacity: 0, scale: 0.6 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ type: 'spring', stiffness: 260, damping: 22 }}
    >
      <Dices size={26} />
    </m.button>
  )
}
```

- [ ] **Step 2: Montare `DiceOverlay` in `App.tsx`**

Apri `webapp/src/App.tsx`. Aggiungi l'import e montaggio.

Aggiungi import (vicino agli altri):
```tsx
import DiceOverlay from './components/DiceOverlay'
```

Modifica il blocco di return dentro `App`:

```tsx
<HashRouter>
  <ModalProvider>
    <DiceAnimationProvider>
      <Suspense fallback={<PageFallback />}>
        <Routes>
          {/* ...tutte le routes invariate... */}
        </Routes>
      </Suspense>
      <DiceOverlay />
    </DiceAnimationProvider>
  </ModalProvider>
</HashRouter>
```

Il componente va **dentro** `DiceAnimationProvider` (per usare `useDiceAnimation` in task successivi) e **dopo** `<Suspense>` così non blocca il render delle routes.

- [ ] **Step 3: Typecheck**

```bash
cd webapp
npx tsc --noEmit
```

Expected: 0 errori.

- [ ] **Step 4: Verifica manuale dev**

Chiedi all'utente di:
1. `npm run dev` già attivo.
2. Aprire `http://localhost:5173/#/` → **FAB non visibile** (character select).
3. Aprire un personaggio `#/char/1` → **FAB visibile** bottom-right.
4. Navigare a `#/char/1/hp` → FAB ancora visibile.
5. Navigare a `#/char/1/dice` → **FAB nascosto**.
6. Tornare a `#/char/1/spells` → FAB riappare.
7. Navigare a `#/session/join`, `#/session` → FAB non visibile.

Se `activeCharId` non è settato, `/session/:id` senza char → FAB nascosto. Test session room richiede char attivo (comportamento atteso).

- [ ] **Step 5: Commit**

```bash
git add webapp/src/components/DiceOverlay.tsx webapp/src/App.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): DiceOverlay skeleton — FAB + route-based visibility

Visible on /char/:id/* (except /dice) and /session/:id (with activeCharId).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Sidebar verticale sopra FAB con pulsanti kind + contatori

Aggiungi la sidebar che appare sopra il FAB con i 7 pulsanti dadi e mostra un badge counter quando `count > 0`. Tap FAB apre/chiude sidebar. Tap sul kind incrementa il counter. Niente lancio ancora.

**Files:**
- Modify: `webapp/src/components/DiceOverlay.tsx`

- [ ] **Step 1: Aggiungere stato e componente sidebar**

Sostituisci il contenuto di `webapp/src/components/DiceOverlay.tsx` con:

```tsx
import { useMemo, useState, useCallback } from 'react'
import { useLocation, matchPath } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { m, AnimatePresence } from 'framer-motion'
import { Dices } from 'lucide-react'
import DiceIcon from '@/components/ui/DiceIcon'
import { useCharacterStore } from '@/store/characterStore'
import { haptic } from '@/auth/telegram'
import type { DiceKind } from '@/dice/types'

const KINDS: DiceKind[] = ['d4', 'd6', 'd8', 'd10', 'd12', 'd20', 'd100']
const SIDES_FOR: Record<DiceKind, number> = {
  d4: 4, d6: 6, d8: 8, d10: 10, d12: 12, d20: 20, d100: 100,
}

type DicePool = Partial<Record<DiceKind, number>>

function useOverlayVisibility(): { visible: boolean; charId: number | null } {
  const location = useLocation()
  const activeCharId = useCharacterStore((s) => s.activeCharId)

  return useMemo(() => {
    const path = location.pathname
    if (matchPath('/char/:id/dice', path)) return { visible: false, charId: null }

    const charAny = matchPath('/char/:id/*', path) ?? matchPath('/char/:id', path)
    if (charAny) {
      const id = Number(charAny.params.id)
      return { visible: Number.isFinite(id), charId: Number.isFinite(id) ? id : null }
    }

    if (matchPath('/session/:id', path) && activeCharId != null) {
      return { visible: true, charId: activeCharId }
    }

    return { visible: false, charId: null }
  }, [location.pathname, activeCharId])
}

export default function DiceOverlay() {
  const { t } = useTranslation()
  const { visible } = useOverlayVisibility()
  const [open, setOpen] = useState(false)
  const [pool, setPool] = useState<DicePool>({})

  const increment = useCallback((kind: DiceKind) => {
    haptic.light()
    setPool((p) => ({ ...p, [kind]: (p[kind] ?? 0) + 1 }))
  }, [])

  const toggleOpen = useCallback(() => {
    haptic.light()
    setOpen((o) => !o)
  }, [])

  if (!visible) return null

  return (
    <div className="fixed bottom-4 right-4 z-[55]">
      {/* Sidebar kind buttons — appare sopra il FAB */}
      <AnimatePresence>
        {open && (
          <m.div
            className="absolute bottom-full right-0 mb-2 flex flex-col-reverse gap-1.5"
            initial={{ opacity: 0, scaleY: 0.6, transformOrigin: 'bottom' }}
            animate={{ opacity: 1, scaleY: 1 }}
            exit={{ opacity: 0, scaleY: 0.6 }}
            transition={{ type: 'spring', stiffness: 320, damping: 26 }}
          >
            {KINDS.map((kind, idx) => {
              const count = pool[kind] ?? 0
              return (
                <m.button
                  key={kind}
                  type="button"
                  onClick={() => increment(kind)}
                  className="relative w-12 h-12 rounded-2xl bg-dnd-surface-raised border border-dnd-border
                             flex items-center justify-center text-dnd-gold-bright
                             hover:border-dnd-gold/60 hover:shadow-halo-gold transition-[box-shadow,border-color]"
                  whileTap={{ scale: 0.9 }}
                  initial={{ opacity: 0, x: 10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: idx * 0.03 }}
                  aria-label={kind}
                >
                  <DiceIcon sides={SIDES_FOR[kind]} size={28} />
                  {count > 0 && (
                    <span className="absolute -top-1 -right-1 min-w-[20px] h-5 px-1
                                     rounded-full bg-dnd-crimson text-white text-[11px]
                                     font-bold font-mono flex items-center justify-center
                                     border border-dnd-surface-raised">
                      {count}
                    </span>
                  )}
                </m.button>
              )
            })}
          </m.div>
        )}
      </AnimatePresence>

      {/* FAB */}
      <m.button
        type="button"
        aria-label={open ? t('character.dice_overlay.close') : t('character.dice_overlay.open')}
        onClick={toggleOpen}
        className="w-14 h-14 rounded-full
                   bg-gradient-to-br from-dnd-gold-deep to-dnd-gold-bright
                   border border-dnd-gold-dim shadow-halo-gold
                   flex items-center justify-center text-dnd-ink"
        whileTap={{ scale: 0.9 }}
        whileHover={{ scale: 1.05 }}
        initial={{ opacity: 0, scale: 0.6 }}
        animate={{ opacity: 1, scale: 1, rotate: open ? 45 : 0 }}
        transition={{ type: 'spring', stiffness: 260, damping: 22 }}
      >
        <Dices size={26} />
      </m.button>
    </div>
  )
}
```

- [ ] **Step 2: Typecheck**

```bash
cd webapp
npx tsc --noEmit
```

Expected: 0 errori.

- [ ] **Step 3: Verifica manuale**

Chiedi all'utente di:
1. Aprire `#/char/1/hp` → FAB visibile.
2. Tap FAB → sidebar espande sopra, 7 pulsanti dadi dal basso (d4) all'alto (d100) con stagger.
3. Tap d6 → badge "1" appare su d6.
4. Tap d6 altre 2 volte → badge "3".
5. Tap d20 → badge "1" su d20, d6 resta "3".
6. Tap FAB di nuovo → sidebar si chiude, FAB ruota di 45° → 0°.
7. Riapri FAB → counters preservati (d6=3, d20=1).

- [ ] **Step 4: Commit**

```bash
git add webapp/src/components/DiceOverlay.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): DiceOverlay — sidebar with kind counters

Tap on a die increments its counter. Badge shown when count > 0.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Pulsante "Lancia" + roll multi-kind + animazione 3D

Aggiungi il bottone Lancia a sinistra del FAB (appare solo con pool non vuoto). Al tap: chiamate parallele `api.dice.roll`, poi `dice.play` multi-group, poi reset counters.

**Files:**
- Modify: `webapp/src/components/DiceOverlay.tsx`

- [ ] **Step 1: Aggiungere roll mutation e animazione**

In `DiceOverlay.tsx`, aggiungi al top degli import:

```tsx
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/client'
import { useDiceAnimation } from '@/dice/useDiceAnimation'
```

Dentro il componente `DiceOverlay`, dopo `const [pool, setPool] = ...`, aggiungi:

```tsx
const { visible, charId } = useOverlayVisibility()
const dice = useDiceAnimation()
const qc = useQueryClient()

type RollGroup = { kind: DiceKind; notation: string; rolls: number[]; total: number }

const rollMutation = useMutation({
  mutationFn: async (entries: Array<[DiceKind, number]>) => {
    if (!charId) throw new Error('no charId')
    const responses = await Promise.all(
      entries.map(([kind, count]) => api.dice.roll(charId, count, kind))
    )
    return entries.map(([kind], i) => {
      const r = responses[i]
      return { kind, notation: r.notation, rolls: r.rolls, total: r.total } as RollGroup
    })
  },
  onSuccess: async (groups) => {
    await dice.play({
      groups: groups.map((g) => ({ kind: g.kind, results: g.rolls })),
      interGroupMs: 150,
    })
    setPool({})
    setOpen(false)
    if (charId) qc.invalidateQueries({ queryKey: ['dice-history', charId] })
    haptic.medium()
    // Task 6 will handle result display here
  },
  onError: () => haptic.error(),
})

const entries = useMemo(
  () => (Object.entries(pool) as Array<[DiceKind, number]>).filter(([, n]) => n > 0),
  [pool]
)
const poolTotal = entries.reduce((s, [, n]) => s + n, 0)
const isRolling = rollMutation.isPending

const handleRoll = useCallback(() => {
  if (!entries.length || isRolling || !charId) return
  rollMutation.mutate(entries)
}, [entries, isRolling, charId, rollMutation])
```

**Importante:** sposta la chiamata `useOverlayVisibility()` (che già esiste) in cima per destrutturare anche `charId` come sopra. Rimuovi la vecchia riga `const { visible } = useOverlayVisibility()`.

- [ ] **Step 2: Aggiungere pulsante "Lancia" nel JSX**

Dentro il `<div className="fixed bottom-4 right-4 z-[55]">`, **prima** del FAB e dopo la sidebar, aggiungi:

```tsx
{/* Lancia button — appare a sinistra del FAB quando pool non vuoto */}
<AnimatePresence>
  {poolTotal > 0 && (
    <m.button
      type="button"
      onClick={handleRoll}
      disabled={isRolling}
      className="absolute right-full top-0 mr-2 h-14 px-5 rounded-2xl
                 bg-gradient-to-r from-dnd-gold-deep to-dnd-gold-bright
                 border border-dnd-gold-dim shadow-halo-gold
                 flex items-center justify-center gap-2 text-dnd-ink
                 font-cinzel uppercase tracking-wider font-bold text-sm
                 disabled:opacity-60 whitespace-nowrap"
      initial={{ opacity: 0, x: 10, scale: 0.9 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 10, scale: 0.9 }}
      whileTap={{ scale: 0.95 }}
      transition={{ type: 'spring', stiffness: 320, damping: 24 }}
    >
      <Dices size={18} />
      {isRolling ? t('character.dice_overlay.rolling') : t('character.dice_overlay.roll')}
    </m.button>
  )}
</AnimatePresence>
```

- [ ] **Step 3: Disabilitare sidebar durante roll**

Nel map dei kind, aggiungi `disabled={isRolling}` al `m.button` di ogni kind:

```tsx
<m.button
  key={kind}
  type="button"
  onClick={() => increment(kind)}
  disabled={isRolling}
  className="... disabled:opacity-40"
  ...
>
```

(Aggiungi anche la classe `disabled:opacity-40` al className esistente.)

- [ ] **Step 4: Typecheck**

```bash
cd webapp
npx tsc --noEmit
```

Expected: 0 errori.

- [ ] **Step 5: Verifica manuale**

Con setting `animate3d` ON (default) e reduced-motion OFF:
1. Aprire `#/char/1/hp`.
2. Tap FAB → sidebar aperta.
3. Tap d6 due volte → badge "2".
4. Tap d20 una volta → badge "1".
5. Pulsante "Lancia" appare a sinistra del FAB.
6. Tap Lancia → sidebar si chiude, scene 3D fullscreen parte, dadi rotolano (2 d6 + 1 d20 in sequenza con 150ms gap).
7. Dopo anim: scena scompare, pool svuotato (badge via).
8. Aprire `/char/1/history` → ultimi eventi includono `2d6` e `1d20` (history popolata).

Con `animate3d` OFF:
1. Apri Settings, disattiva animazione 3D.
2. Torna a `#/char/1/hp`, tap FAB, seleziona 1d20, Lancia.
3. Scena 3D non appare (comportamento `dice.play` no-op), ma i roll vengono comunque salvati in history.

- [ ] **Step 6: Commit**

```bash
git add webapp/src/components/DiceOverlay.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): DiceOverlay — Lancia button + multi-kind parallel roll + 3D anim

Rolls each kind via parallel POST /dice/roll, then chains dice.play() per group.
Respects animate3d setting (no-op if off). Resets pool post-roll.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Result overlay bottom-center con auto-dismiss 3s

Mostra il breakdown per-kind (scelta B — niente totale aggregato) in un overlay fisso bottom-center. Dismiss automatico dopo 3s oppure manuale su tap.

**Files:**
- Modify: `webapp/src/components/DiceOverlay.tsx`

- [ ] **Step 1: Aggiungere stato per risultato + timer**

Dopo gli altri useState/useCallback, prima del `rollMutation`, aggiungi:

```tsx
const [results, setResults] = useState<RollGroup[] | null>(null)
const [resultVisible, setResultVisible] = useState(false)

// Cleanup timer on unmount
const dismissTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
useEffect(() => () => {
  if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current)
}, [])

const showResults = useCallback((groups: RollGroup[]) => {
  setResults(groups)
  setResultVisible(true)
  if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current)
  dismissTimerRef.current = setTimeout(() => setResultVisible(false), 3000)
}, [])

const dismissResults = useCallback(() => {
  if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current)
  setResultVisible(false)
}, [])
```

Aggiungi gli import mancanti al top:
```tsx
import { useEffect, useRef, useMemo, useState, useCallback } from 'react'
```

Assicurati che `useRef` e `useEffect` siano importati da `'react'`.

- [ ] **Step 2: Chiamare `showResults` in `onSuccess`**

Modifica `onSuccess` del `rollMutation`:

```tsx
onSuccess: async (groups) => {
  await dice.play({
    groups: groups.map((g) => ({ kind: g.kind, results: g.rolls })),
    interGroupMs: 150,
  })
  setPool({})
  setOpen(false)
  if (charId) qc.invalidateQueries({ queryKey: ['dice-history', charId] })
  haptic.medium()
  showResults(groups)
},
```

- [ ] **Step 3: Aggiungere il JSX del result overlay**

Subito dopo la chiusura del `<div className="fixed bottom-4 right-4 z-[55]">` (livello top del componente, non dentro il div del widget), aggiungi un fragment / separato:

Tieni il return principale in un Fragment:
```tsx
return (
  <>
    {/* widget container */}
    <div className="fixed bottom-4 right-4 z-[55]">
      {/* ...sidebar + Lancia + FAB... */}
    </div>

    {/* Result overlay bottom-center */}
    <AnimatePresence>
      {resultVisible && results && results.length > 0 && (
        <m.button
          type="button"
          onClick={dismissResults}
          className="fixed bottom-24 left-1/2 -translate-x-1/2 z-[55]
                     max-w-xs w-[calc(100%-2rem)]
                     rounded-2xl bg-dnd-surface-raised/95 backdrop-blur-md
                     border border-dnd-gold-dim shadow-parchment-xl
                     px-4 py-3 text-left"
          initial={{ opacity: 0, y: 20, scale: 0.9 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 10, scale: 0.95 }}
          transition={{ type: 'spring', stiffness: 320, damping: 26 }}
        >
          <div className="space-y-1">
            {results.map((g, i) => (
              <div key={i} className="flex items-baseline justify-between gap-2 font-mono text-sm">
                <span className="text-dnd-gold-dim">
                  {g.notation}
                  {g.rolls.length > 1 && (
                    <span className="text-dnd-text-faint text-xs ml-1">
                      [{g.rolls.join('+')}]
                    </span>
                  )}
                </span>
                <span className="font-display font-black text-dnd-gold-bright text-lg">
                  {g.total}
                </span>
              </div>
            ))}
          </div>
        </m.button>
      )}
    </AnimatePresence>
  </>
)
```

- [ ] **Step 4: Typecheck**

```bash
cd webapp
npx tsc --noEmit
```

Expected: 0 errori.

- [ ] **Step 5: Verifica manuale**

1. Aprire `#/char/1/hp`.
2. FAB → seleziona 2d6 + 1d20 → Lancia.
3. Dopo anim 3D: overlay bottom-center appare con 2 righe: `2d6 [X+Y] = total` e `1d20 [Z] = total`.
4. Attendi 3s → overlay scompare con fade.
5. Ripeti → tap sull'overlay prima dei 3s → scompare immediatamente.
6. Con `animate3d` OFF: il result overlay appare immediatamente senza anim.

- [ ] **Step 6: Commit**

```bash
git add webapp/src/components/DiceOverlay.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): DiceOverlay — result overlay with 3s auto-dismiss

Per-group breakdown (notation + rolls + total), no aggregate total.
Tap to dismiss early, timer cleanup on unmount.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Long-press per resettare counter di un singolo kind

Long-press 500ms su un pulsante kind → reset di quel kind (porta counter a 0).

**Files:**
- Modify: `webapp/src/components/DiceOverlay.tsx`

- [ ] **Step 1: Implementare handler long-press**

Dentro `DiceOverlay`, prima del return:

```tsx
const longPressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
const longPressFiredRef = useRef(false)

const clearKind = useCallback((kind: DiceKind) => {
  haptic.medium()
  setPool((p) => {
    const { [kind]: _removed, ...rest } = p
    return rest
  })
}, [])

const handlePointerDown = useCallback((kind: DiceKind) => {
  longPressFiredRef.current = false
  longPressTimerRef.current = setTimeout(() => {
    longPressFiredRef.current = true
    clearKind(kind)
  }, 500)
}, [clearKind])

const handlePointerUpOrLeave = useCallback(() => {
  if (longPressTimerRef.current) {
    clearTimeout(longPressTimerRef.current)
    longPressTimerRef.current = null
  }
}, [])

const handleKindClick = useCallback((kind: DiceKind) => {
  if (longPressFiredRef.current) {
    longPressFiredRef.current = false
    return
  }
  increment(kind)
}, [increment])
```

Cleanup: aggiungi al `useEffect` di cleanup esistente:

```tsx
useEffect(() => () => {
  if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current)
  if (longPressTimerRef.current) clearTimeout(longPressTimerRef.current)
}, [])
```

- [ ] **Step 2: Collegare handlers al pulsante kind**

Nel JSX del kind button, sostituisci l'`onClick` esistente:

```tsx
<m.button
  key={kind}
  type="button"
  onClick={() => handleKindClick(kind)}
  onPointerDown={() => handlePointerDown(kind)}
  onPointerUp={handlePointerUpOrLeave}
  onPointerLeave={handlePointerUpOrLeave}
  onPointerCancel={handlePointerUpOrLeave}
  disabled={isRolling}
  className="..."
  ...
>
```

- [ ] **Step 3: Typecheck**

```bash
cd webapp
npx tsc --noEmit
```

- [ ] **Step 4: Verifica manuale**

1. Aprire `#/char/1/hp`, FAB → seleziona 3×d6 + 1×d20.
2. Tap breve su d6 → count 4.
3. Premi e tieni d6 per >500ms → haptic medium, badge d6 sparisce (count 0), d20 resta 1.
4. Short tap d20 → count 2.
5. Lancia funziona ancora regolarmente.

- [ ] **Step 5: Commit**

```bash
git add webapp/src/components/DiceOverlay.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): DiceOverlay — long-press 500ms to reset a kind counter

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Integrare animazione 3D in `SavingThrows.tsx`

Il setting `animate3d` deve partire anche qui (§1.6). Prima di aprire `RollResultModal`, chiama `dice.play`.

**Files:**
- Modify: `webapp/src/pages/SavingThrows.tsx:54-64`

- [ ] **Step 1: Importare `useDiceAnimation`**

In `SavingThrows.tsx`, aggiungi import:

```tsx
import { useDiceAnimation } from '@/dice/useDiceAnimation'
```

- [ ] **Step 2: Collegare l'hook e animare**

Dentro `SavingThrows`, subito dopo `const qc = useQueryClient()`:

```tsx
const dice = useDiceAnimation()
```

Modifica `rollMutation.onSuccess`:

```tsx
const rollMutation = useMutation({
  mutationFn: (ability: string) => api.characters.rollSavingThrow(charId, ability),
  onSuccess: async (result, ability) => {
    await dice.play({ groups: [{ kind: 'd20', results: [result.die] }] })
    setRollResult({
      result,
      title: `${t('character.saves.title')} — ${t(`character.stats.${ability}`)}`,
    })
    haptic.success()
  },
  onError: () => haptic.error(),
})
```

Note: `result.die` è il valore raw del d20 (1-20). `dice.play` è no-op se `animate3d` off → behaviour invariato.

- [ ] **Step 3: Typecheck**

```bash
cd webapp
npx tsc --noEmit
```

- [ ] **Step 4: Verifica manuale**

Setting `animate3d` ON:
1. Aprire `#/char/1/saves`.
2. Tap su ability (es. Destrezza) → scene 3D anima un d20.
3. Dopo anim: `RollResultModal` appare con die + bonus + total.

Setting `animate3d` OFF:
1. Tap ability → nessuna anim, modal appare immediatamente (comportamento attuale invariato).

- [ ] **Step 5: Commit**

```bash
git add webapp/src/pages/SavingThrows.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): animate saving throws d20 with dice.play()

Respects animate3d setting per §1.6. No-op when setting is off.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Integrare animazione 3D in `Skills.tsx`

Stesso pattern di Task 8.

**Files:**
- Modify: `webapp/src/pages/Skills.tsx:79-89`

- [ ] **Step 1: Import + hook**

In `Skills.tsx`, aggiungi:
```tsx
import { useDiceAnimation } from '@/dice/useDiceAnimation'
```

Dentro il componente, dopo `const qc = useQueryClient()`:
```tsx
const dice = useDiceAnimation()
```

- [ ] **Step 2: Modificare `rollMutation.onSuccess`**

```tsx
const rollMutation = useMutation({
  mutationFn: (skillName: string) => api.characters.rollSkill(charId, skillName),
  onSuccess: async (result, skillName) => {
    await dice.play({ groups: [{ kind: 'd20', results: [result.die] }] })
    setRollResult({
      result,
      title: t(`character.skills.${skillName}`),
    })
    haptic.success()
  },
  onError: () => haptic.error(),
})
```

- [ ] **Step 3: Typecheck**

```bash
cd webapp
npx tsc --noEmit
```

- [ ] **Step 4: Verifica manuale**

1. Aprire `#/char/1/skills`.
2. Con `animate3d` ON → tap su skill (es. Perception) → anim d20 + modal.
3. Con `animate3d` OFF → modal immediato senza anim.

- [ ] **Step 5: Commit**

```bash
git add webapp/src/pages/Skills.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): animate skills d20 with dice.play()

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Integrare animazione 3D in death save (`HP.tsx`)

**Files:**
- Modify: `webapp/src/pages/HP.tsx:77-85`

- [ ] **Step 1: Import + hook**

In `HP.tsx`, aggiungi ai già presenti:
```tsx
import { useDiceAnimation } from '@/dice/useDiceAnimation'
```

Dentro il componente, vicino agli altri hooks:
```tsx
const dice = useDiceAnimation()
```

- [ ] **Step 2: Modificare `deathRollMutation.onSuccess`**

```tsx
const deathRollMutation = useMutation({
  mutationFn: () => api.characters.rollDeathSave(charId),
  onSuccess: async (result) => {
    await dice.play({ groups: [{ kind: 'd20', results: [result.die] }] })
    setDeathRollResult(result)
    qc.invalidateQueries({ queryKey: ['character', charId] })
    haptic.success()
  },
  onError: () => haptic.error(),
})
```

`result.die` è il d20 raw (vedi `DeathSaveRollResult` in `api/client.ts:57-65`).

- [ ] **Step 3: Typecheck**

```bash
cd webapp
npx tsc --noEmit
```

- [ ] **Step 4: Verifica manuale**

1. Aprire `#/char/1/hp` con un char a HP=0 e `death_saves.stable=false` (se serve, portare HP a 0 con operazione DAMAGE).
2. Tap "Tira Salvezza Morte" → con `animate3d` ON: anim d20, poi update death saves + feedback visivo (es. success/fail indicator).
3. Verificare `haptic.success()` rimanga.
4. Con `animate3d` OFF → no anim, update immediato.

- [ ] **Step 5: Commit**

```bash
git add webapp/src/pages/HP.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): animate death save d20 with dice.play()

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Integrare animazione 3D in `SpellDamageSheet.tsx`

Usa i nuovi campi `main_kind/main_rolls/extra_kind/extra_rolls` introdotti in Task 1.

**Files:**
- Modify: `webapp/src/pages/spells/SpellDamageSheet.tsx:37-47`

- [ ] **Step 1: Import**

```tsx
import { useDiceAnimation } from '@/dice/useDiceAnimation'
import type { DiceKind } from '@/dice/types'
```

Dentro il componente:
```tsx
const dice = useDiceAnimation()
```

- [ ] **Step 2: Modificare `mutation.onSuccess` per animare prima del setResult**

Sostituisci il mutation esistente:

```tsx
const mutation = useMutation({
  mutationFn: (body: RollDamageRequest) => {
    if (!spell) throw new Error('no spell')
    return api.spells.rollDamage(charId, spell.id, body)
  },
  onSuccess: async (data) => {
    const groups = [{ kind: data.main_kind as DiceKind, results: data.main_rolls }]
    if (data.extra_kind && data.extra_rolls.length > 0) {
      groups.push({ kind: data.extra_kind as DiceKind, results: data.extra_rolls })
    }
    await dice.play({ groups, interGroupMs: 150 })
    haptic.success()
    setResult(data)
  },
  onError: () => haptic.error(),
})
```

- [ ] **Step 3: Typecheck**

```bash
cd webapp
npx tsc --noEmit
```

Expected: 0 errori (i nuovi campi esistono già grazie a Task 1).

- [ ] **Step 4: Verifica manuale**

1. Aprire `#/char/1/spells`, tap su un incantesimo con `damage_dice` (es. Firebolt 1d10, Fireball 8d6).
2. "Rolla danni" → sheet bottom.
3. Con `animate3d` ON: tap Rolla → scene 3D anima i main dice (es. 8 dadi d6) → scompare → view risultato nella sheet.
4. Ripeti aggiungendo `extra_dice = "2d4"` → anim 2 gruppi: prima i d6, poi 150ms dopo i d4.
5. Con `animate3d` OFF → sheet mostra risultato senza anim.
6. Toggle Critico → i conteggi raddoppiano (backend fa `*2`) → anim con più dadi.

- [ ] **Step 5: Commit**

```bash
git add webapp/src/pages/spells/SpellDamageSheet.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): animate spell damage rolls with dice.play()

Uses main_kind/main_rolls + extra_kind/extra_rolls from RollDamageResult
to play two separate groups when extra_dice is present.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Build prod, aggiornare roadmap, commit finale

**Files:**
- Modify: `docs/superpowers/roadmap.md:5,18`
- Build: `docs/app/*` (via `npm run build:prod`)

- [ ] **Step 1: Build prod e staging di `docs/app/`**

Per CLAUDE.md regola: le modifiche webapp richiedono build prod committato in `docs/app/`.

```bash
cd webapp
npm run build:prod
```

Il script:
1. Switcha `.env.local` a prod URL.
2. Esegue `tsc && vite build` (fallisce fast se typecheck rotto).
3. Ripristina `.env.local` a dev.
4. `git add docs/app/`.

Se lo script fallisce per TS errors: fixali e ri-esegui. Non saltare questo step.

- [ ] **Step 2: Aggiornare `docs/superpowers/roadmap.md`**

Due modifiche:

**Riga 5 (Stato globale):** aggiornare lista gruppi done.

Prima:
```
**Stato globale:** Gruppi A, B, C, F, G completati e mergeati; D, E, H pending.
```

Dopo:
```
**Stato globale:** Gruppi A, B, C, D, F, G completati e mergeati; E, H pending.
```

**Riga 18 (tabella):** cambiare lo stato di D.

Prima:
```
| D | Widget dadi overlay | §1.3 + §1.6 | ⬜ Pending | — |
```

Dopo:
```
| D | Widget dadi overlay | §1.3 + §1.6 | ✅ Done (PR #XX merged → main) | `feat/dice-overlay-gruppo-d` |
```

Nota: il PR number verrà noto dopo l'apertura della PR. Puoi lasciare `#XX` ora e aggiornarlo dopo il merge in un commit separato (pattern già usato in altri gruppi).

Inoltre aggiorna l'"Ordine consigliato" a riga ~284:

Prima:
```
✅ A → ✅ B → ✅ F → ✅ G → ✅ C → D → E completion → H
```

Dopo:
```
✅ A → ✅ B → ✅ F → ✅ G → ✅ C → ✅ D → E completion → H
```

- [ ] **Step 3: Commit finale**

```bash
git add docs/app/ docs/superpowers/roadmap.md
git commit -m "$(cat <<'EOF'
docs(roadmap): mark Gruppo D as done + prod build

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 4: Verifica manuale finale end-to-end**

Dev server attivo. Con `animate3d` ON:

1. `/char/1/hp` → FAB visibile → Lancia 1d20 → anim → result overlay → dismiss 3s.
2. `/char/1/saves` → tap save → anim d20 → modal.
3. `/char/1/skills` → tap skill → anim d20 → modal.
4. `/char/1/spells` → Rolla danni spell → anim multi-group se extra_dice → sheet.
5. `/char/1/hp` con HP=0 → death save → anim d20 → feedback.
6. `/char/1/dice` → FAB **nascosto**.
7. `/session/<id>` con `activeCharId` valido → FAB visibile.
8. Long-press kind button → counter sparisce.
9. Multi-kind: 2d6 + 1d8 + 1d20 → Lancia → 3 gruppi animati in sequenza → 3 righe nel result overlay.

Con `animate3d` OFF:
- Tutti i flow sopra funzionano senza anim, risultati appaiono immediatamente.

`/history`: ogni roll del widget appare come entries distinti per kind.

- [ ] **Step 5: Push + PR (manuale, l'utente lo fa quando pronto)**

Quando tutto ok:

```bash
git push -u origin feat/dice-overlay-gruppo-d
gh pr create --title "feat: Gruppo D — dice overlay widget + 3D animation" --body "$(cat <<'EOF'
## Summary
- Nuovo widget overlay globale bottom-right per tirare dadi rapidamente (multi-kind).
- Animazione 3D ora rispetta il setting `animate3d` anche in SavingThrows, Skills, Death Save, SpellDamageSheet.
- Estesa `RollDamageResult` con `main_kind/main_rolls/extra_kind/extra_rolls` per animare main vs extra dice separatamente.

Copre §1.3 + §1.6 di `istruzioni.md`.

## Test plan
- [ ] FAB visibile su tutte le pagine `/char/:id/*` eccetto `/dice` + su `/session/:id` con `activeCharId`.
- [ ] Sidebar sopra FAB, pulsanti d4→d100, badge counter.
- [ ] Long-press 500ms resetta kind.
- [ ] Lancia a sinistra del FAB, appare solo con pool non vuoto.
- [ ] Multi-kind parallel roll + anim sequenziale.
- [ ] Result overlay bottom-center 3s auto-dismiss.
- [ ] `animate3d` off → no anim, comportamento invariato.
- [ ] SavingThrows / Skills / Death Save / SpellDamageSheet animano con setting on.
- [ ] History popolata correttamente.
- [ ] Build prod in `docs/app/` staged.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-review (eseguito dall'autore del plan prima di consegnarlo)

**Spec coverage:**
- §1.3 overlay FAB + sidebar + Lancia + result 3s + history → Task 3-6.
- §1.3 contatori per kind → Task 4.
- §1.6 animazione rispetta setting (Saving Throws + coerenza altre pagine) → Task 8-11.
- Scope B (tutti i roll pages animano) → Task 8-11.
- Scope B+C visibilità → Task 3 (`useOverlayVisibility`).
- Scelta A multi-kind → Task 4-5.
- Scelta B breakdown per gruppo → Task 6.
- Scelta A reset post-Lancia → Task 5.

**Placeholder scan:** nessun TBD/TODO/"handle edge cases" senza codice. Ogni step ha codice completo. PR number `#XX` è intentional perché non noto fino al merge.

**Type consistency:**
- `DiceKind` importato da `@/dice/types` in tutti i file.
- `DicePool = Partial<Record<DiceKind, number>>` definito una volta in Task 4 e usato coerentemente.
- `RollGroup` type definito inline Task 5, usato in Task 6. Identico.
- `main_kind/main_rolls/extra_kind/extra_rolls` i nomi campo identici tra backend (Task 1 step 2) e TS (Task 1 step 4) e client (Task 11).
- Tutte le `onSuccess` modificate usano `await dice.play(...)` prima del setState → pattern consistente.

**Edge cases coperti:**
- Timer cleanup (Task 6 step 1, Task 7 step 1 aggiornamento useEffect).
- `isRolling` disabilita input (Task 5 step 3).
- `charId == null` guard (Task 5 step 1 mutation).
- Errore rollMutation → haptic.error (Task 5 step 1, già presente).

Nessun gap trovato.
