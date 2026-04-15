# Webapp Complete Refactoring — "Pergamena & Oro" + Mobile-First UX — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reskin the D&D Telegram Mini App with a warm "Parchment & Gold" fantasy theme, decompose monolithic pages, add shared component library, swipe navigation between page groups, mobile UX improvements, lazy routes, and i18n cleanup.

**Architecture:** Vertical slice — build foundation (tokens, shared components, swipe hook), validate on first slice (CharacterSelect → CharacterMain → Combat group), replicate across remaining groups, polish with i18n + performance.

**Tech Stack:** React 18, TypeScript, Tailwind CSS 3.4, Lucide React (new), Google Font Cinzel (new), CSS animations, TanStack Query, Zustand, react-router-dom (HashRouter)

**Spec:** `docs/superpowers/specs/2026-04-15-webapp-complete-refactoring.md`

---

## File Structure

### New files
| File | Responsibility |
|------|----------------|
| `webapp/src/components/DndInput.tsx` | Reusable form input with label, validation, error |
| `webapp/src/components/DndButton.tsx` | Primary/secondary/danger button with loading state |
| `webapp/src/components/ModalProvider.tsx` | Modal context + useModal hook + swipe-dismiss |
| `webapp/src/components/Skeleton.tsx` | Shimmer loading placeholders (Line, Circle, Rect) |
| `webapp/src/components/ScrollArea.tsx` | Scroll container with bottom fade indicator |
| `webapp/src/components/SectionHeader.tsx` | Cinzel menu section divider |
| `webapp/src/hooks/useSwipeNavigation.ts` | Touch swipe between pages in group |
| `webapp/src/pages/hp/DeathSaves.tsx` | Death saves panel extracted from HP.tsx |
| `webapp/src/pages/hp/HitDiceModal.tsx` | Hit dice spending modal |
| `webapp/src/pages/hp/HpOperationForm.tsx` | Damage/heal/temp HP form |
| `webapp/src/pages/spells/SpellForm.tsx` | Add/edit spell form |
| `webapp/src/pages/spells/SpellItem.tsx` | Spell list item with accordion |
| `webapp/src/pages/spells/CastSpellModal.tsx` | Cast spell + slot selection |
| `webapp/src/pages/spells/SpellFilter.tsx` | Search/filter bar |
| `webapp/src/pages/inventory/ItemForm.tsx` | Add/edit item form |
| `webapp/src/pages/inventory/InventoryItem.tsx` | Inventory list item |
| `webapp/src/pages/inventory/itemMetadata.ts` | Metadata builder (pure logic) |
| `webapp/src/pages/notes/VoiceRecorder.tsx` | Voice recording with MediaRecorder |
| `webapp/src/pages/notes/NoteEditor.tsx` | Note add/edit form |
| `webapp/src/pages/notes/NoteItem.tsx` | Note list item |
| `webapp/src/pages/multiclass/ResourceManager.tsx` | Class resource CRUD |
| `webapp/src/pages/multiclass/AddClassForm.tsx` | Add class form |
| `webapp/src/pages/maps/MapUploadForm.tsx` | Map upload form |
| `webapp/src/pages/maps/MapZoneGroup.tsx` | Map zone grouped display |

### Modified files (in task order)
| File | What Changes |
|------|-------------|
| `webapp/package.json` | Add `lucide-react` |
| `webapp/index.html` | Add Cinzel font `<link>` |
| `webapp/tailwind.config.js` | Add `dnd` colors, `fontFamily.cinzel`, `boxShadow` |
| `webapp/src/index.css` | D&D tokens (dark+light), animations, body styles |
| `webapp/src/components/Card.tsx` | Add `variant` prop |
| `webapp/src/components/Layout.tsx` | Cinzel header, Lucide back, dot indicator, swipe |
| `webapp/src/components/HPBar.tsx` | Gradients, glow, pulse, transition |
| `webapp/src/components/RollResultModal.tsx` | D&D theme, modal-enter, pulse animations |
| `webapp/src/components/WeaponAttackModal.tsx` | Same modal treatment |
| `webapp/src/main.tsx` | Theme detection on init |
| `webapp/src/App.tsx` | ModalProvider wrapper, lazy routes + Suspense |
| `webapp/src/pages/CharacterSelect.tsx` | D&D palette, elevated cards, skeletons |
| `webapp/src/pages/CharacterMain.tsx` | Grouped menu, icons, hero card, gear icon |
| `webapp/src/pages/HP.tsx` | Decomposed, card variants, new components |
| `webapp/src/pages/ArmorClass.tsx` | Token migration + swipe |
| `webapp/src/pages/SavingThrows.tsx` | Token migration + swipe |
| `webapp/src/pages/Spells.tsx` | Decomposed + swipe |
| `webapp/src/pages/SpellSlots.tsx` | Token migration + swipe |
| `webapp/src/pages/AbilityScores.tsx` | Token migration + swipe |
| `webapp/src/pages/Skills.tsx` | Token migration + swipe |
| `webapp/src/pages/Abilities.tsx` | Token migration + swipe |
| `webapp/src/pages/Inventory.tsx` | Decomposed + swipe |
| `webapp/src/pages/Currency.tsx` | Token migration + swipe |
| `webapp/src/pages/Identity.tsx` | Token migration + swipe |
| `webapp/src/pages/Multiclass.tsx` | Decomposed + swipe |
| `webapp/src/pages/Experience.tsx` | Token migration + swipe |
| `webapp/src/pages/Conditions.tsx` | Token migration + swipe |
| `webapp/src/pages/Dice.tsx` | Token migration + swipe |
| `webapp/src/pages/Notes.tsx` | Decomposed + swipe |
| `webapp/src/pages/Maps.tsx` | Decomposed + swipe |
| `webapp/src/pages/History.tsx` | Token migration + swipe |
| `webapp/src/pages/Settings.tsx` | Token migration (no swipe — gear icon only) |
| `webapp/src/locales/it.json` | ~30-40 new keys |
| `webapp/src/locales/en.json` | ~30-40 new keys |

---

## Phase 1: Foundation

### Task 1: Install lucide-react and add Cinzel font

**Files:**
- Modify: `webapp/package.json`
- Modify: `webapp/index.html`

- [ ] **Step 1: Install lucide-react**

```bash
cd webapp && npm install lucide-react
```

- [ ] **Step 2: Add Cinzel Google Font link to index.html**

