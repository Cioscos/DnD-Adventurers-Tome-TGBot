---
name: D&D Adventurer's Tome
description: Illuminated-manuscript-noir Telegram Mini App for live D&D 5e play
colors:
  ink: "#0d0a08"
  bg: "#1a1512"
  surface: "#241d18"
  surface-raised: "#2f261f"
  surface-lifted: "#3b3026"
  border: "#4a3d30"
  border-strong: "#6b5841"
  parchment: "#f4e8c1"
  text: "#ebdfbf"
  text-muted: "#b5a482"
  text-faint: "#857761"
  gold: "#d4a847"
  gold-bright: "#f0c970"
  gold-dim: "#8b7335"
  gold-deep: "#5a4820"
  crimson: "#b33a3a"
  crimson-bright: "#e85050"
  crimson-deep: "#7a1f1f"
  emerald: "#3fa66a"
  emerald-bright: "#6fd195"
  emerald-deep: "#1f6b3f"
  arcane: "#9b59b6"
  arcane-bright: "#c589e8"
  arcane-deep: "#4a2858"
  cobalt: "#3a7ca5"
  cobalt-bright: "#6fa8cf"
  cobalt-deep: "#1e4060"
  amber: "#e8a547"
typography:
  display:
    fontFamily: "\"Cormorant Unicase\", Cinzel, Georgia, serif"
    fontSize: "clamp(1.875rem, 6vw, 2.75rem)"
    fontWeight: 600
    lineHeight: 1.05
    letterSpacing: "0.005em"
  headline:
    fontFamily: "Cinzel, Georgia, serif"
    fontSize: "1.25rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.02em"
  title:
    fontFamily: "Cinzel, Georgia, serif"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "0.04em"
  body:
    fontFamily: "Fraunces, Georgia, serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.55
    fontFeature: "\"ss01\", \"ss02\""
  label:
    fontFamily: "Cinzel, Georgia, serif"
    fontSize: "0.6875rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.08em"
  mono:
    fontFamily: "\"JetBrains Mono\", ui-monospace, monospace"
    fontSize: "0.875rem"
    fontWeight: 500
    lineHeight: 1.2
rounded:
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  full: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  "2xl": "32px"
components:
  button-primary:
    backgroundColor: "{colors.gold}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    padding: "12px 16px"
    height: "48px"
  button-primary-hover:
    backgroundColor: "{colors.gold-bright}"
    textColor: "{colors.ink}"
  button-secondary:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    padding: "12px 16px"
    height: "48px"
  button-danger:
    backgroundColor: "{colors.crimson-deep}"
    textColor: "{colors.crimson-bright}"
    rounded: "{rounded.md}"
    padding: "12px 16px"
    height: "48px"
  button-arcane:
    backgroundColor: "{colors.arcane-deep}"
    textColor: "{colors.parchment}"
    rounded: "{rounded.md}"
    padding: "12px 16px"
    height: "48px"
  button-ghost:
    backgroundColor: "#00000000"
    textColor: "{colors.gold}"
    rounded: "{rounded.md}"
    padding: "12px 16px"
    height: "48px"
  input-default:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    typography: "{typography.body}"
    rounded: "{rounded.sm}"
    padding: "10px 12px"
    height: "48px"
  surface-flat:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.lg}"
    padding: "16px"
  surface-elevated:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.text}"
    rounded: "{rounded.lg}"
    padding: "16px"
  surface-tome:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.text}"
    rounded: "{rounded.lg}"
    padding: "16px"
  chip-default:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.gold-bright}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "4px 10px"
  chip-filter:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-muted}"
    typography: "{typography.label}"
    rounded: "{rounded.full}"
    padding: "6px 12px"
    height: "44px"
  chip-filter-selected:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.gold-bright}"
    rounded: "{rounded.full}"
  dialog-default:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.text}"
    rounded: "{rounded.xl}"
    padding: "24px 24px 28px"
