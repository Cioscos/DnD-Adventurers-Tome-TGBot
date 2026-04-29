# Character Menu — Swipe / Speed / Narrow-Screen / Silhouette Fixes

**Date:** 2026-04-29
**Branch:** `feat/character-menu-3-screens`
**Scope:** four parallel improvements to the 3-screen character hub at `/char/:id`.

## 1. Goals

1. Restore and polish horizontal swipe between the three main screens (Hero / Equipment / Menu).
2. Move the character speed pill out of an absolute-positioned overlap-prone slot into a dedicated, always-stable location.
3. Audit the entire webapp for components that misbehave on narrow viewports and adapt them via container queries.
4. Replace the static Vitruvian silhouette in `EquipmentScreen` with a class+race+gender-specific image, with a graceful fallback to the existing SVG silhouette when no image matches.

Each section below is independent enough to be planned and implemented as its own slice, but they ship together on this branch.

---

## 2. Swipe fix (`CharacterSwiper`)

### Problem

`CharacterSwiper.tsx` uses `framer-motion` `drag="x"` with `dragDirectionLock`, but on Telegram mobile (and in some desktop browsers) the gesture never starts: the user's finger moves and nothing happens.

### Diagnosis

- The `m.div` track has no `touch-action` declaration.
- Each of the three panels has `overflow-y-auto`, so the browser claims the touch as a vertical scroll the moment it begins.
- Without `touch-action: pan-y` the browser can also claim **horizontal** movement as a native scroll, before framer-motion's direction-lock has a chance to start the drag.
- `dragMomentum={false}` plus a stiff spring snap (`stiffness: 400, damping: 40`) make the motion feel hard once it does start.

### Solution

1. Apply `touchAction: 'pan-y'` to the track `m.div` — explicitly cedes vertical to the browser, claims horizontal for the drag handler.
2. Apply `touchAction: 'pan-y'` to each inner panel as well, so the inner scroll is unambiguous.
3. Drop `dragMomentum={false}` so a fast flick carries naturally through the snap.
4. Soften the snap-back spring to `stiffness: 360, damping: 32` for a less abrupt return.
5. Keep the existing velocity / offset thresholds (`VELOCITY_THRESHOLD = 500`, `OFFSET_RATIO = 0.25`) — they already produce sensible page-changes when the drag is allowed to run.

### Out of scope

- Replacing framer-motion with embla-carousel-react. Only revisit if the touch-action change does not fully resolve the gesture conflict on Telegram Android.

---

## 3. Speed pill — dedicated `VitalsStrip` (option C1)

### Problem

The speed `StatPill` is currently anchored `absolute bottom-3 right-3` inside the hero `Surface`. When the Surface contains the conditions row (with `pr-16` reserve) it does not overlap, but when only the abilities row is present — or when the ability scores grid is the last block — the pill can sit on top of dynamic content. The position also "feels different" depending on what content is rendered.

### Solution

Introduce a new component `webapp/src/components/character/VitalsStrip.tsx`:

- Renders a single horizontal strip with a centered emerald `StatPill` showing `{char.speed} ft` and a `GiBootPrints` icon.
- Designed to host additional vitals later (initiative, perception); for now only speed.
- Marked `revealOnTap` to keep parity with the existing pill behavior.

`HeroScreen.tsx` changes:

- Remove the `<StatPill ... className="absolute bottom-3 right-3">` block (lines ~208–217).
- Insert `<VitalsStrip char={char} />` as the first child of the screen container, directly before the hero `<Surface>`.
- Remove the `pr-16` reserve from the conditions row — no longer needed.

### Behavior

- Position is now structural (top of `HeroScreen`), not absolute. It shifts vertically with the rest of the layout but never overlaps the Surface contents.
- Adapts to narrow widths via the container-query work in section 4.

---

## 4. Container-query responsive pass

### Goal

Make the Mini App look correct down to **300 px** viewport width without producing per-component "Compact" duplicates. Use container queries so each component reacts to the width of its own slot, not just the viewport — Telegram's drawer width can shrink independently of the device width.

### Setup

- Add `@tailwindcss/container-queries` to `webapp/package.json` and register the plugin in `webapp/tailwind.config.js`. The plugin provides arbitrary-value `@max-[<width>]:...` classes; no named-alias config is required.
- Two effective tiers used across the codebase:
  - **narrow** — `@max-[360px]:...` (container width up to 360 px).
  - **xnarrow** — `@max-[300px]:...` (container width up to 300 px).
