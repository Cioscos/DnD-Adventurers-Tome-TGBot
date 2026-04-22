# UX Polish — Hero Section & Pagine Correlate (Gruppo A) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rifinire l'hero section del character sheet (XP bar, velocità icon-only floating, condizioni icon-only, abilità passive cliccabili, celle caratteristiche cliccabili), rendere cliccabili le breadcrumb del `Layout`, aggiungere descrizioni inline ai livelli di spossatezza in `/conditions`, e ridisegnare il layout degli editor della pagina `/ac` (Base full-width + Scudo/Magia affiancati).

**Architecture:** Solo frontend webapp (`webapp/src/**`). Riuso componente esistente `StatPill` via estensione props; creo 2 nuovi componenti (`HeroXPBar`, `PassiveAbilityDetailModal`) e 1 nuovo lib (`xpThresholds.ts`). Estendo `lib/conditions.ts` con mappa icone. Nessuna modifica a backend/API/DB.

**Tech Stack:** React 18.3, TypeScript 5.5, Vite 5.4, framer-motion 11, TanStack Query 5, react-router-dom 6, react-i18next 15, lucide-react 1, Tailwind CSS 3.4.

**Testing approach:** Questo repo non ha test suite automatizzata. Ogni task è verificato via `npx tsc --noEmit` (TypeScript typecheck) per correttezza statica. La verifica funzionale è manuale in dev server ed è concentrata in Task 11. Il ciclo TDD red-green-refactor non si applica — i commit frequenti garantiscono rollback granulare.

**Branch:** `feat/ux-polish-hero-section` (già creata e con lo spec committato).

**Spec di riferimento:** `docs/superpowers/specs/2026-04-22-ux-polish-hero-section-design.md`

---

## File map

**Creati:**
- `webapp/src/lib/xpThresholds.ts` — `XP_THRESHOLDS`, `levelFromXp`, `getNextLevelThreshold`.
- `webapp/src/components/ui/HeroXPBar.tsx` — barra progressiva XP con pulsante LEVEL UP inline.
- `webapp/src/pages/abilities/PassiveAbilityDetailModal.tsx` — modale descrizione abilità passiva.

**Modificati:**
- `webapp/src/lib/conditions.ts` — aggiunta mappa `CONDITION_ICONS`.
- `webapp/src/components/ui/StatPill.tsx` — nuovi prop `iconOnly` + `revealOnTap` + `aria-label`.
- `webapp/src/pages/Experience.tsx` — import da `lib/xpThresholds`, rimossi duplicati locali.
- `webapp/src/pages/CharacterMain.tsx` — redesign hero section.
- `webapp/src/components/Layout.tsx` — breadcrumb prev/next cliccabili.
- `webapp/src/pages/Conditions.tsx` — import `CONDITION_ICONS` + descrizioni spossatezza inline.
- `webapp/src/pages/ArmorClass.tsx` — nuovo layout editor (Base full-width + Scudo/Magia grid).
- `webapp/src/locales/it.json` + `en.json` — chiavi nuove (XP bar, modale abilità, layout nav).
- `docs/app/**` — rebuild di produzione.

---

## Task 1 — Estrazione XP_THRESHOLDS in lib

**Files:**
- Create: `webapp/src/lib/xpThresholds.ts`
- Modify: `webapp/src/pages/Experience.tsx` (righe 16, 18-25, 54-55)

- [ ] **Step 1: Crea il nuovo modulo `xpThresholds.ts`**

Crea `webapp/src/lib/xpThresholds.ts` con il contenuto esatto:

```ts
/**
 * D&D 5e experience-point thresholds (SRD).
 * Index `i` = XP required to reach level `i + 1`.
 * Index 0 (= 0) is the baseline for level 1.
 */
export const XP_THRESHOLDS: readonly number[] = [
  0,
  300, 900, 2700, 6500, 14000,
  23000, 34000, 48000, 64000, 85000,
  100000, 120000, 140000, 165000, 195000,
  225000, 265000, 305000, 355000,
] as const

/** Derive the current character level from accumulated XP (capped at 20). */
export function levelFromXp(xp: number): number {
  let level = 1
  for (let i = 1; i < XP_THRESHOLDS.length; i++) {
    if (xp >= XP_THRESHOLDS[i]) level = i + 1
    else break
  }
  return Math.min(level, 20)
}

/** XP threshold needed to reach `currentLevel + 1`. Null if at cap. */
export function getNextLevelThreshold(currentLevel: number): number | null {
  return XP_THRESHOLDS[currentLevel] ?? null
}
```

- [ ] **Step 2: Refactor `Experience.tsx` per importare dal nuovo modulo**

In `webapp/src/pages/Experience.tsx`:

Al top dei file, rimuovi la riga 16:

```ts
const XP_THRESHOLDS = [0, 300, 900, 2700, 6500, 14000, 23000, 34000, 48000, 64000, 85000, 100000, 120000, 140000, 165000, 195000, 225000, 265000, 305000, 355000]
```

e la funzione `levelFromXp` (righe 18-25):

```ts
function levelFromXp(xp: number) {
  let level = 1
  for (let i = 1; i < XP_THRESHOLDS.length; i++) {
    if (xp >= XP_THRESHOLDS[i]) level = i + 1
    else break
  }
  return Math.min(level, 20)
}
```

Al loro posto, aggiungi l'import dopo gli altri import esterni (subito dopo la riga 13 `import { spring } from '@/styles/motion'`):

```ts
import { XP_THRESHOLDS, levelFromXp } from '@/lib/xpThresholds'
```

Le righe che usano `XP_THRESHOLDS` e `levelFromXp` (righe ~54-56) restano identiche — funzionano col nuovo import.

- [ ] **Step 3: Verifica TypeScript**

Run:
```bash
cd webapp && npx tsc --noEmit
```
Expected: zero errori.

- [ ] **Step 4: Commit**