---

# Design System: D&D Adventurer's Tome

## 1. Overview

**Creative North Star: "Illuminated Manuscript Noir"**

The interface borrows from a leather-bound book of hours read by candlelight. Surfaces are warm-brown ink and aged parchment; ornament is gold leaf, applied sparingly so it still catches light. The default mode is dark, the way a real codex looks under a single lamp at the table; the light mode is aged parchment, the way the same codex looks held to a window the next morning. Both are equally first-class.

Density is moderate. There is real ornament — corner flourishes, ornament rules, candle-glow halos — but it is concentrated where the eye lands first (page headers, dialog frames, the rare hero element) and absent everywhere else. Reading surfaces (rule text, item descriptions, dice tallies) defer to plain hierarchy so a player at the table can find their AC in 1.5 seconds. The system is **epica, leggibile, calma, tattile** — epic, legible, calm, tactile — in that order of priority. When two of those collide, legibility wins; tactility loses.

The system explicitly rejects the SaaS-cream "soft neutral + blue accent + rounded-2xl" reflex, the D&D Beyond "neon red on pure black" register, the Roll20 "WordPress 2014" chrome, the gacha mobile "particles on every tap" register, and the AI-slop "tinted-card grid + gradient text" default. Anywhere the design starts converging on one of those, it has failed and gets rebuilt.

**Key Characteristics:**
- Warm-brown ink (`#1a1512`) and aged parchment (`#f4e8c1`) — never pure black, never pure white.
- Gold ink (`#d4a847` → `#f0c970`) reserved for primary affordance and ornament. <10% surface coverage.
- Fantasy-serif type stack: Cormorant Unicase for display, Cinzel for labels and titles, Fraunces for body, JetBrains Mono for numerics.
- Halo glows (gold / arcane / danger) signal *required action*, not decoration.
- Subtle SVG turbulence grain (0.035 opacity in dark, 0.09 in light) — a printed-page texture, not a filter on top.
- Five named semantic palettes: gold (primary), crimson (danger), emerald (success), arcane (magic), cobalt (info), amber (highlight).
- Motion uses ease-out parchment curves (`cubic-bezier(0.22, 1, 0.36, 1)`). One elastic spring (`spring.elastic`, stiffness 240 / damping 10) is reserved for the dice roller and for single-element value pops at the moment a result lands; elastic never moves layout, lists, pages, or modals.

## 2. Colors: The Illuminated Palette

The palette is a single warm-brown family with five semantic accents. Every neutral is tinted toward the gold hue (chroma drifts low toward the extremes). No `#000`, no `#fff`. Light mode is not "white-mode" — it is a separate parchment palette computed independently, not a contrast-flip of the dark tokens.

### Primary
- **Gold Leaf** (`#d4a847`): the only color reserved for primary affordance — primary buttons, the active-page sigil, the focus-visible halo, the page-header underline. Its rarity is the point.
- **Gold Bright** (`#f0c970`): hover state of primary, ink-spread highlight, dialog accent border on success-feeling outcomes (good roll, level-up).
- **Gold Dim** (`#8b7335`): inactive ornament, secondary-button border resting state, label color for de-emphasized form fields.
- **Gold Deep** (`#5a4820`): bottom of the metallic gradient, only inside `--gradient-gold`.

### Secondary (semantic, not visual hierarchy)
- **Dragon Crimson** (`#b33a3a` / bright `#e85050` / deep `#7a1f1f`): damage, danger, HP threshold ≤25%, destructive actions, death saves. Never used decoratively.
- **Druid Emerald** (`#3fa66a` / bright `#6fd195` / deep `#1f6b3f`): healing, success states, HP threshold ≥75%, save passed. Never used decoratively.
- **Arcane Amethyst** (`#9b59b6` / bright `#c589e8` / deep `#4a2858`): magic — spell slots, concentration, spellcasting buttons, arcane dialog accent.
- **Cobalt Sigil** (`#3a7ca5` / bright `#6fa8cf` / deep `#1e4060`): information, neutral metadata, tooltips, info dialogs.
- **Candle Amber** (`#e8a547`): rare-warning highlight (concentration banner pulse, level-up call-out). Adjacent to gold but desaturated; never substituted for gold in primary affordance.

