# Webapp Visual Redesign — "Pergamena & Oro" Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reskin the D&D character management Telegram Mini App with a warm "Parchment & Gold" fantasy theme while keeping the mobile-first functional UX.

**Architecture:** Progressive reskin — update design tokens in Tailwind/CSS, redesign 5 shared components (Card, Layout, HPBar, RollResultModal, WeaponAttackModal), create 1 new component (SectionHeader), restructure CharacterMain with grouped menu. All 21 pages automatically inherit the new palette and component styles. Then do a find-and-replace pass across all pages to swap `--tg-theme-*` references to `--dnd-*` tokens.

**Tech Stack:** React 18, Tailwind CSS 3.4, Lucide React (new), Google Font Cinzel (new), CSS animations

**Spec:** `docs/superpowers/specs/2026-04-13-webapp-visual-redesign.md`

---

## File Structure

### New files
| File | Responsibility |
|------|---------------|
| `webapp/src/components/SectionHeader.tsx` | Cinzel-styled section divider for grouped menus |

### Modified files (in task order)
| File | What Changes |
|------|-------------|
| `webapp/package.json` | Add `lucide-react` dependency |
| `webapp/index.html` | Add Cinzel Google Font `<link>` |
| `webapp/tailwind.config.js` | Add `dnd` color namespace + `fontFamily.cinzel` |
| `webapp/src/index.css` | Replace `--tg-theme-*` fallbacks with `--dnd-*` tokens, add keyframe animations, update body styles |
| `webapp/src/components/Card.tsx` | Add `variant` prop ("elevated" / "default") |
| `webapp/src/components/Layout.tsx` | Cinzel title, Lucide ChevronLeft back button, gold colors, fade-in animation |
| `webapp/src/components/HPBar.tsx` | Color thresholds with gradients/glow, pulse-danger animation, width transition |
| `webapp/src/components/RollResultModal.tsx` | New D&D palette, modal-enter animation, pulse-gold/pulse-danger effects |
| `webapp/src/components/WeaponAttackModal.tsx` | Same modal treatment as RollResultModal |
| `webapp/src/pages/CharacterMain.tsx` | Grouped menu with SectionHeader, Lucide icons, hero card elevated, shimmer inspiration |
| `webapp/src/pages/CharacterSelect.tsx` | New palette, elevated cards, gold buttons |
| `webapp/src/pages/HP.tsx` | Card variant assignments, new button colors |
| All other 17 pages in `webapp/src/pages/` | Replace `--tg-theme-*` with `--dnd-*` tokens, assign Card variants, update button/input colors |

---

## Task 1: Install lucide-react and add Cinzel font

**Files:**
- Modify: `webapp/package.json`
- Modify: `webapp/index.html`

- [ ] **Step 1: Install lucide-react**

```bash
cd webapp && npm install lucide-react
```

- [ ] **Step 2: Add Cinzel Google Font link to index.html**

