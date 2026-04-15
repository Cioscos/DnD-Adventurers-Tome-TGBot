# Webapp Complete Refactoring — "Pergamena & Oro" + Mobile-First UX

**Date:** 2026-04-15
**Supersedes:** `2026-04-13-webapp-visual-redesign.md` (visual-only spec, fully absorbed here)
**Scope:** `webapp/src/` — Telegram Mini App for D&D character management
**Approach:** Vertical slice — foundation → first slice (CharacterSelect → CharacterMain → Combat group) → replicate across all groups → polish

## Design Philosophy

Mobile-first D&D character manager opened as Telegram Mini App. Fantasy identity on focal points (hero card, roll results, headers), clean functional UI on operative pages. The app should feel like opening a well-crafted adventurer's tome. Respects Telegram dark/light theme.

Moderate structural refactoring: monolithic pages decomposed into sub-components, shared component library replaces duplicated patterns, swipe navigation between related pages.

---

## 1. Design Tokens & Theme System

### Dark Mode (default)

```css
:root {
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
}
```

### Light Mode

```css
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
}
```

### Theme Detection

```typescript
// In App.tsx or main.tsx
const colorScheme = window.Telegram?.WebApp?.colorScheme
if (colorScheme === 'light') {
  document.documentElement.classList.add('light')
}

// Listen for live theme changes
window.Telegram?.WebApp?.onEvent('themeChanged', () => {
  const scheme = window.Telegram?.WebApp?.colorScheme
  document.documentElement.classList.toggle('light', scheme === 'light')
})
```

### Tailwind Extension

Extend `tailwind.config.js` with `dnd` color namespace mapping to CSS variables (same pattern as existing `tg` namespace). Add `fontFamily.cinzel` and `boxShadow.dnd-glow`.

### Telegram Theme Integration

`--tg-theme-*` CSS variables remain as fallbacks pointing to `--dnd-*` tokens during migration. Pages migrated to use `--dnd-*` directly. When Telegram injects its theme at runtime, the detection logic above sets the `.light` class which overrides all tokens.

---

## 2. Typography

- **Titles:** Google Font "Cinzel" (weights 700, 900) — serif with classical feel. Used for: character name, page titles, section headers, AC label.
- **Body:** System font stack (`-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`) — unchanged, maximum mobile readability.
- **Stats/Numbers:** System font weight 800 — immediate readability for ability scores, HP, AC.
- **Loading:** Import Cinzel via `<link>` in `index.html` with `display=swap`. Only weights 700 and 900.

---

## 3. Iconography

`lucide-react` — tree-shakeable, ~2KB per icon imported.

| Menu Item       | Lucide Icon     | Color          |
|----------------|-----------------|----------------|
| Punti Ferita   | `Heart`         | `--dnd-gold`   |
| Classe Armatura| `Shield`        | `--dnd-gold`   |
| Tiri Salvezza  | `ShieldAlert`   | `--dnd-gold`   |
| Incantesimi    | `Sparkles`      | `--dnd-gold`   |
| Slot           | `Gem`           | `--dnd-gold`   |
| Statistiche    | `BarChart3`     | `--dnd-gold`   |
| Competenze     | `Target`        | `--dnd-gold`   |
| Capacità       | `Zap`           | `--dnd-gold`   |
| Inventario     | `Swords`        | `--dnd-gold`   |
| Monete         | `Coins`         | `--dnd-gold`   |
| Identità       | `User`          | `--dnd-gold`   |
| Classe         | `Scroll`        | `--dnd-gold`   |
| Esperienza     | `Star`          | `--dnd-gold`   |
| Condizioni     | `CircleDot`     | `--dnd-gold`   |
| Dadi           | `Dices`         | `--dnd-gold`   |
| Note           | `NotebookPen`   | `--dnd-gold`   |
| Mappe          | `Map`           | `--dnd-gold`   |
| Cronologia     | `BookOpen`      | `--dnd-gold`   |

Icons render at 24px in the menu grid, stroke-width 2.

---

## 4. Shared Component Library

### 4.1 Card (2 variants) — existing, modified

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