### Neutral (warm-brown, dark mode default)
- **Lampblack Ink** (`#0d0a08`): deepest surface — page background under all chrome, primary-button text on gold gradient.
- **Tome Background** (`#1a1512`): body background; the candlelit page.
- **Tome Surface** (`#241d18`): default card / surface fill.
- **Surface Raised** (`#2f261f`): elevated card fill, dialog body, secondary button.
- **Surface Lifted** (`#3b3026`): top-of-stack popovers, drag-active states.
- **Border** (`#4a3d30`) / **Border Strong** (`#6b5841`): rules and frames; never colored stripes.
- **Parchment** (`#f4e8c1`): button text on gradients, light-mode page surface, button-arcane label.
- **Manuscript Text** (`#ebdfbf` / muted `#b5a482` / faint `#857761`): three-step text hierarchy on dark surfaces.

### Light mode (aged parchment)
Light mode is a deliberate alternative palette, not a derivation. Background is `#f2e4b9` (aged paper); ink darkens to `#2e2410`; gold darkens to `#8a6a1e` so it still reads as metallic on bright cream. Both modes pass the same contrast and signal bar.

### Named Rules
- **The Gold Leaf Rule.** Gold is the primary affordance and the focus halo. It must not exceed 10% of any rendered screen and must not appear as a decorative gradient on text. If you need to draw the eye somewhere and gold is already used elsewhere on the screen, you have placed the wrong element first — rebuild the hierarchy, do not double-up gold.
- **The Two Inks Rule.** Surfaces use the warm-brown ink family; ornament uses gold ink. Mixing the two on the same element (gold-tinted surfaces, brown-tinted gold) flattens the manuscript metaphor. Keep them separate.
- **The Semantic Triad Rule.** Crimson / Emerald / Arcane are reserved for their semantic meanings (damage, healing, magic). Never use them decoratively to "add color". If a surface needs visual interest, use surface elevation or ornament — not borrowed semantic color.

## 3. Typography

**Display Font:** Cormorant Unicase (with Cinzel, Georgia, serif as fallback) — a small-caps display serif that reads as carved stone or illuminated capitals.
**Headline / Title / Label Font:** Cinzel (with Georgia, serif as fallback) — Roman-inscriptional, all-caps friendly, the workhorse for everything that wants to feel inscribed.
**Body Font:** Fraunces (with Georgia, serif as fallback). Two stylistic sets are enabled globally (`ss01`, `ss02`) for the curlier `g` and `a` — they read as hand-set, not as system serif.
**Numeric / Mono Font:** JetBrains Mono — for dice tallies, AC, modifier values, history rows. Tabular figures so columns line up.

**Character:** the pairing reads "literate but not flowery". Cinzel and Cormorant carry the manuscript metaphor; Fraunces keeps reading text approachable; JetBrains Mono is the only sans-shaped element in the stack — and it is monospaced, so it doesn't compete with the Cinzel inscriptions next to it.

### Hierarchy

- **Display** (Cormorant Unicase, 600, `clamp(1.875rem, 6vw, 2.75rem)`, line-height 1.05): page title bars (e.g. character name on the hero screen), result-dialog titles when the moment is large, entity names (character cards, combatant rows), and hero numerals — the single illuminated value of a surface (current HP, AC in the shield, an ability score). When it carries a hero numeral the weight rises (`font-bold` / `font-black`) and the size scales to the moment, up to 5rem for current HP.
- **Headline** (Cinzel, 700, 1.25rem, line-height 1.2): section headers inside a screen, modal titles.
- **Title** (Cinzel, 600, 1rem, letter-spacing 0.04em): grouped-card titles, list-item headers.
- **Body** (Fraunces, 400, 0.9375rem, line-height 1.55, ss01+ss02): rule text, descriptions, narrative copy. Cap line length at 65–75ch.
- **Label** (Cinzel, 700, 0.6875rem, uppercase, letter-spacing 0.08em): every form label, every chip, every tag, every legend caption. Almost every small piece of inscribed text in the UI is this style.
- **Mono** (JetBrains Mono, 500, 0.875rem, tabular-nums): dice values, AC, HP numbers in tables, history timestamps.