In `webapp/index.html`, add inside `<head>` before the Telegram SDK script:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@700;900&display=swap" rel="stylesheet">
```

The full `<head>` becomes:

```html
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
  <title>D&amp;D Character Sheet</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@700;900&display=swap" rel="stylesheet">
  <!-- Telegram Mini App SDK -->
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
</head>
```

- [ ] **Step 3: Verify dev server starts**

```bash
cd webapp && npm run dev
```

Expected: Vite dev server starts without errors.

- [ ] **Step 4: Commit**

```bash
cd webapp && git add package.json package-lock.json ../webapp/index.html
git commit -m "chore: add lucide-react and Cinzel Google Font"
```

---

## Task 2: Design tokens — Tailwind config and CSS variables

**Files:**
- Modify: `webapp/tailwind.config.js`
- Modify: `webapp/src/index.css`

- [ ] **Step 1: Extend Tailwind config with dnd color namespace and Cinzel font**

Replace the entire content of `webapp/tailwind.config.js` with:

```js
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        tg: {
          bg: 'var(--tg-theme-bg-color)',
          text: 'var(--tg-theme-text-color)',
          hint: 'var(--tg-theme-hint-color)',
          link: 'var(--tg-theme-link-color)',
          button: 'var(--tg-theme-button-color)',
          'button-text': 'var(--tg-theme-button-text-color)',
          'secondary-bg': 'var(--tg-theme-secondary-bg-color)',
        },
        dnd: {
          bg: 'var(--dnd-bg)',
          surface: 'var(--dnd-surface)',
          'surface-elevated': 'var(--dnd-surface-elevated)',
          gold: 'var(--dnd-gold)',
          'gold-dim': 'var(--dnd-gold-dim)',
          parchment: 'var(--dnd-parchment)',
          text: 'var(--dnd-text)',
          'text-secondary': 'var(--dnd-text-secondary)',
          danger: 'var(--dnd-danger)',
          success: 'var(--dnd-success)',
          arcane: 'var(--dnd-arcane)',
          info: 'var(--dnd-info)',
        },
      },
      fontFamily: {
        cinzel: ['Cinzel', 'serif'],
      },
      boxShadow: {
        'dnd-glow': '0 0 20px var(--dnd-gold-glow)',
      },
    },
  },
  plugins: [],
}
```

- [ ] **Step 2: Replace CSS variables and add animations in index.css**

Replace the entire content of `webapp/src/index.css` with:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  /* D&D "Pergamena & Oro" design tokens */
  --dnd-bg: #1a1614;
  --dnd-surface: #2a2320;
  --dnd-surface-elevated: #352d28;
  --dnd-gold: #d4a847;
  --dnd-gold-dim: #8b7335;
  --dnd-gold-glow: rgba(212, 168, 71, 0.15);
  --dnd-parchment: #f4e8c1;
  --dnd-text: #e8e0d4;
  --dnd-text-secondary: #9a8e7f;
  --dnd-danger: #c0392b;
  --dnd-success: #27ae60;
  --dnd-arcane: #8e44ad;
  --dnd-info: #2980b9;

  /* Keep Telegram fallbacks pointing to D&D tokens so old references don't break during migration */
  --tg-theme-bg-color: var(--dnd-bg);
  --tg-theme-text-color: var(--dnd-text);
  --tg-theme-hint-color: var(--dnd-text-secondary);
  --tg-theme-link-color: var(--dnd-gold);
  --tg-theme-button-color: var(--dnd-gold);
  --tg-theme-button-text-color: var(--dnd-bg);
  --tg-theme-secondary-bg-color: var(--dnd-surface);
}

html,
body,
#root {
  width: 100%;
  overflow-x: hidden;
  max-width: 100vw;
}

/* Safe area inset utilities (iPhone X+, Android edge-to-edge) */
.pb-safe { padding-bottom: calc(1rem + env(safe-area-inset-bottom, 0px)); }
.pt-safe { padding-top: calc(0.75rem + env(safe-area-inset-top, 0px)); }
.px-safe {
  padding-left: env(safe-area-inset-left, 0px);
  padding-right: env(safe-area-inset-right, 0px);
}

/* Hide scrollbar while keeping scroll behaviour */
.scrollbar-hide {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
.scrollbar-hide::-webkit-scrollbar {
  display: none;
}

body {
  background-color: var(--dnd-bg);
  color: var(--dnd-text);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  margin: 0;
  padding: 0;
  min-height: 100vh;
}

/* ── Animations ── */

/* Layout content fade-in */
@keyframes fadeIn {
  from { opacity: 0; }
  to   { opacity: 1; }
}
.animate-fade-in {
  animation: fadeIn 150ms ease forwards;
}

/* Spell detail accordion fade-in */
@keyframes spellFadeIn {
  from { opacity: 0; transform: translateY(-4px); }
  to   { opacity: 1; transform: translateY(0); }
}
.spell-detail-enter {
  animation: spellFadeIn 150ms ease forwards;
}

/* Modal entry */
@keyframes modalEnter {
  from { opacity: 0; transform: scale(0.9); }
  to   { opacity: 1; transform: scale(1); }
}
.animate-modal-enter {
  animation: modalEnter 150ms ease-out forwards;
}

/* HP critical pulse */
@keyframes pulseDanger {
  0%, 100% { box-shadow: 0 0 6px rgba(192, 57, 43, 0.3); }
  50%      { box-shadow: 0 0 14px rgba(192, 57, 43, 0.6); }
}
.animate-pulse-danger {
  animation: pulseDanger 2s ease-in-out infinite;
}

/* Critical roll gold pulse (plays 3 times then stops) */
@keyframes pulseGold {
  0%, 100% { box-shadow: 0 0 15px rgba(212, 168, 71, 0.3); }
  50%      { box-shadow: 0 0 30px rgba(212, 168, 71, 0.6); }
}
.animate-pulse-gold {
  animation: pulseGold 1s ease-in-out 3;
}

/* Inspiration shimmer */
@keyframes shimmer {
  0%, 100% { opacity: 0.6; filter: drop-shadow(0 0 3px var(--dnd-gold)); }
  50%      { opacity: 1; filter: drop-shadow(0 0 8px var(--dnd-gold)); }
}
.animate-shimmer {
  animation: shimmer 2s ease-in-out infinite;
}

/* Scrollbar styling */
::-webkit-scrollbar {
  width: 4px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: var(--dnd-text-secondary);
  border-radius: 2px;
}
```

**Key decisions in this step:**
- The `--tg-theme-*` fallbacks now point to `--dnd-*` tokens. This means pages still referencing old `--tg-theme-*` vars will see the new D&D colors immediately. When Telegram injects its theme at runtime, Telegram's values override these fallbacks — but since we'll migrate pages to use `--dnd-*` directly, Telegram's injection won't affect the D&D-themed elements.
- All new keyframe animations are defined here as utility classes.

- [ ] **Step 3: Verify the dev server renders with new colors**

```bash
cd webapp && npm run dev
```

