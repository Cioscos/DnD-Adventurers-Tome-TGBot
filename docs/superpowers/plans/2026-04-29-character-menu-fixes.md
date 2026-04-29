# Character Menu Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship four parallel webapp improvements on `feat/character-menu-3-screens`: restore fluid horizontal swipe, move the speed pill into a dedicated `VitalsStrip`, add container-query-based responsive adaptations across the webapp, and add a class+race+gender silhouette resolver in the equipment paper-doll with SVG fallback.

**Architecture:** All changes are React/TypeScript inside `webapp/`. The swipe fix is a CSS `touch-action` declaration plus framer-motion drag tweaks. The speed pill is extracted into a small dedicated component above the hero card. Responsive work uses the official `@tailwindcss/container-queries` plugin with two tiers (`@max-[360px]` and `@max-[300px]`) — no separate "compact" component duplicates. The silhouette pipeline is: a build-time script enumerates `webapp/public/silhouettes/*.png` into a JSON manifest, a resolver picks the most specific candidate from the manifest using slugged class/race/gender, and `PaperDoll` renders an `<img>` when one matches (falling back to its existing SVG silhouette otherwise).

**Tech Stack:** React 18, TypeScript, Vite 5, Tailwind 3 (with `@tailwindcss/container-queries`), framer-motion 11, react-i18next, react-icons (`gi`), zustand, TanStack Query.

**Spec:** `docs/superpowers/specs/2026-04-29-character-menu-fixes-design.md`

**Project context (must read before starting):**

- `CLAUDE.md` — repo conventions and the "never run `uv sync` from WSL" rule (does not affect this plan; we touch `webapp/` only).
- `CLAUDE.md` § *"Before Committing webapp Changes"* — every webapp change must end with `cd webapp && npm run build:prod` so `docs/app/` stays in sync. The script also rewrites `webapp/.env.local`; restore it back to `http://127.0.0.1:8000` after running.
- `CLAUDE.md` § *"Frontend"* — `LazyMotion features={domMax}` is mandatory for any drag/layout component; we keep using it. Use `m.*` lazy components, not `motion.*`.

**No test suite is configured.** Validation in this plan means: TypeScript compile (`tsc` via `npm run build`), ESLint (`npm run lint`), and manual browser checks at the listed viewport widths and (for the silhouette) by dropping a placeholder PNG into `webapp/public/silhouettes/`.

**Commit cadence:** commit after each task. Conventional Commits, scope `webapp` (or `webapp,docs` when changing both). Sign off with the standard `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` trailer used elsewhere on this branch.

---

## File Structure

**New files:**

| Path | Responsibility |
|---|---|
| `webapp/src/components/character/VitalsStrip.tsx` | Renders a centered SPD pill above the hero card; the dedicated, structural slot for the speed value. |
| `webapp/src/lib/silhouette.ts` | Pure-function resolver: `silhouetteUrl(char) → string \| null`. Owns the canonical-class set, race slug map, gender slug map, and the fallback chain. |
| `webapp/scripts/generate-silhouette-manifest.mjs` | Build-time script that enumerates `webapp/public/silhouettes/*.png` into `webapp/src/data/silhouette-manifest.json`. |
| `webapp/public/silhouettes/.gitkeep` | Keeps the otherwise-empty silhouettes directory in source control. |
| `webapp/src/data/silhouette-manifest.json` | Generated array of available filenames. **Gitignored** — recreated on every dev/build start. |

**Modified files:**

| Path | What changes |
|---|---|
| `webapp/src/components/character/CharacterSwiper.tsx` | Add `touchAction: 'pan-y'` to track `m.div` and to each panel; drop `dragMomentum={false}`; soften snap spring. |
| `webapp/src/pages/character/HeroScreen.tsx` | Remove the absolute-positioned speed `<StatPill>` block; mount `<VitalsStrip char={char} />` as the first child of the screen root; drop `pr-16` from conditions row; wrap relevant subtrees in `@container` and apply narrow/xnarrow classes per spec. |
| `webapp/src/components/character/PaperDoll.tsx` | Accept `silhouetteUrl?: string \| null` prop; render `<img>` (with `onError` SVG fallback) when prop is non-null; otherwise render the existing SVG; add container-query class for narrow widths. |
| `webapp/src/pages/character/EquipmentScreen.tsx` | Compute `silhouetteUrl(char)` and pass to `<PaperDoll>`. |
| `webapp/src/components/character/EquipmentStatsFooter.tsx` | Container-query stack at xnarrow. |
| `webapp/src/components/character/ProgressionPreview.tsx` | Container-query font/column tweaks at narrow / xnarrow. |
| `webapp/src/components/character/ClassTabs.tsx` | Narrow text/padding tweaks. |
| `webapp/src/components/character/EquipItemPicker.tsx` | Stack the meta row (weight/quantity) at narrow. |
| `webapp/src/components/character/SpellSlotsSummary.tsx` | Tighten gap at narrow. |
| `webapp/tailwind.config.js` | Register `@tailwindcss/container-queries` plugin. |
| `webapp/vite.config.ts` | Register the manifest-generation plugin (`buildStart` hook). |
| `webapp/package.json` | Add `@tailwindcss/container-queries` dev dependency. |
| `.gitignore` | Add `webapp/src/data/silhouette-manifest.json`. |

---

## Phase 1 — Swipe fix

### Task 1: Restore horizontal swipe on `CharacterSwiper`

**Files:**
- Modify: `webapp/src/components/character/CharacterSwiper.tsx` (entire `<m.div>` track + inner panel divs + the snap spring config in the `useEffect` and `handleDragEnd`)

- [ ] **Step 1: Read current CharacterSwiper to get oriented**

Run: open `webapp/src/components/character/CharacterSwiper.tsx`. Confirm the structure matches the spec assumption: `m.div` track with `drag={width > 0 ? 'x' : false}`, `dragDirectionLock`, `dragMomentum={false}`, then three inner `<div style={{ width }} className="h-full overflow-y-auto shrink-0">` panels.

- [ ] **Step 2: Add `touchAction: 'pan-y'` to the track and to each panel; drop `dragMomentum={false}`; soften the snap spring**

Replace the JSX `return (...)` block in `CharacterSwiper.tsx` with:

```tsx
  return (
    <div ref={containerRef} className="relative flex-1 min-h-0 overflow-hidden">
      <m.div
        className="flex h-full will-change-transform"
        style={{ x, width: width * 3, touchAction: 'pan-y' }}
        drag={width > 0 ? 'x' : false}
        dragConstraints={{ left: -2 * width, right: 0 }}
        dragElastic={0.15}
        dragDirectionLock
        onDragEnd={handleDragEnd}
      >
        <div style={{ width, touchAction: 'pan-y' }} className="h-full overflow-y-auto shrink-0">{hero}</div>
        <div style={{ width, touchAction: 'pan-y' }} className="h-full overflow-y-auto shrink-0">{equipment}</div>
        <div style={{ width, touchAction: 'pan-y' }} className="h-full overflow-y-auto shrink-0">{menu}</div>
      </m.div>
      <SwiperDots active={activeScreen} onSelect={setActiveScreen} labels={labels} />
    </div>
  )
```