### Named Rules
- **The Inscription Rule.** Cinzel is for inscribed words: section headers, labels, chips, button text, ornamental rules. Use it short — never set a paragraph in Cinzel; never set a label in Fraunces. Long-form text always falls to Fraunces.
- **The Illuminated Capital Rule.** Cormorant Unicase speaks only for what the manuscript would illuminate: proper names (the character, a combatant, a page title) and the one hero value the eye must land on first (current HP, AC, a coin total). Everything structural — section headers, list labels, buttons, form captions — stays in Cinzel. If a screen sets more than one or two values in Cormorant, it has stopped illuminating and started shouting.
- **The Tabular Numerics Rule.** Any number that compares against another number (HP/maxHP, dice rolls, AC components, money totals) is set in JetBrains Mono with `font-variant-numeric: tabular-nums`. Mixed-font numerics inside a row break the rhythm. One sanctioned exception: the single hero numeral of a surface is an illuminated capital in Cormorant Unicase (see The Illuminated Capital Rule); its comparative companions stay mono — `38` may be illuminated, `/54` never is.
- **The No Gradient Text Rule.** Even though the system has a `--gradient-flourish` and an `animate-gold-shimmer` utility, gradient text is reserved for **one** ornamental flourish element per page (the page-header underline glyph). Body text, headings, button labels, numerics — all solid color. The `animate-gold-shimmer` utility outside that one role is forbidden.

## 4. Elevation

The system uses **tonal layering plus warm-brown shadows plus halo accents** — a hybrid. Surfaces stack visually by lifting one step in the warm-brown ladder (`bg → surface → surface-raised → surface-lifted`); shadow depth is reinforcement, not the primary signal. Shadow color is *not* black — it is `rgba(26, 16, 8, 0.25–0.45)`, tinted toward the gold hue so the cast feels like ink soaking through a page rather than a dropped neutral panel.

Halos are a separate vocabulary. They are not for elevation — they are for **required action**. A `halo-gold` ring around an element means "act here next"; `halo-arcane` means "concentration / magic active"; `halo-danger` means "this state needs attention now". They are signal, not chrome.

### Shadow Vocabulary

- **shadow-1** (`0 1px 2px rgba(26,16,8,.25)`): subtle press, button rest.
- **shadow-2** (`0 2px 4px / 0 1px 2px`): list cards, default surface elevation.
- **shadow-3** (`0 6px 14px / 0 2px 4px`): elevated card, popover.
- **shadow-4** (`0 14px 28px / 0 6px 10px`): modal sheet, drag-active.
- **shadow-5** (`0 24px 48px / 0 10px 20px`): result dialog at center stage.
- **shadow-engrave** (`inset 0 1px 0 rgba(255,220,140,.25), inset 0 -1px 2px rgba(0,0,0,.35)`): metallic-pressed inset on gold primary buttons. Sells the "stamped" feel.

### Halo Vocabulary (signal, not elevation)

- **halo-gold** (`0 0 0 2px rgba(212,168,71,.35), 0 0 18px var(--dnd-gold-glow)`): focus-visible, primary call-to-action attention.
- **halo-arcane** (`0 0 0 2px rgba(155,89,182,.35), 0 0 22px rgba(155,89,182,.25)`): concentration active, magic in flight.
- **halo-danger** (`0 0 0 2px rgba(179,58,58,.35), 0 0 14px rgba(179,58,58,.25)`): HP at 0, death-save required, hostile turn.

