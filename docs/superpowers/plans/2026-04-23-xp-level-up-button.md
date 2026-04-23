# XP + Level-up button (Gruppo F) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aggiungere un bottone LEVEL UP e quick-XP buttons proporzionali alla pagina `/xp` (Experience.tsx) del webapp.

**Architecture:** Solo frontend. Nuova helper function in `xpThresholds.ts` per calcolare quick-XP amounts proporzionali. `Experience.tsx` aggiunge una sezione LEVEL UP full-width (click → PATCH `/xp` con `{set}`) e sostituisce il grid di bottoni fissi con uno dinamico basato sulla helper. 2 nuove chiavi i18n per IT/EN.

**Tech Stack:** React + TypeScript + TanStack Query + react-i18next + framer-motion + lucide-react. Tailwind utility classes. No test suite (CLAUDE.md: "No test suite or linter is configured") — verifica manuale in browser.

**Branch:** `feat/xp-level-up-gruppo-f` (già creato).
**Spec:** `docs/superpowers/specs/2026-04-23-xp-level-up-button-design.md`.

---

## File Structure

| File | Responsibility | Action |
|------|----------------|--------|
| `webapp/src/lib/xpThresholds.ts` | Soglie XP + helper di calcolo livello. Aggiungiamo `quickXpAmounts` per isolare la formula dalla pagina. | Modify |
| `webapp/src/pages/Experience.tsx` | UI pagina `/xp`. Rimuove `quickAmounts` fisso, aggiunge sezione LEVEL UP + grid dinamica. | Modify |
| `webapp/src/locales/it.json` | Testi IT. +2 chiavi sotto `character.xp`. | Modify |
| `webapp/src/locales/en.json` | Testi EN. +2 chiavi sotto `character.xp`. | Modify |
| `docs/app/` | Output produzione. Rebuild finale via `npm run build:prod`. | Modify (generated) |

---

### Task 1: Helper `quickXpAmounts` in xpThresholds.ts

**Files:**
- Modify: `webapp/src/lib/xpThresholds.ts`

- [ ] **Step 1: Aprire il file ed esaminare lo stato attuale**

Verifica che il file contenga `XP_THRESHOLDS`, `levelFromXp`, `getNextLevelThreshold` (già presenti dal Gruppo A).

- [ ] **Step 2: Aggiungere `quickXpAmounts` in fondo al file**

Apri `webapp/src/lib/xpThresholds.ts` e aggiungi in fondo (dopo `getNextLevelThreshold`):

```ts
/**
 * Quick-XP button amounts, proportional to XP remaining until the next level.
 *
 * Formula: 2% / 7% / 20% / 50% of `xpToNext`, rounded to multiples of 10,
 * with a minimum of 5 XP per button; adjacent duplicates after rounding are
 * removed so bottom-range progressions (e.g. xpToNext=50) collapse gracefully.
 *
 * Returns an empty array if `xpToNext <= 0` (character is at max level).
 */
export function quickXpAmounts(xpToNext: number): number[] {
  if (xpToNext <= 0) return []
  const PCTS = [0.02, 0.07, 0.20, 0.50] as const
  const MIN_AMOUNT = 5
  const raw = PCTS.map((p) => Math.max(MIN_AMOUNT, Math.round((p * xpToNext) / 10) * 10))
  return raw.filter((v, i) => i === 0 || v !== raw[i - 1])
}
```

- [ ] **Step 3: Verifica mentale del calcolo con alcuni esempi**

Traccia a mano i valori (niente test automatici nel progetto):

- `quickXpAmounts(300)` → raw `[Math.max(5,10), Math.max(5,20), Math.max(5,60), Math.max(5,150)]` → `[10, 20, 60, 150]` (no dedupe).
- `quickXpAmounts(2700)` → `[50, 190, 540, 1350]`.
- `quickXpAmounts(50)` → raw `[max(5,0)=5, max(5,0)=5, max(5,10)=10, max(5,30)=30]` → dedupe `[5, 10, 30]`.
- `quickXpAmounts(0)` → `[]`.