```bash
git add webapp/src/lib/xpThresholds.ts webapp/src/pages/Experience.tsx
git commit -m "refactor(webapp): extract XP thresholds to lib/xpThresholds

Sposta XP_THRESHOLDS e levelFromXp da Experience.tsx a
webapp/src/lib/xpThresholds.ts per riuso nel nuovo HeroXPBar.
Aggiunge getNextLevelThreshold() helper. Nessun cambio funzionale.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2 — CONDITION_ICONS in lib/conditions

**Files:**
- Modify: `webapp/src/lib/conditions.ts`

- [ ] **Step 1: Aggiungi la mappa `CONDITION_ICONS`**

In `webapp/src/lib/conditions.ts`, aggiungi in testa (sopra `formatCondition`) e in coda le nuove esportazioni. Il file finale diventa:

```ts
import type { TFunction } from 'i18next'
import {
  EyeOff, Heart, VolumeX, Ghost, Link2, Cloud, Eye, Zap, Mountain,
  FlaskConical, ArrowDown, Lock, Sparkle, Moon, Flame,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

/**
 * Icon lookup for the 14 standard 5e conditions plus exhaustion.
 * Used by the hero section (icon-only chips) and the /conditions page (icon+label).
 */
export const CONDITION_ICONS: Record<string, LucideIcon> = {
  blinded:       EyeOff,
  charmed:       Heart,
  deafened:      VolumeX,
  frightened:    Ghost,
  grappled:      Link2,
  incapacitated: Cloud,
  invisible:     Eye,
  paralyzed:     Zap,
  petrified:     Mountain,
  poisoned:      FlaskConical,
  prone:         ArrowDown,
  restrained:    Lock,
  stunned:       Sparkle,
  unconscious:   Moon,
  exhaustion:    Flame,
}

/**
 * Localise a condition label for display in a pill / list.
 *
 * Exhaustion renders with its level (e.g. "Spossatezza (livello 3)") when
 * val is a positive number; all other conditions render by slug.
 */
export function formatCondition(
  key: string,
  val: unknown,
  t: TFunction,
): string {
  if (key === 'exhaustion' && typeof val === 'number' && val > 0) {
    return t('character.conditions.exhaustion', { level: val })
  }
  return t(`character.conditions.${key}`)
}
```

- [ ] **Step 2: Verifica TypeScript**

Run:
```bash
cd webapp && npx tsc --noEmit
```
Expected: zero errori.

- [ ] **Step 3: Commit**

```bash
git add webapp/src/lib/conditions.ts
git commit -m "feat(webapp): add CONDITION_ICONS map to lib/conditions

Estrae la mappa chiave→icona delle 14 condizioni standard + exhaustion
da Conditions.tsx a lib/conditions.ts. Sarà riusata dall'hero section
per i chip condizione icon-only. Conditions.tsx verrà aggiornato in
un task successivo.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3 — StatPill: iconOnly + revealOnTap

**Files:**
- Modify: `webapp/src/components/ui/StatPill.tsx`

- [ ] **Step 1: Riscrivi `StatPill.tsx` con i nuovi prop**

Sostituisci completamente il contenuto di `webapp/src/components/ui/StatPill.tsx` con:

```tsx
import React, { useState, useRef, useEffect } from 'react'
import { m } from 'framer-motion'

interface StatPillProps {
  icon?: React.ReactNode
  label?: string
  value: React.ReactNode
  tone?: 'default' | 'gold' | 'arcane' | 'crimson' | 'emerald' | 'cobalt' | 'amber'
  size?: 'sm' | 'md'
  onClick?: () => void
  /**
   * Hide `label` and `value`, show only `icon`.
   * When true, the component becomes focusable (button) with an aria-label.
   */
  iconOnly?: boolean
  /**
   * When `iconOnly` is true, tapping reveals the value inline for `revealDurationMs`
   * then returns to icon-only. Tapping again while revealed resets the timer.
   */
  revealOnTap?: boolean
  revealDurationMs?: number
  'aria-label'?: string
  className?: string
}

function toneClasses(tone: StatPillProps['tone']): string {
  switch (tone) {
    case 'gold':
      return 'bg-dnd-chip-bg border-dnd-gold/40 text-dnd-gold-bright'
    case 'arcane':
      return 'bg-[rgba(155,89,182,0.12)] border-dnd-arcane/40 text-dnd-arcane-bright'
    case 'crimson':
      return 'bg-[rgba(179,58,58,0.12)] border-dnd-crimson/40 text-[var(--dnd-crimson-bright)]'
    case 'emerald':
      return 'bg-[rgba(63,166,106,0.12)] border-dnd-emerald/40 text-[var(--dnd-emerald-bright)]'
    case 'cobalt':
      return 'bg-[rgba(58,124,165,0.12)] border-dnd-cobalt/40 text-[var(--dnd-cobalt-bright)]'
    case 'amber':
      return 'bg-[rgba(232,165,71,0.12)] border-dnd-amber/50 text-[var(--dnd-amber)]'
    case 'default':
    default:
      return 'bg-dnd-surface border-dnd-border text-dnd-text'
  }
}

function StatPillInner({
  icon,
  label,
  value,
  tone = 'default',
  size = 'md',
  onClick,
  iconOnly = false,
  revealOnTap = false,
  revealDurationMs = 2000,
  'aria-label': ariaLabelProp,
  className = '',
}: StatPillProps) {
  const [revealed, setRevealed] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [])

  const handleClick = () => {
    if (iconOnly && revealOnTap) {
      setRevealed(true)
      if (timerRef.current) clearTimeout(timerRef.current)
      timerRef.current = setTimeout(() => setRevealed(false), revealDurationMs)
    }
    onClick?.()
  }

  const isInteractive = !!onClick || (iconOnly && revealOnTap)
  const showValue = !iconOnly || revealed
  const showLabel = !iconOnly && !!label
  const padding = size === 'sm' ? 'px-2 py-1 text-[11px]' : 'px-2.5 py-1 text-xs'
  const cls = `inline-flex items-center gap-1.5 rounded-full border font-medium font-body ${padding} ${toneClasses(tone)} ${isInteractive ? 'cursor-pointer' : ''} ${className}`
  const Component: React.ElementType = isInteractive ? m.button : m.span

  const resolvedAriaLabel =
    ariaLabelProp ??
    (iconOnly && typeof value === 'string' ? value : undefined)

  return (
    <Component
      className={cls}
      onClick={isInteractive ? handleClick : undefined}
      whileTap={isInteractive ? { scale: 0.95 } : undefined}
      aria-label={resolvedAriaLabel}
    >
      {icon && <span className="shrink-0">{icon}</span>}
      {showLabel && <span className="opacity-70">{label}</span>}
      {showValue && <span className="font-mono font-bold">{value}</span>}
    </Component>
  )
}

const StatPill = React.memo(StatPillInner)
export default StatPill
```

Novità rispetto all'originale:
- Prop `iconOnly`, `revealOnTap`, `revealDurationMs`, `aria-label`.
- `useState(revealed)` + `useRef(timerRef)` + `useEffect` cleanup su unmount.
- `handleClick` combina reveal + onClick.
- `isInteractive` include anche `iconOnly && revealOnTap` (diventa bottone per il tap reveal anche senza onClick esplicito).
- `aria-label` auto-derivato da `value` (se stringa) quando `iconOnly`.

- [ ] **Step 2: Verifica TypeScript**

Run:
```bash
cd webapp && npx tsc --noEmit
```
Expected: zero errori. Gli usi esistenti di `<StatPill>` senza i nuovi prop continuano a funzionare (tutti opzionali).

- [ ] **Step 3: Commit**

```bash
git add webapp/src/components/ui/StatPill.tsx
git commit -m "feat(webapp): add iconOnly + revealOnTap props to StatPill

Estende StatPill con:
- iconOnly: nasconde label/value, mostra solo icona (diventa focusable)
- revealOnTap: in combinazione con iconOnly, il tap rivela il value per
  2s poi lo nasconde. Tap successivi resettano il timer.
- aria-label override + auto-derivation da value quando iconOnly.

Backward compatible: tutti i prop nuovi sono opzionali.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4 — HeroXPBar component

**Files:**
- Create: `webapp/src/components/ui/HeroXPBar.tsx`

- [ ] **Step 1: Crea il componente `HeroXPBar`**

Crea `webapp/src/components/ui/HeroXPBar.tsx`:

```tsx
import { m } from 'framer-motion'
import { useTranslation } from 'react-i18next'
import { Star, ChevronsUp } from 'lucide-react'
import { XP_THRESHOLDS, levelFromXp } from '@/lib/xpThresholds'
import { haptic } from '@/auth/telegram'

interface HeroXPBarProps {
  currentXP: number
  totalClassLevel: number
  onLevelUpReady: () => void
  className?: string
}

export default function HeroXPBar({
  currentXP,
  totalClassLevel,
  onLevelUpReady,
  className = '',
}: HeroXPBarProps) {
  const { t } = useTranslation()

  const xpLevel = levelFromXp(currentXP)
  const prevThreshold = xpLevel > 1 ? XP_THRESHOLDS[xpLevel - 1] : 0
  const nextThreshold: number | null = XP_THRESHOLDS[xpLevel] ?? null
  const levelUpReady = xpLevel > totalClassLevel
  const progressPct = nextThreshold
    ? Math.min(100, Math.max(0, Math.round(((currentXP - prevThreshold) / (nextThreshold - prevThreshold)) * 100)))
    : 100

  const handleLevelUp = () => {
    haptic.medium()
    onLevelUpReady()
  }

  const rightLabel = levelUpReady ? null : (
    nextThreshold !== null
      ? t('character.xp.bar.progress', {
          current: currentXP.toLocaleString(),
          threshold: nextThreshold.toLocaleString(),
        })
      : t('character.xp.bar.max')
  )

  return (
    <div
      className={`mt-3 ${className}`}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={nextThreshold ?? currentXP}
      aria-valuenow={currentXP}
      aria-label={t('character.xp.bar.level_label', { level: xpLevel })}
    >
      <div className="flex items-center justify-between gap-2 mb-1.5 text-xs">
        <span className="inline-flex items-center gap-1 text-dnd-gold-bright font-cinzel font-bold">
          <Star size={12} />
          {t('character.xp.bar.level_label', { level: xpLevel })}
        </span>
        {levelUpReady ? (
          <m.button
            type="button"
            onClick={handleLevelUp}
            whileTap={{ scale: 0.95 }}
            className="inline-flex items-center gap-1 animate-shimmer bg-gradient-to-r from-dnd-gold-deep to-dnd-gold-bright text-black px-2.5 py-0.5 rounded-md text-[10px] font-bold tracking-widest uppercase"
          >
            <ChevronsUp size={12} />
            {t('character.xp.bar.level_up')}
          </m.button>
        ) : (
          <span className="font-mono text-dnd-gold">{rightLabel}</span>
        )}
      </div>
      <div className="h-1.5 bg-dnd-surface border border-dnd-border rounded-full overflow-hidden">
        <m.div
          className="h-full bg-gradient-to-r from-dnd-gold-deep to-dnd-gold-bright"
          style={{
            boxShadow: levelUpReady ? '0 0 8px var(--dnd-gold-glow)' : undefined,
          }}
          initial={{ width: 0 }}
          animate={{ width: `${progressPct}%` }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
        />
      </div>
    </div>
  )
}
```

Note:
- `levelFromXp` e `XP_THRESHOLDS` vengono da `lib/xpThresholds.ts` (creato in Task 1).
- `haptic.medium()` è il feedback tattile più forte per un'azione importante (level-up).
- Icone: `Star` + `ChevronsUp` da `lucide-react`.
- Le chiavi i18n (`character.xp.bar.*`) saranno aggiunte in Task 6. A questo punto `tsc` non si lamenta (i18next non controlla chiavi a compile-time), ma a runtime le label saranno ancora nel formato `character.xp.bar.level_label` finché Task 6 non è fatto.

- [ ] **Step 2: Verifica TypeScript**

Run:
```bash
cd webapp && npx tsc --noEmit
```
Expected: zero errori.

- [ ] **Step 3: Commit**

```bash
git add webapp/src/components/ui/HeroXPBar.tsx
git commit -m "feat(webapp): add HeroXPBar component

Barra progressiva XP per l'hero section del character sheet. Renderizza:
- Label sinistra 'LIV N' + valori 'current/next' a destra, OPPURE
- Pulsante LEVEL UP inline quando levelFromXp(xp) > total_level
  (tipicamente multiclasse con XP pendenti).

A livello 20 mostra 'MAX' invece dei numeri. Include role='progressbar'
con aria-valuemin/max/now per accessibilità.

Il componente deriva internamente il livello da XP via levelFromXp,
non dipende da un campo char.level (che non esiste nel backend).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5 — PassiveAbilityDetailModal

**Files:**
- Create: `webapp/src/pages/abilities/PassiveAbilityDetailModal.tsx`

- [ ] **Step 1: Verifica che la directory esista**

```bash
ls webapp/src/pages/abilities/ 2>/dev/null || mkdir -p webapp/src/pages/abilities
```

- [ ] **Step 2: Crea il componente modale**

Crea `webapp/src/pages/abilities/PassiveAbilityDetailModal.tsx`:

```tsx
import { useTranslation } from 'react-i18next'
import DndButton from '@/components/DndButton'
import type { Ability } from '@/types'

interface PassiveAbilityDetailModalProps {
  ability: Ability
  onClose: () => void
}

export default function PassiveAbilityDetailModal({
  ability,
  onClose,
}: PassiveAbilityDetailModalProps) {
  const { t } = useTranslation()

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-end z-50 p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="passive-ability-title"
    >
      <div
        className="w-full rounded-2xl bg-dnd-surface-elevated p-4 space-y-3"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h3 id="passive-ability-title" className="font-semibold font-cinzel text-dnd-gold">
            {ability.name}
          </h3>
          <button
            onClick={onClose}
            aria-label={t('common.close')}
            className="text-dnd-text-secondary text-sm p-1"
          >
            &#x2715;
          </button>
        </div>
        {ability.description ? (
          <p className="text-sm text-dnd-text font-body leading-relaxed whitespace-pre-line">
            {ability.description}
          </p>
        ) : (
          <p className="text-sm italic text-dnd-text-faint font-body">
            {t('character.abilities.detail.no_description')}
          </p>
        )}
        <DndButton variant="secondary" onClick={onClose} className="w-full">
          {t('common.close')}
        </DndButton>
      </div>
    </div>
  )
}
```

Pattern ricalcato da `webapp/src/pages/conditions/ConditionDetailModal.tsx` (overlay nero semi-trasparente, sheet bottom, `onClick={onClose}` su overlay + `stopPropagation` sul contenitore).

- [ ] **Step 3: Verifica TypeScript**

Run:
```bash
cd webapp && npx tsc --noEmit
```
Expected: zero errori.

- [ ] **Step 4: Commit**

```bash
git add webapp/src/pages/abilities/PassiveAbilityDetailModal.tsx
git commit -m "feat(webapp): add PassiveAbilityDetailModal

Modale di dettaglio per le abilità passive, invocato dal tap sui chip
nell'hero section. Mostra nome + descrizione dell'Ability; se la
description è assente mostra 'Nessuna descrizione disponibile' in
corsivo come fallback.

Pattern basato su ConditionDetailModal (overlay + bottom sheet).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6 — i18n: chiavi nuove per hero section

**Files:**
- Modify: `webapp/src/locales/it.json`
- Modify: `webapp/src/locales/en.json`

- [ ] **Step 1: Aggiungi le chiavi italiane**

Apri `webapp/src/locales/it.json`. All'interno del nodo `"character"` aggiungi un figlio `"xp"` (se non esiste già come `xp` con altre chiavi, aggiungi `bar` al suo interno) e un figlio `"abilities"` (stesso discorso). Poi a livello top aggiungi un nodo `"layout"`.

**Snippet da integrare** (da mergere — usa l'editor JSON, NON incollare letteralmente un doppione):

Nodo `character.xp.bar` (dentro `character.xp`, che nel file esiste già per `title` e `add_fast`):

```json
"bar": {
  "level_label": "LIV {{level}}",
  "progress": "{{current}} / {{threshold}}",
  "level_up": "LEVEL UP",
  "max": "MAX"
}
```

Nodo `character.abilities.detail` (dentro `character.abilities`, che nel file esiste per altre chiavi):

```json
"detail": {
  "no_description": "Nessuna descrizione disponibile"
}
```

Nodo top-level `layout` (nuovo nodo al pari di `character`, `common`, etc.):

```json
"layout": {
  "nav": {
    "go_to": "Vai a {{page}}"
  }
}
```

Per verificare: dopo il merge, `jq '.character.xp.bar' webapp/src/locales/it.json` deve mostrare l'oggetto con 4 chiavi.

- [ ] **Step 2: Aggiungi le chiavi inglesi equivalenti**

Apri `webapp/src/locales/en.json` e aggiungi gli stessi nodi con traduzioni:

```json
"bar": {
  "level_label": "LVL {{level}}",
  "progress": "{{current}} / {{threshold}}",
  "level_up": "LEVEL UP",
  "max": "MAX"
}
```

```json
"detail": {
  "no_description": "No description available"
}
```

```json
"layout": {
  "nav": {
    "go_to": "Go to {{page}}"
  }
}
```

- [ ] **Step 3: Verifica JSON ben formato**

Run:
```bash
jq . webapp/src/locales/it.json > /dev/null && echo "it.json OK"
jq . webapp/src/locales/en.json > /dev/null && echo "en.json OK"
```
Expected: entrambi stampano "OK" (nessun errore di parsing).

Se `jq` non è installato, usa Node:
```bash
node -e "JSON.parse(require('fs').readFileSync('webapp/src/locales/it.json','utf8')); console.log('it.json OK')"
node -e "JSON.parse(require('fs').readFileSync('webapp/src/locales/en.json','utf8')); console.log('en.json OK')"
```

- [ ] **Step 4: Commit**

```bash
git add webapp/src/locales/it.json webapp/src/locales/en.json
git commit -m "feat(webapp): add i18n keys for hero section UX polish

Nuove chiavi (it + en):
- character.xp.bar.{level_label, progress, level_up, max} — HeroXPBar
- character.abilities.detail.no_description — PassiveAbilityDetailModal fallback
- layout.nav.go_to — aria-label per prev/next breadcrumb cliccabili

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7 — Redesign hero section (`CharacterMain.tsx`)

**Files:**
- Modify: `webapp/src/pages/CharacterMain.tsx`

Questo è il task più corposo. Cambio: importi nuovi, stato locale aggiuntivo, rimozione meta row XP+Speed, aggiunta `HeroXPBar`, modifica chip passive abilities/condizioni, aggiunta velocità floating, celle ability score cliccabili.

- [ ] **Step 1: Aggiorna gli import in cima al file**

In `webapp/src/pages/CharacterMain.tsx` righe 1-22, sostituisci il blocco import con:

```tsx
import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import {
  Heart, Shield, ShieldAlert, Sparkles, Gem,
  BarChart3, Target, Zap, Swords, Coins,
  User, Scroll, Star, CircleDot, Dices,
  NotebookPen, Map, BookOpen, ChevronLeft, Settings, FlaskConical,
  Footprints,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { api } from '@/api/client'
import HPGauge from '@/components/ui/HPGauge'
import HeroXPBar from '@/components/ui/HeroXPBar'
import Surface from '@/components/ui/Surface'
import SectionDivider from '@/components/ui/SectionDivider'
import StatPill from '@/components/ui/StatPill'
import Reveal from '@/components/ui/Reveal'
import Skeleton from '@/components/ui/Skeleton'
import { ShieldEmblem } from '@/components/ui/Ornament'
import { haptic } from '@/auth/telegram'
import { spring, stagger } from '@/styles/motion'
import { formatCondition } from '@/lib/conditions'
import { CONDITION_ICONS } from '@/lib/conditions'
import ConditionDetailModal from '@/pages/conditions/ConditionDetailModal'
import PassiveAbilityDetailModal from '@/pages/abilities/PassiveAbilityDetailModal'
import type { Ability } from '@/types'
```

Aggiunte rispetto all'originale: `useState` da react, `Footprints` da lucide, `HeroXPBar`, `CONDITION_ICONS`, `ConditionDetailModal`, `PassiveAbilityDetailModal`, `type Ability`.

- [ ] **Step 2: Aggiungi stato locale per i modali**

Dentro `CharacterMain()`, subito dopo la dichiarazione di `qc` (riga ~120 `const qc = useQueryClient()`), aggiungi:

```tsx
const [detailCondKey, setDetailCondKey] = useState<string | null>(null)
const [detailAbility, setDetailAbility] = useState<Ability | null>(null)
```

- [ ] **Step 3: Sostituisci la meta row XP+Speed con `HeroXPBar`**

Nel file originale, le righe ~270-285 sono:

```tsx
{/* Meta row */}
<div className="flex flex-wrap gap-2 mt-3">
  <StatPill
    icon={<Star size={12} />}
    label="XP"
    value={char.experience_points}
    tone="amber"
    size="sm"
  />
  <StatPill
    label={t('character.identity.speed', { defaultValue: 'Speed' })}
    value={`${char.speed}ft`}
    tone="default"
    size="sm"
  />
</div>
```

Sostituisci con:

```tsx
{/* XP bar — replaces the old XP pill and Speed pill */}
<HeroXPBar
  currentXP={char.experience_points}
  totalClassLevel={char.total_level}
  onLevelUpReady={() => navigate(`/char/${charId}/xp`)}
/>
```

(La velocità torna più in basso come chip floating — vedi Step 6.)

- [ ] **Step 4: Modifica il chip abilità passive per aprire il modale**

Nel file originale, righe ~305-311 sono:

```tsx
{/* Passive abilities */}
{passiveAbilities.length > 0 && (
  <div className="flex flex-wrap gap-1.5 mt-3 overflow-x-auto scrollbar-hide max-h-14">
    {passiveAbilities.map(a => (
      <StatPill key={a.id} icon={<Zap size={10} />} value={a.name} tone="gold" size="sm" />
    ))}
  </div>
)}
```

Sostituisci con:

```tsx
{/* Passive abilities — chip invariate, tap apre modale descrizione */}
{passiveAbilities.length > 0 && (
  <div className="flex flex-wrap gap-1.5 mt-3 overflow-x-auto scrollbar-hide max-h-14">
    {passiveAbilities.map(a => (
      <StatPill
        key={a.id}
        icon={<Zap size={10} />}
        value={a.name}
        tone="gold"
        size="sm"
        onClick={() => setDetailAbility(a)}
      />
    ))}
  </div>
)}
```

- [ ] **Step 5: Modifica i chip condizioni in icon-only con modale**

Nel file originale, righe ~313-326 sono:

```tsx
{/* Active conditions */}
{activeConditions.length > 0 && (
  <div className="flex flex-wrap gap-1.5 mt-2 overflow-x-auto scrollbar-hide max-h-14">
    {activeConditions.map(([key, val]) => (
      <StatPill
        key={key}
        icon={<CircleDot size={10} />}
        value={formatCondition(key, val, t)}
        tone="crimson"
        size="sm"
      />
    ))}
  </div>
)}
```

Sostituisci con:

```tsx
{/* Active conditions — icon-only, tap apre ConditionDetailModal */}
{activeConditions.length > 0 && (
  <div className="flex flex-wrap gap-1.5 mt-2 overflow-x-auto scrollbar-hide max-h-14">
    {activeConditions.map(([key, val]) => {
      const Icon = CONDITION_ICONS[key] ?? CircleDot
      return (
        <StatPill
          key={key}
          icon={<Icon size={14} />}
          value={formatCondition(key, val, t)}
          tone="crimson"
          size="sm"
          iconOnly
          onClick={() => setDetailCondKey(key)}
        />
      )
    })}
  </div>
)}
```

Nota: l'icona passa da `CircleDot` statico a quella specifica della condizione via `CONDITION_ICONS`. Fallback a `CircleDot` se mappa incompleta.

- [ ] **Step 6: Aggiungi la velocità icon-only floating bottom-right**

Subito dopo il blocco "Active conditions" (ma ancora dentro la `<Surface>` dell'hero), aggiungi:

```tsx
{/* Velocità — icon-only floating bottom-right, tap rivela valore */}
<StatPill
  icon={<Footprints size={14} />}
  value={`${char.speed} ft`}
  tone="emerald"
  size="sm"
  iconOnly
  revealOnTap
  aria-label={`${t('character.identity.speed', { defaultValue: 'Speed' })}: ${char.speed} ft`}
  className="absolute bottom-3 right-3"
/>
```

- [ ] **Step 7: Rendi cliccabili le celle ability score**

Nel file originale, righe ~340-360 renderizzano la griglia delle caratteristiche. Sostituisci l'intero `<m.div>` interno del map con un `<m.button>`:

Prima:

```tsx
{char.ability_scores.map((score) => {
  const key = score.name.toLowerCase()
  const colorCls = ABILITY_COLORS[key] ?? ABILITY_COLORS.charisma
  return (
    <m.div
      key={score.name}
      className={`flex flex-col items-center rounded-lg p-1.5 border bg-gradient-to-b ${colorCls}`}
      variants={{ initial: { opacity: 0, y: 8 }, animate: { opacity: 1, y: 0 } }}
      transition={spring.snappy}
    >
      <span className="text-[9px] font-cinzel uppercase tracking-widest opacity-80">
        {score.name.slice(0, 3)}
      </span>
      <span className="text-xl font-display font-black leading-none mt-0.5">{score.value}</span>
      <span className="text-[11px] font-mono font-bold mt-0.5 px-1.5 py-0.5 rounded-full bg-black/25">
        {score.modifier >= 0 ? '+' : ''}{score.modifier}
      </span>
    </m.div>
  )
})}
```

Dopo:

```tsx
{char.ability_scores.map((score) => {
  const key = score.name.toLowerCase()
  const colorCls = ABILITY_COLORS[key] ?? ABILITY_COLORS.charisma
  const modStr = `${score.modifier >= 0 ? '+' : ''}${score.modifier}`
  return (
    <m.button
      key={score.name}
      type="button"
      onClick={() => {
        haptic.light()
        navigate(`/char/${charId}/stats`)
      }}
      aria-label={`${score.name}: ${score.value}, mod ${modStr}`}
      className={`flex flex-col items-center rounded-lg p-1.5 border bg-gradient-to-b cursor-pointer hover:border-dnd-gold transition-colors ${colorCls}`}
      variants={{ initial: { opacity: 0, y: 8 }, animate: { opacity: 1, y: 0 } }}
      transition={spring.snappy}
      whileTap={{ scale: 0.95 }}
    >
      <span className="text-[9px] font-cinzel uppercase tracking-widest opacity-80">
        {score.name.slice(0, 3)}
      </span>
      <span className="text-xl font-display font-black leading-none mt-0.5">{score.value}</span>
      <span className="text-[11px] font-mono font-bold mt-0.5 px-1.5 py-0.5 rounded-full bg-black/25">
        {modStr}
      </span>
    </m.button>
  )
})}
```

- [ ] **Step 8: Aggiungi i modali condizionali in fondo**

Subito prima della chiusura `</div>` del wrapper root (riga `return ()` finale, prima del `)}`), aggiungi:

```tsx
{/* Modals */}
{detailCondKey !== null && (
  <ConditionDetailModal
    condKey={detailCondKey}
    exhaustionLevel={
      typeof (char.conditions as Record<string, unknown>)?.['exhaustion'] === 'number'
        ? ((char.conditions as Record<string, unknown>)['exhaustion'] as number)
        : 0
    }
    onClose={() => setDetailCondKey(null)}
  />
)}
{detailAbility !== null && (
  <PassiveAbilityDetailModal
    ability={detailAbility}
    onClose={() => setDetailAbility(null)}
  />
)}
```

(Posizionali prima della chiusura del wrapper root principale — il `<div className="w-full flex flex-col">` che contiene tutto.)

- [ ] **Step 9: Verifica TypeScript**

Run:
```bash
cd webapp && npx tsc --noEmit
```
Expected: zero errori.

- [ ] **Step 10: Commit**

```bash
git add webapp/src/pages/CharacterMain.tsx
git commit -m "feat(webapp): redesign hero section with XP bar and icon-only chips

- Sostituisce meta row XP pill + Speed pill con HeroXPBar (barra
  progressiva + LEVEL UP button inline quando XP pendenti).
- Chip condizioni: icon-only con icona specifica per condizione,
  tap apre ConditionDetailModal.
- Chip abilità passive: invariate visivamente (icon+nome), tap apre
  nuovo PassiveAbilityDetailModal con descrizione.
- Velocità: chip icon-only floating absolute bottom-right, tap rivela
  il valore inline per 2s (simmetrico allo shield CA top-right).
- Celle ability score cliccabili: tap naviga a /stats con haptic.

Nessun cambio al backend; tutti i dati già presenti su char.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8 — Breadcrumb cliccabile (`Layout.tsx`)

**Files:**
- Modify: `webapp/src/components/Layout.tsx`

- [ ] **Step 1: Aggiungi import `useParams` e `haptic`**

In `webapp/src/components/Layout.tsx`, sostituisci il blocco import iniziale (righe 1-6) con:

```tsx
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ChevronLeft } from 'lucide-react'
import { m } from 'framer-motion'
import { useSwipeNavigation, getGroupInfo } from '@/hooks/useSwipeNavigation'
import { spring } from '@/styles/motion'
import { haptic } from '@/auth/telegram'
```

Aggiunte: `useParams` (per ottenere `id`), `haptic` (per feedback tattile).

- [ ] **Step 2: Estrai `id` e definisci handler di navigazione**

Dentro `Layout()` dopo le dichiarazioni di `navigate`, `t`, `swipe`, `info` (riga ~20), aggiungi:

```tsx
const { id } = useParams<{ id: string }>()
```

- [ ] **Step 3: Riscrivi il blocco breadcrumb con prev/next cliccabili**

Sostituisci il blocco condizionale `{info && (() => { ... })()}` (righe ~55-84) con:

```tsx
{info && (() => {
  const prevKey = info.index > 0 ? info.pages[info.index - 1] : null
  const currKey = info.pages[info.index]
  const nextKey = info.index < info.total - 1 ? info.pages[info.index + 1] : null

  const goToPrev = () => {
    if (prevKey && id) {
      haptic.light()
      navigate(`/char/${id}/${prevKey}`, { replace: true })
    }
  }
  const goToNext = () => {
    if (nextKey && id) {
      haptic.light()
      navigate(`/char/${id}/${nextKey}`, { replace: true })
    }
  }

  return (
    <div className="flex items-center justify-center gap-1.5 mt-2 text-xs overflow-x-auto scrollbar-hide font-body">
      {prevKey && (
        <>
          <m.button
            type="button"
            onClick={goToPrev}
            whileTap={{ scale: 0.95 }}
            aria-label={t('layout.nav.go_to', { page: t(`character.menu.${prevKey}`) })}
            className="text-dnd-text-muted opacity-70 whitespace-nowrap px-1.5 py-0.5 rounded hover:filter-none hover:text-dnd-gold-bright hover:opacity-100 transition-colors"
            style={{ filter: 'blur(0.5px)' }}
          >
            {t(`character.menu.${prevKey}`)}
          </m.button>
          <span className="text-dnd-gold-dim/50 shrink-0">◈</span>
        </>
      )}
      <span className="text-dnd-gold-bright font-semibold whitespace-nowrap">
        {t(`character.menu.${currKey}`)}
      </span>
      {nextKey && (
        <>
          <span className="text-dnd-gold-dim/50 shrink-0">◈</span>
          <m.button
            type="button"
            onClick={goToNext}
            whileTap={{ scale: 0.95 }}
            aria-label={t('layout.nav.go_to', { page: t(`character.menu.${nextKey}`) })}
            className="text-dnd-text-muted opacity-70 whitespace-nowrap px-1.5 py-0.5 rounded hover:filter-none hover:text-dnd-gold-bright hover:opacity-100 transition-colors"
            style={{ filter: 'blur(0.5px)' }}
          >
            {t(`character.menu.${nextKey}`)}
          </m.button>
        </>
      )}
    </div>
  )
})()}
```

Note:
- Prev/next sono ora `<m.button>` con `onClick`, `whileTap`, `aria-label`, hover che rimuove il blur.
- Current resta `<span>` (non cliccabile).
- I separatori `◈` restano `<span>` inerti.
- `padding x-1.5 y-0.5` aumenta il tap target per mobile senza disturbare il layout.
- `id` è già in closure dal Step 2.

- [ ] **Step 4: Verifica TypeScript**

Run:
```bash
cd webapp && npx tsc --noEmit
```
Expected: zero errori.

- [ ] **Step 5: Commit**

```bash
git add webapp/src/components/Layout.tsx
git commit -m "feat(webapp): make breadcrumb prev/next clickable in Layout

Il 'page carousel' orizzontale nell'header ora permette di tappare
il nome della pagina sibling (prev/next) per saltarci senza dover
swipare. Conservato swipe navigation parallelamente. Aggiunto feedback
haptic.light() e hover state che rimuove il blur di base.

Current page resta non cliccabile (sei già lì).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9 — Conditions.tsx: refactor CONDITION_ICONS + exhaustion inline

**Files:**
- Modify: `webapp/src/pages/Conditions.tsx`

- [ ] **Step 1: Sostituisci gli import delle icone con `CONDITION_ICONS`**

In `webapp/src/pages/Conditions.tsx` sostituisci il blocco import (righe 1-16) con:

```tsx
import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Flame, Info } from 'lucide-react'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import { haptic } from '@/auth/telegram'
import { spring, stagger } from '@/styles/motion'
import ConditionDetailModal from '@/pages/conditions/ConditionDetailModal'
import { CONDITION_ICONS } from '@/lib/conditions'
```

Aggiunto: `CONDITION_ICONS` da `@/lib/conditions`. Rimossi: gli import individuali di `EyeOff, Heart, VolumeX, Ghost, Link2, Cloud, Eye, Zap, Mountain, FlaskConical, ArrowDown, Lock, Sparkle, Moon` (ora vivono in `lib/conditions.ts`). Tenuti: `Flame` (per l'icona di exhaustion section) e `Info`.

- [ ] **Step 2: Sostituisci l'array `CONDITIONS` con una versione derivata dalla mappa**

Nel file originale, righe 18-33 c'è:

```tsx
const CONDITIONS: { key: string; icon: LucideIcon }[] = [
  { key: 'blinded',       icon: EyeOff },
  // ...14 voci...
]
```

Sostituisci con:

```tsx
const CONDITION_KEYS = [
  'blinded', 'charmed', 'deafened', 'frightened', 'grappled',
  'incapacitated', 'invisible', 'paralyzed', 'petrified', 'poisoned',
  'prone', 'restrained', 'stunned', 'unconscious',
] as const
```

L'ordine è identico all'originale (mantiene la UX della grid attuale).

Rimuovi anche l'import `type { LucideIcon } from 'lucide-react'` se presente ed ora inutilizzato.

- [ ] **Step 3: Adegua il map delle condition cards**

Nel file originale riga ~153 c'è:

```tsx
{CONDITIONS.map((cond) => {
  const Icon = cond.icon
  const active = !!conditions[cond.key]
```

Sostituisci con:

```tsx
{CONDITION_KEYS.map((key) => {
  const Icon = CONDITION_ICONS[key]
  const active = !!conditions[key]
```

Poi all'interno di quello scope, ovunque comparisse `cond.key` sostituiscilo con `key` (c'è anche un `t(\`character.conditions.${cond.key}\`)` e un `onClick={() => toggle(cond.key)}` e `onClick={() => setDetailKey(cond.key)}`).

Equivalente full-diff per il blocco map (righe ~153-191, sostituisci tutto):

```tsx
{CONDITION_KEYS.map((key) => {
  const Icon = CONDITION_ICONS[key]
  const active = !!conditions[key]
  return (
    <m.div
      key={key}
      variants={{
        initial: { opacity: 0, y: 8 },
        animate: { opacity: 1, y: 0 },
      }}
      className={`flex items-center rounded-xl border transition-colors
        ${active
          ? 'bg-gradient-to-br from-[var(--dnd-crimson-deep)]/40 to-[var(--dnd-crimson)]/20 border-dnd-crimson/60 shadow-halo-danger text-dnd-text'
          : 'bg-dnd-surface border-dnd-border text-dnd-text-muted'}`}
      animate={active ? { x: [-2, 2, -1, 1, 0] } : {}}
      transition={{ duration: 0.25 }}
    >
      <m.button
        type="button"
        onClick={() => toggle(key)}
        whileTap={{ scale: 0.95 }}
        className="flex-1 flex items-center gap-2 px-3 py-3 text-left"
      >
        <Icon size={18} className={active ? 'text-[var(--dnd-crimson-bright)]' : 'text-dnd-text-faint'} />
        <span className="text-sm font-body leading-tight">
          {t(`character.conditions.${key}`)}
        </span>
      </m.button>
      <button
        type="button"
        aria-label={t('character.conditions.detail_aria')}
        onClick={() => setDetailKey(key)}
        className="shrink-0 p-3 text-dnd-text-muted hover:text-dnd-gold-bright transition-colors"
      >
        <Info size={16} />
      </button>
    </m.div>
  )
})}
```

- [ ] **Step 4: Aggiungi descrizioni inline sotto il selettore exhaustion**

Nel file originale riga ~141, dopo la `</div>` di chiusura del `flex gap-1.5` dei bottoni 0-6, c'è già `</Surface>` della Exhaustion Surface. Sostituisci il blocco della Surface exhaustion (righe ~98-141) con la versione estesa:

```tsx
{/* Exhaustion tracker + inline level descriptions */}
<Surface variant="elevated" ornamented>
  <div className="flex items-center justify-between mb-3">
    <div className="flex items-center gap-2">
      <Flame size={16} className="text-[var(--dnd-amber)]" />
      <span className="font-cinzel uppercase tracking-widest text-xs text-dnd-gold-dim">
        {t('character.conditions.exhaustion_condition')}
      </span>
      <button
        type="button"
        aria-label={t('character.conditions.detail_aria')}
        onClick={() => setDetailKey('exhaustion')}
        className="text-dnd-text-muted hover:text-dnd-gold-bright transition-colors"
      >
        <Info size={14} />
      </button>
    </div>
    <span className={`text-lg font-display font-black
      ${currentExhaustion > 0 ? 'text-[var(--dnd-amber)]' : 'text-dnd-text-faint'}`}>
      {currentExhaustion}<span className="text-sm text-dnd-text-muted">/6</span>
    </span>
  </div>
  <div className="flex gap-1.5">
    {[0, 1, 2, 3, 4, 5, 6].map((level) => {
      const isActive = (exhaustionLevel ?? currentExhaustion) === level
      const isFilled = level <= (exhaustionLevel ?? currentExhaustion)
      return (
        <m.button
          key={level}
          onClick={() => setExhaustion(level)}
          className={`flex-1 min-h-[40px] rounded-lg font-cinzel font-black text-sm
            ${isActive
              ? 'bg-gradient-ember text-white shadow-parchment-md'
              : isFilled
                ? 'bg-[var(--dnd-amber)]/40 text-[var(--dnd-amber)]'
                : 'bg-dnd-surface border border-dnd-border text-dnd-text-faint'}`}
          whileTap={{ scale: 0.92 }}
          transition={spring.press}
        >
          {level}
        </m.button>
      )
    })}
  </div>

  {/* Inline level descriptions — current highlighted, others grey */}
  {(() => {
    const levels = t('character.conditions.desc.exhaustion_levels', {
      returnObjects: true,
    }) as string[]
    return (
      <div className="mt-4 space-y-1 text-sm">
        {levels.map((desc, idx) => {
          const lvl = idx + 1
          const isCurrent = lvl === currentExhaustion
          return (
            <div
              key={lvl}
              className={
                isCurrent
                  ? 'px-3 py-2 rounded-md border-l-2 border-dnd-gold bg-dnd-gold/10 text-dnd-gold-bright'
                  : 'px-3 py-1.5 text-dnd-text-faint opacity-60'
              }
            >
              {desc}
            </div>
          )
        })}
      </div>
    )
  })()}
</Surface>
```

Blocco aggiunto: le righe dopo il `</div>` del selettore — il `{(() => { ... })()}` che mappa `exhaustion_levels` in 6 `<div>` con stile condizionale.

Quando `currentExhaustion === 0`: `lvl === 0` è sempre false (lvl parte da 1), quindi nessun livello viene evidenziato — tutti grigi. Coerente con "non spossato".

- [ ] **Step 5: Verifica TypeScript**

Run:
```bash
cd webapp && npx tsc --noEmit
```
Expected: zero errori.

- [ ] **Step 6: Commit**

```bash
git add webapp/src/pages/Conditions.tsx
git commit -m "feat(webapp): inline exhaustion descriptions + share CONDITION_ICONS

- Conditions.tsx importa CONDITION_ICONS da lib/conditions invece di
  duplicare il map locale.
- Sotto il selettore 0-6 exhaustion, aggiunte le 6 descrizioni inline
  (da character.conditions.desc.exhaustion_levels[]). Il livello
  corrente è evidenziato con border+background oro; gli altri sono
  grigio chiaro opacity 60 per leggibilità senza distrazione.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 10 — ArmorClass.tsx: nuovo layout Base + Scudo/Magia

**Files:**
- Modify: `webapp/src/pages/ArmorClass.tsx`

- [ ] **Step 1: Sostituisci il blocco Component editors**

Nel file originale `webapp/src/pages/ArmorClass.tsx`, il blocco (righe ~100-125) è:

```tsx
{/* Component editors */}
{fields.map((f, idx) => (
  <m.div
    key={f.key}
    initial={{ opacity: 0, y: 8 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ ...spring.drift, delay: 0.1 + idx * 0.05 }}
  >
    <Surface variant="elevated">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="font-cinzel text-xs uppercase tracking-widest text-dnd-gold-dim">{f.label}</p>
          <p className="text-3xl font-display font-black text-dnd-gold-bright mt-0.5">{f.cur}</p>
        </div>
        <Input
          type="number"
          min={0}
          value={f.val}
          onChange={f.set}
          placeholder={String(f.cur)}
          inputMode="numeric"
          className="w-28 [&_input]:text-xl [&_input]:font-display [&_input]:font-bold [&_input]:text-center"
        />
      </div>
    </Surface>
  </m.div>
))}
```

Sostituisci con:

```tsx
{/* Base full-width */}
<m.div
  initial={{ opacity: 0, y: 8 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ ...spring.drift, delay: 0.10 }}
>
  <Surface variant="elevated">
    <div className="flex items-center justify-between gap-3">
      <div>
        <p className="font-cinzel text-xs uppercase tracking-widest text-dnd-gold-dim">
          {t('character.ac.base')}
        </p>
        <p className="text-4xl font-display font-black text-dnd-gold-bright mt-0.5">
          {char.base_armor_class}
        </p>
      </div>
      <Input
        type="number"
        min={0}
        value={base}
        onChange={setBase}
        placeholder={String(char.base_armor_class)}
        inputMode="numeric"
        className="w-32 [&_input]:text-xl [&_input]:font-display [&_input]:font-bold [&_input]:text-center"
      />
    </div>
  </Surface>
</m.div>

{/* Scudo + Magia affiancati in grid 2 colonne */}
<m.div
  initial={{ opacity: 0, y: 8 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ ...spring.drift, delay: 0.15 }}
  className="grid grid-cols-2 gap-2"
>
  <Surface variant="elevated">
    <p className="font-cinzel text-[10px] uppercase tracking-widest text-dnd-gold-dim">
      {t('character.ac.shield')}
    </p>
    <p className="text-2xl font-display font-black text-dnd-gold-bright mt-0.5">
      {char.shield_armor_class}
    </p>
    <Input
      type="number"
      min={0}
      value={shield}
      onChange={setShield}
      placeholder={String(char.shield_armor_class)}
      inputMode="numeric"
      className="mt-2 w-full [&_input]:text-base [&_input]:font-display [&_input]:font-bold [&_input]:text-center"
    />
  </Surface>
  <Surface variant="elevated">
    <p className="font-cinzel text-[10px] uppercase tracking-widest text-dnd-gold-dim">
      {t('character.ac.magic')}
    </p>
    <p className="text-2xl font-display font-black text-dnd-gold-bright mt-0.5">
      {char.magic_armor}
    </p>
    <Input
      type="number"
      min={0}
      value={magic}
      onChange={setMagic}
      placeholder={String(char.magic_armor)}
      inputMode="numeric"
      className="mt-2 w-full [&_input]:text-base [&_input]:font-display [&_input]:font-bold [&_input]:text-center"
    />
  </Surface>
</m.div>
```

- [ ] **Step 2: Rimuovi l'array `fields` ora inutilizzato**

Nel file originale righe ~52-56 c'è:

```tsx
const fields = [
  { key: 'base',   label: t('character.ac.base'),   val: base,   set: setBase,   cur: char.base_armor_class },
  { key: 'shield', label: t('character.ac.shield'), val: shield, set: setShield, cur: char.shield_armor_class },
  { key: 'magic',  label: t('character.ac.magic'),  val: magic,  set: setMagic,  cur: char.magic_armor },
]
```

Rimuovi questo array completamente — non è più usato.

- [ ] **Step 3: Verifica TypeScript**

Run:
```bash
cd webapp && npx tsc --noEmit
```
Expected: zero errori. (In particolare TypeScript segnalerà unused warnings se il prop `fields` non è stato rimosso correttamente — fixare eventuali warning.)

- [ ] **Step 4: Commit**

```bash
git add webapp/src/pages/ArmorClass.tsx
git commit -m "feat(webapp): redesign AC editor layout

CA Base su riga dedicata a tutta larghezza (valore a 4xl, evidenziato
come componente principale). Scudo + Magia affiancati in grid 2
colonne, valori a 2xl. Input allineati verticalmente sotto il valore
corrente per ciascuna colonna.

Hero section AC (ShieldEmblem grande con valore totale) resta invariata.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 11 — Verifica manuale + production build

**Files:**
- Modify: `docs/app/**` (build output)

- [ ] **Step 1: Avvia dev server e verifica visualmente**

In due terminali separati:

Terminal 1 (API — da Windows/PowerShell, NON da WSL):
```bash
uv run uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

Terminal 2 (webapp):
```bash
cd webapp && npm run dev
```

Apri `http://localhost:5173/` in un browser. Testa su almeno due character diversi:

**Character A — basic** (single-class, niente condizioni, niente abilità passive):
- [ ] Hero section mostra HP bar, XP bar sotto (con `LIV N` + `current/threshold`), niente LEVEL UP button, niente conc banner, niente chip passivi, niente chip condizioni, velocità icon bottom-right.
- [ ] Tap sull'icona velocità rivela `30 ft` (o valore) per ~2s poi nasconde.
- [ ] Tap su una cella STR/DEX/CON/INT/WIS/CHA naviga a `/stats`.
- [ ] Nella pagina `/ac` vedi Base fullwidth in cima, Scudo+Magia affiancati sotto.
- [ ] Nella pagina `/conditions` il selettore 0-6 spossatezza è invariato; sotto 6 righe grigie (nessuna evidenziata se liv 0).
- [ ] Nella pagina `/hp` (o qualsiasi child) la breadcrumb `prev ◈ current ◈ next` prev e next sono cliccabili e navigano.

**Character B — complesso** (multiclass con XP pendenti, condizioni attive, abilità passive, exhaustion > 0, vicino al level-up):
- [ ] XP bar mostra **pulsante LEVEL UP** shimmer invece dei numeri.
- [ ] Click su LEVEL UP naviga a `/xp`.
- [ ] Chip condizioni appaiono solo come icone (no label).
- [ ] Tap su una chip condizione apre `ConditionDetailModal` con la condizione corretta.
- [ ] Chip abilità passive restano con icon+nome; tap apre `PassiveAbilityDetailModal`.
- [ ] Modale mostra descrizione se presente, altrimenti "Nessuna descrizione disponibile" in corsivo.
- [ ] Banner di concentrazione visibile (se il char è in concentrazione) — navigabile come prima.
- [ ] In `/conditions` con exhaustion > 0, il livello corrente è evidenziato con bordo/sfondo oro, gli altri grigi.

**Verifica lingue:**
- [ ] Con `language_code = 'en'` nelle preferenze Telegram (o `localStorage.setItem('i18nextLng', 'en')` nel browser console), riapri e verifica che `LVL N`, `LEVEL UP`, `MAX`, `No description available`, `Go to {page}` appaiano in inglese.

**Verifica regressioni:**
- [ ] Swipe navigation fra sibling pages continua a funzionare (swipe left/right in una pagina figlia sposta alla successiva/precedente).
- [ ] Aprire `ConditionDetailModal` dal bottone ℹ️ sulla pagina `/conditions` funziona ancora (non rotto da estrazione CONDITION_ICONS).
- [ ] Esperienza in `/xp` continua a mostrare soglie XP corrette (test che il refactor Task 1 non ha rotto nulla).

Se uno dei check fallisce, torna al task incriminato, correggi, committa il fix, ripeti.

- [ ] **Step 2: Production build**

```bash
cd webapp && npm run build:prod
```

Questo script:
1. Switcha `webapp/.env.local` a `VITE_API_BASE_URL=https://api.cischi.dev`.
2. Esegue `tsc && vite build` → output in `docs/app/`.
3. Ripristina `.env.local` a `http://localhost:8000`.
4. Esegue `git add docs/app/`.

Expected: zero errori TypeScript, build completa, `docs/app/` aggiornato e staged.

- [ ] **Step 3: Commit build**

```bash
git commit -m "chore(webapp): rebuild docs/app for hero section UX polish

Rebuild di produzione con VITE_API_BASE_URL=https://api.cischi.dev.
Include tutti i cambi del Gruppo A: HeroXPBar, chip icon-only, breadcrumb
cliccabile, descrizioni spossatezza inline, nuovo layout AC.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 4: Push del branch**

```bash
git push -u origin feat/ux-polish-hero-section
```

- [ ] **Step 5: Apri PR (manuale)**

Dopo il push, usa `gh pr create` o l'interfaccia web GitHub per aprire una PR con:
- Titolo: `feat(webapp): UX polish hero section (Gruppo A)`
- Body: riassunto delle decisioni di design + riferimento allo spec `docs/superpowers/specs/2026-04-22-ux-polish-hero-section-design.md`.
- Test plan checklist copiato dai success criteria dello spec.

---

## Criteri di successo (ripresi dallo spec)

- [ ] Hero section rende: HP bar, XP bar sotto HP, concentration banner (condizionale), abilità passive chip (icon+nome), condizioni chip (solo icon), velocità icon floating bottom-right.
- [ ] Tap sulla velocità icon rivela "30 ft" per 2s poi nasconde.
- [ ] Tap su un chip condizione apre `ConditionDetailModal` con la condizione corretta.
- [ ] Tap su un chip abilità passiva apre il nuovo modale con nome e descrizione (o fallback "nessuna descrizione").
- [ ] Tap su una cella caratteristica naviga a `/stats`.
- [ ] `HeroXPBar` mostra barra + LIV + numeri `current/threshold`. Mostra pulsante LEVEL UP quando `levelFromXp(xp) > char.total_level`.
- [ ] A livello 20: mostra `MAX`, nessun pulsante LEVEL UP.
- [ ] Click sul pulsante LEVEL UP naviga a `/xp`.
- [ ] Breadcrumb prev/next nelle pagine figlie cliccabili, ciascuno naviga alla sibling corrispondente, feedback haptic al tap.
- [ ] `/conditions`: selettore 0-6 invariato, sotto 6 descrizioni inline, corrente evidenziata con bordo/sfondo oro, altre grigio.
- [ ] `/ac`: Base full-width in testa, Scudo + Magia in grid 2 colonne sotto.
- [ ] Tutti i testi via i18n (it + en), nessun hardcoded.
- [ ] Build `npm run build:prod` completa senza errori TypeScript.
- [ ] Swipe navigation + modali esistenti non regrediti.