In `webapp/index.html`, replace the entire `<head>` with:

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
git add webapp/package.json webapp/package-lock.json webapp/index.html
git commit -m "chore: add lucide-react and Cinzel Google Font"
```

---

### Task 2: Design tokens — Tailwind config, CSS variables, theme detection

**Files:**
- Modify: `webapp/tailwind.config.js`
- Modify: `webapp/src/index.css`
- Modify: `webapp/src/main.tsx`

- [ ] **Step 1: Replace tailwind.config.js**

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

- [ ] **Step 2: Replace index.css**

Replace the entire content of `webapp/src/index.css` with:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  /* D&D "Pergamena & Oro" design tokens — Dark mode (default) */
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

  /* Keep Telegram fallbacks pointing to D&D tokens so old references work during migration */
  --tg-theme-bg-color: var(--dnd-bg);
  --tg-theme-text-color: var(--dnd-text);
  --tg-theme-hint-color: var(--dnd-text-secondary);
  --tg-theme-link-color: var(--dnd-gold);
  --tg-theme-button-color: var(--dnd-gold);
  --tg-theme-button-text-color: var(--dnd-bg);
  --tg-theme-secondary-bg-color: var(--dnd-surface);
}

/* Light mode — activated via .light class on <html> */
.light {
  --dnd-bg: #f4e8c1;
  --dnd-surface: #efe0b8;
  --dnd-surface-elevated: #fff8e7;
  --dnd-gold: #b8922e;
  --dnd-gold-dim: #c9a84c;
  --dnd-gold-glow: rgba(122, 92, 30, 0.1);
  --dnd-parchment: #fff8e7;
  --dnd-text: #3a2e1e;
  --dnd-text-secondary: #8a7a5a;
  --dnd-danger: #a93226;
  --dnd-success: #1e8449;
  --dnd-arcane: #7d3c98;
  --dnd-info: #2471a3;

  --tg-theme-bg-color: var(--dnd-bg);
  --tg-theme-text-color: var(--dnd-text);
  --tg-theme-hint-color: var(--dnd-text-secondary);
  --tg-theme-link-color: var(--dnd-gold);
  --tg-theme-button-color: var(--dnd-gold);
  --tg-theme-button-text-color: var(--dnd-parchment);
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

/* Skeleton shimmer */
@keyframes shimmerBg {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
.animate-skeleton {
  background: linear-gradient(90deg, var(--dnd-surface) 25%, var(--dnd-surface-elevated) 50%, var(--dnd-surface) 75%);
  background-size: 200% 100%;
  animation: shimmerBg 1.5s infinite;
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

- [ ] **Step 3: Add theme detection to main.tsx**

Replace the entire content of `webapp/src/main.tsx` with:

```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import './index.css'
import './i18n'

// Signal Telegram that the Mini App is ready
window.Telegram?.WebApp?.ready()
window.Telegram?.WebApp?.expand()

// Theme detection: apply .light class if Telegram reports light mode
function applyTheme() {
  const scheme = window.Telegram?.WebApp?.colorScheme
  document.documentElement.classList.toggle('light', scheme === 'light')
}
applyTheme()

// Listen for live theme changes (user toggles dark/light in Telegram)
window.Telegram?.WebApp?.onEvent?.('themeChanged', applyTheme)

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>
)
```

- [ ] **Step 4: Verify dev server shows new dark background**

```bash
cd webapp && npm run dev
```

Open http://localhost:5173 — background should be warm dark brown (#1a1614) instead of cold gray (#1c1c1e).

- [ ] **Step 5: Commit**

```bash
git add webapp/tailwind.config.js webapp/src/index.css webapp/src/main.tsx
git commit -m "feat: add D&D design tokens (dark+light), Tailwind dnd namespace, CSS animations, theme detection"
```

---

### Task 3: Shared components — DndInput, DndButton, Skeleton, ScrollArea, SectionHeader

**Files:**
- Create: `webapp/src/components/DndInput.tsx`
- Create: `webapp/src/components/DndButton.tsx`
- Create: `webapp/src/components/Skeleton.tsx`
- Create: `webapp/src/components/ScrollArea.tsx`
- Create: `webapp/src/components/SectionHeader.tsx`

- [ ] **Step 1: Create DndInput component**

Create `webapp/src/components/DndInput.tsx`:

```tsx
import { useState, useCallback } from 'react'

interface DndInputProps {
  label?: string
  type?: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  error?: string
  min?: number
  max?: number
  disabled?: boolean
  inputMode?: 'text' | 'numeric' | 'decimal' | 'tel' | 'search' | 'email' | 'url'
  className?: string
}

