# Character Menu — 3-Screen Refactoring Design

**Date**: 2026-04-28
**Status**: Draft (pending user review)
**Scope**: Webapp character management hub (`/char/:id`)

## Goal

Split the current monolithic `CharacterMain.tsx` page into a 3-screen swipeable carousel:

1. **HeroScreen** — full-viewport character snapshot (HP, AC, XP, stats, spell slots summary, level progression preview)
2. **EquipmentScreen** — MMO-style paper-doll for managing equipped weapons/armor/accessories
3. **MenuScreen** — existing menu sections (Combat / Magic / Skills / Equipment / Character / Tools)

Every actionable element on HeroScreen is tappable and routes to its dedicated subpage (HP bar → `/hp`, AC shield → `/ac`, etc.).

## Non-Goals

- Drag-and-drop equipment management (mobile-first, tap-only)
- Per-class/race/gender silhouette variants (single neutral Vitruvian figure)
- Cross-session persistence of `activeScreen` (in-memory only)
- Animation overhaul or cinematic level-up effects
- Automated test suite (no pytest in repo, manual verification only)

## Architecture

### Routing

`/char/:id` remains the single entry point. No new routes added.

```
CharacterMain (existing wrapper — handles data fetch + Suspense)
└─ CharacterSwiper (new — manages swipe + dot indicator)
   ├─ HeroScreen        (idx 0)
   ├─ EquipmentScreen   (idx 1)
   └─ MenuScreen        (idx 2)
```

### Carousel mechanics

- **Library**: `framer-motion` (already in package.json) — no new deps
- **Drag**: horizontal drag with `dragConstraints={{ left: -2 * w, right: 0 }}`, `dragElastic={0.2}`
- **Snap logic**: on `onDragEnd`, advance idx if `velocity.x < -500` OR `offset.x < -screenWidth * 0.2`; mirror for backward
- **Dot indicator**: 3 dots fixed at bottom (above safe area), active = `--dnd-gold-bright`, inactive = `rgba(212,175,55,0.3)`. Tap dot → animate to that screen
- **Reduced motion**: respect `prefers-reduced-motion`, fall back to instant snap

### State

Zustand `characterStore` extension:

```ts
interface CharacterStore {
  activeCharId: number | null
  activeScreen: 0 | 1 | 2  // NEW
  setActiveCharId: (id) => void  // RESETS activeScreen to 0
  setActiveScreen: (idx: 0 | 1 | 2) => void  // NEW
  locale: string
  setLocale: (locale) => void
}
```

In-memory only. Reset to `0` whenever `activeCharId` changes.

## Screen 1 — HeroScreen

### Layout (compact, fits ~750px viewport without scroll)