**Card Variant Decision Rules:**

| Use `elevated`                          | Use `default`                     |
|-----------------------------------------|-----------------------------------|
| HP display (number + bar)              | Form inputs (HP value, spell name)|
| Roll result display                    | Lists (inventory, spells, notes)  |
| Death saves panel                      | Selectors (HP operation, filters) |
| Concentration banner                   | Quick shortcut buttons            |
| Character stat block                   | Settings                          |

Rule of thumb: shows important character data or a result → elevated. Interactive control to modify data → default.

### 4.2 Layout — existing, modified

- Header title: Cinzel font, `--dnd-gold` color
- Back button: Lucide `ChevronLeft` icon, `--dnd-gold` color
- Dot indicator for swipe navigation (when `group` + `page` props provided)
- Fade-in on mount: `opacity 0 → 1`, 150ms CSS animation
- Safe-area handling unchanged
- Props: `title`, `children`, `backTo?`, `group?`, `page?`

### 4.3 HPBar — existing, modified

- Height: 10px (up from 8px)
- Border-radius: 5px
- Transition: `width 500ms ease`
- Color thresholds:
  - `>50%` HP: green gradient (`#27ae60 → #2ecc71`), green glow
  - `25-50%` HP: amber gradient (`#d4a847 → #f0c040`), amber glow
  - `<25%` HP: red gradient (`#c0392b → #e74c3c`), red glow + `pulse-danger` animation (2s loop)
- Temp HP: overlay with `--dnd-info` color (blue)

### 4.4 SectionHeader — new

Used in CharacterMain for grouped menu sections.

- Font: Cinzel, 0.65rem, uppercase, letter-spacing 1.5px
- Color: `--dnd-gold-dim`
- Decorative line: `::after` pseudo-element, flex-grow, 1px height, gradient `--dnd-gold-dim → transparent`

### 4.5 DndInput — new

Reusable form input replacing ~40 duplicate input patterns across pages.

- **Props:** `label`, `type`, `value`, `onChange`, `placeholder`, `error?`, `min?`, `max?`, `disabled?`, `inputMode?`
- **States:** default → focused (gold border + ring) → error (red border + message below) → disabled (opacity 40%)
- **Label:** Above input, uppercase, 11px, `--dnd-gold-dim` color. Turns `--dnd-gold` on focus, `--dnd-danger` on error.
- **Touch target:** 48px min-height (12px padding × 2 + 14px font + breathing room)
- **Validation:** Triggered on blur, not keystroke. Error clears when user starts typing.
- **Number inputs:** Use `inputMode="numeric"` instead of `type="number"` to avoid browser spinners. Manual validation.
- **Placeholder-only hints:** Always use `placeholder` for suggested/example values (e.g., `placeholder="Es. Palla di Fuoco"`), never `value` or `defaultValue`. Fields must start empty to prevent accidental wrong submissions. Existing pre-filled patterns in the codebase must be converted to placeholders during migration.
- **Styling:** Background `--dnd-surface`, border transparent → `--dnd-gold-dim` on focus with `box-shadow: 0 0 0 2px rgba(gold, 0.2)`. Border-radius 12px.

### 4.6 DndButton — new

3 variants replacing inconsistent button styles.

- **Props:** `variant` (`'primary'` | `'secondary'` | `'danger'`), `loading?`, `disabled?`, `icon?`, `children`
- **Primary:** `--dnd-gold` background, `--dnd-bg` text. Disabled: opacity 40%.
- **Secondary:** `--dnd-surface` background, `--dnd-text` text, subtle border `white/10`.
- **Danger:** `--dnd-danger/15` background, `--dnd-danger` text, `--dnd-danger/30` border.
- **Loading:** Spinner + "..." text. Button disabled during loading.
- **All:** min-height 48px, border-radius 12px, `active:scale-[0.97] active:opacity-70 transition-all duration-75`.

### 4.7 ModalProvider + useModal — new

Context-based modal system replacing per-page modal state management.