### Named Rules
- **The Warm-Shadow Rule.** Shadows are tinted warm-brown (`rgba(26,16,8,...)`), never neutral gray, never pure black. A neutral-gray drop shadow on a parchment surface looks like a screenshot of a dialog box, not a page lifting off a tome.
- **The Halo-as-Signal Rule.** Halos carry meaning, never decoration, never hover-only fluff. They speak two dialects. **Attention** ("act here now": 0 HP, concentration active, focus-visible) allows at most one per screen — if two attention halos compete, the user can't tell where to look. **Selection** (the ring on a selected filter pill, gold or arcane by tone) marks "this is shaping what you see" and may repeat across a filter row. A halo that is neither attention nor selection is forbidden.

## 5. Components

### Buttons
Buttons read as inscribed plates pressed into the page. Primary is gold leaf with shadow-engrave inset and an ink-spread ripple on press; secondary is a raised parchment surface with a gold-dim hairline border that warms to gold on hover; ghost is a transparent gold-text affordance for tertiary navigation.

- **Shape:** rounded `12px` (`rounded-xl`). Never sharp; never pill.
- **Sizes:** sm `min-h-40px`, md `min-h-48px`, lg `min-h-56px`. Never below 40px on a phone.
- **Primary:** `bg-gradient-gold`, `text-dnd-ink`, `shadow-engrave`. Hover: brighten gradient (no scale). Press: `scale 0.97`, ink-spread ripple at click coordinate (320ms ease-out).
- **Secondary:** `bg-dnd-surface-raised`, `text-dnd-text`, `border border-dnd-gold-dim/30`. Hover: border warms to `border-dnd-gold/70`.
- **Danger:** crimson tint at 15% on surface, crimson-bright text, crimson border at 40%. No solid red fill — danger reads as warning ink, not as alarm.
- **Arcane:** gradient `arcane-deep → arcane`, parchment-white text, halo-arcane shadow. Reserved for explicit magic actions (cast, concentrate).
- **Ghost:** transparent, gold text, no border at rest. Hover: gold-bright text only.
- **Loading:** spinner (current-color, 4px stroke) replaces leading icon; label remains visible.
- **Haptic:** every variant fires a Telegram haptic on press (light by default, success/error/warning/medium overridable).
- **Kit only:** raw `<button>`/`<m.button>` are forbidden outside `components/ui/` (enforced by ESLint). Every tappable surface is `Button`, `IconButton`, or the unstyled `Pressable`; all of them express a pending state (spinner + disabled) that MUST be wired to `mutation.isPending` for any BE-triggering control. `SwitchToggle` takes `pending` for async toggles. The pending spinner appears immediately on tap — no delay, no minimum duration.

### Inputs
Inputs are a single horizontal underline rule that warms to gold under focus, like a quill drawing the writing line. Floating placeholders are not used; the label is a Cinzel small-caps caption above the field.

- **Shape:** `rounded-lg` (8px) on the field background; the gold underline is a 2px bottom border.
- **Default:** `bg-dnd-surface`, `text-dnd-text`, body font, faint placeholder. Bottom border `border-dnd-border` (warm brown).
- **Focus:** bottom border shifts to `border-dnd-gold`, plus a `0 2px 0 0 var(--dnd-gold-glow)` underline glow. Label color also warms to `gold-bright`.
- **Error:** label and underline both turn `crimson-bright`; the field shakes (`x: [-4, 4, -2, 2, 0]` over 250ms) once on the failing blur. Error message slides in below in `crimson-bright` body.
- **Numeric inputs** use `inputMode='numeric'` with min/max validation on blur (not on every keystroke). The shake fires once per failed commit.

### Cards / Surfaces
Surfaces come in seven named variants — each is a scene the page wants to evoke, not just an elevation token.