```
┌─────────────────────────────────────────┐
│ HERO CARD (~62vh)                       │ Surface variant="tome"
│  ─ Name (gold, large) + Inspiration ✨  │
│  ─ Lv N Class • Race  + AC shield 90px │
│  ─ HPGauge (existing component)         │
│  ─ HeroXPBar (existing component)       │
│  ─ Concentration banner (if active)     │
│  ─ Conditions chips + Passive chips     │
│  ─ ──────── divider ────────────         │
│  ─ 6 Stats grid (anchored bottom)       │
├─────────────────────────────────────────┤
│ SPELL SLOTS SUMMARY (~14vh)             │ Surface variant="tome"
│  Level | 1 2 3 4 5 6 7 8 9              │
│  Slot  | 4 3 3 3 3 1 1 1 1              │
├─────────────────────────────────────────┤
│ PROGRESSION PREVIEW (~24vh)             │ Surface variant="tome"
│  [Class tabs — multi-class only]        │
│  ┌──────────────────────────────────┐   │
│  │ Lv │ PB │ Features              │   │
│  │  6 │ +3 │ Path feature          │   │
│  │► 7◄│ +3 │ ASI         (current) │   │
│  │  8 │ +3 │ Brutal Critical       │   │
│  │  9 │ +4 │ —                     │   │
│  │ 10 │ +4 │ Path feature          │   │
│  └──────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

### Visible window of progression preview

- Current level highlighted (gold border, slight glow)
- Window: `[currentLv-1, currentLv, currentLv+1, currentLv+2, currentLv+3]`
- Edge cases: at Lv 1 → window `[1,2,3,4,5]`; at Lv 18 → window `[17,18,19,20]`; at Lv 20 → window `[16,17,18,19,20]` with current highlighted
- Tap any row → opens `<ProgressionFullTableModal>` (full 1-20 with current highlighted)

### Multiclass behavior

- Single class: `<ProgressionPreview classKey={char.classes[0].class_name}>` direct
- Multi-class: `<ClassTabs>` strip above preview. Default selected = class with most recent level-up (resolved via `char.history` LEVEL_UP entries; fallback = first class alphabetically)
- Class tab tapped → switches preview body, persists selection in component-local state (not Zustand — ephemeral)

### Click targets (every element navigates or opens modal)

| Element | Action |
|---------|--------|
| Name | `/char/:id/identity` |
| AC shield | `/char/:id/ac` |
| HPGauge | `/char/:id/hp` |
| HeroXPBar | `/char/:id/xp` |
| Concentration banner | `/char/:id/spells` |
| Conditions chips | `/char/:id/conditions` |
| Passive chips | existing modal (passive ability detail) |
| Inspiration toggle | toggle inline (existing) |
| Stat cell | `/char/:id/stats` |
| Spell slots row | `/char/:id/slots` |
| Progression row (any) | `<ProgressionFullTableModal>` |
| Class tab | switch displayed class (no nav) |

### New components

- `<SpellSlotsSummary char={char}>` — read-only table styled with `Surface variant="tome"`. Renders 9 columns (levels 1-9), each with total slot count for that level. Hidden if char has no slots at all.
- `<ProgressionPreview classKey={string}>` — 5-row window of `class-progression.json[classKey]`. Highlights current level row.
- `<ProgressionFullTableModal char classKey>` — full 1-20 progression in scrollable modal. Auto-scrolls to current level on open.
- `<ClassTabs char onSelect>` — segmented control for multi-class chars.

## Screen 2 — EquipmentScreen

### Layout (fits ~750px viewport)

```
┌─────────────────────────────────────────┐
│ Header: "Equipment" + total weight wt   │
├─────┬───────────────────────┬───────────┤
│ 4   │                       │ 4 slots   │
│slots│   Vitruvian SVG       │ HEAD      │
│ left│   (anatomical, gold   │   ↓       │
│     │    on dark gradient)  │ NECK      │
│HEAD │   ~280px height       │ CLOAK     │
│ ↓   │                       │ HANDS     │
│NECK │                       │ RING1     │
│CLOAK│                       │ RING2     │
│BODY │                       │ FEET      │
├─────┴───────────────────────┴───────────┤
│  ┌──┐  ┌──┐  ┌──┐                        │
│  │MH│  │OH│  │AM│  Weapon row (3 slots) │
│  └──┘  └──┘  └──┘                        │
├─────────────────────────────────────────┤
│ Computed stats:                         │
│  AC total | Main-hand damage | Encum.   │
└─────────────────────────────────────────┘
```

Reorganized layout to avoid sidebar collision (4 left + 4 right + 3 bottom = 11 slots):

| Left column | Right column |
|-------------|--------------|
| HEAD | HANDS |
| NECK | RING1 |
| CLOAK | RING2 |
| BODY | FEET |

Bottom row: `MAIN_HAND` | `OFF_HAND` | `AMMUNITION`

### Vitruvian silhouette (custom SVG)

- Anatomical proportions: head, neck, broad shoulders, tapered torso, arms slightly out (Vitruvian-pose), legs apart, feet
- Single SVG `<path>` set with cubic Bezier curves. Color: `linearGradient` from `#3a2820` to `#1a1208`, stroked with `--dnd-gold-bright`
- `filter: drop-shadow(0 0 8px rgba(212,175,55,0.4))` for ambient glow
- No external assets required

### Slot UI states

| State | Border | Background | Content |
|-------|--------|------------|---------|
| Empty | 2px gold | `rgba(212,175,55,0.08)` | `lucide-react` placeholder icon (per slot, see mapping below) |
| Equipped | 2px `--dnd-gold-bright` | `rgba(212,175,55,0.18)` | item icon (lucide based on `item_type` + optional `item_metadata.icon`) + truncated name (8px) below |
| Active (last tapped) | gold | + `box-shadow: 0 0 12px var(--dnd-gold-bright)` | + Reveal pulse animation |

