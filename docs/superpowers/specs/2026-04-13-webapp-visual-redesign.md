# Webapp Visual Redesign — "Pergamena & Oro"

**Date:** 2026-04-13
**Scope:** `webapp/src/` only — Telegram Mini App for D&D character management
**Approach:** Progressive reskin — update design tokens + shared components, pages benefit automatically

## Design Philosophy

Mobile-first D&D character manager. Balanced theming: strong fantasy identity on focal points (character sheet, hero card, roll results), clean functional UI on operative pages (inventory, forms, settings). The app should feel like opening a well-crafted adventurer's tome, not a generic utility app.

## 1. Design Tokens & Palette

### CSS Custom Properties

```css
:root {
  --dnd-bg: #1a1614;              /* Main background — very dark warm brown */
  --dnd-surface: #2a2320;         /* Operative cards — dark brown */
  --dnd-surface-elevated: #352d28; /* Important cards — lighter brown */
  --dnd-gold: #d4a847;            /* Primary accent — gold */
  --dnd-gold-dim: #8b7335;        /* Secondary accent — muted gold */
  --dnd-gold-glow: rgba(212, 168, 71, 0.15); /* Glow effect for elevated cards */
  --dnd-parchment: #f4e8c1;       /* Text on accent backgrounds */
  --dnd-text: #e8e0d4;            /* Primary text — warm white */
  --dnd-text-secondary: #9a8e7f;  /* Hint/secondary text */
  --dnd-danger: #c0392b;          /* Low HP, failures, damage */
  --dnd-success: #27ae60;         /* Heals, successes */
  --dnd-arcane: #8e44ad;          /* Magic, concentration, spell slots */
  --dnd-info: #2980b9;            /* Links, info, rests */
}
```

### Tailwind Extension

Extend `tailwind.config.js` `theme.extend.colors` with a `dnd` namespace mapping to the CSS variables above (same pattern as existing `tg` namespace).

### Telegram Theme Integration

The `--tg-theme-*` CSS variables remain as runtime overrides. When the app runs inside Telegram, the client injects its theme. The `--dnd-*` tokens are used for D&D-specific theming that doesn't depend on Telegram's palette. Fallback values in `:root` use the D&D palette.

## 2. Typography

### Fonts

- **Titles:** Google Font "Cinzel" (weights 700, 900) — serif with classical feel. Used for: character name, page titles, section headers, AC label.
- **Body:** System font stack (`-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`) — unchanged, maximum mobile readability.
- **Stats/Numbers:** System font weight 800 — immediate readability for ability scores, HP, AC.

### Loading

Import Cinzel via `<link>` in `index.html` with `display=swap` to avoid FOIT. Only weights 700 and 900.

## 3. Iconography

### Library

`lucide-react` — tree-shakeable, ~2KB per icon imported. Install as dependency.

### Icon Mapping

| Menu Item    | Lucide Icon     | Context Color        |
|-------------|-----------------|----------------------|
| Punti Ferita | `Heart`         | `--dnd-gold`         |
| Classe Armatura | `Shield`     | `--dnd-gold`         |
| Tiri Salvezza | `ShieldAlert`  | `--dnd-gold`         |
| Incantesimi  | `Sparkles`      | `--dnd-gold`         |
| Slot         | `Gem`           | `--dnd-gold`         |
| Statistiche  | `BarChart3`     | `--dnd-gold`         |
| Competenze   | `Target`        | `--dnd-gold`         |
| Capacità     | `Zap`           | `--dnd-gold`         |
| Inventario   | `Swords`        | `--dnd-gold`         |
| Monete       | `Coins`         | `--dnd-gold`         |
| Identità     | `User`          | `--dnd-gold`         |
| Classe       | `Scroll`        | `--dnd-gold`         |
| Esperienza   | `Star`          | `--dnd-gold`         |
| Condizioni   | `CircleDot`     | `--dnd-gold`         |
| Dadi         | `Dices`         | `--dnd-gold`         |
| Note         | `NotebookPen`   | `--dnd-gold`         |
| Mappe        | `Map`           | `--dnd-gold`         |
| Cronologia   | `BookOpen`      | `--dnd-gold`         |
| Impostazioni | `Settings`      | `--dnd-gold`         |

