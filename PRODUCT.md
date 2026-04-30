# Product

## Register

product

## Users

D&D 5e players and Dungeon Masters using the Mini App during live tabletop sessions and during between-session prep. The interface lives inside Telegram on a phone held under the table or on a tablet propped on it. Two ambient contexts coexist:

- **Session mode** — dim room, candle/lamp lighting, the user has 3 seconds before the next initiative tick to read HP, roll a save, or update concentration.
- **Prep mode** — normal indoor light, longer attention span, the user is editing the sheet, learning spells, or arranging inventory.

Italian is the primary locale; English is fully supported. Both audiences are familiar with D&D 5e mechanics — the app is not a teaching tool. They expect terminology to be exact (saving throw, AC, hit dice, concentration) without onboarding glossaries.

## Product Purpose

A character-sheet companion that replaces paper, PDF, and tab-flipping during play. The bot, the API, and the Mini App share one source of truth so that any change made on the phone (damage taken, slot consumed, condition applied) is consistent for the rest of the session.

Success looks like: a player at the table never reaches for a paper sheet or a second app, a DM updates the party's HP from one screen, and the session does not slow down because someone is hunting for an inventory item.

## Brand Personality

Four words: **epica, leggibile, calma, tattile** (epic, legible, calm, tactile).

- **Epica** — the visual language is fantasy-committed (illuminated-manuscript noir, gold ink, parchment). The aesthetic is part of the experience, not chrome around a generic CRUD app.
- **Leggibile** — under any light, with the phone held at arm's length, every number that matters at this turn must be readable without zoom. Theme never wins against a missed HP value.
- **Calma** — high-stakes moments (HP at 0, concentration save, death save) read as decisive, never as panic. No flashing, no shouting red, no celebration confetti for damage.
- **Tattile** — interactions feel physical: ink that sets, parchment that lifts, gold that catches light. Subtle weight on press, real motion when something matters. Never gimmick, never decorative-only.

Voice: literate but not flowery. Item names and rule terms stay canonical D&D; UI copy is direct ("Riposo lungo" not "Reset all the things"). No marketing tone, no exclamations, no winks at the user.

## Anti-references

Match-and-refuse list. If the design starts heading toward any of these, restart the visual decision.

- **Generic SaaS dashboard** — Stripe-clone, Linear-clone, Notion-clone. Tinted-neutral cards on tinted-neutral background, blue accent, rounded-2xl everywhere, sans-serif geometric. The product is not a B2B tool.
- **D&D Beyond's neon-on-black** — flat saturated red over pure black, body text in thin sans-serif, dashboard chrome that fights the fantasy theme. We are committed to parchment-noir, not console-gamer.
- **Roll20 / classic VTT chrome** — "WordPress 2014" tabs, gradient buttons, table-row UI, no hierarchy. Looks dated within the same week it ships.
- **Mobile-game gacha UI** — oversized icons, particle effects on every tap, ranked-up celebrations, FOMO banners, fake gold coins. Treats the player like a slot-machine target.
- **AI-slop default** — tinted-neutral hero card with a big number, gradient text headings, generic illustration spots, identical card grids, glassmorphism filling space because nothing else was decided. Could-be-anything-product look.

## Design Principles

1. **Tabletop-first ergonomics.** Every screen must answer the turn-time question in under 3 seconds: where is HP, where do I roll, where is this spell. Tap targets respect a thumb under low light. Information density bends to readability, never the other way.
2. **Themed signal, not themed decoration.** Parchment, gold ink, fantasy serifs are signal: they tell the player they are in their character's world. Anywhere they would slow comprehension (data tables, dice results, concentration banners) the theme defers to plain hierarchy. Theme costs zero milliseconds of cognition.
3. **Multi-channel reinforcement.** State changes are communicated by color + icon + motion together, never by color alone. HP crossing 0 changes hue, swaps icon, and uses motion (no flashing). Required-action prompts read as required even with color filtering, even with reduce-motion enabled (motion downgrades to weight/border/shape, never disappears as the only signal).
4. **Calm under the dice.** The most dramatic moments in D&D (death saves, crit, concentration break) are the ones the UI must handle most quietly. Decisive — yes. Loud — no. Confetti, screen-shake, full-bleed red overlays are banned. Drama lives in typography weight, ink density, and one beat of motion, not in noise.
5. **Tactile over flashy.** Press states have weight. Surfaces lift, ink spreads, gold catches a single specular highlight. Animations follow ease-out parchment curves; nothing bounces, nothing elastic-overshoots. If a motion does not communicate state or affordance, it is cut.

## Accessibility & Inclusion

No formal WCAG target is mandated, but the product is held to working principles:

- **Redundant semantics.** Danger / success / arcane / info / amber states pair color with a dedicated icon and a state label. A color-blind user must be able to read the same signal a sighted user reads.
- **Required actions are visually loud without being color-loud.** A required save, a 0-HP state, or a concentration check is signaled by icon + position + weight + a single restrained motion cue, so the user notices even at a glance from across the table.
- **Reduce-motion respected.** When `prefers-reduced-motion: reduce` is set, animation collapses to instant state changes; the underlying signal (color, icon, copy) carries the meaning alone.
- **Tap targets** at minimum 40px on phone, 44px where the action is destructive or hard to undo.
- **Theme parity.** Light mode (aged parchment) is held to the same contrast and signal-strength bar as dark mode (illuminated noir); neither is a second-class citizen.
- **No keyboard or screen-reader regressions.** Interactive elements use real semantics; custom controls expose state via ARIA. Icons that carry meaning have accessible labels.