**Empty-slot placeholder icons** (lucide-react):

| Slot | Icon |
|------|------|
| HEAD | `Crown` |
| NECK | `Gem` |
| CLOAK | `Shirt` (rotated) |
| BODY | `Shield` (filled body silhouette stand-in) — fallback `ShieldHalf` |
| HANDS | `HandMetal` |
| RING1, RING2 | `Circle` |
| FEET | `Footprints` |
| MAIN_HAND | `Sword` |
| OFF_HAND | `ShieldHalf` (also acceptable for off-hand weapon: tap reveals both) |
| AMMUNITION | `Feather` |

### Slot interactions

- **Tap empty slot** → `<EquipItemPicker slot="head">` modal listing inventory items compatible with that slot
- **Tap occupied slot** → bottom action sheet: `Details` / `Replace` / `Unequip`
  - Details: `<ItemDetailModal>` (existing)
  - Replace: opens picker, on confirm → server swaps atomically
  - Unequip: server sets `is_equipped=false, equipment_slot=null`
- **Confirm equip**: `PATCH /characters/{id}/items/{itemId}` body `{is_equipped: true, equipment_slot: "head"}`. Server-side: if another item already in that slot, atomically unset its equip state in the same transaction.

### Computed stats footer

Three `StatPill`s:
- **AC total**: base armor AC + DEX mod (capped per armor type) + shield bonus + misc
- **Main-hand damage**: dice + STR/DEX mod + magic bonus, with damage type
- **Encumbrance**: total weight of equipped items, warn (`tone="amber"`) if > carry capacity

## Screen 3 — MenuScreen

Direct extract of the existing menu block from `CharacterMain.tsx`. No layout changes.

- Reuses existing `MENU_SECTIONS` constant (Combat, Magic, Skills, Equipment, Character, Tools)
- Each section: 3-column grid of menu items (icon + label + tone color)
- Reveal.Stagger animations preserved
- Surface variant="tome" wrappers preserved

After extraction, `MENU_SECTIONS` and related constants live in `webapp/src/pages/character/MenuScreen.tsx` (or a colocated `MenuScreenSections.ts` if they grow).

## Backend changes

### Schema

**Migration**: add `equipment_slot` column to `items` table.

`core/db/models.py`:
```python
class EquipmentSlot(str, Enum):
    HEAD = "head"
    NECK = "neck"
    CLOAK = "cloak"
    BODY = "body"
    HANDS = "hands"
    RING1 = "ring1"
    RING2 = "ring2"
    FEET = "feet"
    MAIN_HAND = "main_hand"
    OFF_HAND = "off_hand"
    AMMUNITION = "ammunition"

class Item(Base):
    # ... existing fields ...
    equipment_slot: Mapped[Optional[EquipmentSlot]] = mapped_column(
        SAEnum(EquipmentSlot), nullable=True
    )
```

`core/db/engine.py` `_MIGRATIONS`:
```python
("items", "equipment_slot", "ALTER TABLE items ADD COLUMN equipment_slot VARCHAR NULL"),
```

### `item_type` → `equipment_slot` compatibility

| `item_type` | Allowed slots |
|-------------|---------------|
| `weapon` | `MAIN_HAND`, `OFF_HAND` |
| `armor` | `BODY` |
| `shield` | `OFF_HAND` |
| `accessory` | `NECK`, `CLOAK`, `RING1`, `RING2` |
| `gear` | `HEAD`, `HANDS`, `FEET`, `AMMUNITION` |
| (other) | none — not equippable on paper-doll |

Encoded as a constant `EQUIPMENT_SLOT_COMPAT: dict[str, set[EquipmentSlot]]` in `api/services/equipment.py`.

### Pydantic schemas

`api/schemas/items.py`:
- Add `equipment_slot: Optional[EquipmentSlot]` to `ItemUpdate` and `ItemRead`
- Validator: if `equipment_slot` set, must be in `EQUIPMENT_SLOT_COMPAT[item_type]`. Else 422.

### Endpoint behavior

`PATCH /characters/{id}/items/{item_id}`:
- If body includes `equipment_slot` AND `is_equipped=true`:
  1. In same transaction, find existing item with same `(char_id, equipment_slot)` and unset its `is_equipped` and `equipment_slot`
  2. Set new item's `is_equipped=true` and `equipment_slot`
  3. Commit atomically