- **Provider:** Wraps App in `<ModalProvider>`. Renders modal stack with backdrop.
- **Hook:** `const { openModal, closeModal } = useModal()`
- **openModal options:**
  - `content: ReactNode` — modal body
  - `dismissible: boolean` — tap backdrop or swipe-down to close (default: true)
- **Features:**
  - Backdrop: `black/65`
  - Container: `--dnd-surface-elevated` background, border-radius 20px
  - max-height: `85vh`, overflow-y: auto, `-webkit-overflow-scrolling: touch`
  - Entry animation: `scale(0.9) → scale(1)` + `opacity 0 → 1`, 150ms ease-out
  - Swipe-down dismiss: 120px drag threshold, visual translate feedback
  - Body scroll lock when open
  - z-index stacking for nested modals
  - Exposes `isModalOpen` for swipe navigation conflict avoidance

### 4.8 Skeleton — new

Loading placeholder components. CSS-only shimmer animation.

- **Sub-components:** `Skeleton.Line` (text), `Skeleton.Circle` (avatar), `Skeleton.Rect` (card/block)
- **Props:** `width?`, `height?`, `rounded?`
- **Animation:** Shimmer gradient (`surface 25% → surface-elevated 50% → surface 75%`), background-size 200%, 1.5s infinite. Staggered delays via `animation-delay`.
- **Page skeletons:** Each page exports a skeleton constant matching its layout shape. Used as `Suspense` fallback and query loading state.

### 4.9 ScrollArea — new

Wrapper component with scroll indicator.

- **Gradient fade:** 48px from bottom, `--dnd-bg → transparent`. Adapts to light mode automatically (uses CSS variable).
- **"↓ scorri" hint text:** Only on first visit (localStorage flag `scroll-hint-seen`). After that, gradient-only.
- **Detection:** IntersectionObserver on sentinel `<div>` at bottom of children. When sentinel is visible → hide gradient.
- **Props:** `children`, `className?`

### 4.10 RollResultModal — existing, modified

- Container: `--dnd-surface-elevated` background, border-radius 20px
- Entry animation: `animate-modal-enter`
- Critical (nat 20): 2px `--dnd-gold` border + `animate-pulse-gold` (3 cycles)
- Fumble (nat 1): 2px `--dnd-danger` border + `animate-pulse-danger`
- Normal success: 2px `--dnd-success` border
- Normal fail: 2px `--dnd-danger` border
- OK button: `--dnd-gold` background, `--dnd-bg` text

### 4.11 WeaponAttackModal — existing, modified

Same treatment as RollResultModal. Two sections (to-hit + damage) with `--dnd-surface` background sub-cards.

---

## 5. Swipe Navigation

### Page Groups

| Group           | Pages                                           |
|----------------|--------------------------------------------------|
| Combat         | HP → AC → Saving Throws                          |
| Magic          | Spells → Spell Slots                             |
| Skills         | Ability Scores → Skills → Abilities              |
| Equipment      | Inventory → Currency                             |
| Character      | Identity → Multiclass → Experience → Conditions  |
| Tools          | Dice → Notes → Maps → History                    |

Settings is **not** in any group — accessed via gear icon in CharacterMain header.

### Hook: `useSwipeNavigation`

- **File:** `webapp/src/hooks/useSwipeNavigation.ts`
- **Input:** `group` key + current `page` key
- **Output:** `{ onTouchStart, onTouchMove, onTouchEnd, currentIndex, total }` — handlers attached to Layout content area
- **Touch handling:**
  - `touchstart` → record X, Y position
  - `touchmove` → calculate deltaX, deltaY. Only engage if `|deltaX| > |deltaY| × 1.5` (horizontal intent). Apply CSS `translateX` to content for drag feedback.
  - `touchend` → if `|deltaX| > 80px` → navigate to prev/next via `react-router`. If below threshold → snap back with transition.
- **Conflict avoidance:**
  - Disabled while modal is open (reads `isModalOpen` from ModalProvider)
  - Disabled during scroll (only triggers when content `scrollTop === 0` or horizontal intent is dominant)
- **Edge behavior:** Rubber-band bounce at group boundaries (translate with resistance, snap back). No wrap-around.

### Dot Indicator

