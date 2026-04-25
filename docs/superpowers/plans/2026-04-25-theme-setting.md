# Theme Setting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Dark / Light / Auto theme selector in the Mini App Settings page, persisted in `localStorage`, replacing the inline Telegram-only theme detection in `main.tsx`.

**Architecture:** New Zustand store with `persist` holds the user choice (`'auto' | 'dark' | 'light'`). A small theme module exposes `initTheme()` which subscribes to the store, listens to `Telegram.WebApp.themeChanged` (only effective in `auto`), and toggles the existing `.light` class on `<html>`. Settings page gets a 3-button segmented control matching the existing `spell_slots_mode` pattern.

**Tech Stack:** React, TypeScript, Zustand 4 (`persist` middleware), Tailwind, framer-motion (`m`), react-i18next, lucide-react.

**Reference spec:** `docs/superpowers/specs/2026-04-25-theme-setting-design.md`

**Branch:** `feat/theme-setting` (already created and checked out).

**Note on testing:** No automated test suite exists in `webapp/`. This plan uses TypeScript compilation (`tsc`) plus manual browser verification as the verification layer. The user runs `npm run build:prod` from Windows (per `CLAUDE.md`) — agent should NOT run `uv sync`/`uv run`. `npm`/`tsc` from WSL are fine.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `webapp/src/store/themeSettings.ts` | NEW — Zustand store: `mode`, `setMode`. localStorage persist key `dnd-theme-settings`. |
| `webapp/src/theme/applyTheme.ts` | NEW — `resolveTheme(mode)`, `applyTheme()`, `initTheme()`. Pure DOM + Telegram glue. |
| `webapp/src/main.tsx` | MODIFY — remove inline `applyTheme` block (lines 14-22); call `initTheme()` once. |
| `webapp/src/pages/Settings.tsx` | MODIFY — insert theme card under language card. |
| `webapp/src/locales/it.json` | MODIFY — add `character.settings.theme.*` keys. |
| `webapp/src/locales/en.json` | MODIFY — add `character.settings.theme.*` keys. |

---

## Task 1: Create theme settings store

**Files:**
- Create: `webapp/src/store/themeSettings.ts`

- [ ] **Step 1: Create the store file**

Write `webapp/src/store/themeSettings.ts`:

```ts
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type ThemeMode = 'auto' | 'dark' | 'light'

interface ThemeSettingsStore {
  mode: ThemeMode
  setMode: (mode: ThemeMode) => void
}

export const useThemeSettings = create<ThemeSettingsStore>()(
  persist(
    (set) => ({
      mode: 'auto',
      setMode: (mode) => set({ mode }),
    }),
    { name: 'dnd-theme-settings' },
  ),
)
```

- [ ] **Step 2: Type-check**

Run from `webapp/`:
```bash
npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add webapp/src/store/themeSettings.ts
git commit -m "feat(theme): add Zustand store for theme mode preference"
```

---

## Task 2: Create theme apply module

**Files:**
- Create: `webapp/src/theme/applyTheme.ts`

- [ ] **Step 1: Create the module**

Write `webapp/src/theme/applyTheme.ts`:

```ts
import { useThemeSettings, type ThemeMode } from '@/store/themeSettings'

type ResolvedTheme = 'dark' | 'light'

/**
 * Resolve a ThemeMode to a concrete theme.
 * - 'dark' / 'light' → user's explicit choice
 * - 'auto' inside Telegram → follow Telegram.WebApp.colorScheme
 * - 'auto' outside Telegram → 'light' (matches local-dev default expectation)
 */
export function resolveTheme(mode: ThemeMode): ResolvedTheme {
  if (mode === 'dark' || mode === 'light') return mode
  const tgScheme = window.Telegram?.WebApp?.colorScheme
  if (tgScheme === 'dark' || tgScheme === 'light') return tgScheme
  return 'light'
}

/** Apply current theme to <html> by toggling the .light class. */
export function applyTheme(): void {
  const mode = useThemeSettings.getState().mode
  const resolved = resolveTheme(mode)
  document.documentElement.classList.toggle('light', resolved === 'light')
}

/**
 * Initialize the theme system. Call once on startup.
 * - Apply the current theme.
 * - Subscribe to store changes → re-apply on user toggle.
 * - Listen to Telegram themeChanged → re-apply only when mode === 'auto'.
 */
export function initTheme(): void {
  applyTheme()
  useThemeSettings.subscribe(() => {
    applyTheme()
  })
  window.Telegram?.WebApp?.onEvent?.('themeChanged', () => {
    if (useThemeSettings.getState().mode === 'auto') {
      applyTheme()
    }
  })
}
```