Open http://localhost:5173 — the background should now be warm dark brown (#1a1614) instead of the old cold gray (#1c1c1e). All existing pages should still render correctly because `--tg-theme-*` fallbacks point to the new tokens.

- [ ] **Step 4: Commit**

```bash
git add webapp/tailwind.config.js webapp/src/index.css
git commit -m "feat: add D&D design tokens, Tailwind dnd namespace, and CSS animations"
```

---

## Task 3: Card component — add variant prop

**Files:**
- Modify: `webapp/src/components/Card.tsx`

- [ ] **Step 1: Rewrite Card with variant support**

Replace the entire content of `webapp/src/components/Card.tsx` with:

```tsx
interface CardProps {
  children: React.ReactNode
  className?: string
  variant?: 'default' | 'elevated'
  onClick?: (e: React.MouseEvent<HTMLDivElement>) => void
}

export default function Card({ children, className = '', variant = 'default', onClick }: CardProps) {
  const base = 'rounded-2xl p-4 transition-all duration-150 active:opacity-70'
  const cursor = onClick ? 'cursor-pointer' : ''

  const variantStyles =
    variant === 'elevated'
      ? 'bg-dnd-surface-elevated border border-dnd-gold-dim shadow-dnd-glow'
      : 'bg-dnd-surface'

  return (
    <div className={`${base} ${variantStyles} ${cursor} ${className}`} onClick={onClick}>
      {children}
    </div>
  )
}
```

- [ ] **Step 2: Verify existing pages still render**

Open http://localhost:5173 — all pages using `<Card>` should render with the new default surface color. No variant prop means "default" (operative card), so nothing breaks.

- [ ] **Step 3: Commit**

```bash
git add webapp/src/components/Card.tsx
git commit -m "feat: Card component with elevated/default variant"
```

---

## Task 4: Layout component — Cinzel title, Lucide back button, fade-in

**Files:**
- Modify: `webapp/src/components/Layout.tsx`

- [ ] **Step 1: Rewrite Layout component**

Replace the entire content of `webapp/src/components/Layout.tsx` with:

```tsx
import { useNavigate } from 'react-router-dom'
import { ChevronLeft } from 'lucide-react'

interface LayoutProps {
  title: string
  children: React.ReactNode
  backTo?: string
}

export default function Layout({ title, children, backTo }: LayoutProps) {
  const navigate = useNavigate()

  const handleBack = () => {
    if (backTo) navigate(backTo)
    else navigate(-1)
  }

  return (
    <div className="min-h-screen w-full flex flex-col bg-dnd-bg">
      <header
        className="sticky top-0 z-10 flex items-center gap-3 px-4 py-3 pt-safe
                    bg-dnd-surface-elevated border-b border-dnd-gold-dim/30"
      >
        <button
          onClick={handleBack}
          className="p-1 rounded-lg active:opacity-60 transition-opacity"
          aria-label="Indietro"
        >
          <ChevronLeft size={20} className="text-dnd-gold" />
        </button>
        <h1 className="text-lg font-bold font-cinzel text-dnd-gold truncate flex-1">
          {title}
        </h1>
      </header>

      <main className="flex-1 min-w-0 p-4 space-y-3 pb-safe animate-fade-in">
        {children}
      </main>
    </div>
  )
}
```

- [ ] **Step 2: Verify a page that uses Layout (e.g. HP)**

Navigate to any character's HP page. The header should have a gold Cinzel title and a Lucide chevron back button. Content should fade in.

- [ ] **Step 3: Commit**

```bash
git add webapp/src/components/Layout.tsx
git commit -m "feat: Layout with Cinzel gold header, Lucide back button, fade-in"
```

---

## Task 5: HPBar component — gradients, glow, pulse animation

**Files:**
- Modify: `webapp/src/components/HPBar.tsx`

- [ ] **Step 1: Rewrite HPBar with color thresholds and animations**

Replace the entire content of `webapp/src/components/HPBar.tsx` with:

```tsx
interface HPBarProps {
  current: number
  max: number
  temp?: number
  size?: 'sm' | 'md'
}

export default function HPBar({ current, max, temp = 0, size = 'md' }: HPBarProps) {
  const pct = max > 0 ? Math.min(100, (current / max) * 100) : 0

  const height = size === 'sm' ? 'h-1.5' : 'h-2.5'

  // Color thresholds with gradients
  let gradient: string
  let glow: string
  let pulse = false

  if (pct > 50) {
    gradient = 'linear-gradient(90deg, #27ae60, #2ecc71)'
    glow = '0 0 8px rgba(39, 174, 96, 0.4)'
  } else if (pct > 25) {
    gradient = 'linear-gradient(90deg, #d4a847, #f0c040)'
    glow = '0 0 8px rgba(212, 168, 71, 0.4)'
  } else {
    gradient = 'linear-gradient(90deg, #c0392b, #e74c3c)'
    glow = '0 0 8px rgba(192, 57, 43, 0.5)'
    pulse = true
  }

  return (
    <div className={`w-full ${height} rounded-full bg-white/10 overflow-hidden relative`}>
      <div
        className={`h-full rounded-full transition-all duration-500 ${pulse ? 'animate-pulse-danger' : ''}`}
        style={{
          width: `${pct}%`,
          background: gradient,
          boxShadow: glow,
        }}
      />
      {temp > 0 && (
        <div
          className="absolute top-0 left-0 h-full rounded-full opacity-60"
          style={{
            width: `${Math.min(100, (temp / max) * 100)}%`,
            backgroundColor: 'var(--dnd-info)',
          }}
        />
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify HP bar on CharacterSelect (list) and HP page**

Navigate to character select — each character's HP bar should show the new gradient colors. Navigate to the HP page for a character with low HP to see the pulsing red glow.

- [ ] **Step 3: Commit**

```bash
git add webapp/src/components/HPBar.tsx
git commit -m "feat: HPBar with gradient thresholds, glow, and pulse-danger animation"
```

---

## Task 6: RollResultModal — new styling and animations

**Files:**
- Modify: `webapp/src/components/RollResultModal.tsx`

- [ ] **Step 1: Rewrite RollResultModal with D&D theme**

Replace the entire content of `webapp/src/components/RollResultModal.tsx` with:

```tsx
export type RollResult = {
  die: number
  bonus: number
  total: number
  is_critical: boolean
  is_fumble: boolean
  description?: string
}

type Props = {
  result: RollResult
  title: string
  onClose: () => void
}