Note the two changes:
- Removed `dragMomentum={false}` — fast flicks now carry through with momentum.
- Added `touchAction: 'pan-y'` to the track and to each panel via inline style.

- [ ] **Step 3: Soften the snap-back spring (two call sites)**

Replace both `animate(x, target, { type: 'spring', stiffness: 400, damping: 40 })` calls with `animate(x, target, { type: 'spring', stiffness: 360, damping: 32 })`. There are two: one inside the `useEffect` that snaps to `activeScreen`, and one inside the `else` branch of `handleDragEnd` (for the no-change case).

- [ ] **Step 4: TypeScript + lint**

Run from `webapp/`:

```bash
npm run build
npm run lint
```

Expected: build passes (no TS errors), lint passes (no warnings — `--max-warnings 0` is set in the script).

- [ ] **Step 5: Manual browser check (dev)**

Start the dev stack per `CLAUDE.md`:

```bash
# Terminal 1 (from repo root)
uv run uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
# Terminal 2 (from webapp/)
npm run dev
```

Open `http://localhost:5173/`, navigate to any character (`/char/<id>`), and verify:
- Horizontal drag on the hero/equipment/menu carousel produces 1:1 finger tracking and snaps to the next/prev screen on release with a fast flick.
- Vertical scroll inside each panel still works (try scrolling inside `HeroScreen` content).
- Tapping the dots still switches screens with a smooth spring.

**Telegram WSL constraint:** running `uv run` is fine when invoked from your **Windows** shell, but Claude Code in WSL must not run `uv` commands per `CLAUDE.md`. If you are an agent, ask the user to run the dev stack and report back. If the user is doing manual verification themselves, they already know.

- [ ] **Step 6: Commit**

```bash
git add webapp/src/components/character/CharacterSwiper.tsx
git commit -m "$(cat <<'EOF'
fix(webapp): restore horizontal swipe with touch-action + softer snap

- Track and panels now declare touch-action: pan-y so the browser
  cedes horizontal gestures to framer-motion drag instead of claiming
  them as native scroll.
- Drop dragMomentum={false} so flicks carry through with momentum.
- Soften snap spring (stiffness 400→360, damping 40→32) for a less
  abrupt return.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 2 — VitalsStrip (dedicated speed slot)

### Task 2: Create `VitalsStrip` component

**Files:**
- Create: `webapp/src/components/character/VitalsStrip.tsx`

- [ ] **Step 1: Write the component**

Create `webapp/src/components/character/VitalsStrip.tsx` with this content:

```tsx
import { useTranslation } from 'react-i18next'
import { GiBootPrints } from 'react-icons/gi'
import StatPill from '@/components/ui/StatPill'
import type { CharacterFull } from '@/types'

interface Props {
  char: CharacterFull
}

export default function VitalsStrip({ char }: Props) {
  const { t } = useTranslation()

  return (
    <div className="@container flex justify-center">
      <StatPill
        icon={<GiBootPrints size={14} />}
        value={`${char.speed} ft`}
        tone="emerald"
        size="sm"
        iconOnly
        revealOnTap
        aria-label={`${t('character.identity.speed', { defaultValue: 'Speed' })}: ${char.speed} ft`}
      />
    </div>
  )
}
```

Notes:
- The wrapper is `@container` so future per-strip narrow tweaks compose without touching the surrounding screen.
- `iconOnly + revealOnTap` keeps the existing UX: tap the boot icon to reveal `30 ft`.

- [ ] **Step 2: TypeScript**

Run `npm run build` from `webapp/`. Expected: passes (the component is not yet referenced; the build only checks that the file compiles in isolation).

- [ ] **Step 3: Commit**

```bash
git add webapp/src/components/character/VitalsStrip.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): add VitalsStrip with single SPD pill

A small dedicated component for above-the-card vital pills. Currently
hosts only the speed pill; reserved for future vitals (initiative,
perception) without re-introducing absolute-positioned overlap risk.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 3: Mount `VitalsStrip` in `HeroScreen`, remove the absolute speed pill

**Files:**
- Modify: `webapp/src/pages/character/HeroScreen.tsx`

- [ ] **Step 1: Add the import**

Open `webapp/src/pages/character/HeroScreen.tsx`. Just below the existing `import ClassTabs from '@/components/character/ClassTabs'` line, add:

```tsx
import VitalsStrip from '@/components/character/VitalsStrip'
```

- [ ] **Step 2: Mount `<VitalsStrip>` as the first child of the screen root**

Replace the screen root opening:

```tsx
  return (
    <div className="p-4 space-y-3 pb-safe">
      {/* Hero card */}
      <Surface
```

with:

```tsx
  return (
    <div className="p-4 space-y-3 pb-safe">
      <VitalsStrip char={char} />
      {/* Hero card */}
      <Surface
```

- [ ] **Step 3: Remove the absolute-positioned speed pill from inside `<Surface>`**

Delete the entire `<StatPill>` block currently around lines 208-217:

```tsx
        <StatPill
          icon={<GiBootPrints size={14} />}
          value={`${char.speed} ft`}
          tone="emerald"
          size="sm"
          iconOnly
          revealOnTap
          aria-label={`${t('character.identity.speed', { defaultValue: 'Speed' })}: ${char.speed} ft`}
          className="absolute bottom-3 right-3"
        />
```

- [ ] **Step 4: Drop the `pr-16` reserve from the conditions row**

Locate the active-conditions block (around lines 189-206). Change:

```tsx
          <div className="flex flex-wrap gap-1.5 mt-2 overflow-x-auto scrollbar-hide max-h-14 pr-16">
```

to:

```tsx
          <div className="flex flex-wrap gap-1.5 mt-2 overflow-x-auto scrollbar-hide max-h-14">
```

- [ ] **Step 5: Remove the now-unused `GiBootPrints` import**

In the `react-icons/gi` import line near the top of the file:

```tsx
import {
  GiHeartPlus, GiLightningTrio, GiPotionBall, GiBootPrints,
} from 'react-icons/gi'
```