export default function DndInput({
  label,
  type = 'text',
  value,
  onChange,
  placeholder,
  error,
  min,
  max,
  disabled = false,
  inputMode,
  className = '',
}: DndInputProps) {
  const [focused, setFocused] = useState(false)
  const [localError, setLocalError] = useState('')

  const displayError = error || localError

  const handleBlur = useCallback(() => {
    setFocused(false)
    if (inputMode === 'numeric' || type === 'number') {
      const num = Number(value)
      if (value !== '' && isNaN(num)) {
        setLocalError('Valore non valido')
        return
      }
      if (min !== undefined && num < min) {
        setLocalError(`Minimo: ${min}`)
        return
      }
      if (max !== undefined && num > max) {
        setLocalError(`Massimo: ${max}`)
        return
      }
    }
    setLocalError('')
  }, [value, min, max, inputMode, type])

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (localError) setLocalError('')
    onChange(e.target.value)
  }

  const labelColor = displayError
    ? 'text-[var(--dnd-danger)]'
    : focused
      ? 'text-dnd-gold'
      : 'text-dnd-gold-dim'

  const borderColor = displayError
    ? 'border-[var(--dnd-danger)]'
    : focused
      ? 'border-dnd-gold-dim shadow-[0_0_0_2px_var(--dnd-gold-glow)]'
      : 'border-transparent'

  return (
    <div className={className}>
      {label && (
        <label className={`block text-[11px] uppercase tracking-wider mb-1 font-medium transition-colors ${labelColor}`}>
          {label}
        </label>
      )}
      <input
        type={inputMode === 'numeric' ? 'text' : type}
        inputMode={inputMode}
        value={value}
        onChange={handleChange}
        onFocus={() => setFocused(true)}
        onBlur={handleBlur}
        placeholder={placeholder}
        disabled={disabled}
        className={`w-full px-3 py-3 min-h-[48px] rounded-xl bg-dnd-surface text-dnd-text
                    border ${borderColor} outline-none transition-all duration-150
                    placeholder:text-dnd-text-secondary/50
                    disabled:opacity-40 disabled:cursor-not-allowed`}
      />
      {displayError && (
        <p className="text-[var(--dnd-danger)] text-[11px] mt-1">{displayError}</p>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Create DndButton component**

Create `webapp/src/components/DndButton.tsx`:

```tsx
import React from 'react'

interface DndButtonProps {
  variant?: 'primary' | 'secondary' | 'danger'
  loading?: boolean
  disabled?: boolean
  icon?: React.ReactNode
  children: React.ReactNode
  onClick?: () => void
  className?: string
  type?: 'button' | 'submit'
}

function DndButtonInner({
  variant = 'primary',
  loading = false,
  disabled = false,
  icon,
  children,
  onClick,
  className = '',
  type = 'button',
}: DndButtonProps) {
  const isDisabled = disabled || loading

  const base = 'min-h-[48px] px-4 py-3 rounded-xl font-semibold text-sm flex items-center justify-center gap-2 transition-all duration-75 active:scale-[0.97] active:opacity-70 disabled:opacity-40 disabled:pointer-events-none'

  const variants = {
    primary: 'bg-dnd-gold text-dnd-bg',
    secondary: 'bg-dnd-surface text-dnd-text border border-dnd-gold-dim/20',
    danger: 'bg-[var(--dnd-danger)]/15 text-[var(--dnd-danger)] border border-[var(--dnd-danger)]/30',
  }

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={isDisabled}
      className={`${base} ${variants[variant]} ${className}`}
    >
      {loading ? (
        <>
          <span className="w-4 h-4 border-2 border-current/30 border-t-current rounded-full animate-spin" />
          {children}
        </>
      ) : (
        <>
          {icon}
          {children}
        </>
      )}
    </button>
  )
}

const DndButton = React.memo(DndButtonInner)
export default DndButton
```

- [ ] **Step 3: Create Skeleton component**

Create `webapp/src/components/Skeleton.tsx`:

```tsx
import React from 'react'

interface SkeletonProps {
  width?: string
  height?: string
  rounded?: string
  className?: string
  delay?: number
}

function Line({ width = '100%', height = '14px', className = '', delay = 0 }: SkeletonProps) {
  return (
    <div
      className={`animate-skeleton rounded ${className}`}
      style={{ width, height, animationDelay: `${delay}ms` }}
    />
  )
}

function Circle({ width = '40px', height, className = '', delay = 0 }: SkeletonProps) {
  return (
    <div
      className={`animate-skeleton rounded-full ${className}`}
      style={{ width, height: height ?? width, animationDelay: `${delay}ms` }}
    />
  )
}

function Rect({ width = '100%', height = '80px', rounded = 'rounded-2xl', className = '', delay = 0 }: SkeletonProps) {
  return (
    <div
      className={`animate-skeleton ${rounded} ${className}`}
      style={{ width, height, animationDelay: `${delay}ms` }}
    />
  )
}

const Skeleton = { Line: React.memo(Line), Circle: React.memo(Circle), Rect: React.memo(Rect) }
export default Skeleton
```

- [ ] **Step 4: Create ScrollArea component**

Create `webapp/src/components/ScrollArea.tsx`:

```tsx
import { useRef, useState, useEffect } from 'react'

interface ScrollAreaProps {
  children: React.ReactNode
  className?: string
}

export default function ScrollArea({ children, className = '' }: ScrollAreaProps) {
  const sentinelRef = useRef<HTMLDivElement>(null)
  const [atBottom, setAtBottom] = useState(false)
  const [showHint] = useState(() => !localStorage.getItem('scroll-hint-seen'))

  useEffect(() => {
    const sentinel = sentinelRef.current
    if (!sentinel) return

    const observer = new IntersectionObserver(
      ([entry]) => {
        setAtBottom(entry.isIntersecting)
        if (entry.isIntersecting && showHint) {
          localStorage.setItem('scroll-hint-seen', '1')
        }
      },
      { threshold: 0.1 }
    )
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [showHint])

  return (
    <div className={`relative ${className}`}>
      {children}
      <div ref={sentinelRef} className="h-1" />
      {!atBottom && (
        <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-12 bg-gradient-to-t from-[var(--dnd-bg)] to-transparent flex items-end justify-center pb-2">
          {showHint && (
            <span className="text-[10px] text-dnd-gold-dim opacity-70">↓ scorri</span>
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 5: Create SectionHeader component**

Create `webapp/src/components/SectionHeader.tsx`:

```tsx
import React from 'react'

interface SectionHeaderProps {
  children: React.ReactNode
}

function SectionHeaderInner({ children }: SectionHeaderProps) {
  return (
    <div className="flex items-center gap-2 mt-4 mb-2">
      <span className="text-[0.65rem] font-cinzel font-bold text-dnd-gold-dim uppercase tracking-widest whitespace-nowrap">
        {children}
      </span>
      <div className="flex-1 h-px bg-gradient-to-r from-dnd-gold-dim to-transparent" />
    </div>
  )
}

const SectionHeader = React.memo(SectionHeaderInner)
export default SectionHeader
```

- [ ] **Step 6: Verify TypeScript compiles**

```bash
cd webapp && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add webapp/src/components/DndInput.tsx webapp/src/components/DndButton.tsx webapp/src/components/Skeleton.tsx webapp/src/components/ScrollArea.tsx webapp/src/components/SectionHeader.tsx
git commit -m "feat: add shared components — DndInput, DndButton, Skeleton, ScrollArea, SectionHeader"
```

---

### Task 4: ModalProvider + useModal hook

**Files:**
- Create: `webapp/src/components/ModalProvider.tsx`

- [ ] **Step 1: Create ModalProvider**

Create `webapp/src/components/ModalProvider.tsx`:

```tsx
import { createContext, useContext, useState, useCallback, useRef, type ReactNode } from 'react'

interface ModalOptions {
  content: ReactNode
  dismissible?: boolean
}

interface ModalContextValue {
  openModal: (options: ModalOptions) => void
  closeModal: () => void
  isModalOpen: boolean
}

const ModalContext = createContext<ModalContextValue | null>(null)

export function useModal() {
  const ctx = useContext(ModalContext)
  if (!ctx) throw new Error('useModal must be used within ModalProvider')
  return ctx
}

export default function ModalProvider({ children }: { children: ReactNode }) {
  const [stack, setStack] = useState<ModalOptions[]>([])
  const dragRef = useRef({ startY: 0, currentY: 0, dragging: false })
  const modalRef = useRef<HTMLDivElement>(null)

  const openModal = useCallback((options: ModalOptions) => {
    document.body.style.overflow = 'hidden'
    setStack((prev) => [...prev, { dismissible: true, ...options }])
  }, [])

  const closeModal = useCallback(() => {
    setStack((prev) => {
      const next = prev.slice(0, -1)
      if (next.length === 0) document.body.style.overflow = ''
      return next
    })
  }, [])

  const top = stack[stack.length - 1]

  // Swipe-down dismiss handlers
  const onTouchStart = useCallback((e: React.TouchEvent) => {
    dragRef.current = { startY: e.touches[0].clientY, currentY: e.touches[0].clientY, dragging: true }
  }, [])

  const onTouchMove = useCallback((e: React.TouchEvent) => {
    if (!dragRef.current.dragging) return
    const deltaY = e.touches[0].clientY - dragRef.current.startY
    dragRef.current.currentY = e.touches[0].clientY
    if (deltaY > 0 && modalRef.current) {
      modalRef.current.style.transform = `translateY(${deltaY}px)`
      modalRef.current.style.transition = 'none'
    }
  }, [])

  const onTouchEnd = useCallback(() => {
    const deltaY = dragRef.current.currentY - dragRef.current.startY
    dragRef.current.dragging = false
    if (modalRef.current) {
      modalRef.current.style.transition = 'transform 150ms ease'
      modalRef.current.style.transform = ''
    }
    if (deltaY > 120 && top?.dismissible) {
      closeModal()
    }
  }, [closeModal, top?.dismissible])

  return (
    <ModalContext.Provider value={{ openModal, closeModal, isModalOpen: stack.length > 0 }}>
      {children}
      {top && (
        <div
          className="fixed inset-0 bg-black/65 flex items-center justify-center p-4"
          style={{ zIndex: 50 + stack.length }}
          onClick={top.dismissible ? closeModal : undefined}
        >
          <div
            ref={modalRef}
            className="rounded-2xl bg-dnd-surface-elevated max-h-[85vh] overflow-y-auto w-full max-w-sm animate-modal-enter"
            style={{ WebkitOverflowScrolling: 'touch' }}
            onClick={(e) => e.stopPropagation()}
            onTouchStart={top.dismissible ? onTouchStart : undefined}
            onTouchMove={top.dismissible ? onTouchMove : undefined}
            onTouchEnd={top.dismissible ? onTouchEnd : undefined}
          >
            {top.content}
          </div>
        </div>
      )}
    </ModalContext.Provider>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd webapp && npx tsc --noEmit
```

- [ ] **Step 3: Wrap App with ModalProvider**

ModalProvider must be an ancestor of any component using `useModal()` — including `useSwipeNavigation` (used by Layout). Add it now so all subsequent tasks work.

In `webapp/src/App.tsx`, add the import at the top:

```tsx
import ModalProvider from './components/ModalProvider'
```

Then wrap the `<HashRouter>` contents:

```tsx
export default function App() {
  return (
    <HashRouter>
      <ModalProvider>
        <Routes>
          {/* ... existing routes unchanged ... */}
        </Routes>
      </ModalProvider>
    </HashRouter>
  )
}
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd webapp && npx tsc --noEmit
```

- [ ] **Step 5: Commit**

```bash
git add webapp/src/components/ModalProvider.tsx webapp/src/App.tsx
git commit -m "feat: add ModalProvider with swipe-dismiss, scroll lock, and z-index stacking"
```

---

### Task 5: Swipe navigation hook and page groups config

**Files:**
- Create: `webapp/src/hooks/useSwipeNavigation.ts`

- [ ] **Step 1: Create useSwipeNavigation hook**

Create `webapp/src/hooks/useSwipeNavigation.ts`:

```ts
import { useRef, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useModal } from '@/components/ModalProvider'
import { haptic } from '@/auth/telegram'

const PAGE_GROUPS: Record<string, string[]> = {
  combat: ['hp', 'ac', 'saves'],
  magic: ['spells', 'slots'],
  skills: ['stats', 'skills', 'abilities'],
  equipment: ['inventory', 'currency'],
  character: ['identity', 'class', 'xp', 'conditions'],
  tools: ['dice', 'notes', 'maps', 'history'],
}

export function getGroupInfo(group?: string, page?: string) {
  if (!group || !page) return null
  const pages = PAGE_GROUPS[group]
  if (!pages) return null
  const index = pages.indexOf(page)
  if (index === -1) return null
  return { pages, index, total: pages.length }
}

export function useSwipeNavigation(group?: string, page?: string) {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const { isModalOpen } = useModal()
  const touchRef = useRef({ startX: 0, startY: 0, swiping: false })
  const contentRef = useRef<HTMLDivElement>(null)

  const info = getGroupInfo(group, page)

  const onTouchStart = useCallback((e: React.TouchEvent) => {
    if (isModalOpen || !info) return
    const touch = e.touches[0]
    touchRef.current = { startX: touch.clientX, startY: touch.clientY, swiping: false }
  }, [isModalOpen, info])

  const onTouchMove = useCallback((e: React.TouchEvent) => {
    if (isModalOpen || !info) return
    const touch = e.touches[0]
    const deltaX = touch.clientX - touchRef.current.startX
    const deltaY = touch.clientY - touchRef.current.startY

    // Only engage if horizontal intent dominates
    if (!touchRef.current.swiping) {
      if (Math.abs(deltaX) > Math.abs(deltaY) * 1.5 && Math.abs(deltaX) > 10) {
        touchRef.current.swiping = true
      } else {
        return
      }
    }

    if (contentRef.current) {
      // Rubber-band at edges
      const atEdge = (deltaX > 0 && info.index === 0) || (deltaX < 0 && info.index === info.total - 1)
      const translate = atEdge ? deltaX * 0.3 : deltaX
      contentRef.current.style.transform = `translateX(${translate}px)`
      contentRef.current.style.transition = 'none'
    }
  }, [isModalOpen, info])

  const onTouchEnd = useCallback(() => {
    if (!info || !touchRef.current.swiping) {
      if (contentRef.current) {
        contentRef.current.style.transform = ''
        contentRef.current.style.transition = ''
      }
      return
    }

    const deltaX = (contentRef.current?.style.transform
      ? parseFloat(contentRef.current.style.transform.replace('translateX(', '').replace('px)', ''))
      : 0)

    if (contentRef.current) {
      contentRef.current.style.transition = 'transform 150ms ease'
      contentRef.current.style.transform = ''
    }

    if (Math.abs(deltaX) > 80) {
      const direction = deltaX > 0 ? -1 : 1
      const nextIndex = info.index + direction
      if (nextIndex >= 0 && nextIndex < info.total) {
        haptic.light()
        navigate(`/char/${id}/${info.pages[nextIndex]}`, { replace: true })
      }
    }

    touchRef.current.swiping = false
  }, [info, navigate, id])

  return {
    contentRef,
    onTouchStart,
    onTouchMove,
    onTouchEnd,
    currentIndex: info?.index ?? 0,
    total: info?.total ?? 1,
  }
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd webapp && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add webapp/src/hooks/useSwipeNavigation.ts
git commit -m "feat: add useSwipeNavigation hook with touch gestures and page groups"
```

---

### Task 6: Upgrade existing shared components — Card, Layout, HPBar, RollResultModal, WeaponAttackModal

**Files:**
- Modify: `webapp/src/components/Card.tsx`
- Modify: `webapp/src/components/Layout.tsx`
- Modify: `webapp/src/components/HPBar.tsx`
- Modify: `webapp/src/components/RollResultModal.tsx`
- Modify: `webapp/src/components/WeaponAttackModal.tsx`

- [ ] **Step 1: Replace Card.tsx with variant support**

Replace the entire content of `webapp/src/components/Card.tsx` with:

```tsx
import React from 'react'

interface CardProps {
  children: React.ReactNode
  className?: string
  variant?: 'default' | 'elevated'
  onClick?: (e: React.MouseEvent<HTMLDivElement>) => void
}

function CardInner({ children, className = '', variant = 'default', onClick }: CardProps) {
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

const Card = React.memo(CardInner)
export default Card
```

- [ ] **Step 2: Replace Layout.tsx with Cinzel header, dots, swipe support**

Replace the entire content of `webapp/src/components/Layout.tsx` with:

```tsx
import { useNavigate } from 'react-router-dom'
import { ChevronLeft } from 'lucide-react'
import { useSwipeNavigation, getGroupInfo } from '@/hooks/useSwipeNavigation'

interface LayoutProps {
  title: string
  children: React.ReactNode
  backTo?: string
  group?: string
  page?: string
}

export default function Layout({ title, children, backTo, group, page }: LayoutProps) {
  const navigate = useNavigate()
  const swipe = useSwipeNavigation(group, page)
  const info = getGroupInfo(group, page)

  const handleBack = () => {
    if (backTo) navigate(backTo)
    else navigate(-1)
  }

  return (
    <div className="min-h-screen w-full flex flex-col bg-dnd-bg">
      <header
        className="sticky top-0 z-10 flex flex-col px-4 py-3 pt-safe
                    bg-dnd-surface-elevated border-b border-dnd-gold-dim/30"
      >
        <div className="flex items-center gap-3">
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
        </div>
        {info && (
          <div className="flex justify-center gap-1.5 mt-2">
            {Array.from({ length: info.total }).map((_, i) => (
              <div
                key={i}
                className={`w-2 h-2 rounded-full transition-colors ${
                  i === info.index ? 'bg-dnd-gold' : 'bg-dnd-gold-dim/40'
                }`}
              />
            ))}
          </div>
        )}
      </header>

      <main
        ref={swipe.contentRef}
        className="flex-1 min-w-0 p-4 space-y-3 pb-safe animate-fade-in"
        onTouchStart={swipe.onTouchStart}
        onTouchMove={swipe.onTouchMove}
        onTouchEnd={swipe.onTouchEnd}
      >
        {children}
      </main>
    </div>
  )
}
```

- [ ] **Step 3: Replace HPBar.tsx with gradients and glow**

Replace the entire content of `webapp/src/components/HPBar.tsx` with:

```tsx
import React from 'react'

interface HPBarProps {
  current: number
  max: number
  temp?: number
  size?: 'sm' | 'md'
}

function HPBarInner({ current, max, temp = 0, size = 'md' }: HPBarProps) {
  const pct = max > 0 ? Math.min(100, (current / max) * 100) : 0
  const height = size === 'sm' ? 'h-1.5' : 'h-2.5'

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
        style={{ width: `${pct}%`, background: gradient, boxShadow: glow }}
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

const HPBar = React.memo(HPBarInner)
export default HPBar
```

- [ ] **Step 4: Replace RollResultModal.tsx with D&D theme**

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
          className="w-full py-2.5 rounded-xl bg-dnd-gold text-dnd-bg font-semibold mt-2
                     min-h-[48px] active:scale-[0.97] active:opacity-70 transition-all duration-75"
        >
          OK
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Replace WeaponAttackModal.tsx with D&D theme**

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
          className="w-full py-2.5 rounded-xl bg-dnd-gold text-dnd-bg font-semibold
                     min-h-[48px] active:scale-[0.97] active:opacity-70 transition-all duration-75"
        >
          OK
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 6: Verify all components compile and dev server renders**

```bash
cd webapp && npx tsc --noEmit && npm run dev
```

Open http://localhost:5173 — pages should render with new warm colors via the `--tg-theme-*` → `--dnd-*` fallback chain. Cards should use new surface color. Layout header should show gold Cinzel title.

- [ ] **Step 7: Commit**

```bash
git add webapp/src/components/Card.tsx webapp/src/components/Layout.tsx webapp/src/components/HPBar.tsx webapp/src/components/RollResultModal.tsx webapp/src/components/WeaponAttackModal.tsx
git commit -m "feat: upgrade Card, Layout, HPBar, RollResultModal, WeaponAttackModal with D&D theme"
```

---

## Phase 2: First Vertical Slice

### Task 7: CharacterSelect — D&D palette, elevated cards, skeletons

**Files:**
- Modify: `webapp/src/pages/CharacterSelect.tsx`

This is a mechanical token migration + Card variant assignment. The page is 336 lines.

- [ ] **Step 1: Apply token replacements across CharacterSelect.tsx**

Open `webapp/src/pages/CharacterSelect.tsx` and apply these find-and-replace operations:

| Find | Replace |
|------|---------|
| `text-[var(--tg-theme-hint-color)]` | `text-dnd-text-secondary` |
| `bg-[var(--tg-theme-button-color)]` | `bg-dnd-gold` |
| `text-[var(--tg-theme-button-text-color)]` | `text-dnd-bg` |
| `focus:ring-[var(--tg-theme-button-color)]` | `focus:ring-dnd-gold` |
| `bg-[var(--tg-theme-secondary-bg-color)]` | `bg-dnd-surface` |
| `bg-[var(--tg-theme-bg-color)]` | `bg-dnd-bg` |
| `bg-white/10` | `bg-dnd-surface` |
| `text-red-400` | `text-[var(--dnd-danger)]` |

Additionally:
1. Find the page title `<h1>` and change it to: `<h1 className="text-2xl font-bold font-cinzel text-dnd-gold pt-2">`
2. Add `animate-fade-in` to the root `<div>`: change `className="min-h-screen p-4 space-y-4 pb-safe"` to `className="min-h-screen p-4 space-y-4 pb-safe animate-fade-in"`
3. For each `<Card>` that wraps a character in the list (the ones with `onClick`), add `variant="elevated"`
4. For the character creation form Card, keep `variant` as default (no prop needed)

- [ ] **Step 2: Add loading skeleton**

Find the loading state (`isLoading`) section in CharacterSelect.tsx — currently shows `<p>{t('common.loading')}</p>`. Replace it with:

```tsx
import Skeleton from '@/components/Skeleton'

// In the loading return:
return (
  <div className="min-h-screen p-4 space-y-4 pb-safe animate-fade-in">
    <Skeleton.Line width="200px" height="28px" />
    <Skeleton.Rect height="120px" />
    <Skeleton.Rect height="120px" delay={100} />
    <Skeleton.Rect height="120px" delay={200} />
  </div>
)
```

- [ ] **Step 3: Verify CharacterSelect renders correctly**

Open http://localhost:5173 — character cards should have gold borders and glow, buttons should be gold, title should be Cinzel font.

- [ ] **Step 4: Commit**

```bash
git add webapp/src/pages/CharacterSelect.tsx
git commit -m "feat: CharacterSelect with D&D palette, elevated cards, skeleton loading"
```

---

### Task 8: CharacterMain — grouped menu, Lucide icons, hero card, gear icon, skeletons

**Files:**
- Modify: `webapp/src/pages/CharacterMain.tsx`

This is a full rewrite of CharacterMain.tsx (currently 207 lines). The new version uses SectionHeader, Lucide icons, hero card with elevated variant, gear icon for Settings, and i18n for menu section labels.

- [ ] **Step 1: Rewrite CharacterMain.tsx**

Replace the entire content of `webapp/src/pages/CharacterMain.tsx` with the CharacterMain code from the spec (Section 6). The full code is in the existing plan at `docs/superpowers/plans/2026-04-13-webapp-visual-redesign.md` Task 9, Step 1 — with these modifications:

1. Remove `Settings` from `MENU_SECTIONS` Tools group
2. Add gear icon to header bar (Lucide `Settings` icon, gold, navigates to `/char/${charId}/settings`)
3. Use `t('character.menu.sections.combat')` etc. for section headers instead of hardcoded Italian
4. Add loading skeleton when `isLoading` is true
5. Import `Skeleton` from `@/components/Skeleton`

The key structural changes from current CharacterMain:
- Import Lucide icons instead of using emoji strings
- Replace flat MENU_ITEMS array with grouped MENU_SECTIONS
- Replace emoji-based menu grid with icon-based grouped grid using SectionHeader
- Add Settings gear icon in header between inspiration and party badge
- Add `animate-fade-in` to root div

- [ ] **Step 2: Add i18n keys for menu sections**

Add these keys to `webapp/src/locales/it.json` under `character.menu`:

```json
"sections": {
  "combat": "Combattimento",
  "magic": "Magia",
  "skills": "Abilità",
  "equipment": "Equipaggiamento",
  "character": "Personaggio",
  "tools": "Strumenti"
}
```

Add matching keys to `webapp/src/locales/en.json`:

```json
"sections": {
  "combat": "Combat",
  "magic": "Magic",
  "skills": "Skills",
  "equipment": "Equipment",
  "character": "Character",
  "tools": "Tools"
}
```

- [ ] **Step 3: Verify CharacterMain renders**

Navigate to a character's main page. Verify: gold Cinzel header, grouped menu with SectionHeader dividers, Lucide icons in gold, hero card with elevated style, gear icon in header.

- [ ] **Step 4: Commit**

```bash
git add webapp/src/pages/CharacterMain.tsx webapp/src/locales/it.json webapp/src/locales/en.json
git commit -m "feat: CharacterMain with grouped menu, Lucide icons, hero card, gear icon"
```

---

### Task 9: HP page — decompose into sub-components + apply D&D theme + swipe

**Files:**
- Create: `webapp/src/pages/hp/DeathSaves.tsx`
- Create: `webapp/src/pages/hp/HitDiceModal.tsx`
- Create: `webapp/src/pages/hp/HpOperationForm.tsx`
- Modify: `webapp/src/pages/HP.tsx`

This is the most complex decomposition. HP.tsx (546 lines) becomes ~180 lines orchestrating 3 sub-components.

- [ ] **Step 1: Create HpOperationForm sub-component**

Create `webapp/src/pages/hp/HpOperationForm.tsx` — extracts the damage/heal/set/temp HP form logic. This component receives the character data and mutation function as props. Uses DndInput for the value field. Quick buttons (±1, ±5, ±10, ±20) with DndButton styling.

Key props: `charId: number`, `currentHp: number`, `maxHp: number`, `tempHp: number`, `onMutate: (op, value) => void`, `isPending: boolean`

The form contains: operation selector (damage/heal/set/temp), numeric input, quick buttons, submit button.

- [ ] **Step 2: Create DeathSaves sub-component**

Create `webapp/src/pages/hp/DeathSaves.tsx` — extracts death saves panel + roll logic. Uses Card variant="elevated". Receives death saves state and roll mutation as props.

Key props: `deathSaves: DeathSaves`, `charId: number`, `onRoll: () => void`, `rollResult: DeathSaveRollResult | null`, `onCloseResult: () => void`

- [ ] **Step 3: Create HitDiceModal sub-component**

Create `webapp/src/pages/hp/HitDiceModal.tsx` — extracts hit dice spending UI. Opened via ModalProvider. Shows available hit dice per class, spending buttons, result display.

Key props: `charId: number`, `classes: CharacterClass[]`, `onSpend: (classId, count) => void`, `result: HitDiceSpendResult | null`

- [ ] **Step 4: Simplify HP.tsx**

Rewrite `webapp/src/pages/HP.tsx` to:
1. Import and use the 3 sub-components
2. Use Layout with `group="combat" page="hp"` for swipe navigation
3. Apply D&D token replacements (same pattern as CharacterSelect)
4. Use Card `variant="elevated"` for HP display, death saves, concentration banner
5. Use DndButton for rest buttons and concentration save
6. Use ModalProvider for hit dice result and concentration save result modals
7. Remove all extracted state/logic — sub-components own their own state

Target: ~180 lines for the orchestrator.

- [ ] **Step 5: Apply token replacements**

Same replacement table as Task 7 Step 1, applied to all 4 files. Additionally replace any `bg-green-500/20`, `bg-red-500/20`, `bg-yellow-500/20` modal backgrounds with `bg-dnd-surface-elevated` + appropriate border color.

- [ ] **Step 6: Verify HP page**

Navigate to a character's HP page. Test:
- Damage/heal operations work
- Death saves section shows at HP=0
- Short/long rest buttons work
- Hit dice spending works
- Swipe left/right navigates to other Combat group pages
- Dots indicator shows 3 dots with first active

- [ ] **Step 7: Commit**

```bash
git add webapp/src/pages/hp/ webapp/src/pages/HP.tsx
git commit -m "feat: decompose HP page — extract DeathSaves, HitDiceModal, HpOperationForm + D&D theme + swipe"
```

---

### Task 10: ArmorClass + SavingThrows — token migration + swipe (complete Combat group)

**Files:**
- Modify: `webapp/src/pages/ArmorClass.tsx`
- Modify: `webapp/src/pages/SavingThrows.tsx`

These are small pages (93 and 128 lines). Mechanical token migration + add Layout swipe props.

- [ ] **Step 1: Update ArmorClass.tsx**

1. Apply standard token replacements (same table as Task 7)
2. Change `<Layout title={...} backTo={...}>` to `<Layout title={...} backTo={...} group="combat" page="ac">`
3. Add `variant="elevated"` to the Card wrapping AC display values
4. Replace any raw `<button>` styles with DndButton or apply gold button classes

- [ ] **Step 2: Update SavingThrows.tsx**

1. Apply standard token replacements
2. Change `<Layout>` to include `group="combat" page="saves"`
3. Add `variant="elevated"` to the Card wrapping the saving throw list
4. Replace button styles with D&D gold classes

- [ ] **Step 3: Verify Combat group swipe**

Navigate to HP page → swipe left → should go to AC. Swipe left again → Saving Throws. Dots should show position correctly. Swipe right at HP → rubber-band bounce (edge of group).

- [ ] **Step 4: Commit**

```bash
git add webapp/src/pages/ArmorClass.tsx webapp/src/pages/SavingThrows.tsx
git commit -m "feat: ArmorClass + SavingThrows — D&D tokens + Combat group swipe"
```

---

## Phase 3: Replicate Pattern

### Task 11: Magic group — Spells decomposition + SpellSlots + swipe

**Files:**
- Create: `webapp/src/pages/spells/SpellForm.tsx`
- Create: `webapp/src/pages/spells/SpellItem.tsx`
- Create: `webapp/src/pages/spells/CastSpellModal.tsx`
- Create: `webapp/src/pages/spells/SpellFilter.tsx`
- Modify: `webapp/src/pages/Spells.tsx`
- Modify: `webapp/src/pages/SpellSlots.tsx`

Spells.tsx (652 lines) → ~200 main + 4 sub-components. SpellSlots.tsx (148 lines) stays intact, just token migration + swipe.

- [ ] **Step 1: Create SpellFilter sub-component**

Extract the search input and level filter dropdowns into `spells/SpellFilter.tsx`. Props: `search`, `onSearchChange`, `levelFilter`, `onLevelFilterChange`.

- [ ] **Step 2: Create SpellItem sub-component**

Extract the individual spell rendering (accordion with expand/collapse, spell details, cast/damage buttons) into `spells/SpellItem.tsx`. Wrap with `React.memo`. Props: spell data, charId, onCast, onRemove, isConcentrating, etc.

- [ ] **Step 3: Create SpellForm sub-component**

Extract add/edit spell form into `spells/SpellForm.tsx`. Uses DndInput for all fields. Props: initialData (for edit), onSubmit, onCancel.

- [ ] **Step 4: Create CastSpellModal sub-component**

Extract spell slot selection + cast logic into `spells/CastSpellModal.tsx`. Opened via ModalProvider. Props: spell, spellSlots, onCast, onCancel.

- [ ] **Step 5: Simplify Spells.tsx**

Rewrite to use sub-components. Add `group="magic" page="spells"` to Layout. Apply token replacements. Use ScrollArea for spell list.

- [ ] **Step 6: Update SpellSlots.tsx**

Apply token replacements. Add `group="magic" page="slots"` to Layout.

- [ ] **Step 7: Verify Magic group**

Test: add/edit/delete spells, cast with slot selection, search/filter, concentration tracking. Swipe between Spells ↔ Spell Slots.

- [ ] **Step 8: Commit**

```bash
git add webapp/src/pages/spells/ webapp/src/pages/Spells.tsx webapp/src/pages/SpellSlots.tsx
git commit -m "feat: decompose Spells page + SpellSlots — D&D theme + Magic group swipe"
```

---

### Task 12: Skills group — AbilityScores + Skills + Abilities + swipe

**Files:**
- Modify: `webapp/src/pages/AbilityScores.tsx`
- Modify: `webapp/src/pages/Skills.tsx`
- Modify: `webapp/src/pages/Abilities.tsx`

All three pages are under 310 lines — no decomposition needed, just token migration + swipe.

- [ ] **Step 1: Update AbilityScores.tsx**

Apply token replacements. Add `group="skills" page="stats"` to Layout. Add `variant="elevated"` to the ability score editing Card.

- [ ] **Step 2: Update Skills.tsx**

Apply token replacements. Add `group="skills" page="skills"` to Layout. Use ScrollArea for skill list.

- [ ] **Step 3: Update Abilities.tsx**

Apply token replacements. Add `group="skills" page="abilities"` to Layout. Use ScrollArea for abilities list.

- [ ] **Step 4: Verify Skills group swipe**

Navigate between AbilityScores ↔ Skills ↔ Abilities via swipe.

- [ ] **Step 5: Commit**

```bash
git add webapp/src/pages/AbilityScores.tsx webapp/src/pages/Skills.tsx webapp/src/pages/Abilities.tsx
git commit -m "feat: AbilityScores + Skills + Abilities — D&D tokens + Skills group swipe"
```

---

### Task 13: Equipment group — Inventory decomposition + Currency + swipe

**Files:**
- Create: `webapp/src/pages/inventory/ItemForm.tsx`
- Create: `webapp/src/pages/inventory/InventoryItem.tsx`
- Create: `webapp/src/pages/inventory/itemMetadata.ts`
- Modify: `webapp/src/pages/Inventory.tsx`
- Modify: `webapp/src/pages/Currency.tsx`

Inventory.tsx (659 lines) → ~200 main + 3 files. Currency.tsx (258 lines) stays intact.

- [ ] **Step 1: Create itemMetadata.ts**

Extract metadata building logic (damage dice/type for weapons, AC for armor, properties, etc.) into pure function `buildItemMetadata(formState) → Record<string, unknown>`. No UI — just logic.

- [ ] **Step 2: Create InventoryItem sub-component**

Extract individual item rendering into `inventory/InventoryItem.tsx`. Wrap with `React.memo`. Props: item, onEquipToggle, onQuantityChange, onAttack, onDelete, onEdit.

- [ ] **Step 3: Create ItemForm sub-component**

Extract add/edit item form into `inventory/ItemForm.tsx`. Uses DndInput for all fields. Dynamic metadata fields based on item_type. Uses `buildItemMetadata` from itemMetadata.ts.

- [ ] **Step 4: Simplify Inventory.tsx**

Rewrite to use sub-components. Add `group="equipment" page="inventory"` to Layout. Use ScrollArea for item list.

- [ ] **Step 5: Update Currency.tsx**

Apply token replacements. Add `group="equipment" page="currency"` to Layout.

- [ ] **Step 6: Verify Equipment group**

Test: add/edit/delete items, weapon attack, equip toggle, currency conversion. Swipe between Inventory ↔ Currency.

- [ ] **Step 7: Commit**

```bash
git add webapp/src/pages/inventory/ webapp/src/pages/Inventory.tsx webapp/src/pages/Currency.tsx
git commit -m "feat: decompose Inventory page + Currency — D&D theme + Equipment group swipe"
```

---

### Task 14: Character group — Identity + Multiclass decomposition + Experience + Conditions + swipe

**Files:**
- Create: `webapp/src/pages/multiclass/ResourceManager.tsx`
- Create: `webapp/src/pages/multiclass/AddClassForm.tsx`
- Modify: `webapp/src/pages/Identity.tsx`
- Modify: `webapp/src/pages/Multiclass.tsx`
- Modify: `webapp/src/pages/Experience.tsx`
- Modify: `webapp/src/pages/Conditions.tsx`

Multiclass.tsx (389 lines) → ~150 main + 2 sub-components. Others stay intact.

- [ ] **Step 1: Create AddClassForm sub-component**

Extract class picker + hit die selection into `multiclass/AddClassForm.tsx`. Uses DndInput + DndButton. Props: onAdd, existingClassNames.

- [ ] **Step 2: Create ResourceManager sub-component**

Extract resource CRUD (add/edit/delete/use resources) into `multiclass/ResourceManager.tsx`. Props: classId, charId, resources, onAddResource, onUseResource, onDeleteResource.

- [ ] **Step 3: Simplify Multiclass.tsx**

Rewrite to use sub-components. Add `group="character" page="class"` to Layout.

- [ ] **Step 4: Update Identity.tsx**

Apply token replacements. Add `group="character" page="identity"` to Layout. Replace raw inputs with DndInput where appropriate.

- [ ] **Step 5: Update Experience.tsx**

Apply token replacements. Add `group="character" page="xp"` to Layout. Add `variant="elevated"` to XP display Card. Fix hardcoded "Liv." → use `t('character.xp.level_abbr')`.

- [ ] **Step 6: Update Conditions.tsx**

Apply token replacements. Add `group="character" page="conditions"` to Layout.

- [ ] **Step 7: Verify Character group**

Navigate Identity ↔ Multiclass ↔ Experience ↔ Conditions via swipe.

- [ ] **Step 8: Commit**

```bash
git add webapp/src/pages/multiclass/ webapp/src/pages/Multiclass.tsx webapp/src/pages/Identity.tsx webapp/src/pages/Experience.tsx webapp/src/pages/Conditions.tsx
git commit -m "feat: decompose Multiclass + update Character group — D&D theme + swipe"
```

---

### Task 15: Tools group — Dice + Notes decomposition + Maps decomposition + History + swipe

**Files:**
- Create: `webapp/src/pages/notes/VoiceRecorder.tsx`
- Create: `webapp/src/pages/notes/NoteEditor.tsx`
- Create: `webapp/src/pages/notes/NoteItem.tsx`
- Create: `webapp/src/pages/maps/MapUploadForm.tsx`
- Create: `webapp/src/pages/maps/MapZoneGroup.tsx`
- Modify: `webapp/src/pages/Dice.tsx`
- Modify: `webapp/src/pages/Notes.tsx`
- Modify: `webapp/src/pages/Maps.tsx`
- Modify: `webapp/src/pages/History.tsx`

Notes.tsx (428 lines) → ~150 main + 3 sub-components. Maps.tsx (361 lines) → ~120 main + 2 sub-components.

- [ ] **Step 1: Create VoiceRecorder sub-component**

Extract MediaRecorder logic, duration timer, recording controls into `notes/VoiceRecorder.tsx`. Props: onRecordComplete(blob, duration), onCancel.

- [ ] **Step 2: Create NoteEditor sub-component**

Extract add/edit note form into `notes/NoteEditor.tsx`. Props: initialNote (for edit), onSave, onCancel. Uses DndInput for title, textarea for body.

- [ ] **Step 3: Create NoteItem sub-component**

Extract note list item rendering into `notes/NoteItem.tsx`. Wrap with `React.memo`. Props: note, onEdit, onDelete, onPlay (for voice notes), voiceUrl.

- [ ] **Step 4: Simplify Notes.tsx**

Rewrite to use sub-components. Add `group="tools" page="notes"` to Layout. Use ScrollArea for note list.

- [ ] **Step 5: Create MapUploadForm sub-component**

Extract file upload form into `maps/MapUploadForm.tsx`. Props: charId, onUploadComplete. Uses DndInput for zone name, DndButton for submit.

- [ ] **Step 6: Create MapZoneGroup sub-component**

Extract zone group display into `maps/MapZoneGroup.tsx`. Props: zoneName, maps, onDelete, onDeleteZone, charId.

- [ ] **Step 7: Simplify Maps.tsx**

Rewrite to use sub-components. Add `group="tools" page="maps"` to Layout.

- [ ] **Step 8: Update Dice.tsx**

Apply token replacements. Add `group="tools" page="dice"` to Layout. Use ScrollArea for dice history.

- [ ] **Step 9: Update History.tsx**

Apply token replacements. Add `group="tools" page="history"` to Layout. Use ScrollArea for event list.

- [ ] **Step 10: Verify Tools group**

Navigate Dice ↔ Notes ↔ Maps ↔ History via swipe. Test voice recording, map upload, dice rolls.

- [ ] **Step 11: Commit**

```bash
git add webapp/src/pages/notes/ webapp/src/pages/Notes.tsx webapp/src/pages/maps/ webapp/src/pages/Maps.tsx webapp/src/pages/Dice.tsx webapp/src/pages/History.tsx
git commit -m "feat: decompose Notes + Maps + update Dice + History — D&D theme + Tools group swipe"
```

---

### Task 16: Settings — gear icon access only, token migration

**Files:**
- Modify: `webapp/src/pages/Settings.tsx`

Settings is no longer in any swipe group — accessed via gear icon in CharacterMain header.

- [ ] **Step 1: Update Settings.tsx**

Apply token replacements. Do NOT add `group` or `page` props to Layout. Use DndButton for toggle buttons (language, spell slots mode, party active).

- [ ] **Step 2: Commit**

```bash
git add webapp/src/pages/Settings.tsx
git commit -m "feat: Settings page — D&D token migration, no swipe group"
```

---

## Phase 4: Polish

### Task 17: i18n cleanup — move hardcoded strings to locale files

**Files:**
- Modify: `webapp/src/locales/it.json`
- Modify: `webapp/src/locales/en.json`
- Modify: `webapp/src/pages/CharacterSelect.tsx`
- Modify: `webapp/src/pages/Experience.tsx`
- Modify: `webapp/src/pages/Multiclass.tsx`

- [ ] **Step 1: Move DND_CLASSES to locale files**

In `CharacterSelect.tsx`, the `DND_CLASSES` array has hardcoded Italian class names. Move to i18n:

Add to `it.json`:
```json
"dnd": {
  "classes": {
    "barbarian": "Barbaro",
    "bard": "Bardo",
    "cleric": "Chierico",
    "druid": "Druido",
    "fighter": "Guerriero",
    "rogue": "Ladro",
    "wizard": "Mago",
    "monk": "Monaco",
    "paladin": "Paladino",
    "ranger": "Ranger",
    "sorcerer": "Stregone",
    "warlock": "Warlock"
  }
}
```

Add English equivalents to `en.json`:
```json
"dnd": {
  "classes": {
    "barbarian": "Barbarian",
    "bard": "Bard",
    "cleric": "Cleric",
    "druid": "Druid",
    "fighter": "Fighter",
    "rogue": "Rogue",
    "wizard": "Wizard",
    "monk": "Monk",
    "paladin": "Paladin",
    "ranger": "Ranger",
    "sorcerer": "Sorcerer",
    "warlock": "Warlock"
  }
}
```

Update `CharacterSelect.tsx` and `Multiclass.tsx` to use `t('dnd.classes.barbarian')` etc. instead of hardcoded strings.

- [ ] **Step 2: Fix Experience.tsx hardcoded "Liv."**

Replace `"Liv."` with `t('character.xp.level_abbr')`.

Add to `it.json`: `"level_abbr": "Liv."` under `character.xp`.
Add to `en.json`: `"level_abbr": "Lv."` under `character.xp`.

- [ ] **Step 3: Verify all pages render with correct translations**

Switch language in Settings between Italian and English. All text should translate — no Italian text visible in English mode.

- [ ] **Step 4: Commit**

```bash
git add webapp/src/locales/ webapp/src/pages/CharacterSelect.tsx webapp/src/pages/Experience.tsx webapp/src/pages/Multiclass.tsx
git commit -m "feat: i18n cleanup — move hardcoded strings to locale files"
```

---

### Task 18: Performance — lazy routes + React.memo in App.tsx

**Files:**
- Modify: `webapp/src/App.tsx`

- [ ] **Step 1: Rewrite App.tsx with lazy routes and ModalProvider**

Replace the entire content of `webapp/src/App.tsx` with:

```tsx
import { lazy, Suspense } from 'react'
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom'
import ModalProvider from './components/ModalProvider'
import Skeleton from './components/Skeleton'

// Lazy-loaded pages
const CharacterSelect = lazy(() => import('./pages/CharacterSelect'))
const CharacterMain = lazy(() => import('./pages/CharacterMain'))
const HP = lazy(() => import('./pages/HP'))
const ArmorClass = lazy(() => import('./pages/ArmorClass'))
const AbilityScores = lazy(() => import('./pages/AbilityScores'))
const Skills = lazy(() => import('./pages/Skills'))
const SavingThrows = lazy(() => import('./pages/SavingThrows'))
const Spells = lazy(() => import('./pages/Spells'))
const SpellSlots = lazy(() => import('./pages/SpellSlots'))
const Inventory = lazy(() => import('./pages/Inventory'))
const Currency = lazy(() => import('./pages/Currency'))
const Abilities = lazy(() => import('./pages/Abilities'))
const Multiclass = lazy(() => import('./pages/Multiclass'))
const Experience = lazy(() => import('./pages/Experience'))
const Conditions = lazy(() => import('./pages/Conditions'))
const History = lazy(() => import('./pages/History'))
const Notes = lazy(() => import('./pages/Notes'))
const Maps = lazy(() => import('./pages/Maps'))
const Dice = lazy(() => import('./pages/Dice'))
const Identity = lazy(() => import('./pages/Identity'))
const Settings = lazy(() => import('./pages/Settings'))

function PageFallback() {
  return (
    <div className="min-h-screen p-4 space-y-3">
      <Skeleton.Line width="140px" height="24px" />
      <Skeleton.Rect height="160px" />
      <Skeleton.Rect height="80px" delay={100} />
      <Skeleton.Rect height="80px" delay={200} />
    </div>
  )
}

export default function App() {
  return (
    <HashRouter>
      <ModalProvider>
        <Suspense fallback={<PageFallback />}>
          <Routes>
            <Route path="/" element={<CharacterSelect />} />
            <Route path="/char/:id" element={<CharacterMain />} />
            <Route path="/char/:id/hp" element={<HP />} />
            <Route path="/char/:id/ac" element={<ArmorClass />} />
            <Route path="/char/:id/stats" element={<AbilityScores />} />
            <Route path="/char/:id/skills" element={<Skills />} />
            <Route path="/char/:id/saves" element={<SavingThrows />} />
            <Route path="/char/:id/spells" element={<Spells />} />
            <Route path="/char/:id/slots" element={<SpellSlots />} />
            <Route path="/char/:id/inventory" element={<Inventory />} />
            <Route path="/char/:id/currency" element={<Currency />} />
            <Route path="/char/:id/abilities" element={<Abilities />} />
            <Route path="/char/:id/class" element={<Multiclass />} />
            <Route path="/char/:id/xp" element={<Experience />} />
            <Route path="/char/:id/conditions" element={<Conditions />} />
            <Route path="/char/:id/history" element={<History />} />
            <Route path="/char/:id/notes" element={<Notes />} />
            <Route path="/char/:id/maps" element={<Maps />} />
            <Route path="/char/:id/dice" element={<Dice />} />
            <Route path="/char/:id/identity" element={<Identity />} />
            <Route path="/char/:id/settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </ModalProvider>
    </HashRouter>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd webapp && npx tsc --noEmit
```

- [ ] **Step 3: Verify lazy loading works**

Open http://localhost:5173. Open browser DevTools Network tab. Navigate to a character's HP page — you should see a separate chunk loaded for HP.tsx. Navigate to Spells — another chunk loads.

- [ ] **Step 4: Production build**

```bash
cd webapp && npm run build:prod
```

Expected: build succeeds, output in `docs/app/`.

- [ ] **Step 5: Commit**

```bash
git add webapp/src/App.tsx docs/app/
git commit -m "feat: lazy routes + ModalProvider in App.tsx + production build"
```

---

## Verification Checklist

After all tasks are complete, run through these flows:

1. **Character select** → create new character → class selection → navigate to character main
2. **CharacterMain** → verify grouped menu, Lucide icons, gold theme, gear icon for Settings
3. **Combat group** → HP → swipe to AC → swipe to Saves → swipe back
4. **HP page** → damage → heal → death saves (HP=0) → rest → hit dice
5. **Magic group** → Spells → add spell → cast → concentration → swipe to Slots
6. **Skills group** → ability scores → skills → roll skill check → abilities
7. **Equipment group** → Inventory → add weapon → attack roll → Currency → convert coins
8. **Character group** → Identity → Multiclass → add class → Experience → Conditions
9. **Tools group** → Dice → roll → Notes → add note → voice note → Maps → upload → History
10. **Settings** → toggle language → verify translations
11. **Theme** — if testing in Telegram, toggle dark/light mode and verify palette switches
12. **TypeScript** → `npx tsc --noEmit` → no errors
13. **Build** → `npm run build:prod` → succeeds