- [ ] **Step 2: Type-check**

Run from `webapp/`:
```bash
npx tsc --noEmit
```
Expected: no errors. If `@/store/themeSettings` import path complains, verify `vite.config.ts` already aliases `@` → `src` (it does — same pattern as `@/store/diceSettings` in `Settings.tsx:19`).

- [ ] **Step 3: Commit**

```bash
git add webapp/src/theme/applyTheme.ts
git commit -m "feat(theme): add resolver and apply module with Telegram integration"
```

---

## Task 3: Wire theme init into app entry point

**Files:**
- Modify: `webapp/src/main.tsx` (lines 14-22)

- [ ] **Step 1: Replace the inline applyTheme block**

In `webapp/src/main.tsx`, find this block (lines 14-22):

```ts
// Theme detection: apply .light class if Telegram reports light mode
function applyTheme() {
  const scheme = window.Telegram?.WebApp?.colorScheme
  document.documentElement.classList.toggle('light', scheme === 'light')
}
applyTheme()

// Listen for live theme changes (user toggles dark/light in Telegram)
window.Telegram?.WebApp?.onEvent?.('themeChanged', applyTheme)
```

Replace with:

```ts
import { initTheme } from './theme/applyTheme'

initTheme()
```

The `import` line goes with the other imports at the top of the file. The `initTheme()` call replaces both the function definition and its old call sites.

Final top section of `main.tsx` should look like:

```ts
import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { LazyMotion, domAnimation } from 'framer-motion'
import App from './App'
import Toast from './components/ui/Toast'
import { initTheme } from './theme/applyTheme'
import './index.css'
import './i18n'

// Signal Telegram that the Mini App is ready
window.Telegram?.WebApp?.ready()
window.Telegram?.WebApp?.expand()

// Theme system: read user preference from store, follow Telegram in auto mode
initTheme()
```

The `syncViewportHeight()` block (lines 25-32 in current file) and everything below stays unchanged.

- [ ] **Step 2: Type-check**