- Each component that needs to react wraps its root in `className="@container"` and uses the two tier classes above.

### Audit & adaptation map

| Component | Issue at narrow widths | Adaptation |
|---|---|---|
| `HeroScreen` ability scores grid (`grid-cols-6`) | Pills become unreadable below ~320 px | `@max-[300px]:grid-cols-3` (renders as 3 × 2) |
| Hero card top row (HP gauge + AC shield in flex) | AC shield 90 px + HP block stack horizontally | `@max-[300px]:flex-col items-stretch` so AC sits above HP |
| `EquipmentStatsFooter` 3-column tome card | Labels truncated below ~320 px | `@max-[300px]:grid-cols-1 gap-2` stack |
| `ProgressionPreview` table | Wide "features" column overflows | `@max-[360px]:text-xs`; `@max-[300px]` hide the proficiency-bonus column |
| `PaperDoll` (`grid-cols-[56px_1fr_56px]`) | 56 px slots + 200 px svg + 56 px overflow on small phones | `@max-[360px]` shrink slot column to `48px` and SVG `width: 100%`; manage spacing via `gap-1.5` |
| `ClassTabs` | Long Italian class names overflow tabs | Already scrollable; add `@max-[360px]:text-[10px] @max-[360px]:px-2` |
| `EquipItemPicker` modal cards | Weight + quantity inline pills wrap awkwardly | `@max-[360px]:flex-col @max-[360px]:items-start` on the meta row |
| `SpellSlotsSummary` slots row | Slot pills wrap into 2 rows clumsily | `@max-[360px]:gap-1` and `flex-wrap` already present, just shrink gap |
| `SwiperDots` | None — already minimal | skip |

All adaptations are **inline** on the existing components. No `*Compact.tsx` files are introduced.

### Validation strategy

- Manual: open the app at 280 / 320 / 360 / 400 px widths via DevTools responsive mode.
- Spot-check on a real Android Telegram session before merging.

---

## 5. Class+race+gender silhouette

### Filesystem layout

Images live in `webapp/public/silhouettes/`:

```
wizard_elf_male.png
wizard_elf_female.png
fighter_human_male.png
...
```

- Format: PNG with transparent background.
- Naming: `{class}_{race}_{gender}.png`, all lowercase, underscores only.
- `class` uses the canonical English-lowercase D&D 5e key (`barbarian`, `bard`, `cleric`, `druid`, `fighter`, `monk`, `paladin`, `ranger`, `rogue`, `sorcerer`, `warlock`, `wizard`).
- Partial-match files are also valid: `wizard_elf.png`, `wizard_male.png`, `wizard.png` are all eligible fallbacks.
- The directory may be empty at first commit; resolver simply returns `null` and the SVG fallback is used.

### Build-time manifest

Vite reads `webapp/public/` only when the file is referenced, so we cannot rely on the dev server to enumerate matches. Instead:

- New script `webapp/scripts/generate-silhouette-manifest.mjs` runs `fs.readdirSync('webapp/public/silhouettes')`, filters to `.png`, writes `webapp/src/data/silhouette-manifest.json` as a `string[]` of filenames (without path).
- Hook the script into Vite via a tiny custom plugin in `webapp/vite.config.ts` (`buildStart` hook) so dev and build both regenerate the manifest. `npm run build:prod` automatically picks it up.
- `webapp/src/data/silhouette-manifest.json` is added to `.gitignore` (regenerated, not source).

### Resolver — `webapp/src/lib/silhouette.ts`

Public API:

```ts
export function silhouetteUrl(char: CharacterFull): string | null
```

Algorithm:

1. **Pick the primary canonical class.** Filter `char.classes` to those whose `class_name` is in `CANONICAL_CLASSES`. If empty, return `null` (all classes are custom; caller falls back to SVG). Otherwise pick the entry with the highest `level`; tie-break alphabetic on `class_name`.
2. **Slug race.** Lowercase + trim `char.race`, look up in `RACE_SLUG_MAP`. Missing key → race slug is `null`.
3. **Slug gender.** Lowercase + trim `char.gender`, look up in `GENDER_SLUG_MAP`. Anything not in the map (including non-binary, "altro", empty) → gender slug is `null`.
4. **Build candidate filename list** in order of specificity:
   - `${classSlug}_${raceSlug}_${genderSlug}.png` (only if both race and gender slugs are non-null)
   - `${classSlug}_${raceSlug}.png` (only if race slug is non-null)
   - `${classSlug}_${genderSlug}.png` (only if gender slug is non-null)
   - `${classSlug}.png`