Icons render at 24px in the menu grid, stroke-width 2.

## 4. Component Redesign

### Card (2 variants)

```
Card variant="elevated"
├── Background: --dnd-surface-elevated
├── Border: 1px solid --dnd-gold-dim
├── Box-shadow: 0 0 20px --dnd-gold-glow
├── Border-radius: 16px (rounded-2xl)
├── Padding: 16px
└── Use for: stats display, HP display, roll results, hero card, death saves

Card variant="default" (or no prop)
├── Background: --dnd-surface
├── Border: none
├── Border-radius: 16px (rounded-2xl)
├── Padding: 16px
└── Use for: forms, lists, inventory, input areas, settings
```

Both variants keep `active:opacity-70` and `transition-opacity` when clickable.

### Layout

- Header title: Cinzel font, `--dnd-gold` color
- Back button: Lucide `ChevronLeft` icon, `--dnd-gold` color
- Fade-in on mount: `opacity 0 → 1`, 150ms CSS animation
- Safe-area handling unchanged

### HPBar

- Height: 10px (up from implied 8px)
- Border-radius: 5px
- Transition: `width 500ms ease` for smooth animation on HP change
- Color thresholds:
  - `>50%` HP: green gradient (`#27ae60 → #2ecc71`), green glow
  - `25-50%` HP: amber gradient (`#d4a847 → #f0c040`), amber glow
  - `<25%` HP: red gradient (`#c0392b → #e74c3c`), red glow + `pulse-danger` animation (2s loop)
- Temp HP: overlay with `--dnd-info` color (blue)

### Modal (RollResultModal, WeaponAttackModal)

- Overlay: `black/65`
- Container: `--dnd-surface-elevated` background, border-radius 20px
- Entry animation: `scale(0.9) → scale(1)` + `opacity 0 → 1`, 150ms ease-out
- Critical (nat 20): 2px `--dnd-gold` border + `pulse-gold` animation (glow pulses 3 times then stops)
- Fumble (nat 1): 2px `--dnd-danger` border + `pulse-danger` glow
- Normal success: 2px `--dnd-success` border
- Normal fail: 2px `--dnd-danger` border

### New Component: SectionHeader

Used in CharacterMain for grouped menu sections.

- Font: Cinzel, 0.65rem, uppercase, letter-spacing 1.5px
- Color: `--dnd-gold-dim`
- Decorative line: `::after` pseudo-element, flex-grow, 1px height, gradient `--dnd-gold-dim → transparent`

## 5. CharacterMain Layout

Top-to-bottom structure:

### Header Bar
- Back button (Lucide `ChevronLeft`, gold)
- Character name (Cinzel, gold, truncate)
- Inspiration button (Lucide `Sparkles`, `shimmer` animation when active, opacity 0.25 when inactive)
- "Party" badge (green) if active

### Hero Card (elevated)
- Left: class summary + race
- Right: AC (large number, bold)
- HP: label + bar with glow
- XP + Speed row
- Concentration spell badge (arcane color)
- Passive abilities badges (gold)
- Active conditions badges (danger color)

### Ability Scores (elevated)
- 6-column grid
- Each: stat box with `--dnd-surface` background, 1px border `--dnd-gold-dim` at 0.3 opacity
- Label (3-letter abbreviation, uppercase, gold-dim), value (large bold), modifier (secondary text)

### Menu Grid (grouped)

6 sections with SectionHeader:

1. **Combattimento** — HP, AC, Tiri Salvezza
2. **Magia** — Incantesimi, Slot
3. **Abilità** — Statistiche, Competenze, Capacità
4. **Equipaggiamento** — Inventario, Monete
5. **Personaggio** — Identità, Classe, Esperienza, Condizioni
6. **Strumenti** — Dadi, Note, Mappe, Cronologia, Impostazioni

Each item: 3-column grid, `--dnd-surface` background, Lucide icon (gold, 24px) + label (secondary text, 0.65rem). Border transparent → `--dnd-gold-dim` on active, with gold glow transition.

## 6. Animations

All CSS-only, no additional libraries.

### Global
- Buttons: `transition: opacity 150ms, border-color 150ms`
- Clickable cards: `transition: opacity 150ms, box-shadow 150ms`
- Layout content fade-in on mount: `opacity 0 → 1`, 150ms

