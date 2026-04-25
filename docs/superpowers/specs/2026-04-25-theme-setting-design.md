# Theme Setting (Dark / Light / Auto)

**Status:** Approved
**Date:** 2026-04-25
**Scope:** webapp only (Mini App). No backend, no bot.

## Goal

Allow users to explicitly choose the Mini App color scheme: `Dark`, `Light`, or `Auto`. `Auto` is the current behavior (follow Telegram). Preference persists across sessions on the same device.

## Non-Goals

- No per-character theme: theme is a global UI preference, not character data.
- No backend persistence (no cross-device sync).
- No new color palettes: dark and light palettes already exist in `webapp/src/index.css`.
- No automatic OS `prefers-color-scheme` detection. Outside Telegram, `auto` falls back to **light** (matches user's local-dev default expectation).

## Current State

- `webapp/src/main.tsx:14-22` defines `applyTheme()` that reads `window.Telegram?.WebApp?.colorScheme` and toggles `.light` on `<html>`. Listener on Telegram `themeChanged` event re-applies on theme change.
- `webapp/src/index.css:5-149` defines two palettes: dark (`:root`) and light (`.light`).
- No user-facing theme control.

## Design

### Storage

New Zustand store `webapp/src/store/themeSettings.ts` with `persist` middleware.

```ts
type ThemeMode = 'auto' | 'dark' | 'light'

interface ThemeSettingsStore {
  mode: ThemeMode      // default: 'auto'
  setMode: (m: ThemeMode) => void
}
```

Persist key: `dnd-theme-settings` (consistent with `dnd-dice-settings`).

### Resolver

Pure function `resolveTheme(mode: ThemeMode): 'dark' | 'light'`:

- `mode === 'dark'` → `'dark'`
- `mode === 'light'` → `'light'`
- `mode === 'auto'`:
  - if `window.Telegram?.WebApp?.colorScheme` is `'dark'` or `'light'` → use it
  - else → `'light'`

### Apply layer

New module `webapp/src/theme/applyTheme.ts`:

- `applyTheme()`: reads `useThemeSettings.getState().mode`, computes `resolveTheme(mode)`, toggles `.light` class on `document.documentElement`.
- `initTheme()`:
  1. Calls `applyTheme()` once on startup.
  2. Subscribes to `useThemeSettings` store changes (`useThemeSettings.subscribe`) → re-applies.
  3. Registers `Telegram.WebApp.onEvent('themeChanged', ...)` → re-applies **only when** current `mode === 'auto'` (otherwise the user's explicit choice would be overridden by Telegram).

`main.tsx` removes the inline `applyTheme` block (lines 14-22) and calls `initTheme()` instead.

### UI (Settings page)

Location: `webapp/src/pages/Settings.tsx`, inside the existing **Preferenze** section, between the Language card and the Dice 3D card.

A new `<Surface variant="elevated">` card containing:
- header line with `Sun`/`Moon` icon (lucide-react) + label `t('character.settings.theme.title')`
- italic hint `t('character.settings.theme.hint')` ("Auto segue il tema di Telegram")
- segmented control: 3 buttons (Auto / Chiaro / Scuro), styled identically to the existing `spell_slots_mode` segmented control (lines 97-112). `grid-cols-3`.

Tap → `setMode(value)` + `haptic.light()`.

### i18n keys

`webapp/src/locales/it.json` and `en.json`:

```
character.settings.theme.title       → "Tema" / "Theme"
character.settings.theme.hint        → "Auto segue il tema di Telegram." / "Auto follows Telegram theme."
character.settings.theme.mode_auto   → "Auto" / "Auto"
character.settings.theme.mode_light  → "Chiaro" / "Light"
character.settings.theme.mode_dark   → "Scuro" / "Dark"
```

## Files Touched

| File | Change |
|------|--------|
| `webapp/src/store/themeSettings.ts` | NEW — Zustand store + persist |
| `webapp/src/theme/applyTheme.ts` | NEW — `applyTheme`, `initTheme`, `resolveTheme` |
| `webapp/src/main.tsx` | remove inline applyTheme block, call `initTheme()` |
| `webapp/src/pages/Settings.tsx` | add segmented control card |
| `webapp/src/locales/it.json` | add 5 keys |
| `webapp/src/locales/en.json` | add 5 keys |

## Edge Cases

- **First load on existing device**: no persisted value → defaults to `'auto'` → identical to current behavior. No flash.
- **User picks Dark, then Telegram switches to Light**: ignored, stays Dark (listener guarded by `mode === 'auto'`).
- **User picks Auto outside Telegram**: resolver returns `'light'` → light theme.
- **Hydration timing**: Zustand `persist` is synchronous on web (localStorage). `initTheme()` runs after `persist` rehydrates → no FOUC beyond what already exists.

## Testing

Manual verification (no automated test suite in repo):
1. Pick Dark in Settings → reload → still Dark.
2. Pick Light → reload → still Light.
3. Pick Auto inside Telegram, switch Telegram theme → app follows.
4. Pick Auto in localhost (no Telegram) → light theme.
5. Pick Dark, then trigger `themeChanged` (impossible to test in localhost; verified by code review of guard condition).

## Build

`npm run build:prod` from `webapp/` before commit (per CLAUDE.md). Stages `docs/app/` automatically.