- If `equipment_slot` set without `is_equipped=true` → 422 (slot only meaningful when equipped)
- If `is_equipped=false` → also clear `equipment_slot` (defensive)

### Existing items migration

After column added, all existing equipped items have `equipment_slot=NULL`. They render in inventory as "equipped (legacy)" — user must re-equip via paper-doll to assign slot. UI shows non-blocking hint banner on first EquipmentScreen visit if any legacy item exists.

## Data flow

### Reads (no API changes for fetching)

- `useCharacter(charId)` (TanStack Query) returns full character including items with their `equipment_slot`
- `useClassProgression()` imports static `webapp/src/data/class-progression.json` (no fetch)
- Spell slots already in `char.spell_slots`

### Writes (mutations invalidate `['character', charId]`)

- Equip: `api.items.update(charId, itemId, { is_equipped: true, equipment_slot })`
- Unequip: `api.items.update(charId, itemId, { is_equipped: false, equipment_slot: null })`
- Replace: same as equip — server handles swap

## Error handling

| Scenario | Behavior |
|----------|----------|
| Equip on occupied slot | Server swaps atomically, no error. Frontend optionally shows "Replaced X" toast. |
| Slot incompatible with item type | Frontend filters picker to compatible items only; server returns 422 if bypassed |
| Item deleted while equipped | Server clears `equipment_slot` on delete; frontend invalidates query |
| Class missing from `class-progression.json` | Show placeholder "Progression data not available for {class}" |
| Multi-class without level-up history | Tab default = first class alphabetically |
| `prefers-reduced-motion` | Carousel snaps without animation |
| Telegram WebApp narrow viewport (<360px) | Hero stats grid wraps to 3×2 instead of 6×1; equipment slot columns reduce icon size |

## Component changes summary

### New components
- `webapp/src/components/character/CharacterSwiper.tsx` — carousel container
- `webapp/src/components/character/SwiperDots.tsx` — dot indicator
- `webapp/src/pages/character/HeroScreen.tsx` — screen 1
- `webapp/src/pages/character/EquipmentScreen.tsx` — screen 2
- `webapp/src/pages/character/MenuScreen.tsx` — screen 3 (extract)
- `webapp/src/components/character/SpellSlotsSummary.tsx`
- `webapp/src/components/character/ProgressionPreview.tsx`
- `webapp/src/components/character/ProgressionFullTableModal.tsx`
- `webapp/src/components/character/ClassTabs.tsx`
- `webapp/src/components/character/PaperDoll.tsx` — Vitruvian SVG + slot grid
- `webapp/src/components/character/EquipmentSlot.tsx` — single slot cell
- `webapp/src/components/character/EquipItemPicker.tsx` — modal
- `webapp/src/components/character/SlotActionSheet.tsx` — bottom sheet for occupied slots

### Modified components
- `webapp/src/pages/CharacterMain.tsx` — slim wrapper around `CharacterSwiper`
- `webapp/src/store/characterStore.ts` — add `activeScreen` state
- `webapp/src/api/client.ts` — extend `items.update` types to include `equipment_slot`

### Backend files modified
- `core/db/models.py` — add `EquipmentSlot` enum + `Item.equipment_slot` column
- `core/db/engine.py` — add migration entry
- `api/schemas/items.py` — add `equipment_slot` field + validator
- `api/services/equipment.py` (new) — compat mapping + swap helper
- `api/routers/items.py` — atomic swap logic in PATCH

## Verification (manual — no test suite)

- Swipe gesture on Telegram WebApp Android + iOS (real devices)
- Tap each HeroScreen element → confirm correct nav
- Equip/unequip across all 11 slots, every `item_type`
- Swap workflow: equip item in occupied slot → previous item's `is_equipped=false`
- Multi-class char: switch tabs, current level highlighted correctly per class
- Single class char: no tabs visible
- Char with no spell slots: spell slots summary hidden
- Char at Lv 1 / Lv 20: progression window edge cases render correctly
- `prefers-reduced-motion` ON: no carousel animation
- Backend migration: deploy on existing DB, confirm `items.equipment_slot` column added, no data loss

## Open questions

None — all decisions captured above.