### HP-specific
- Bar width: `transition: width 500ms ease`
- Critical HP (<25%): `@keyframes pulse-danger` — box-shadow opacity 0.3 → 0.6, 2s infinite loop

### Modals
- Entry: `@keyframes modal-enter` — scale 0.9→1 + opacity 0→1, 150ms ease-out
- Critical result: `@keyframes pulse-gold` — glow intensity cycles 3 times then stops
- Fumble result: reuses `pulse-danger`

### Inspiration
- Active: `@keyframes shimmer` — opacity 0.6→1 + drop-shadow glow, 2s infinite ease-in-out
- Toggle: opacity transition 0.25 ↔ 1

### No page transitions
No route transition animations — adds complexity for little value on mobile, and React Router doesn't support it natively without extra libraries.

## 7. Operative Pages — Guidelines

Pages not explicitly redesigned (Skills, Dice, Spells, Inventory, Currency, etc.) benefit automatically from:

- New palette via design tokens
- Updated Card component (elevated/default)
- Layout with gold Cinzel header
- HPBar with glow and animation
- Modal with new animations
- Button transitions

### Card Variant Decision Rules

| Use `elevated`                          | Use `default`                     |
|-----------------------------------------|-----------------------------------|
| HP display (number + bar)              | Form inputs (HP value, spell name)|
| Roll result display                    | Lists (inventory, spells, notes)  |
| Death saves panel                      | Selectors (HP operation, filters) |
| Concentration banner                   | Quick shortcut buttons            |
| Character stat block                   | Settings                          |

**Rule of thumb:** Shows important character data or a result → elevated. Interactive control to modify data → default.

### Input Fields
- Background: `--dnd-surface`
- Border: 1px transparent → `--dnd-gold-dim` on focus
- Focus ring: `--dnd-gold` (replaces Telegram blue)
- **Always use `placeholder` for hint text, never pre-filled values.** Fields must start empty to prevent accidental wrong submissions.

### Primary Buttons
- Background: `--dnd-gold`
- Text: `--dnd-bg` (dark on gold)
- Disabled: opacity 40%
- Replaces current Telegram blue buttons

### Secondary Buttons
- Background: `--dnd-surface`
- Border: 1px subtle (white/10 equivalent)
- Text: `--dnd-text`

## 8. Dependencies

### New
- `lucide-react` — icon library (tree-shakeable)
- Google Font "Cinzel" (700, 900) — loaded via `<link>` in `index.html`

### Unchanged
- Tailwind CSS 3.4 — extended config, no version change
- All existing runtime dependencies unchanged

## 9. Files Affected

### Modified
- `webapp/tailwind.config.js` — add `dnd` color tokens
- `webapp/src/index.css` — new CSS variables, animations, updated global styles
- `webapp/index.html` — add Cinzel font `<link>`
- `webapp/src/components/Card.tsx` — add `variant` prop (elevated/default)
- `webapp/src/components/Layout.tsx` — Cinzel title, gold back button, fade-in
- `webapp/src/components/HPBar.tsx` — color thresholds, glow, transition, pulse animation
- `webapp/src/components/RollResultModal.tsx` — new styling, entry animation, critical/fumble effects
- `webapp/src/components/WeaponAttackModal.tsx` — same modal treatment
- `webapp/src/pages/CharacterMain.tsx` — grouped menu, SectionHeader, Lucide icons, hero card elevated
- `webapp/src/pages/CharacterSelect.tsx` — new palette, elevated cards, gold primary button
- `webapp/src/pages/HP.tsx` — card variant assignments, updated button colors
- All other pages under `webapp/src/pages/` — minor: Card variant assignment, button color updates via token changes

### New
- `webapp/src/components/SectionHeader.tsx` — grouped menu section header

### Package
- `webapp/package.json` — add `lucide-react`

## 10. Out of Scope

- Light mode / theme switching — stays dark-only
- Page route transitions
- Custom SVG icon design
- Structural changes to pages other than CharacterMain
- Backend/API changes
- Bot changes
- New features or functionality

## Visual Reference

Mockups available at `.superpowers/brainstorm/2363-1776112698/content/design-final.html` — covers CharacterSelect, CharacterMain, HP page, modals, and component reference.