Se i valori non corrispondono, rivedi `Math.round`/`Math.max` (JS: `Math.round(2.5) === 3`).

- [ ] **Step 4: Commit**

```bash
git add webapp/src/lib/xpThresholds.ts
git commit -m "feat(webapp): add quickXpAmounts helper for proportional XP buttons

Computes 4 round-number XP amounts proportional to xpToNext
(2/7/20/50% with MIN=5, dedupe adjacent). Used by Experience.tsx
to replace fixed [50,100,200,500].

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: i18n keys IT + EN

**Files:**
- Modify: `webapp/src/locales/it.json`
- Modify: `webapp/src/locales/en.json`

- [ ] **Step 1: Aggiungere le chiavi in `it.json`**

Apri `webapp/src/locales/it.json`. Individua il blocco `"xp": { ... }` sotto `character` (circa linee 324-342). Subito prima della chiusura del blocco `"bar": { ... }` (quindi dopo `"hp_gained_toast"` e **prima** di `"bar":`), aggiungi due nuove chiavi:

Prima:
```json
      "hp_gained_toast": "+{{hp}} HP",
      "bar": {
```

Dopo:
```json
      "hp_gained_toast": "+{{hp}} HP",
      "level_up_cta": "SALI DI LIVELLO",
      "level_up_to": "Porta al livello {{level}}",
      "bar": {
```

- [ ] **Step 2: Aggiungere le stesse chiavi in `en.json`**

Apri `webapp/src/locales/en.json`. Stessa posizione (dentro `character.xp`, subito prima di `"bar":`):

Prima:
```json
      "hp_gained_toast": "+{{hp}} HP",
      "bar": {
```

Dopo:
```json
      "hp_gained_toast": "+{{hp}} HP",
      "level_up_cta": "LEVEL UP",
      "level_up_to": "Jump to level {{level}}",
      "bar": {
```

- [ ] **Step 3: Validare JSON**

Esegui (da WSL, solo lettura, nessun `uv sync`):

```bash
python3 -c "import json; json.load(open('webapp/src/locales/it.json'))"
python3 -c "import json; json.load(open('webapp/src/locales/en.json'))"
```

Expected: nessun output, exit code 0. Se invece ottieni un `JSONDecodeError`, controlla le virgole.

- [ ] **Step 4: Commit**

```bash
git add webapp/src/locales/it.json webapp/src/locales/en.json
git commit -m "feat(webapp): i18n keys for level-up CTA (Gruppo F)

Add character.xp.level_up_cta + level_up_to in IT/EN.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Experience.tsx — LEVEL UP button + dynamic quick-XP grid

**Files:**
- Modify: `webapp/src/pages/Experience.tsx`

- [ ] **Step 1: Aggiornare gli import**

Apri `webapp/src/pages/Experience.tsx`. Cambia l'import da `lucide-react` (linea 6) per includere `ChevronsUp`:

Prima:
```tsx
import { Sparkles, Star, Check } from 'lucide-react'
```

Dopo:
```tsx
import { Sparkles, Star, Check, ChevronsUp } from 'lucide-react'
```

Cambia l'import da `xpThresholds` (linea 16) per includere `quickXpAmounts`:

Prima:
```tsx
import { XP_THRESHOLDS, levelFromXp } from '@/lib/xpThresholds'
```

Dopo:
```tsx
import { XP_THRESHOLDS, levelFromXp, quickXpAmounts } from '@/lib/xpThresholds'
```

- [ ] **Step 2: Rimuovere la costante `quickAmounts` hardcoded**

Individua la linea (circa 70):

```tsx
  const quickAmounts = [50, 100, 200, 500]
```

Eliminala completamente.

- [ ] **Step 3: Aggiungere il calcolo dinamico e il check per liv 20**

Subito sotto il blocco dei calcoli XP (dopo la linea con `levelUpAvailable`, circa linea 62), aggiungi:

```tsx
  const isMaxLevel = level >= 20
  const quickAmounts = quickXpAmounts(xpToNext)
```

Così il blocco risulterà:

```tsx
  const totalClassLevel = (char.classes ?? []).reduce((s: number, c: { level: number }) => s + c.level, 0)
  const isSingleClass = (char.classes ?? []).length === 1
  const isMulticlass = (char.classes ?? []).length > 1
  const levelUpAvailable = isMulticlass && level > totalClassLevel
  const isMaxLevel = level >= 20
  const quickAmounts = quickXpAmounts(xpToNext)
```

- [ ] **Step 4: Aggiungere handler `handleLevelUp`**

Subito dopo `handleApply` (circa linea 68), aggiungi:

```tsx
  const handleLevelUp = () => {
    if (nextThreshold === null) return
    mutation.mutate({ set: nextThreshold })
  }
```

Il risultato completo della sezione handler sarà:

```tsx
  const handleApply = () => {
    const n = parseInt(addValue, 10)
    if (isNaN(n)) return
    mutation.mutate(setMode ? { set: n } : { add: n })
  }

  const handleLevelUp = () => {
    if (nextThreshold === null) return
    mutation.mutate({ set: nextThreshold })
  }
```

- [ ] **Step 5: Inserire la sezione LEVEL UP nel JSX prima della grid**

Individua la grid dei quick-XP (circa linee 188-201):

```tsx
      <div className="grid grid-cols-4 gap-2">
        {quickAmounts.map((n) => (
          <m.button
            key={n}
            onClick={() => mutation.mutate({ add: n })}
            className="min-h-[48px] rounded-xl bg-dnd-surface border border-dnd-border
                       hover:border-dnd-gold/60 transition-colors
                       font-mono font-bold text-dnd-gold-bright"
            whileTap={{ scale: 0.93 }}
          >
            +{n}
          </m.button>
        ))}
      </div>
```

Sostituiscila interamente con:

```tsx
      {!isMaxLevel && (
        <>
          <Button
            variant="primary"
            size="lg"
            fullWidth
            onClick={handleLevelUp}
            loading={mutation.isPending}
            icon={<ChevronsUp size={18} />}
            haptic="medium"
            aria-label={t('character.xp.level_up_to', { level: level + 1 })}
          >
            <span className="font-cinzel tracking-widest uppercase">
              {t('character.xp.level_up_cta')}
            </span>
          </Button>

          <div
            className="grid gap-2"
            style={{ gridTemplateColumns: `repeat(${quickAmounts.length}, minmax(0, 1fr))` }}
          >
            {quickAmounts.map((n) => (
              <m.button
                key={n}
                onClick={() => mutation.mutate({ add: n })}
                disabled={mutation.isPending}
                className="min-h-[48px] rounded-xl bg-dnd-surface border border-dnd-border
                           hover:border-dnd-gold/60 transition-colors
                           font-mono font-bold text-dnd-gold-bright
                           disabled:opacity-40 disabled:pointer-events-none"
                whileTap={{ scale: 0.93 }}
              >
                +{n}
              </m.button>
            ))}
          </div>
        </>
      )}
```

**Note sull'implementazione:**
- Usiamo `Button` (già importato) per il CTA: coerente con il resto del webapp, haptic medium, ripple gold, supporto `loading` automatico.
- `grid-cols-${N}` non può essere generato dinamicamente da Tailwind JIT quindi usiamo `style={{ gridTemplateColumns: ... }}` per supportare 2/3/4 bottoni quando `quickXpAmounts` fa dedupe.
- Il click sui bottoni quick-XP è ora `disabled` durante mutation pending (coerente con il CTA).
- `aria-label` usa `level_up_to` per accessibility ("Porta al livello {{level+1}}").

- [ ] **Step 6: Validazione TypeScript**

Dal terminale Windows (non WSL), esegui:

```bash
cd webapp
npx tsc --noEmit
```

Expected: nessun errore. Se ottieni errori di tipo su `quickXpAmounts` o `Button`, rivedi gli import.

*(Nota per Claude in WSL: chiedi all'utente di eseguire `npx tsc --noEmit` da Windows; non puoi eseguire comandi che toccano `.venv` o `node_modules` del repo da WSL secondo CLAUDE.md. `npx tsc` è sicuro perché non modifica `.venv`, ma per coerenza con l'ambiente dell'utente conviene farlo da Windows.)*

- [ ] **Step 7: Commit**

```bash
git add webapp/src/pages/Experience.tsx
git commit -m "feat(webapp): level-up button + proportional quick-XP grid (Gruppo F)

- LEVEL UP CTA full-width visible when level < 20; clicks PATCH /xp
  with {set: XP_THRESHOLDS[level]} to jump to the next tier.
- Quick-XP buttons now use quickXpAmounts(xpToNext) — 2/7/20/50% of
  remaining XP, rounded/deduped. Fixed [50,100,200,500] removed.
- Grid column count adapts to len(amounts) (2-4) so dedupe at liv 19
  doesn't leave blank slots.
- Both sections hidden at level 20 (manual input remains).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Verifica manuale in browser

**Files:** nessuno modificato in questa task.

Scenario di verifica descritti dalla spec §5. Eseguire con stack locale (API + webapp dev).

- [ ] **Step 1: Avvia lo stack locale**

Terminal 1 (Windows):
```bash
uv run uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

Terminal 2 (Windows):
```bash
cd webapp && npm run dev
```

Apri `http://localhost:5173/` e scegli (o crea) un personaggio single-class di liv 1.

- [ ] **Step 2: Verificare scenario 1 — liv 1 single-class, XP=0**

Vai su `/xp`. Controlla:
- Bottone LEVEL UP full-width sotto l'input numerico.
- Sotto il LEVEL UP: 4 bottoni quick-XP con valori `+10 +20 +60 +150`.
- Progress bar al 0%.

- [ ] **Step 3: Verificare scenario 2 — click LEVEL UP da liv 1 single-class**

Click su LEVEL UP.

Expected:
- XP = 300.
- Livello classe = 2.
- Toast "+N HP" (verde con cuore) visibile per ~2s.
- Progress bar a 0% del nuovo range (livello 2 → 3).
- Quick-XP buttons ora mostrano valori scalati (es. `+10 +40 +120 +300` con xpToNext=600).

- [ ] **Step 4: Verificare scenario 3 — click +540 a liv 3**

Porta il personaggio a liv 3 (click LEVEL UP un paio di volte). A liv 3 i bottoni quick-XP dovrebbero essere `+50 +190 +540 +1350` (xpToNext=2700).

Click `+540`.

Expected:
- XP aumentata di 540.
- Livello invariato (liv 3).
- Nessun toast HP.

- [ ] **Step 5: Verificare scenario 4 — liv 20**

Porta il personaggio a XP=355000+ (click LEVEL UP più volte oppure usa SET mode e inserisci `355000`).

Expected a liv 20:
- Bottone LEVEL UP **nascosto**.
- Grid quick-XP **nascosta**.
- Banner "MAX" visibile nella progress bar della hero.
- Input manuale + toggle add/set ancora visibili.

- [ ] **Step 6: Verificare scenario 5 — multiclass**

Crea (o modifica) un personaggio con 2 classi (es. Chierico 2 / Guerriero 1, XP=0). Vai su `/xp`.

Expected a liv 3 multiclass (XP=0):
- Nessun banner "livello disponibile" (level == totalClassLevel).
- Bottone LEVEL UP visibile.
- Click LEVEL UP → XP = 2700, banner "livello disponibile" appare, classi invariate (somma resta 3).
- Toast HP NON compare (backend non bumpa classe in multiclass).

- [ ] **Step 7: Verificare scenario 6 — edge case liv 19 xpToNext=50**

Porta il personaggio a liv 19 XP=354950 (usa SET mode). xpToNext = 355000-354950 = 50.

Expected:
- Bottone LEVEL UP visibile.
- Grid con **3 bottoni** (non 4): `+5 +10 +30` (grid-cols-3 applicata via `gridTemplateColumns` inline).

- [ ] **Step 8: Documentare i risultati della verifica**

Se tutti gli scenari passano, procedi al Task 5.

Se qualche scenario fallisce, NON marcare questo task completato: apri un bug, torna al Task corrispondente (1 se helper, 2 se i18n, 3 se UI), fixa, re-verifica.

---

### Task 5: Build di produzione + PR

**Files:**
- Modify: `webapp/docs/app/` (build output — generato, non editato a mano)

- [ ] **Step 1: Build produzione**

Dal terminale **Windows**:

```bash
cd webapp
npm run build:prod
```

Lo script (`webapp/scripts/build-prod.sh`):
1. Switcha `.env.local` a `VITE_API_BASE_URL=https://api.cischi.dev`.
2. Esegue `tsc && vite build`.
3. Ripristina `.env.local` a `http://localhost:8000`.
4. Esegue `git add docs/app/`.

Expected: script completa senza errori. Se `tsc` fallisce, torna al Task 3 Step 6 e fixa i tipi.

- [ ] **Step 2: Verifica che `docs/app/` sia staged**

```bash
git status
```

Expected: file sotto `docs/app/` (nuovi + modificati) sono staged. `.env.local` NON staged (gitignored).

- [ ] **Step 3: Commit build output**

```bash
git commit -m "chore(webapp): rebuild docs/app for Gruppo F

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 4: Push branch e apertura PR**

```bash
git push -u origin feat/xp-level-up-gruppo-f
```

Poi:

```bash
gh pr create --title "feat: Gruppo F — XP + level-up button (#istruzioni §1.8)" --body "$(cat <<'EOF'
## Summary
- Aggiunge bottone LEVEL UP in `/xp` (set XP al threshold del livello successivo).
- Sostituisce quick-XP fissi `[50,100,200,500]` con valori proporzionali (2/7/20/50% di `xpToNext`).
- Nasconde LEVEL UP + grid a livello 20.

Spec: `docs/superpowers/specs/2026-04-23-xp-level-up-button-design.md`.
Plan: `docs/superpowers/plans/2026-04-23-xp-level-up-button.md`.
Roadmap: Gruppo F — parte della decomposizione di `istruzioni.md` §1.8.

## Test plan
- [x] Liv 1 single-class → quick buttons `[10, 20, 60, 150]`, LEVEL UP visibile.
- [x] Click LEVEL UP da liv 1 → XP=300, classe liv 2, toast `+N HP`.
- [x] Click `+540` a liv 3 → XP+540, liv invariato.
- [x] Liv 20 → LEVEL UP e quick-XP nascosti, "MAX" in progress bar.
- [x] Multiclass → click LEVEL UP → XP=2700, banner "livello disponibile" appare, classi invariate.
- [x] Liv 19 xpToNext=50 → 3 bottoni `[5, 10, 30]`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 5: Aggiorna roadmap post-merge**

Dopo che la PR è merged, nuova sessione o feature branch: aggiornare `docs/superpowers/roadmap.md`:
- Riga tabella Gruppo F: `⬜ Pending` → `✅ Done (PR #<n> merged → main)`.
- Sezione `## Gruppo F`: header `⬜` → `✅`, aggiungi breve riga stato.
- Sezione "Ordine consigliato": `→ F →` diventa `→ ✅ F →`.

---

## Verifica completa del plan

Dopo aver completato tutti i task:
- [ ] Tutti i commit sul branch `feat/xp-level-up-gruppo-f`.
- [ ] PR aperta e verifica manuale superata.
- [ ] `docs/app/` rigenerato e committato.
- [ ] Roadmap aggiornata post-merge.