Run from `webapp/`:
```bash
npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Manual smoke test (browser)**

Ask the user to start the dev server and verify on `http://localhost:5173/`:
1. Page loads with light theme (default for `auto` outside Telegram per resolver).
2. Open DevTools → Application → Local Storage → key `dnd-theme-settings` exists with value `{"state":{"mode":"auto"},"version":0}` after first interaction (or doesn't exist yet — acceptable, persist writes lazily).
3. No console errors.

If the user is not running the dev server, skip the smoke test and rely on the build check in Task 7.

- [ ] **Step 4: Commit**

```bash
git add webapp/src/main.tsx
git commit -m "feat(theme): wire initTheme into app entry point"
```

---

## Task 4: Add i18n keys (Italian)

**Files:**
- Modify: `webapp/src/locales/it.json`

- [ ] **Step 1: Add the theme keys**

In `webapp/src/locales/it.json`, locate the `character.settings.privacy` block (lines 577-581). The block is the LAST key inside `character.settings`. Insert a new sibling key `theme` immediately BEFORE `privacy` so the order in Settings page rendering matches:

```json
      "theme": {
        "title": "Tema",
        "hint": "Auto segue il tema di Telegram.",
        "mode_auto": "Auto",
        "mode_light": "Chiaro",
        "mode_dark": "Scuro"
      },
      "privacy": {
```

The full diff in context — change:

```json
      "hp": {
        ...
      },
      "privacy": {
```

to:

```json
      "hp": {
        ...
      },
      "theme": {
        "title": "Tema",
        "hint": "Auto segue il tema di Telegram.",
        "mode_auto": "Auto",
        "mode_light": "Chiaro",
        "mode_dark": "Scuro"
      },
      "privacy": {
```

- [ ] **Step 2: Validate JSON**

Run from repo root:
```bash
python3 -c "import json; json.load(open('webapp/src/locales/it.json'))" && echo OK
```
Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add webapp/src/locales/it.json
git commit -m "i18n(it): add theme settings keys"
```

---

## Task 5: Add i18n keys (English)

**Files:**
- Modify: `webapp/src/locales/en.json`

- [ ] **Step 1: Add the theme keys**

In `webapp/src/locales/en.json`, locate the `character.settings.privacy` block. Insert a new sibling key `theme` immediately BEFORE `privacy`:

```json
      "theme": {
        "title": "Theme",
        "hint": "Auto follows the Telegram theme.",
        "mode_auto": "Auto",
        "mode_light": "Light",
        "mode_dark": "Dark"
      },
      "privacy": {
```

- [ ] **Step 2: Validate JSON**

```bash
python3 -c "import json; json.load(open('webapp/src/locales/en.json'))" && echo OK
```
Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add webapp/src/locales/en.json
git commit -m "i18n(en): add theme settings keys"
```

---

## Task 6: Add theme card in Settings page

**Files:**
- Modify: `webapp/src/pages/Settings.tsx`

- [ ] **Step 1: Add icon import**

In the lucide-react import line (`Settings.tsx:6`):

```tsx
import { Settings2, Languages, RefreshCw, Eye } from 'lucide-react'
```

change to:

```tsx
import { Settings2, Languages, RefreshCw, Eye, Sun } from 'lucide-react'
```

- [ ] **Step 2: Add theme store import**

Below the existing `useDiceSettings` import line (`Settings.tsx:19`), add:

```tsx
import { useThemeSettings, type ThemeMode } from '@/store/themeSettings'
```

- [ ] **Step 3: Read store inside the component**

Inside the `Settings()` function body, find the existing dice-settings reads (`Settings.tsx:31-34`):

```tsx
const animate3d = useDiceSettings((s) => s.animate3d)
const setAnimate3d = useDiceSettings((s) => s.setAnimate3d)
const packId = useDiceSettings((s) => s.packId)
const setPackId = useDiceSettings((s) => s.setPackId)
```

Add immediately after them:

```tsx
const themeMode = useThemeSettings((s) => s.mode)
const setThemeMode = useThemeSettings((s) => s.setMode)
```

- [ ] **Step 4: Insert the theme card**

In `Settings.tsx`, locate the language card — the `<Surface variant="elevated">` block at roughly lines 119-131 that renders the `Languages` icon and the language toggle button. It ends with `</Surface>`.

Immediately AFTER that closing `</Surface>` (and BEFORE the next `<Surface>` for `Dices` / `dice_3d`), insert:

```tsx
<Surface variant="elevated">
  <div className="flex items-start gap-3 mb-3">
    <Sun size={16} className="text-dnd-gold-bright shrink-0 mt-0.5" />
    <div className="flex-1">
      <p className="font-display font-bold text-dnd-gold-bright">
        {t('character.settings.theme.title')}
      </p>
      <p className="text-xs text-dnd-text-muted mt-0.5 font-body italic">
        {t('character.settings.theme.hint')}
      </p>
    </div>
  </div>
  <div className="grid grid-cols-3 gap-2">
    {(['auto', 'light', 'dark'] as const satisfies readonly ThemeMode[]).map((mode) => (
      <m.button
        key={mode}
        onClick={() => {
          setThemeMode(mode)
          haptic.light()
        }}
        className={`min-h-[44px] rounded-xl font-cinzel text-xs uppercase tracking-widest transition-colors
          ${themeMode === mode
            ? 'bg-gradient-gold text-dnd-ink shadow-engrave'
            : 'bg-dnd-surface border border-dnd-border text-dnd-text-muted'}`}
        whileTap={{ scale: 0.96 }}
        transition={spring.press}
      >
        {t(`character.settings.theme.mode_${mode}`)}
      </m.button>
    ))}
  </div>
</Surface>
```

This card mirrors the visual structure of the `spell_slots_mode` card (`Settings.tsx:90-113`) but with three buttons (`grid-cols-3`) instead of two, and is keyed off `themeMode` from the new store rather than `char.settings.spell_slots_mode`.

- [ ] **Step 5: Type-check**

Run from `webapp/`:
```bash
npx tsc --noEmit
```
Expected: no errors. Common pitfalls:
- If TS complains that `t(`character.settings.theme.mode_${mode}`)` is too dynamic, the project's i18n setup already accepts string templates elsewhere — check `Settings.tsx:109` (`t(`character.settings.mode_${mode}`)`) for the same pattern. No fix needed.

- [ ] **Step 6: Manual verification (browser)**

Ask the user to verify on `http://localhost:5173/` (dev server):
1. Open Settings page for any character.
2. New "Tema" card visible between Lingua and Dadi 3D, with three buttons: Auto / Chiaro / Scuro.
3. Auto button is highlighted on first load.
4. Tap **Scuro** → page switches to dark palette immediately. Reload → still Scuro.
5. Tap **Chiaro** → page switches to light. Reload → still Chiaro.
6. Tap **Auto** → outside Telegram, resolves to light.
7. Switch app language to English → labels become "Theme / Auto / Light / Dark".

If the user can't run dev server, skip this step and rely on Task 7's build check.

- [ ] **Step 7: Commit**

```bash
git add webapp/src/pages/Settings.tsx
git commit -m "feat(theme): add theme selector card in Settings page"
```

---

## Task 7: Production build + final verification

**Files:**
- Generates: `webapp/docs/app/` (build output, staged automatically by `build:prod`)

This task MUST run on the user's Windows shell, not WSL. The `build:prod` script invokes `vite build` and rewrites `webapp/.env.local`; running it from WSL is fine for npm but the user's normal flow per `CLAUDE.md` is Windows.

- [ ] **Step 1: Ask the user to run the production build**

Instruct the user (Italian, since they speak Italian):

> Esegui da PowerShell, dentro `webapp\`:
> ```
> npm run build:prod
> ```
> Verifica che termini senza errori TypeScript e che `docs/app/` sia stato modificato.

Wait for the user to confirm the build succeeded.

- [ ] **Step 2: Verify staged build output**

Run from repo root:
```bash
git status
```
Expected: `docs/app/` files appear as staged (the `build:prod` script does `git add docs/app/` at the end).

- [ ] **Step 3: Commit the build output**

```bash
git commit -m "chore(webapp): rebuild for theme setting feature"
```

- [ ] **Step 4: Final manual smoke test**

Ask the user to open the deployed Mini App in Telegram (after pushing/merging) and verify:
1. Default theme matches Telegram's current scheme (Auto behavior unchanged).
2. Switching to Dark/Light persists across reloads of the Mini App.
3. While in Auto mode, changing Telegram's theme propagates to the app.
4. While in Dark/Light mode, changing Telegram's theme does NOT override the choice.

This step is informational — do not block PR creation on it. The user typically verifies on Telegram after merge.

- [ ] **Step 5: Push branch and offer to open PR**

```bash
git push -u origin feat/theme-setting
```

Ask the user whether to open the PR via `gh pr create` (per CLAUDE.md, pushes/PRs require explicit user authorization).

---

## Spec Coverage Check

| Spec section | Implemented in |
|--------------|----------------|
| Goal: Dark/Light/Auto selector | Task 6 (UI) + Task 1 (store) |
| Non-goal: no per-character | Task 1 — global Zustand store |
| Non-goal: no backend | Task 1 — `persist` to localStorage only |
| Non-goal: no `prefers-color-scheme` | Task 2 — resolver omits media query |
| Storage: Zustand `persist` key `dnd-theme-settings` | Task 1 |
| Resolver behavior | Task 2 (`resolveTheme`) |
| Apply layer with subscribe + Telegram listener guarded by mode | Task 2 (`initTheme`) |
| `main.tsx` cleanup | Task 3 |
| Settings UI segmented control | Task 6 |
| 5 i18n keys | Tasks 4 + 5 |
| Edge cases (default `auto`, listener guard, fallback light, hydration sync) | Covered by Task 2 implementation |

All spec sections have a task. No placeholders detected on self-review.