export default function RollResultModal({ result, title, onClose }: Props) {
  const { die, bonus, total, is_critical, is_fumble } = result

  const borderColor = is_critical
    ? 'border-dnd-gold'
    : is_fumble
      ? 'border-dnd-danger'
      : 'border-dnd-success'

  const pulseClass = is_critical
    ? 'animate-pulse-gold'
    : is_fumble
      ? 'animate-pulse-danger'
      : ''

  const dieColor = is_critical
    ? 'text-[var(--dnd-gold)]'
    : is_fumble
      ? 'text-[var(--dnd-danger)]'
      : 'text-dnd-text'

  const bonusStr = bonus >= 0 ? `+${bonus}` : `${bonus}`

  return (
    <div
      className="fixed inset-0 bg-black/65 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className={`rounded-2xl p-6 w-full max-w-xs text-center space-y-3
                     bg-dnd-surface-elevated border-2 ${borderColor} ${pulseClass}
                     animate-modal-enter`}
        onClick={(e) => e.stopPropagation()}
      >
        <p className="text-sm text-dnd-text-secondary font-medium">{title}</p>

        {is_critical && (
          <p className="text-[var(--dnd-gold)] font-bold text-sm">✦ CRITICO!</p>
        )}
        {is_fumble && (
          <p className="text-[var(--dnd-danger)] font-bold text-sm">💀 FUMBLE!</p>
        )}

        <div className={`text-6xl font-black ${dieColor}`}>{die}</div>

        <p className="text-dnd-text-secondary text-sm">
          d20 ({die}) {bonusStr} = <span className="text-dnd-text font-bold text-lg">{total}</span>
        </p>

        {result.description && (
          <p className="text-xs text-dnd-text-secondary">{result.description}</p>
        )}

        <button
          onClick={onClose}
          className="w-full py-2.5 rounded-xl bg-dnd-gold text-dnd-bg font-semibold mt-2"
        >
          OK
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add webapp/src/components/RollResultModal.tsx
git commit -m "feat: RollResultModal with D&D theme, modal-enter and pulse animations"
```

---

## Task 7: WeaponAttackModal — new styling and animations

**Files:**
- Modify: `webapp/src/components/WeaponAttackModal.tsx`

- [ ] **Step 1: Rewrite WeaponAttackModal with D&D theme**

Replace the entire content of `webapp/src/components/WeaponAttackModal.tsx` with:

```tsx
export type WeaponAttackResult = {
  weapon_name: string
  to_hit_die: number
  to_hit_bonus: number
  to_hit_total: number
  is_critical: boolean
  is_fumble: boolean
  damage_dice: string
  damage_rolls: number[]
  damage_bonus: number
  damage_total: number
}

type Props = {
  result: WeaponAttackResult
  onClose: () => void
}

export default function WeaponAttackModal({ result, onClose }: Props) {
  const {
    weapon_name, to_hit_die, to_hit_bonus, to_hit_total,
    is_critical, is_fumble, damage_dice, damage_rolls, damage_bonus, damage_total,
  } = result

  const bonusStr = (n: number) => n >= 0 ? `+${n}` : `${n}`

  const borderColor = is_critical
    ? 'border-dnd-gold'
    : is_fumble
      ? 'border-dnd-danger'
      : 'border-dnd-success'

  const pulseClass = is_critical
    ? 'animate-pulse-gold'
    : is_fumble
      ? 'animate-pulse-danger'
      : ''

  return (
    <div
      className="fixed inset-0 bg-black/65 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className={`rounded-2xl p-5 w-full max-w-sm space-y-4
                     bg-dnd-surface-elevated border-2 ${borderColor} ${pulseClass}
                     animate-modal-enter`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="text-center">
          <p className="text-sm text-dnd-text-secondary">⚔️ {weapon_name}</p>
          {is_critical && <p className="text-[var(--dnd-gold)] font-bold">✦ CRITICO!</p>}
          {is_fumble && <p className="text-[var(--dnd-danger)] font-bold">💀 FUMBLE!</p>}
        </div>

        <div className="rounded-xl bg-dnd-surface p-3 text-center">
          <p className="text-xs text-dnd-text-secondary mb-1">Per colpire</p>
          <p className="text-sm text-dnd-text-secondary">
            d20 ({to_hit_die}) {bonusStr(to_hit_bonus)}
          </p>
          <p className={`text-3xl font-black ${is_critical ? 'text-[var(--dnd-gold)]' : is_fumble ? 'text-[var(--dnd-danger)]' : 'text-dnd-text'}`}>
            {to_hit_total}
          </p>
        </div>

        {!is_fumble && (
          <div className="rounded-xl bg-dnd-surface p-3 text-center">
            <p className="text-xs text-dnd-text-secondary mb-1">
              Danno{is_critical ? ' (critico)' : ''} — {damage_dice}
            </p>
            <p className="text-sm text-dnd-text-secondary">
              [{damage_rolls.join(', ')}] {bonusStr(damage_bonus)}
            </p>
            <p className="text-3xl font-black text-[var(--dnd-danger)]">{damage_total}</p>
          </div>
        )}

        <button
          onClick={onClose}
          className="w-full py-2.5 rounded-xl bg-dnd-gold text-dnd-bg font-semibold"
        >
          OK
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add webapp/src/components/WeaponAttackModal.tsx
git commit -m "feat: WeaponAttackModal with D&D theme and animations"
```

---

## Task 8: SectionHeader component

**Files:**
- Create: `webapp/src/components/SectionHeader.tsx`

- [ ] **Step 1: Create SectionHeader component**

Create the file `webapp/src/components/SectionHeader.tsx` with:

```tsx
interface SectionHeaderProps {
  children: React.ReactNode
}

export default function SectionHeader({ children }: SectionHeaderProps) {
  return (
    <div className="flex items-center gap-2 mt-4 mb-2">
      <span className="text-xs font-cinzel font-bold text-dnd-gold-dim uppercase tracking-widest whitespace-nowrap">
        {children}
      </span>
      <div className="flex-1 h-px bg-gradient-to-r from-dnd-gold-dim to-transparent" />
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add webapp/src/components/SectionHeader.tsx
git commit -m "feat: add SectionHeader component for grouped menus"
```

---

## Task 9: CharacterMain — grouped menu, Lucide icons, hero card elevated

**Files:**
- Modify: `webapp/src/pages/CharacterMain.tsx`

- [ ] **Step 1: Rewrite CharacterMain**

Replace the entire content of `webapp/src/pages/CharacterMain.tsx` with:

```tsx
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import HPBar from '@/components/HPBar'
import Card from '@/components/Card'
import SectionHeader from '@/components/SectionHeader'
import { haptic } from '@/auth/telegram'
import {
  Heart, Shield, ShieldAlert, Sparkles, Gem,
  BarChart3, Target, Zap, Swords, Coins,
  User, Scroll, Star, CircleDot, Dices,
  NotebookPen, Map, BookOpen, Settings, ChevronLeft,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

type MenuItem = {
  key: string
  icon: LucideIcon
  path: string
}

const MENU_SECTIONS: { label: string; items: MenuItem[] }[] = [
  {
    label: 'Combattimento',
    items: [
      { key: 'hp',    icon: Heart,       path: 'hp' },
      { key: 'ac',    icon: Shield,      path: 'ac' },
      { key: 'saves', icon: ShieldAlert, path: 'saves' },
    ],
  },
  {
    label: 'Magia',
    items: [
      { key: 'spells', icon: Sparkles, path: 'spells' },
      { key: 'slots',  icon: Gem,      path: 'slots' },
    ],
  },
  {
    label: 'Abilità',
    items: [
      { key: 'stats',     icon: BarChart3, path: 'stats' },
      { key: 'skills',    icon: Target,    path: 'skills' },
      { key: 'abilities', icon: Zap,       path: 'abilities' },
    ],
  },
  {
    label: 'Equipaggiamento',
    items: [
      { key: 'inventory', icon: Swords, path: 'inventory' },
      { key: 'currency',  icon: Coins,  path: 'currency' },
    ],
  },
  {
    label: 'Personaggio',
    items: [
      { key: 'identity',   icon: User,      path: 'identity' },
      { key: 'class',      icon: Scroll,    path: 'class' },
      { key: 'xp',         icon: Star,      path: 'xp' },
      { key: 'conditions', icon: CircleDot, path: 'conditions' },
    ],
  },
  {
    label: 'Strumenti',
    items: [
      { key: 'dice',     icon: Dices,       path: 'dice' },
      { key: 'notes',    icon: NotebookPen, path: 'notes' },
      { key: 'maps',     icon: Map,         path: 'maps' },
      { key: 'history',  icon: BookOpen,    path: 'history' },
      { key: 'settings', icon: Settings,    path: 'settings' },
    ],
  },
]

export default function CharacterMain() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const navigate = useNavigate()
  const { t } = useTranslation()
  const qc = useQueryClient()

  const { data: char, isLoading, isError } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
    enabled: !!charId,
  })

  const inspirationMutation = useMutation({
    mutationFn: (value: boolean) => api.characters.updateInspiration(charId, value),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      haptic.light()
    },
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-dnd-text-secondary">{t('common.loading')}</p>
      </div>
    )
  }

  if (isError || !char) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4 p-4">
        <p className="text-[var(--dnd-danger)]">{t('common.error')}</p>
        <button onClick={() => navigate('/')} className="underline text-dnd-gold">
          {t('common.back')}
        </button>
      </div>
    )
  }

  const hpPct = char.hit_points > 0
    ? Math.round((char.current_hit_points / char.hit_points) * 100)
    : 0

  return (
    <div className="min-h-screen p-4 space-y-4 pb-safe animate-fade-in">
      {/* Header bar */}
      <div className="flex items-center gap-2 pt-1">
        <button onClick={() => navigate('/')} className="p-1 active:opacity-60">
          <ChevronLeft size={20} className="text-dnd-gold" />
        </button>
        <h1 className="text-xl font-bold font-cinzel text-dnd-gold truncate flex-1">
          {char.name}
        </h1>
        <button
          onClick={() => inspirationMutation.mutate(!char.heroic_inspiration)}
          title={char.heroic_inspiration ? t('character.inspiration.tap_to_spend') : t('character.inspiration.tap_to_grant')}
          className={`transition-opacity active:opacity-60 ${char.heroic_inspiration ? 'animate-shimmer' : 'opacity-25'}`}
        >
          <Sparkles size={22} className="text-dnd-gold" />
        </button>
        {char.is_party_active && (
          <span className="text-xs px-2 py-0.5 rounded-full bg-dnd-success/20 text-[#2ecc71]">
            Party
          </span>
        )}
      </div>

      {/* Hero card */}
      <Card variant="elevated">
        <div className="flex justify-between items-start mb-3">
          <div>
            <p className="text-sm text-dnd-text-secondary">{char.class_summary}</p>
            {char.race && (
              <p className="text-xs text-dnd-text-secondary">{char.race}</p>
            )}
          </div>
          <div className="text-right">
            <span className="text-2xl font-black">{char.ac}</span>
            <p className="text-xs text-dnd-gold-dim">CA</p>
          </div>
        </div>

        <div className="mb-1 flex items-center justify-between text-sm">
          <span>
            ❤️ {char.current_hit_points}/{char.hit_points}
            {char.temp_hp > 0 && (
              <span className="text-dnd-info ml-1">(+{char.temp_hp} temp)</span>
            )}
          </span>
          <span className="text-dnd-text-secondary">{hpPct}%</span>
        </div>
        <HPBar current={char.current_hit_points} max={char.hit_points} temp={char.temp_hp} />

        <div className="flex gap-4 mt-3 text-sm text-dnd-text-secondary">
          <span>⭐ {char.experience_points} XP</span>
          <span>💨 {char.speed}ft</span>
        </div>

        {char.concentrating_spell_id && (() => {
          const spell = char.spells?.find(s => s.id === char.concentrating_spell_id)
          return (
            <div className="mt-2">
              <span className="text-xs px-2 py-0.5 rounded-full bg-dnd-arcane/20 text-[#a569bd]">
                🔮 {spell?.name ?? t('character.spells.concentration')}
              </span>
            </div>
          )
        })()}

        {char.abilities?.filter(a => a.is_passive).length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {char.abilities.filter(a => a.is_passive).map(a => (
              <span key={a.id} className="text-xs px-2 py-0.5 rounded-full bg-[var(--dnd-gold-glow)] text-dnd-gold">
                ⚡ {a.name}
              </span>
            ))}
          </div>
        )}

        {char.conditions && Object.entries(char.conditions).filter(([, v]) => v).length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {Object.entries(char.conditions).filter(([, v]) => v).map(([key, val]) => (
              <span key={key} className="text-xs px-2 py-0.5 rounded-full bg-dnd-danger/20 text-[#e74c3c]">
                🌀 {t(`character.conditions.${key}`)}
                {typeof val === 'number' && val > 1 ? ` (${val})` : ''}
              </span>
            ))}
          </div>
        )}
      </Card>

      {/* Ability scores */}
      {char.ability_scores.length > 0 && (
        <Card variant="elevated" className="!p-3">
          <div className="grid grid-cols-6 gap-1 text-center">
            {char.ability_scores.map((score) => (
              <div key={score.name} className="flex flex-col items-center bg-dnd-surface rounded-lg p-1 border border-dnd-gold-dim/30">
                <span className="text-[0.55rem] text-dnd-gold-dim uppercase tracking-wide">
                  {score.name.slice(0, 3)}
                </span>
                <span className="text-lg font-black leading-tight">{score.value}</span>
                <span className="text-xs text-dnd-text-secondary">
                  {score.modifier >= 0 ? '+' : ''}{score.modifier}
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Menu grid — grouped */}
      {MENU_SECTIONS.map((section) => (
        <div key={section.label}>
          <SectionHeader>{section.label}</SectionHeader>
          <div className="grid grid-cols-3 gap-2">
            {section.items.map((item) => {
              const Icon = item.icon
              return (
                <button
                  key={item.key}
                  onClick={() => {
                    haptic.light()
                    navigate(`/char/${charId}/${item.path}`)
                  }}
                  className="flex flex-col items-center gap-1 p-3 rounded-2xl
                             bg-dnd-surface border border-transparent
                             active:border-dnd-gold-dim active:shadow-dnd-glow
                             transition-all duration-150"
                >
                  <Icon size={24} className="text-dnd-gold" strokeWidth={2} />
                  <span className="text-xs text-dnd-text-secondary text-center leading-tight">
                    {t(`character.menu.${item.key}`)}
                  </span>
                </button>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 2: Verify CharacterMain renders correctly**

Navigate to a character's main page. Verify:
- Gold Cinzel header with character name
- Shimmer animation on inspiration when active
- Hero card has gold border and glow
- Ability scores have subtle gold borders
- Menu is grouped into 6 sections with decorative headers
- Lucide icons in gold

- [ ] **Step 3: Commit**

```bash
git add webapp/src/pages/CharacterMain.tsx webapp/src/components/SectionHeader.tsx
git commit -m "feat: CharacterMain with grouped menu, Lucide icons, elevated hero card"
```

---

## Task 10: CharacterSelect — new palette and elevated cards

**Files:**
- Modify: `webapp/src/pages/CharacterSelect.tsx`

- [ ] **Step 1: Update CharacterSelect with D&D tokens**

Apply the following replacements across the entire file `webapp/src/pages/CharacterSelect.tsx`:

1. Replace all `text-[var(--tg-theme-hint-color)]` with `text-dnd-text-secondary`
2. Replace all `bg-[var(--tg-theme-button-color)]` with `bg-dnd-gold`
3. Replace all `text-[var(--tg-theme-button-text-color)]` with `text-dnd-bg`
4. Replace all `focus:ring-[var(--tg-theme-button-color)]` with `focus:ring-dnd-gold`
5. Replace all `bg-white/10` with `bg-dnd-surface`
6. Replace `text-red-400` with `text-[var(--dnd-danger)]`
7. Change the page title h1 to: `<h1 className="text-2xl font-bold font-cinzel text-dnd-gold pt-2">⚔️ {t('character.select.title')}</h1>`
8. Add `variant="elevated"` to the Card components that wrap each character in the list (the ones with `onClick`)
9. Add `animate-fade-in` to the root `<div>`: `<div className="min-h-screen p-4 space-y-4 pb-safe animate-fade-in">`

- [ ] **Step 2: Verify CharacterSelect**

Open http://localhost:5173 — character cards should have gold borders, buttons should be gold, text should use warm tones.

- [ ] **Step 3: Commit**

```bash
git add webapp/src/pages/CharacterSelect.tsx
git commit -m "feat: CharacterSelect with D&D palette, elevated cards, gold buttons"
```

---

## Task 11: HP page — card variants and new button colors

**Files:**
- Modify: `webapp/src/pages/HP.tsx`

- [ ] **Step 1: Update HP.tsx with D&D tokens**

Apply the following replacements across `webapp/src/pages/HP.tsx`:

1. Replace all `text-[var(--tg-theme-hint-color)]` with `text-dnd-text-secondary`
2. Replace all `bg-[var(--tg-theme-button-color)]` with `bg-dnd-gold`
3. Replace all `text-[var(--tg-theme-button-text-color)]` with `text-dnd-bg`
4. Replace all `focus:ring-[var(--tg-theme-button-color)]` with `focus:ring-dnd-gold`
5. Replace all `bg-white/10` with `bg-dnd-surface`
6. Replace `focus:ring-purple-500` with `focus:ring-dnd-arcane`
7. Add `variant="elevated"` to:
   - The HP display Card (the first Card that shows current HP / max HP and the HPBar)
   - The death saves Card (the one with the 💀 title)
   - The concentration save Card (the one with 🔮)
8. Modals inside HP.tsx (hitDiceResult, deathRollResult, concSaveResult): update their `<div>` containers:
   - Replace `bg-green-500/20 border border-green-500/40` with `bg-dnd-surface-elevated border-2 border-dnd-success`
   - Replace `bg-red-500/20 border border-red-500/40` with `bg-dnd-surface-elevated border-2 border-dnd-danger`
   - Replace `bg-yellow-500/20 border border-yellow-500/40` with `bg-dnd-surface-elevated border-2 border-dnd-gold`
   - Add `animate-modal-enter` class to each modal container
   - Update modal OK buttons from `bg-[var(--tg-theme-button-color)] text-[var(--tg-theme-button-text-color)]` to `bg-dnd-gold text-dnd-bg`
9. Update the death save roll button: `bg-yellow-500/20 text-yellow-300` → `bg-[var(--dnd-gold-glow)] text-dnd-gold`

- [ ] **Step 2: Verify HP page**

Test: damage/heal operations, death saves section (set HP to 0), rest buttons. Verify gold buttons, elevated cards for HP display and death saves, operative cards for input/shortcuts.

- [ ] **Step 3: Commit**

```bash
git add webapp/src/pages/HP.tsx
git commit -m "feat: HP page with D&D palette, card variants, modal animations"
```

---

## Task 12: Bulk update all remaining pages — replace tg-theme tokens

**Files:**
- Modify: All 17 remaining pages in `webapp/src/pages/`

This is a mechanical find-and-replace across all remaining page files. Apply these replacements to **every file** listed below:

**Files:** `AbilityScores.tsx`, `ArmorClass.tsx`, `SpellSlots.tsx`, `Conditions.tsx`, `Identity.tsx`, `Settings.tsx`, `SavingThrows.tsx`, `Multiclass.tsx`, `Experience.tsx`, `Inventory.tsx`, `Currency.tsx`, `Notes.tsx`, `Maps.tsx`, `Spells.tsx`, `Abilities.tsx`, `Dice.tsx`, `Skills.tsx`, `History.tsx`

- [ ] **Step 1: Apply token replacements**

For each file, apply these replacements (in this order):

| Find | Replace |
|------|---------|
| `text-[var(--tg-theme-hint-color)]` | `text-dnd-text-secondary` |
| `text-[var(--tg-theme-text-color)]` | `text-dnd-text` |
| `bg-[var(--tg-theme-button-color)]` | `bg-dnd-gold` |
| `text-[var(--tg-theme-button-text-color)]` | `text-dnd-bg` |
| `bg-[var(--tg-theme-secondary-bg-color)]` | `bg-dnd-surface` |
| `bg-[var(--tg-theme-bg-color)]` | `bg-dnd-bg` |
| `focus:ring-[var(--tg-theme-button-color)]` | `focus:ring-dnd-gold` |
| `bg-white/10` | `bg-dnd-surface` |
| `bg-[var(--tg-theme-button-color)]/15` | `bg-dnd-gold/15` |

Additionally for inline styles:
| Find | Replace |
|------|---------|
| `background: 'var(--tg-theme-bg-color)'` | `background: 'var(--dnd-bg)'` |
| `background: 'var(--tg-theme-secondary-bg-color)'` | `background: 'var(--dnd-surface)'` |

- [ ] **Step 2: Assign Card variants where appropriate**

For pages where Card wraps important character data (stat displays, roll results), add `variant="elevated"`. Specifically:

- **AbilityScores.tsx**: The Card wrapping the ability score editing grid → `variant="elevated"`
- **SavingThrows.tsx**: The Card wrapping the saving throw list → `variant="elevated"`
- **Experience.tsx**: The Card showing current XP/level → `variant="elevated"`
- **Conditions.tsx**: No change — condition toggles are interactive controls → keep default
- **Spells.tsx**: The sticky search/filter header Card → keep default; individual spell cards → keep default (they're list items)
- **All others**: keep default (they're forms, lists, or settings)

- [ ] **Step 3: Verify each page renders correctly**

Run `npm run dev` and navigate through all pages to spot-check. Focus on:
- Gold buttons replacing blue Telegram buttons
- Warm text tones
- Correct card backgrounds
- No leftover blue Telegram accent colors

- [ ] **Step 4: Commit**

```bash
git add webapp/src/pages/
git commit -m "feat: migrate all pages from tg-theme to dnd design tokens"
```

---

## Task 13: Final verification and build

- [ ] **Step 1: TypeScript check**

```bash
cd webapp && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 2: Visual smoke test**

Run `npm run dev` and verify these flows in the browser:
1. Character select → create new character → class selection → character main
2. Character main → HP → damage → verify HP bar animation → death saves (set HP to 0)
3. Character main → Skills → roll a skill → verify RollResultModal styling
4. Character main → Inventory → add a weapon → attack roll → verify WeaponAttackModal
5. Character main → verify grouped menu sections, Lucide icons, gold theme

- [ ] **Step 3: Production build**

```bash
cd webapp && npm run build:prod
```

Expected: build succeeds, output in `docs/app/`.

- [ ] **Step 4: Commit build output and all changes**

```bash
git add docs/app/
git commit -m "chore: rebuild webapp with Pergamena & Oro theme"
```