- **Shape:** `rounded-2xl` (16px). Internal padding `16px` default.
- **flat**: bare surface, transparent border. The basic content well.
- **elevated**: surface-raised + gold-dim/50 border + shadow-parchment-lg. The default for grouped-content cards.
- **tome**: gradient-parchment background + border-strong + shadow-parchment-xl + grain overlay. Hero containers; rule excerpts; spell descriptions worth lingering on.
- **parchment**: gradient-parchment + plain border + shadow-parchment-md. The lighter cousin of tome — quieter pages.
- **arcane**: gradient-arcane-mist + arcane/40 border + halo-arcane. Spell slots, concentration target.
- **ember**: surface + crimson/50 border + halo-danger. The 0-HP banner, hostile-turn pane.
- **sigil**: gradient-parchment + gold/40 border + shadow-parchment-xl + grain. Reserved — a "this is the sealed declaration" surface, used once per page if at all.
- **Interactive surfaces** scale to `0.98` on press with the press spring (`stiffness 420, damping 28, mass 0.6`). Optional layoutId for shared-element transitions.

### Chips / Pills
Two species share the Cinzel-caps inscription but differ in shape, and the shape is the signal: a lozenge is a static label, a pill is a tappable toggle.

- **Inscribed chip** (static label, tag, badge): `rounded-lg` (8px), padding `4px 10px`, `bg-dnd-chip-bg`, `border border-dnd-chip-border`, `text-dnd-gold-bright`, label typography (Cinzel 11px uppercase 0.08em). Never interactive, never haloed. Semantic variants swap tint and text color but keep the lozenge.
- **Filter pill** (`FilterChip`, interactive filter / toggle): `rounded-full`, min-height 44px (touch target), same label typography, optional leading icon and mono count badge. Three tones: gold (default), arcane (magic filters), neutral.
  - **Resting:** `bg-dnd-surface`, `border-dnd-border`, muted text.
  - **Selected:** tinted ground (gold chip tint / arcane mist), strong border (`gold/70` / `arcane/70`), bright text, plus the matching **selection halo** (`shadow-halo-gold` / `shadow-halo-arcane`) — a selection ring, not an attention halo (see The Halo-as-Signal Rule). The neutral tone selects without a halo.
- The full-round shape is reserved for the filter pill: buttons, inscribed chips, and inputs never go pill.

### Dialogs / Result Modals
The signature container of the system. A parchment-gradient panel framed by an accent border (gold by default; swappable to crimson, emerald, arcane, cobalt) and four corner flourishes. Backdrop is the warm overlay (`#2e2410` at 55% / `#0d0a08` at 82%) plus a 6px backdrop blur.

- **Shape:** `rounded-3xl` (24px), corners ornamented with SVG flourishes.
- **Entrance:** opacity `0 → 1` plus scale `0.92 → 1` plus y-offset `20 → 0`, swipe spring (`stiffness 260, damping 28`). 200ms backdrop fade.
- **Pulse modifier:** `animate-pulse-gold` for celebratory outcomes (3 cycles), `animate-pulse-danger` for alarming outcomes (2s loop). Both opt-in; default is no pulse.
- **Tap outside dismisses; ESC dismisses.** Never trap the user.

### Hero Numbers (signature)
HP, AC, dice totals, XP — the values the player checks first. The hero value itself is an illuminated capital: Cormorant Unicase (`font-display`), heavy (`font-black`), large (up to 5rem for current HP). Its comparative companions stay in JetBrains Mono — the `/max` beside it, the breakdown rows beneath it, the history columns around it. `38` is illuminated; `/54` is not. HP carries one of three drop-shadow glows that map to threshold:
- `hp-glow-emerald` for healthy (≥75%)
- `hp-glow-gold` for wounded (25–75%)
- `hp-glow-crimson` for critical (≤25%)
The glow itself is signal — hue and intensity together communicate state at a glance from across the table. On value change the number pops in with `spring.elastic` (scale 0.85 → 1): the one sanctioned elastic gesture outside the dice roller.