5. **Pick the first candidate present in the manifest set.** Return `${import.meta.env.BASE_URL}silhouettes/<file>` so the path works correctly under the `/DnD-Adventurers-Tome-TGBot/app/` GitHub Pages prefix as well as the local `/` dev base.
6. **No match** → return `null`.

### Slug seed maps

```ts
const CANONICAL_CLASSES = new Set([
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
```

Lookup is exact-match on the lowercased trimmed input. No fuzzy matching, no Unicode normalization beyond `toLowerCase()`. Anything not in the table reduces the fallback chain rather than guessing.

### Render integration

- `PaperDoll` gains an optional prop `silhouetteUrl?: string | null`.
  - When `null` or `undefined`: render the existing SVG silhouette unchanged.
  - When a string: render `<img src={silhouetteUrl} ... />` in the same container slot, sized to fit the same min-height. Add `onError` to swap back to the SVG node (defensive against manifest/file divergence).
- `EquipmentScreen` computes `silhouetteUrl(char)` once per render and passes it to `<PaperDoll>`.

### Out of scope

- Authoring the actual PNG art. The directory ships empty; the resolver's `null` path keeps the screen functional until art is added.
- Per-subclass variations.
- Animation / hover effects on the rendered image.

---

## 6. File / module change list

New files:

- `webapp/src/components/character/VitalsStrip.tsx`
- `webapp/src/lib/silhouette.ts`
- `webapp/scripts/generate-silhouette-manifest.mjs`
- `webapp/public/silhouettes/.gitkeep` (so the directory exists in source control)
- `webapp/src/data/silhouette-manifest.json` (generated, gitignored)

Modified files:

- `webapp/src/components/character/CharacterSwiper.tsx` — touch-action + spring tweaks.
- `webapp/src/pages/character/HeroScreen.tsx` — remove absolute speed pill, mount `VitalsStrip`, drop `pr-16` from conditions row.
- `webapp/src/components/character/PaperDoll.tsx` — accept `silhouetteUrl` prop, conditional `<img>` render with SVG fallback.
- `webapp/src/pages/character/EquipmentScreen.tsx` — compute and pass `silhouetteUrl`.
- `webapp/tailwind.config.js` — register `@tailwindcss/container-queries` plugin.
- `webapp/vite.config.ts` — register manifest-generation plugin.
- `webapp/package.json` — add `@tailwindcss/container-queries` dependency.
- `.gitignore` — `webapp/src/data/silhouette-manifest.json`.
- The components listed in section 4 — inline container-query class additions.

---

## 7. Build & validation

- After all changes: `cd webapp && npm install` (new dep) → `npm run build:prod` so the production `docs/app/` bundle is rebuilt before merge, per the project rule.
- After `build:prod`, restore `webapp/.env.local` to `http://127.0.0.1:8000` (known build-prod quirk).
- Manual verification: open `http://localhost:5173/` at viewport widths 320 / 360 / 400 / 768 px (the two tier breakpoints are 360 and 300, so 320 lands in `xnarrow` territory). A 280 px sanity check is welcome but not a hard requirement — the spec target is 300 px and below.
- Drop a placeholder PNG into `webapp/public/silhouettes/wizard.png` during testing to verify the resolver / manifest pipeline; remove before commit.

## 8. Risks & open items

- **Telegram Android pointer events**: the touch-action fix is the canonical browser-level fix; if a specific Android version still misbehaves we revisit with embla-carousel as a fallback (out of scope for this spec).
- **Manifest staleness**: in dev, when a PNG is added without restarting Vite, the manifest does not refresh until the next dev-server start. The `buildStart` hook covers builds; for dev a watcher is overkill given how rarely files will be added.
- **Race slug seed**: only PHB races are seeded. Custom races (e.g., "Aasimar", "Genasi") will not match — silhouette falls back to class-only, which is acceptable. Future work can extend the map.