drop `GiBootPrints` (it's now used only inside `VitalsStrip.tsx`):

```tsx
import {
  GiHeartPlus, GiLightningTrio, GiPotionBall,
} from 'react-icons/gi'
```

- [ ] **Step 6: TypeScript + lint**

```bash
npm run build
npm run lint
```

Expected: passes. If lint complains about an unused symbol, you missed step 5.

- [ ] **Step 7: Manual browser check**

Open `/char/<id>` in dev. Verify:
- The speed pill appears centered above the hero card, never overlapping conditions or ability scores.
- Tap the pill — `30 ft` (or whatever `char.speed` is) reveals for 2 seconds, then collapses back to the boot icon.
- Conditions row no longer has unused right-padding.

- [ ] **Step 8: Commit**

```bash
git add webapp/src/pages/character/HeroScreen.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): mount VitalsStrip in HeroScreen, remove absolute speed pill

The speed pill no longer floats over hero card content. It now lives
in a dedicated strip above the card, centered, with the same
icon-only-with-reveal behavior. Conditions row drops its pr-16 reserve.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 3 — Container queries setup

### Task 4: Install `@tailwindcss/container-queries` and register the plugin

**Files:**
- Modify: `webapp/package.json` (add devDependency)
- Modify: `webapp/tailwind.config.js` (register plugin)

- [ ] **Step 1: Install the plugin**

From `webapp/`:

```bash
npm install --save-dev @tailwindcss/container-queries
```

This adds the package to `devDependencies` and updates `package-lock.json`.

- [ ] **Step 2: Register the plugin in `tailwind.config.js`**

Open `webapp/tailwind.config.js`. Change the last line of the file:

```js
  plugins: [],
}
```

to:

```js
  plugins: [require('@tailwindcss/container-queries')],
}
```

The config file is ESM (`export default`) but the plugin uses CommonJS — `require` works because Vite's tailwind toolchain resolves it through Node's CJS interop. If your project enforces pure ESM and `require` is not available, replace with:

```js
import containerQueries from '@tailwindcss/container-queries'
// ...
  plugins: [containerQueries],
```

Verify by opening any existing component, adding `className="@container @max-[300px]:opacity-50"` to a wrapper, running `npm run dev`, narrowing the viewport, and confirming the element fades. Remove the test class before committing.

- [ ] **Step 3: TypeScript + lint**

```bash
npm run build
npm run lint
```

Expected: build passes, lint passes. (Tailwind config is JS so TS doesn't type-check it.)

- [ ] **Step 4: Commit**

```bash
git add webapp/package.json webapp/package-lock.json webapp/tailwind.config.js
git commit -m "$(cat <<'EOF'
chore(webapp): add @tailwindcss/container-queries plugin

Enables @container + @max-[<width>]: arbitrary-value classes for the
upcoming narrow-screen responsive pass.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 4 — Container-query adaptations per component

Each task here wraps a single component's root in `@container` (where it isn't already from a prior phase) and adds the narrow / xnarrow tier classes from the spec's audit table.

### Task 5: `HeroScreen` — ability scores grid + hero top row

**Files:**
- Modify: `webapp/src/pages/character/HeroScreen.tsx`

- [ ] **Step 1: Wrap the screen root in `@container`**

Change the screen root from:

```tsx
    <div className="p-4 space-y-3 pb-safe">
```

to:

```tsx
    <div className="@container p-4 space-y-3 pb-safe">
```

- [ ] **Step 2: Adapt the ability scores grid (`grid-cols-6 → @max-[300px]:grid-cols-3`)**

Find the ability scores `m.div` (around line 222):

```tsx
            <m.div
              className="grid grid-cols-6 gap-1.5 text-center"
              initial="initial"
```

Change to:

```tsx
            <m.div
              className="grid grid-cols-6 @max-[300px]:grid-cols-3 gap-1.5 text-center"
              initial="initial"
```

- [ ] **Step 3: Adapt the HP+AC top row (stack at xnarrow)**

Find the `mt-4 flex items-center gap-3` row (around line 93):

```tsx
        <div className="mt-4 flex items-center gap-3">
```

Change to:

```tsx
        <div className="mt-4 flex items-center gap-3 @max-[300px]:flex-col @max-[300px]:items-stretch">
```

- [ ] **Step 4: TypeScript + lint**

```bash
npm run build
npm run lint
```

Expected: passes.

- [ ] **Step 5: Manual browser check at 280 / 320 / 400 px**

Open `/char/<id>`, use DevTools responsive mode. At 280 px the ability grid should render 3×2 and the AC shield should sit above the HP gauge. At 320 px it returns to 6×1 ability + side-by-side HP/AC. At 400 px nothing has changed from before.

- [ ] **Step 6: Commit**

```bash
git add webapp/src/pages/character/HeroScreen.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): HeroScreen narrow-screen container queries

- Ability scores: grid-cols-6 → grid-cols-3 (3×2) at @max-[300px]
- Hero top row (HP gauge + AC shield): stack vertically at @max-[300px]

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 6: `EquipmentStatsFooter` — single-column at xnarrow

**Files:**
- Modify: `webapp/src/components/character/EquipmentStatsFooter.tsx`

- [ ] **Step 1: Wrap the Surface root in `@container`**

Open `webapp/src/components/character/EquipmentStatsFooter.tsx`. Change:

```tsx
    <Surface variant="tome" className="mt-3 !px-3 !py-3">
      <div className="grid grid-cols-3 divide-x divide-dnd-gold/20 text-center">
```

to:

```tsx
    <Surface variant="tome" className="@container mt-3 !px-3 !py-3">
      <div className="grid grid-cols-3 @max-[300px]:grid-cols-1 @max-[300px]:divide-x-0 @max-[300px]:divide-y @max-[300px]:gap-2 divide-x divide-dnd-gold/20 text-center">
```

The `@max-[300px]` variants:
- Stack the three cells in a single column.
- Replace the vertical divider with a horizontal one.
- Add gap so the cells don't touch.

- [ ] **Step 2: TypeScript + lint**

```bash
npm run build
npm run lint
```

- [ ] **Step 3: Manual browser check**

Open `/char/<id>` → Equipment screen at 280 px. Confirm AC / Damage / Carry stack vertically with horizontal dividers.

- [ ] **Step 4: Commit**

```bash
git add webapp/src/components/character/EquipmentStatsFooter.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): EquipmentStatsFooter stacks at xnarrow

3-col grid collapses to single column with horizontal dividers below
300px container width.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 7: `ProgressionPreview` — narrow font + xnarrow column drop

**Files:**
- Modify: `webapp/src/components/character/ProgressionPreview.tsx`

- [ ] **Step 1: Wrap the Surface root in `@container`**

Find:

```tsx
      <Surface variant="tome" className="!p-2.5">
```

Change to:

```tsx
      <Surface variant="tome" className="@container !p-2.5">
```

- [ ] **Step 2: Hide the proficiency bonus column at xnarrow + shrink text at narrow**

Replace the row `<m.button>` block. Find:

```tsx
              <m.button
                key={lv}
                type="button"
                onClick={() => setShowFull(true)}
                whileTap={{ scale: 0.99 }}
                className={`w-full grid grid-cols-[28px_36px_1fr] gap-2 items-center rounded-md px-1.5 py-1 text-left transition-colors ${
                  isCurrent
                    ? 'bg-dnd-gold/15 border border-dnd-gold text-dnd-gold-bright'
                    : 'border border-transparent text-dnd-text-muted hover:bg-dnd-surface'
                }`}
                aria-current={isCurrent ? 'true' : undefined}
              >
                <span className="font-mono text-[11px] font-bold text-center">L{lv}</span>
                <span className="font-mono text-[10px] text-center">+{row?.proficiency_bonus ?? '?'}</span>
                <span className="text-[11px] truncate">{row?.features ?? '—'}</span>
              </m.button>
```

Change to:

```tsx
              <m.button
                key={lv}
                type="button"
                onClick={() => setShowFull(true)}
                whileTap={{ scale: 0.99 }}
                className={`w-full grid grid-cols-[28px_36px_1fr] @max-[300px]:grid-cols-[28px_1fr] gap-2 items-center rounded-md px-1.5 py-1 text-left transition-colors @max-[360px]:text-[10px] ${
                  isCurrent
                    ? 'bg-dnd-gold/15 border border-dnd-gold text-dnd-gold-bright'
                    : 'border border-transparent text-dnd-text-muted hover:bg-dnd-surface'
                }`}
                aria-current={isCurrent ? 'true' : undefined}
              >
                <span className="font-mono text-[11px] font-bold text-center">L{lv}</span>
                <span className="font-mono text-[10px] text-center @max-[300px]:hidden">+{row?.proficiency_bonus ?? '?'}</span>
                <span className="text-[11px] truncate">{row?.features ?? '—'}</span>
              </m.button>
```

Two changes:
- `grid-cols-[28px_36px_1fr]` collapses to `grid-cols-[28px_1fr]` at xnarrow.
- The proficiency bonus `<span>` gets `@max-[300px]:hidden`.
- Whole button text shrinks one step at narrow.

- [ ] **Step 3: TypeScript + lint**

```bash
npm run build
npm run lint
```

- [ ] **Step 4: Manual browser check**

At 280 px verify the proficiency bonus column is gone and the level + features columns fit. At 320 px the bonus column reappears with the smaller font.

- [ ] **Step 5: Commit**