### Ornaments (signature)
- **Corner flourishes**: 4 SVG sigils on dialog corners, gold-dim, decorative-only.
- **Ornament line**: a flourish-gradient hairline with `◈` glyphs at each end. Page-header divider, never inside content.
- **Section divider**: small Cinzel label with two `ornament-line` halves; used to break a long page into ritual sections.

## 6. Do's and Don'ts

### Do:
- **Do** ground every neutral in the warm-brown family; tint gray toward `#1a1512` or `#f4e8c1`. Pure neutrals look like screenshots, not pages.
- **Do** reserve gold (`#d4a847` / `#f0c970`) for primary affordance and ornament — under 10% of any screen.
- **Do** pair color with icon and label on every semantic state (danger, success, arcane, info, amber). A color-blind user must read the same signal at a glance.
- **Do** use attention halos (`halo-gold`, `halo-arcane`, `halo-danger`) only when the user must act now; selection halos only on selected filter pills. Never decorative.
- **Do** set inscribed elements (titles, labels, chips, buttons) in Cinzel; set reading copy in Fraunces; set numerics in JetBrains Mono with tabular-nums.
- **Do** ease motion with the parchment curve `cubic-bezier(0.22, 1, 0.36, 1)`. Springs for press feedback (`spring.press`), dialog/swipe entrances (`spring.swipe`), state snaps (`spring.snappy`), page drift (`spring.drift`), and value pops (`spring.elastic`, value reveals only).
- **Do** respect `prefers-reduced-motion`: collapse animations to instant; signal lives in color + icon + copy.
- **Do** keep tap targets at minimum 40px, 44px for destructive or hard-to-undo actions.
- **Do** treat the light "aged parchment" mode with the same ornamental and contrast rigor as dark mode. It is not a contrast-flip.

### Don't:
- **Don't** ship the **SaaS-cream cliché**: tinted-neutral cards on tinted-neutral background, blue accent, rounded-2xl everywhere, sans-serif geometric. We are not a B2B tool.
- **Don't** ship the **D&D Beyond neon-on-black** register: flat saturated red on pure `#000`, thin sans body, dashboard chrome fighting the theme.
- **Don't** ship the **Roll20 / "WordPress 2014"** chrome: gradient buttons, table-row layouts, untreated dropdowns, no hierarchy.
- **Don't** ship the **gacha mobile** register: oversized icons, particles on every tap, ranked-up celebrations, fake gold coins, FOMO banners.
- **Don't** ship the **AI-slop default**: tinted-neutral hero card with a big number, gradient-text headings, identical card grids, glassmorphism filling space because nothing else was decided.
- **Don't** use `border-left` or `border-right` greater than 1px as a colored accent on cards, list items, callouts, or alerts. Side-stripe borders are banned.
- **Don't** use `background-clip: text` on body, headings, or button labels. The one exception is the page-header flourish glyph.
- **Don't** apply glassmorphism (`backdrop-filter: blur`) decoratively. The only sanctioned use is the dialog backdrop overlay.
- **Don't** use bouncing or elastic easing on layout, lists, pages, or modals. Elastic lives in exactly two places: the dice roller and the single-element pop of a hero number or result value. No `outBack` for layout transitions.
- **Don't** flash the screen, shake the viewport, or full-bleed-overlay red on damage. Drama lives in typography weight, ink density, and one beat of motion.
- **Don't** stack two named halos on the same screen. If two things need the user's attention at once, the page is the problem.
- **Don't** use `#000` or `#fff` anywhere — for any reason. There is always a tinted neighbor that reads better.
- **Don't** repeat decorative ornament (corner flourishes, ornament rules) inside content lists. Ornament is for frames and headers, not row dividers.
- **Don't** localize visual hierarchy with em dashes in copy. UI copy uses commas, colons, semicolons, periods, parentheses — never em dashes.