Rendered by Layout when `group` + `page` props are provided:
- Centered below header, inside sticky header area
- Gold dot for active page, dim dots for others
- 8px diameter, 6px gap

### Navigation

Swipe triggers `navigate(`/char/${charId}/${targetPage}`, { replace: true })`. Using `replace: true` so back button returns to CharacterMain, not through every swiped page.

---

## 6. CharacterMain Layout

### Header Bar
- Back button (Lucide `ChevronLeft`, gold) → navigates to CharacterSelect
- Character name (Cinzel, gold, truncate)
- Inspiration button (Lucide `Sparkles`, `shimmer` animation when active, opacity 0.25 when inactive)
- Gear icon (Lucide `Settings`, gold) → navigates to Settings
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

6 sections with SectionHeader (i18n'd labels):

1. **Combattimento** — HP, AC, Tiri Salvezza
2. **Magia** — Incantesimi, Slot
3. **Abilità** — Statistiche, Competenze, Capacità
4. **Equipaggiamento** — Inventario, Monete
5. **Personaggio** — Identità, Classe, Esperienza, Condizioni
6. **Strumenti** — Dadi, Note, Mappe, Cronologia

Settings removed from grid — gear icon in header instead.

Each item: 3-column grid, `--dnd-surface` background, Lucide icon (gold, 24px) + label (secondary text, 0.65rem). Border transparent → `--dnd-gold-dim` on active, with gold glow transition.

---

## 7. Page Decomposition

### HP.tsx (545 → ~180 main + 3 sub-components)

| Extract | File | Responsibility |
|---------|------|----------------|
| Death saves panel | `hp/DeathSaves.tsx` | UI + roll logic, own state |
| Hit dice spending | `hp/HitDiceModal.tsx` | Modal with mutation, dice selection |
| HP operation form | `hp/HpOperationForm.tsx` | Damage/heal/temp form with DndInput + validation |

Concentration save and rest confirmations use `ModalProvider` — no dedicated component needed.

### Spells.tsx (651 → ~200 main + 4 sub-components)

| Extract | File | Responsibility |
|---------|------|----------------|
| Add/edit form | `spells/SpellForm.tsx` | Form logic with DndInput fields |
| Spell list item | `spells/SpellItem.tsx` | Accordion expand/collapse, cast/damage actions. `React.memo`. |
| Cast spell modal | `spells/CastSpellModal.tsx` | Slot selection + cast mutation |
| Search/filter bar | `spells/SpellFilter.tsx` | Sticky header with search + level filter |

### Inventory.tsx (658 → ~200 main + 3 sub-components + 1 util)

| Extract | File | Responsibility |
|---------|------|----------------|
| Add/edit form | `inventory/ItemForm.tsx` | 10+ conditional fields by item type |
| Item list item | `inventory/InventoryItem.tsx` | Render + equip/action buttons. `React.memo`. |
| Metadata builder | `inventory/itemMetadata.ts` | Pure logic: build metadata object from form state |

Weapon attack flow uses existing `WeaponAttackModal` via `ModalProvider`.

### Notes.tsx (427 → ~150 main + 3 sub-components)

| Extract | File | Responsibility |
|---------|------|----------------|
| Voice recorder | `notes/VoiceRecorder.tsx` | MediaRecorder, refs, duration tracking, blob handling |
| Note editor | `notes/NoteEditor.tsx` | Add/edit form with textarea |
| Note list item | `notes/NoteItem.tsx` | Render + play/edit/delete actions. `React.memo`. |

### Multiclass.tsx (388 → ~150 main + 2 sub-components)

| Extract | File | Responsibility |
|---------|------|----------------|
| Resource manager | `multiclass/ResourceManager.tsx` | Add/edit/delete resource forms |
| Add class form | `multiclass/AddClassForm.tsx` | Class picker + hit die selection |

### Maps.tsx (360 → ~120 main + 2 sub-components)

| Extract | File | Responsibility |
|---------|------|----------------|
| Upload form | `maps/MapUploadForm.tsx` | File input + zone name |
| Zone group | `maps/MapZoneGroup.tsx` | Grouped display with image overlay, delete |

### Rules

- Pages under 250 lines with single concern → leave alone (ArmorClass, Experience, Skills, Conditions, SpellSlots, SavingThrows, AbilityScores, Dice, Currency, History, Identity, Settings)
- Sub-components are **co-located** in page-specific subfolders, not in shared `components/`
- Sub-components receive data via props — parent page owns queries/mutations
- Modals use `ModalProvider` — sub-components call `useModal()` instead of managing show/hide state

---

## 8. Mobile UX Improvements

### 8.1 Loading States (Skeletons)

- Every page with `useQuery` shows page-specific skeleton during loading
- Skeletons match layout shape (shimmer animation, staggered delays)
- `React.lazy` routes use skeleton as `Suspense` fallback
- No "Loading..." text anywhere

### 8.2 Modal Overflow

- max-height: `85vh` on all modal containers
- overflow-y: `auto` with `-webkit-overflow-scrolling: touch`
- Swipe-down dismiss: 120px drag threshold, visual translate feedback
- Body scroll lock: `document.body.style.overflow = 'hidden'` when modal open

### 8.3 Form Inputs (via DndInput)

- Validation on blur, not keystroke
- `inputMode="numeric"` for number fields (no browser spinners)
- Error: red border + message below, clears on typing
- Consistent focus ring: gold border + glow

### 8.4 Touch Targets

- Minimum 48px height on all interactive elements
- Tap feedback: `active:scale-[0.97] transition-transform duration-75` on buttons
- Menu items: `active:scale-95` + border flash
- Haptic patterns standardized:
  - `haptic.light()` — navigation, toggle, selection
  - `haptic.success()` — mutation success
  - `haptic.error()` — validation error, failed action
  - `haptic.warning()` — destructive action confirmation

### 8.5 Scroll Indicators (via ScrollArea)

- Applied to: spell list, inventory list, notes list, maps zone list, dice history, skill list
- Bottom gradient fade: 48px, `--dnd-bg → transparent`
- "↓ scorri" hint text on first visit only (localStorage flag)
- Disappears when IntersectionObserver detects bottom sentinel visible

### 8.6 Button Press Animations

- Primary buttons: `active:scale-[0.97]` + gold glow
- Menu items: `active:scale-95` + border flash `transparent → gold-dim`
- List items with actions: `active:bg-dnd-surface-elevated` background flash
- All transitions: 75-150ms

---

## 9. Performance

### Lazy Routes

Every page loaded via `React.lazy()` + `Suspense` with page-specific skeleton fallback.

```tsx
const HP = lazy(() => import('./pages/HP'))
// ...
<Suspense fallback={<HpSkeleton />}>
  <Route path="/char/:id/hp" element={<HP />} />
</Suspense>
```

Initial bundle: CharacterSelect + shared components only. Each page loaded on first navigation.

### React.memo

Applied to frequently re-rendered list items and static display components:

| Component | Reason |
|-----------|--------|
| `SpellItem` | Long list, parent re-renders on filter |
| `InventoryItem` | Long list, parent re-renders on CRUD |
| `NoteItem` | List re-renders on CRUD |
| `Card` | Rendered dozens of times per page |
| `DndButton` | Rendered many times, rarely changes props |
| `HPBar` | Only changes when HP changes |
| `SectionHeader` | Static content |

Not memo'd: DndInput (changes frequently), page-level components (route roots).

### Query Optimization

Standardize optimistic updates: every mutation returning `CharacterFull` uses `qc.setQueryData` instead of `invalidateQueries`. No other TanStack Query changes.

---

## 10. i18n Cleanup

Hardcoded strings to move into locale files:

| Location | String | i18n Key |
|----------|--------|----------|
| `CharacterSelect.tsx` | `DND_CLASSES` array | `dnd.classes.*` |
| `Experience.tsx` | `"Liv."` | `character.xp.level_abbr` |
| `CharacterMain.tsx` | Menu section labels | `character.menu.sections.*` |
| `HP.tsx` | Modal headers | `character.hp.*` |
| `Multiclass.tsx` | Hit dice labels, resource types | `character.class.*` |
| Swipe navigation group names | Same as menu sections | `character.menu.sections.*` |

~30-40 new keys added to both `it.json` and `en.json`. Same i18next setup, same `useTranslation()` pattern.

---

## 11. Animations

All CSS-only, no additional libraries.

### Global
- Buttons: `transition: all 75ms` (scale + opacity)
- Clickable cards: `transition: all 150ms` (opacity + box-shadow)
- Layout content fade-in: `opacity 0 → 1`, 150ms

### HP-specific
- Bar width: `transition: width 500ms ease`
- Critical HP (<25%): `@keyframes pulseDanger` — box-shadow 0.3 → 0.6, 2s infinite

### Modals
- Entry: `@keyframes modalEnter` — scale 0.9→1 + opacity 0→1, 150ms ease-out
- Critical result: `@keyframes pulseGold` — glow cycles 3 times then stops
- Fumble: reuses `pulseDanger`

### Inspiration
- Active: `@keyframes shimmer` — opacity 0.6→1 + drop-shadow glow, 2s infinite
- Toggle: opacity transition 0.25 ↔ 1

### Skeletons
- `@keyframes shimmerBg` — background-position slide, 1.5s infinite

### No page transitions
No route animations — swipe navigation handles the spatial feeling. React Router doesn't support transitions natively without extra libraries.

---

## 12. Input Fields & Buttons — Style Rules

### Input Fields
- Background: `--dnd-surface`
- Border: 1px transparent → `--dnd-gold-dim` on focus
- Focus ring: `--dnd-gold` via box-shadow
- Always use `placeholder` for hint text, never pre-filled values
- min-height: 48px

### Primary Buttons
- Background: `--dnd-gold`
- Text: `--dnd-bg` (dark on gold for dark mode, light on darker gold for light mode)
- Disabled: opacity 40%

### Secondary Buttons
- Background: `--dnd-surface`
- Border: 1px `rgba(255,255,255,0.1)` in dark mode, `rgba(0,0,0,0.1)` in light mode (use `--dnd-gold-dim/20` for both)
- Text: `--dnd-text`

### Danger Buttons
- Background: `--dnd-danger/15`
- Border: 1px `--dnd-danger/30`
- Text: `--dnd-danger`

---

## 13. Dependencies

### New
- `lucide-react` — icon library (tree-shakeable)
- Google Font "Cinzel" (700, 900) — loaded via `<link>` in `index.html`

### Unchanged
- Tailwind CSS 3.4 — extended config only
- All existing runtime dependencies unchanged
- No new gesture libraries — custom touch handlers

---

## 14. Files Affected

### New files (~22)

| File | Responsibility |
|------|----------------|
| `components/DndInput.tsx` | Reusable form input |
| `components/DndButton.tsx` | Primary/secondary/danger button |
| `components/ModalProvider.tsx` | Modal context + useModal hook |
| `components/Skeleton.tsx` | Loading placeholders |
| `components/ScrollArea.tsx` | Scroll indicator wrapper |
| `components/SectionHeader.tsx` | Menu section header |
| `hooks/useSwipeNavigation.ts` | Swipe between pages in group |
| `pages/hp/DeathSaves.tsx` | Death saves panel |
| `pages/hp/HitDiceModal.tsx` | Hit dice spending |
| `pages/hp/HpOperationForm.tsx` | Damage/heal/temp form |
| `pages/spells/SpellForm.tsx` | Add/edit spell form |
| `pages/spells/SpellItem.tsx` | Spell list item |
| `pages/spells/CastSpellModal.tsx` | Cast spell + slot selection |
| `pages/spells/SpellFilter.tsx` | Search/filter bar |
| `pages/inventory/ItemForm.tsx` | Add/edit item form |
| `pages/inventory/InventoryItem.tsx` | Item list item |
| `pages/inventory/itemMetadata.ts` | Metadata builder (pure logic) |
| `pages/notes/VoiceRecorder.tsx` | Voice recording |
| `pages/notes/NoteEditor.tsx` | Note add/edit form |
| `pages/notes/NoteItem.tsx` | Note list item |
| `pages/multiclass/ResourceManager.tsx` | Class resource CRUD |
| `pages/multiclass/AddClassForm.tsx` | Add class form |
| `pages/maps/MapUploadForm.tsx` | Map upload form |
| `pages/maps/MapZoneGroup.tsx` | Map zone grouped display |

### Modified files (~30)

| File | What Changes |
|------|-------------|
| `package.json` | Add `lucide-react` |
| `index.html` | Add Cinzel font `<link>` |
| `tailwind.config.js` | Add `dnd` colors, `fontFamily.cinzel`, `boxShadow.dnd-glow` |
| `src/index.css` | New CSS variables (dark+light), animations, body styles |
| `src/App.tsx` | ModalProvider wrapper, lazy routes + Suspense, theme detection |
| `src/main.tsx` | Theme detection on init |
| `src/components/Card.tsx` | Add `variant` prop |
| `src/components/Layout.tsx` | Cinzel title, gold back, dot indicator, fade-in |
| `src/components/HPBar.tsx` | Gradients, glow, pulse, transition |
| `src/components/RollResultModal.tsx` | D&D theme, animations |
| `src/components/WeaponAttackModal.tsx` | D&D theme, animations |
| `src/pages/CharacterMain.tsx` | Grouped menu, icons, hero card, gear icon, skeletons |
| `src/pages/CharacterSelect.tsx` | New palette, elevated cards, skeletons |
| `src/pages/HP.tsx` | Decomposed, card variants, new buttons |
| `src/pages/Spells.tsx` | Decomposed, card variants, new buttons |
| `src/pages/Inventory.tsx` | Decomposed, card variants, new buttons |
| `src/pages/Notes.tsx` | Decomposed, new buttons |
| `src/pages/Multiclass.tsx` | Decomposed, new buttons |
| `src/pages/Maps.tsx` | Decomposed, new buttons |
| All other pages | Token migration, Card variants, DndButton/DndInput, ScrollArea |
| `src/locales/it.json` | ~30-40 new keys |
| `src/locales/en.json` | ~30-40 new keys |

---

## 15. Implementation Order (Vertical Slice)

### Phase 1: Foundation
1. Install lucide-react + add Cinzel font
2. Design tokens + theme system (dark/light CSS vars, Tailwind config, theme detection)
3. Shared components: DndInput, DndButton, ModalProvider, Skeleton, ScrollArea, SectionHeader
4. Swipe navigation hook + PAGE_GROUPS config
5. Layout upgrade: Cinzel header, gold back, dot indicator, fade-in

### Phase 2: First Vertical Slice
6. CharacterSelect — palette, skeletons, DndButton, elevated cards
7. CharacterMain — grouped menu, Lucide icons, hero card, gear icon, skeletons
8. HP page — decompose + apply all new components + swipe
9. ArmorClass + SavingThrows — token migration + swipe (completes Combat group)

### Phase 3: Replicate Pattern
10. Magic group — Spells decomposition + SpellSlots + swipe
11. Skills group — AbilityScores + Skills + Abilities + swipe
12. Equipment group — Inventory decomposition + Currency + swipe
13. Character group — Identity + Multiclass decomposition + Experience + Conditions + swipe
14. Tools group — Dice + Notes decomposition + Maps decomposition + History + swipe
15. Settings — gear icon access only, token migration

### Phase 4: Polish
16. i18n cleanup — move all hardcoded strings to locale files
17. Performance — lazy routes in App.tsx, React.memo on identified components
18. Final verification — TypeScript check, visual smoke test, production build

---

## 16. Out of Scope

- Page route transition animations (swipe handles spatial feeling)
- Custom SVG icon design
- Backend/API changes
- Bot changes
- New features or functionality beyond UX improvements described here
- Full accessibility overhaul (WCAG compliance)
- Test infrastructure (vitest, MSW, RTL)
- Light mode custom design — light mode uses automatic token inversion, not a bespoke design

---

## Visual Reference

Mockups from brainstorming session available at `.superpowers/brainstorm/2001-1776287634/content/` — covers theme tokens comparison, component library showcase, and swipe navigation design.