```bash
git add webapp/src/components/character/ProgressionPreview.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): ProgressionPreview narrow + xnarrow tweaks

- @max-[360px]: shrink row text to 10px
- @max-[300px]: hide proficiency bonus column, collapse grid

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 8: `PaperDoll` — narrow grid shrink

**Files:**
- Modify: `webapp/src/components/character/PaperDoll.tsx`

- [ ] **Step 1: Wrap the outer container in `@container` and adapt the grid**

Find the outer wrapper:

```tsx
    <div
      className="relative w-full mx-auto rounded-2xl overflow-hidden p-3"
      style={{
        maxWidth: 420,
```

Change `className` to:

```tsx
    <div
      className="@container relative w-full mx-auto rounded-2xl overflow-hidden p-3"
      style={{
        maxWidth: 420,
```

- [ ] **Step 2: Shrink the slot columns at narrow**

Find:

```tsx
      <div className="grid grid-cols-[56px_1fr_56px] gap-2 items-start">
```

Change to:

```tsx
      <div className="grid grid-cols-[56px_1fr_56px] @max-[360px]:grid-cols-[48px_1fr_48px] gap-2 @max-[360px]:gap-1.5 items-start">
```

- [ ] **Step 3: TypeScript + lint**

```bash
npm run build
npm run lint
```

- [ ] **Step 4: Manual browser check**

At 320 px confirm slot cells are slightly smaller (48 px) and the silhouette still fits comfortably in the middle column. At 400 px the layout is unchanged.

- [ ] **Step 5: Commit**

```bash
git add webapp/src/components/character/PaperDoll.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): PaperDoll narrow column + gap shrink

@max-[360px]: slot columns 56→48px, gap 2→1.5 so the silhouette has
breathing room on small viewports.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 9: `ClassTabs` — narrow text/padding

**Files:**
- Modify: `webapp/src/components/character/ClassTabs.tsx`

- [ ] **Step 1: Wrap the tab strip in `@container` and shrink tab text/padding at narrow**

Open `webapp/src/components/character/ClassTabs.tsx`. Replace:

```tsx
    <div role="tablist" className="flex gap-1 overflow-x-auto scrollbar-hide mb-2">
      {classes.map((c) => {
        const isActive = c.class_name === selected
        return (
          <m.button
            key={c.class_name}
            role="tab"
            aria-selected={isActive}
            type="button"
            onClick={() => onSelect(c.class_name)}
            whileTap={{ scale: 0.96 }}
            className={`shrink-0 px-3 py-1.5 rounded-full border text-xs font-cinzel uppercase tracking-wider transition-colors ${
              isActive
                ? 'bg-dnd-gold/20 border-dnd-gold text-dnd-gold-bright'
                : 'bg-dnd-surface border-dnd-gold-dim/30 text-dnd-text-muted'
            }`}
          >
            {t(`dnd.classes.${c.class_name}`, { defaultValue: c.class_name })}
            <span className="ml-1 opacity-70">L{c.level}</span>
          </m.button>
        )
      })}
    </div>
```

with:

```tsx
    <div role="tablist" className="@container flex gap-1 overflow-x-auto scrollbar-hide mb-2">
      {classes.map((c) => {
        const isActive = c.class_name === selected
        return (
          <m.button
            key={c.class_name}
            role="tab"
            aria-selected={isActive}
            type="button"
            onClick={() => onSelect(c.class_name)}
            whileTap={{ scale: 0.96 }}
            className={`shrink-0 px-3 @max-[360px]:px-2 py-1.5 rounded-full border text-xs @max-[360px]:text-[10px] font-cinzel uppercase tracking-wider transition-colors ${
              isActive
                ? 'bg-dnd-gold/20 border-dnd-gold text-dnd-gold-bright'
                : 'bg-dnd-surface border-dnd-gold-dim/30 text-dnd-text-muted'
            }`}
          >
            {t(`dnd.classes.${c.class_name}`, { defaultValue: c.class_name })}
            <span className="ml-1 opacity-70">L{c.level}</span>
          </m.button>
        )
      })}
    </div>
```

Two changes:
- Tablist root gains `@container`.
- Tab button className gains `@max-[360px]:px-2` and `@max-[360px]:text-[10px]`.

- [ ] **Step 2: TypeScript + lint**

```bash
npm run build
npm run lint
```

- [ ] **Step 3: Manual browser check (multiclass character)**

Set up or load a multiclass character with at least three classes. At 320 px confirm tab labels still fit without horizontal scroll fights; at 400 px they look unchanged.

- [ ] **Step 4: Commit**

```bash
git add webapp/src/components/character/ClassTabs.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): ClassTabs narrow text + padding

Tab labels shrink to 10px and padding to px-2 below 360px container
width so multiclass characters with long Italian class names fit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 10: `EquipItemPicker` — narrow item card padding/text

**Files:**
- Modify: `webapp/src/components/character/EquipItemPicker.tsx`

The actual item card uses simple stacked text (`flex flex-col gap-0.5`) — name on top, "type · weight lb" below — so there is no inline meta row to break apart. The narrow tweak here is just to give the modal body a container context and shrink the secondary line one step at xnarrow so very long item type strings still fit.

- [ ] **Step 1: Add `@container` to the modal sheet root and shrink the secondary line at xnarrow**

Open `webapp/src/components/character/EquipItemPicker.tsx`. Replace:

```tsx
        <m.div
          className="w-full max-w-md max-h-[85vh] overflow-y-auto bg-dnd-surface-raised border border-dnd-gold rounded-t-2xl sm:rounded-2xl"
          initial={{ y: 40, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 40, opacity: 0 }}
          onClick={(e) => e.stopPropagation()}
        >
```

with:

```tsx
        <m.div
          className="@container w-full max-w-md max-h-[85vh] overflow-y-auto bg-dnd-surface-raised border border-dnd-gold rounded-t-2xl sm:rounded-2xl"
          initial={{ y: 40, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 40, opacity: 0 }}
          onClick={(e) => e.stopPropagation()}
        >
```

Then replace the per-item meta line:

```tsx
                    <span className="text-[11px] text-dnd-text-muted">
                      {it.item_type} · {it.weight} lb
                    </span>
```

with:

```tsx
                    <span className="text-[11px] @max-[300px]:text-[10px] text-dnd-text-muted break-words">
                      {it.item_type} · {it.weight} lb
                    </span>
```

Two additions: `@max-[300px]:text-[10px]` (one-step shrink at xnarrow) and `break-words` (so unusually long item types wrap rather than overflow).

- [ ] **Step 2: TypeScript + lint**

```bash
npm run build
npm run lint
```

- [ ] **Step 3: Manual browser check**

Open `/char/<id>` → Equipment screen. Tap an empty slot to open the picker. Confirm at 280 px the secondary text line uses smaller font and wraps cleanly; at 400 px it looks unchanged.

- [ ] **Step 4: Commit**

```bash
git add webapp/src/components/character/EquipItemPicker.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): EquipItemPicker narrow text + container queries

Modal sheet root becomes a container; per-item secondary line shrinks
to 10px at @max-[300px] and uses break-words so unusual long item-type
strings wrap instead of overflowing.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 11: `SpellSlotsSummary` — narrow text + xnarrow gap

**Files:**
- Modify: `webapp/src/components/character/SpellSlotsSummary.tsx`

The grid is fixed `grid-cols-9` (one column per spell level 1–9). At 280 px each cell is ~30 px wide so the number text crowds the gap. The fix is to shrink the cell text at xnarrow and tighten the gap further from `gap-1` to `gap-0.5`.

- [ ] **Step 1: Wrap the Surface in `@container` and add narrow tweaks**

Open `webapp/src/components/character/SpellSlotsSummary.tsx`. Replace:

```tsx
    <Surface variant="tome" className="!p-2.5">
```

with:

```tsx
    <Surface variant="tome" className="@container !p-2.5">
```

Replace the grid:

```tsx
        <div className="grid grid-cols-9 gap-1 text-center font-mono text-dnd-text">
          {cells.map((c) => (
            <div key={c.level} className="flex flex-col">
              <span className="text-[9px] text-dnd-gold-dim">{c.level}</span>
              <span className={c.total === 0 ? 'text-dnd-text-faint' : 'text-dnd-gold-bright font-bold'}>
                {c.total}
              </span>
            </div>
          ))}
        </div>
```

with:

```tsx
        <div className="grid grid-cols-9 gap-1 @max-[300px]:gap-0.5 text-center font-mono text-dnd-text">
          {cells.map((c) => (
            <div key={c.level} className="flex flex-col">
              <span className="text-[9px] @max-[300px]:text-[8px] text-dnd-gold-dim">{c.level}</span>
              <span className={`@max-[300px]:text-[11px] ${c.total === 0 ? 'text-dnd-text-faint' : 'text-dnd-gold-bright font-bold'}`}>
                {c.total}
              </span>
            </div>
          ))}
        </div>
```

Three additions:
- Grid gap collapses to `gap-0.5` at xnarrow.
- Level label shrinks `text-[9px]` → `text-[8px]` at xnarrow.
- Slot count uses `text-[11px]` at xnarrow instead of inheriting body size.

- [ ] **Step 2: TypeScript + lint**

```bash
npm run build
npm run lint
```

- [ ] **Step 3: Manual browser check**

Load a spellcaster character. At 280 px the 9 slot cells should fit on a single row without truncation; at 400 px nothing visibly changed.

- [ ] **Step 4: Commit**

```bash
git add webapp/src/components/character/SpellSlotsSummary.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): SpellSlotsSummary narrow text + xnarrow gap

Surface gains @container; at @max-[300px] the grid gap shrinks from 1
to 0.5, the level label drops to 8px and the count to 11px so all 9
spell levels fit on one row even on the smallest viewports.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 5 — Class+race+gender silhouette

### Task 12: Create the manifest-generation script

**Files:**
- Create: `webapp/scripts/generate-silhouette-manifest.mjs`
- Create: `webapp/public/silhouettes/.gitkeep`
- Modify: `.gitignore`

- [ ] **Step 1: Create the silhouettes directory placeholder**

```bash
mkdir -p webapp/public/silhouettes
touch webapp/public/silhouettes/.gitkeep
```

- [ ] **Step 2: Add the manifest output to `.gitignore`**

Open `.gitignore` (repo root). Append:

```
webapp/src/data/silhouette-manifest.json
```

- [ ] **Step 3: Write the manifest generator**

Create `webapp/scripts/generate-silhouette-manifest.mjs`:

```js
// Enumerates webapp/public/silhouettes/*.png and writes the list of
// filenames to webapp/src/data/silhouette-manifest.json.
//
// Run by the Vite plugin in webapp/vite.config.ts on every dev/build.

import { readdirSync, mkdirSync, writeFileSync, existsSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const WEBAPP_ROOT = resolve(__dirname, '..')
const SILHOUETTE_DIR = join(WEBAPP_ROOT, 'public', 'silhouettes')
const OUT_PATH = join(WEBAPP_ROOT, 'src', 'data', 'silhouette-manifest.json')

export function generateSilhouetteManifest() {
  let files = []
  if (existsSync(SILHOUETTE_DIR)) {
    files = readdirSync(SILHOUETTE_DIR)
      .filter((f) => f.toLowerCase().endsWith('.png'))
      .sort()
  }

  mkdirSync(dirname(OUT_PATH), { recursive: true })
  writeFileSync(OUT_PATH, JSON.stringify(files, null, 2) + '\n', 'utf8')

  return files
}

// CLI: node scripts/generate-silhouette-manifest.mjs
if (import.meta.url === `file://${process.argv[1]}`) {
  const files = generateSilhouetteManifest()
  console.log(`Wrote ${files.length} entries to ${OUT_PATH}`)
}
```

- [ ] **Step 4: Run the script once manually to seed the manifest**

```bash
node webapp/scripts/generate-silhouette-manifest.mjs
```

Expected output: `Wrote 0 entries to /.../webapp/src/data/silhouette-manifest.json`. Verify the file exists with content `[]` (followed by a newline).

- [ ] **Step 5: Commit**

```bash
git add webapp/scripts/generate-silhouette-manifest.mjs webapp/public/silhouettes/.gitkeep .gitignore
git commit -m "$(cat <<'EOF'
chore(webapp): silhouette manifest generator + ignored artifact

Adds webapp/scripts/generate-silhouette-manifest.mjs which enumerates
PNG files in webapp/public/silhouettes/ into a build-time JSON manifest
consumed by the silhouette resolver. The output JSON is gitignored —
regenerated on every dev/build.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 13: Wire the manifest generator into Vite

**Files:**
- Modify: `webapp/vite.config.ts`

- [ ] **Step 1: Add the plugin**

Open `webapp/vite.config.ts`. Replace the current contents with:

```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { generateSilhouetteManifest } from './scripts/generate-silhouette-manifest.mjs'

function silhouetteManifestPlugin() {
  return {
    name: 'silhouette-manifest',
    buildStart() {
      const files = generateSilhouetteManifest()
      this.info(`silhouette-manifest: ${files.length} entries`)
    },
  }
}

// https://vitejs.dev/config/
export default defineConfig(({ command }) => ({
  base: command === 'build' ? '/DnD-Adventurers-Tome-TGBot/app/' : '/',
  build: {
    outDir: '../docs/app',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (
            id.includes('node_modules/three/') ||
            id.includes('node_modules/@react-three/') ||
            id.includes('node_modules/cannon-es/')
          ) {
            return 'dice-scene'
          }
        },
      },
    },
  },
  plugins: [react(), silhouetteManifestPlugin()],
  resolve: {
    alias: {
      '@': '/src',
    },
  },
}))
```

The plugin re-runs `generateSilhouetteManifest()` on `buildStart`, which Vite fires for both `vite dev` (once at startup) and `vite build`.

- [ ] **Step 2: TypeScript + lint**

```bash
npm run build
npm run lint
```

The build should print `silhouette-manifest: 0 entries` (or higher if you've added PNGs). If TS complains about the `.mjs` import lacking types, that is expected — the script returns a runtime value used only inside the plugin and the plugin function is not type-annotated. Add `// @ts-expect-error untyped .mjs script` above the import only if `tsc` actually fails the build; otherwise leave it.

- [ ] **Step 3: Commit**

```bash
git add webapp/vite.config.ts
git commit -m "$(cat <<'EOF'
chore(webapp): vite plugin to regenerate silhouette manifest on build

Hooks generate-silhouette-manifest.mjs into buildStart so dev and
production builds always start with a fresh JSON manifest.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 14: Write the silhouette resolver

**Files:**
- Create: `webapp/src/lib/silhouette.ts`

- [ ] **Step 1: Write the module**

Create `webapp/src/lib/silhouette.ts`:

```ts
import manifest from '@/data/silhouette-manifest.json'
import type { CharacterFull } from '@/types'

const MANIFEST_SET: ReadonlySet<string> = new Set(manifest as string[])

const CANONICAL_CLASSES: ReadonlySet<string> = new Set([
  'barbarian', 'bard', 'cleric', 'druid', 'fighter', 'monk',
  'paladin', 'ranger', 'rogue', 'sorcerer', 'warlock', 'wizard',
])

const RACE_SLUG_MAP: Record<string, string> = {
  human: 'human', umano: 'human', umana: 'human',
  elf: 'elf', elfo: 'elf', elfa: 'elf',
  dwarf: 'dwarf', nano: 'dwarf', nana: 'dwarf',
  halfling: 'halfling', mezzuomo: 'halfling',
  half_elf: 'half_elf', mezzelfo: 'half_elf', mezzelfa: 'half_elf', 'half-elf': 'half_elf',
  half_orc: 'half_orc', mezzorco: 'half_orc', 'half-orc': 'half_orc',
  gnome: 'gnome', gnomo: 'gnome', gnoma: 'gnome',
  tiefling: 'tiefling',
  dragonborn: 'dragonborn', dracoide: 'dragonborn',
}

const GENDER_SLUG_MAP: Record<string, string> = {
  m: 'male', male: 'male', maschio: 'male', maschile: 'male',
  f: 'female', female: 'female', femmina: 'female', femminile: 'female',
}

function pickPrimaryCanonicalClass(char: CharacterFull): string | null {
  const canonical = (char.classes ?? []).filter((c) =>
    CANONICAL_CLASSES.has(c.class_name),
  )
  if (canonical.length === 0) return null
  // Highest level wins; tie-break alphabetic on class_name for determinism.
  canonical.sort((a, b) => {
    if (b.level !== a.level) return b.level - a.level
    return a.class_name.localeCompare(b.class_name)
  })
  return canonical[0].class_name
}

function slugFrom(map: Record<string, string>, raw: string | null | undefined): string | null {
  if (!raw) return null
  const key = raw.trim().toLowerCase()
  return map[key] ?? null
}

/**
 * Resolve a class+race+gender silhouette image URL for a character.
 *
 * Falls back through: class_race_gender → class_race → class_gender → class.
 * Returns null when no canonical class is present or no candidate matches.
 * Caller should render the existing SVG silhouette when this returns null.
 */
export function silhouetteUrl(char: CharacterFull): string | null {
  const classSlug = pickPrimaryCanonicalClass(char)
  if (!classSlug) return null

  const raceSlug = slugFrom(RACE_SLUG_MAP, char.race)
  const genderSlug = slugFrom(GENDER_SLUG_MAP, char.gender)

  const candidates: string[] = []
  if (raceSlug && genderSlug) candidates.push(`${classSlug}_${raceSlug}_${genderSlug}.png`)
  if (raceSlug) candidates.push(`${classSlug}_${raceSlug}.png`)
  if (genderSlug) candidates.push(`${classSlug}_${genderSlug}.png`)
  candidates.push(`${classSlug}.png`)

  for (const file of candidates) {
    if (MANIFEST_SET.has(file)) {
      return `${import.meta.env.BASE_URL}silhouettes/${file}`
    }
  }
  return null
}
```

- [ ] **Step 2: TypeScript + lint**

```bash
npm run build
npm run lint
```

Both should pass. If `tsc` complains about importing JSON, confirm that `webapp/tsconfig.json` has `"resolveJsonModule": true` (Vite's default; this is already on for any project that imports JSON elsewhere — `class-progression.json` is imported similarly in `webapp/src/lib/classProgression.ts`, so this is fine).

- [ ] **Step 3: Commit**

```bash
git add webapp/src/lib/silhouette.ts
git commit -m "$(cat <<'EOF'
feat(webapp): silhouette resolver with canonical class + slug maps

silhouetteUrl(char) returns the most specific PNG path present in the
build-time manifest, or null when no canonical class is found. Falls
back: class_race_gender → class_race → class_gender → class.
Race/gender slug maps cover PHB races and the common Italian/English
gender variants; non-binary and unknown values reduce the chain rather
than guessing.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 15: Render the silhouette in `PaperDoll`

**Files:**
- Modify: `webapp/src/components/character/PaperDoll.tsx`

- [ ] **Step 1: Add the new prop and a tiny render-fallback state**

At the top of `webapp/src/components/character/PaperDoll.tsx`, change the imports to:

```tsx
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ALL_SLOTS } from '@/lib/equipmentSlots'
import EquipmentSlotCell from './EquipmentSlotCell'
import type { EquipmentSlot, Item } from '@/types'
```

Update the `Props` interface and the function signature:

```tsx
interface Props {
  items: Item[]
  onSlotTap: (slot: EquipmentSlot, equipped: Item | null) => void
  silhouetteUrl?: string | null
}

const LEFT_SLOTS: EquipmentSlot[] = ['head', 'neck', 'cloak', 'body']
const RIGHT_SLOTS: EquipmentSlot[] = ['hands', 'ring1', 'ring2', 'feet']
const BOTTOM_SLOTS: EquipmentSlot[] = ['main_hand', 'off_hand', 'ammunition']

function findEquipped(items: Item[], slot: EquipmentSlot): Item | null {
  return items.find((i) => i.is_equipped && i.equipment_slot === slot) ?? null
}

export default function PaperDoll({ items, onSlotTap, silhouetteUrl }: Props) {
  const { t } = useTranslation()
  const [imgFailed, setImgFailed] = useState(false)
  // sanity: all 11 slots used exactly once
  void ALL_SLOTS

  const showImage = !!silhouetteUrl && !imgFailed
```

- [ ] **Step 2: Conditionally render the image instead of the SVG inside the silhouette slot**

Find the silhouette `<div>` (currently around lines 49-92):

```tsx
        {/* Vitruvian silhouette */}
        <div className="flex items-center justify-center min-h-[280px]">
          <svg
            viewBox="0 0 200 360"
            ...
          >
            ...
          </svg>
        </div>
```

Replace with:

```tsx
        {/* Vitruvian silhouette OR class+race+gender PNG */}
        <div className="flex items-center justify-center min-h-[280px]">
          {showImage ? (
            <img
              src={silhouetteUrl as string}
              alt={t('character.equipment.equipment', { defaultValue: 'Equipment' })}
              className="max-h-[320px] w-auto object-contain"
              style={{ filter: 'drop-shadow(0 0 8px rgba(212,175,55,0.4))' }}
              onError={() => setImgFailed(true)}
            />
          ) : (
            <svg
              viewBox="0 0 200 360"
              width="100%"
              height="320"
              style={{ filter: 'drop-shadow(0 0 8px rgba(212,175,55,0.4))' }}
              aria-hidden="true"
            >
              <defs>
                <linearGradient id="paperdoll-body" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3a2820" />
                  <stop offset="100%" stopColor="#1a1208" />
                </linearGradient>
              </defs>
              {/* Head */}
              <ellipse cx="100" cy="40" rx="22" ry="26"
                fill="url(#paperdoll-body)" stroke="#d4af37" strokeWidth="1.5" />
              {/* Neck */}
              <path d="M88 62 L88 75 L112 75 L112 62 Z"
                fill="url(#paperdoll-body)" stroke="#d4af37" strokeWidth="1.5" />
              {/* Torso */}
              <path d="M65 78 Q62 82 60 95 L55 145 Q58 160 70 165 L130 165 Q142 160 145 145 L140 95 Q138 82 135 78 Z"
                fill="url(#paperdoll-body)" stroke="#d4af37" strokeWidth="1.5" />
              {/* Arms */}
              <path d="M62 95 Q40 110 32 150 Q28 180 35 200 L48 200 Q42 180 46 155 Q52 125 70 110 Z"
                fill="url(#paperdoll-body)" stroke="#d4af37" strokeWidth="1.5" />
              <path d="M138 95 Q160 110 168 150 Q172 180 165 200 L152 200 Q158 180 154 155 Q148 125 130 110 Z"
                fill="url(#paperdoll-body)" stroke="#d4af37" strokeWidth="1.5" />
              {/* Hands */}
              <circle cx="41" cy="208" r="8"
                fill="url(#paperdoll-body)" stroke="#d4af37" strokeWidth="1.5" />
              <circle cx="159" cy="208" r="8"
                fill="url(#paperdoll-body)" stroke="#d4af37" strokeWidth="1.5" />
              {/* Pelvis + legs */}
              <path d="M70 165 L75 200 L72 270 Q72 290 80 310 L92 310 Q90 280 95 240 L100 200 L105 240 Q110 280 108 310 L120 310 Q128 290 128 270 L125 200 L130 165 Z"
                fill="url(#paperdoll-body)" stroke="#d4af37" strokeWidth="1.5" />
              {/* Feet */}
              <ellipse cx="86" cy="320" rx="12" ry="6"
                fill="url(#paperdoll-body)" stroke="#d4af37" strokeWidth="1.5" />
              <ellipse cx="114" cy="320" rx="12" ry="6"
                fill="url(#paperdoll-body)" stroke="#d4af37" strokeWidth="1.5" />
            </svg>
          )}
        </div>
```

The SVG block is verbatim copy of the existing one — the spec keeps the same fallback art.

- [ ] **Step 3: TypeScript + lint**

```bash
npm run build
npm run lint
```

- [ ] **Step 4: Commit**

```bash
git add webapp/src/components/character/PaperDoll.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): PaperDoll renders class+race+gender silhouette PNG

PaperDoll accepts an optional silhouetteUrl prop. When non-null, an
<img> renders in the silhouette slot with the same drop-shadow as the
SVG and onError falls back to the SVG (defensive against
manifest/file divergence). When null/undefined, the existing Vitruvian
SVG renders unchanged.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 16: Compute and pass `silhouetteUrl` from `EquipmentScreen`

**Files:**
- Modify: `webapp/src/pages/character/EquipmentScreen.tsx`

- [ ] **Step 1: Import the resolver and pass the result to `PaperDoll`**

Open `webapp/src/pages/character/EquipmentScreen.tsx`. Add this import after the existing `import` lines:

```tsx
import { silhouetteUrl } from '@/lib/silhouette'
```

Inside the component, just before `return (`, add:

```tsx
  const sUrl = silhouetteUrl(char)
```

In the JSX, change:

```tsx
      <PaperDoll items={char.items ?? []} onSlotTap={handleSlotTap} />
```

to:

```tsx
      <PaperDoll items={char.items ?? []} onSlotTap={handleSlotTap} silhouetteUrl={sUrl} />
```

- [ ] **Step 2: TypeScript + lint**

```bash
npm run build
npm run lint
```

- [ ] **Step 3: Manual test of the resolver pipeline**

a. Drop a 1×1 transparent PNG (or any test PNG) into `webapp/public/silhouettes/wizard.png`.
b. Restart the dev server (`npm run dev`) so the manifest plugin re-runs.
c. Open the equipment screen for a character whose primary canonical class is `wizard`. The PNG should render where the SVG used to be.
d. Now load a character with no canonical classes (all custom), or one whose primary class doesn't have a matching file. The SVG silhouette should appear unchanged.
e. Delete the test PNG and restart `npm run dev`; both characters now show the SVG.

This is a manual smoke test, not a permanent commit — make sure no test PNG is left in `webapp/public/silhouettes/` before the final commit.

- [ ] **Step 4: Commit**

```bash
git add webapp/src/pages/character/EquipmentScreen.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): EquipmentScreen wires silhouette resolver

Resolves silhouetteUrl(char) once per render and passes it to
PaperDoll. When art is added to webapp/public/silhouettes/ matching
the class+race+gender (or its fallback chain), the PNG replaces the
SVG silhouette.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 6 — Production build & validation

### Task 17: Build production bundle and update `docs/app/`

**Files:**
- Modify: `docs/app/**` (regenerated by `npm run build:prod`)

- [ ] **Step 1: Run the production build helper**

From `webapp/`:

```bash
npm run build:prod
```

This script:
1. Switches `webapp/.env.local` to `https://api.cischi.dev`.
2. Runs `tsc && vite build` (the silhouette manifest plugin runs as part of `vite build`).
3. Restores `.env.local` to `http://localhost:8000` (note: not `127.0.0.1`).
4. Runs `git add docs/app/`.

Expected: the run prints `silhouette-manifest: 0 entries` (or higher if you have art in place) early in the build, the build completes, and `docs/app/` is freshly staged.

- [ ] **Step 2: Restore `.env.local` to the dev URL**

Per `CLAUDE.md` quirk note:

```bash
printf 'VITE_API_BASE_URL=http://127.0.0.1:8000\n' > webapp/.env.local
```

- [ ] **Step 3: Final manual smoke test at multiple widths**

Restart the dev stack, open `http://localhost:5173/`, navigate to `/char/<id>`, and at 320 / 360 / 400 / 768 px viewport widths verify:

1. **Swipe** — drag horizontally between Hero / Equipment / Menu screens; finger tracking is 1:1, snap on release works, vertical scroll inside each screen still works.
2. **Speed pill** — visible centered above the hero card on every screen size, never overlapping conditions or ability scores. Tap reveals the value.
3. **Hero ability scores** — 6 columns at 320 px+, 3×2 at 280 px (DevTools — sanity only, not a hard requirement per spec).
4. **Hero top row** — HP gauge + AC shield side-by-side at 320 px+, stacked at 280 px.
5. **Equipment footer** — three columns at 320 px+, single stacked column with horizontal dividers at 280 px.
6. **Progression preview** — proficiency bonus column visible at 320 px, hidden at 280 px; row text shrinks to 10 px at 360 px and below.
7. **PaperDoll** — slot cells slightly smaller at 320 px, silhouette/SVG always fits.
8. **ClassTabs** (multiclass character) — tab labels readable at 320 px without weird scroll.
9. **EquipItemPicker** — open the picker, item meta row stacks at 320 px.
10. **SpellSlotsSummary** (spellcaster character) — slot pills fit on a single row at 320 px.

- [ ] **Step 4: Commit the production bundle**

If `git status` shows changes under `docs/app/` (it should — at minimum bundle hashes change):

```bash
git commit -m "$(cat <<'EOF'
chore(webapp): rebuild after character menu fixes

Production build with: swipe touch-action fix, VitalsStrip,
container-query responsive pass across 7 components, and the
class+race+gender silhouette resolver.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review Checklist

After completing all tasks, sanity-check against the spec:

- [ ] **Spec §2 (swipe):** Task 1 covers `touch-action`, dropped `dragMomentum`, softened spring.
- [ ] **Spec §3 (speed pill):** Task 2 creates `VitalsStrip`, Task 3 mounts it and removes the absolute pill, drops `pr-16`.
- [ ] **Spec §4 (container queries):** Task 4 installs the plugin; Tasks 5–11 cover every component listed in the audit table (HeroScreen ability grid, Hero top row, EquipmentStatsFooter, ProgressionPreview, PaperDoll, ClassTabs, EquipItemPicker, SpellSlotsSummary; SwiperDots intentionally skipped per spec).
- [ ] **Spec §5 (silhouette):** Task 12 manifest script + dir + gitignore; Task 13 Vite plugin; Task 14 resolver with canonical/race/gender maps and fallback chain; Task 15 PaperDoll renders `<img>` with onError SVG fallback; Task 16 EquipmentScreen passes the URL.
- [ ] **Spec §7 (build):** Task 17 runs `build:prod`, restores `.env.local`, performs the manual width matrix, commits the bundle.
- [ ] No placeholder text ("TBD", "TODO", "implement later") anywhere in this plan.
- [ ] Every code-changing step contains the actual code or the exact diff to apply.
- [ ] File paths everywhere are absolute-from-repo or anchored to `webapp/`.

---

## Risks & open items

- **Telegram Android pointer events:** if a specific Android Telegram build still ignores `touch-action: pan-y`, the fallback is to swap framer-motion drag for `embla-carousel-react`. This is out of scope for this plan and would be a separate spec.
- **Manifest staleness in dev:** adding a PNG to `webapp/public/silhouettes/` while `vite dev` is already running does not refresh the manifest until the next `vite dev` start. A file watcher is overkill given how rarely this happens.
- **Race slug seed scope:** only PHB races are seeded. Custom races silently fall back to class-only, which is the spec'd behavior. Future work can extend the map.
