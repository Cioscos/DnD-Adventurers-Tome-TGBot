# Character Menu 3-Screens Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `webapp/src/pages/CharacterMain.tsx` from a single-page hub into a 3-screen swipeable carousel: HeroScreen (info + stats + spell slots summary + class progression preview), EquipmentScreen (Vitruvian paper-doll with 11 D&D 5e equipment slots), MenuScreen (existing menu sections extracted verbatim).

**Architecture:** Backend gains an `EquipmentSlot` enum and `items.equipment_slot` column with a PATCH endpoint that atomically swaps slot occupants. Frontend wraps the existing `CharacterMain` data fetch around a new `<CharacterSwiper>` (framer-motion drag) that renders three screens; each screen is a separate component with single responsibility. Existing UI primitives (`Surface`, `HPGauge`, `HeroXPBar`, `StatPill`, `Reveal`) are preserved.

**Tech Stack:** Python 3 + FastAPI + SQLAlchemy async + Pydantic v2 (backend); React 18 + TypeScript + TanStack Query + Zustand + framer-motion + Tailwind + react-i18next (frontend). No test framework; verification is manual via `tsc --noEmit`, `uv run uvicorn` smoke runs, and Telegram WebApp browser checks.

**Spec reference:** `docs/superpowers/specs/2026-04-28-character-menu-3-screens-design.md`

## File Structure

### Backend (created/modified)

| File | Responsibility |
|------|----------------|
| `core/db/models.py` | Add `EquipmentSlot` `str, Enum` + `Item.equipment_slot` `Optional[EquipmentSlot]` column |
| `core/db/engine.py` | Add `equipment_slot` migration entry to `_MIGRATIONS` |
| `api/schemas/item.py` | Add `equipment_slot` field to `ItemRead`/`ItemCreate`/`ItemUpdate` + slot validator |
| `api/services/equipment.py` (new) | `EQUIPMENT_SLOT_COMPAT` mapping + `swap_slot_occupant()` helper |
| `api/routers/items.py` | Wire `equipment_slot` into PATCH; call swap helper when slot is set |

### Frontend (created/modified)

| File | Responsibility |
|------|----------------|
| `webapp/src/types/index.ts` | Add `equipment_slot?: EquipmentSlot` to `Item` + `EquipmentSlot` type literal |
| `webapp/src/store/characterStore.ts` | Add `activeScreen: 0\|1\|2` + `setActiveScreen` (resets on `setActiveCharId`) |
| `webapp/src/lib/equipmentSlots.ts` (new) | Slot constants, lucide icon mapping, `item_type → allowed slots` mapping (mirrors backend) |
| `webapp/src/components/character/CharacterSwiper.tsx` (new) | Carousel container (framer-motion drag, snap, dots) |
| `webapp/src/components/character/SwiperDots.tsx` (new) | 3-dot indicator (tap to navigate) |
| `webapp/src/pages/character/HeroScreen.tsx` (new) | Screen 1 wrapper |
| `webapp/src/pages/character/EquipmentScreen.tsx` (new) | Screen 2 wrapper |
| `webapp/src/pages/character/MenuScreen.tsx` (new) | Screen 3 (extract from CharacterMain) |
| `webapp/src/components/character/SpellSlotsSummary.tsx` (new) | Read-only 9-column slot count table (Surface variant=tome) |
| `webapp/src/components/character/ProgressionPreview.tsx` (new) | 5-row window of class progression with current level highlighted |
| `webapp/src/components/character/ProgressionFullTableModal.tsx` (new) | Full 1-20 progression modal |
| `webapp/src/components/character/ClassTabs.tsx` (new) | Segmented control for multi-class chars |
| `webapp/src/components/character/PaperDoll.tsx` (new) | Vitruvian SVG silhouette + slot grid layout |
| `webapp/src/components/character/EquipmentSlotCell.tsx` (new) | Single slot cell (empty / equipped / active states) |
| `webapp/src/components/character/EquipItemPicker.tsx` (new) | Modal listing inventory items compatible with target slot |
| `webapp/src/components/character/SlotActionSheet.tsx` (new) | Bottom sheet for occupied slot (Details / Replace / Unequip) |
| `webapp/src/components/character/EquipmentStatsFooter.tsx` (new) | AC/damage/encumbrance pills |
| `webapp/src/pages/CharacterMain.tsx` | Slim wrapper: data fetch + Suspense + `<CharacterSwiper>` |

### i18n keys (added)

`webapp/src/locales/it.json` and `en.json` get a `character.equipment.*` namespace with: `equipment`, `slots.head`, `slots.neck`, `slots.cloak`, `slots.body`, `slots.hands`, `slots.ring1`, `slots.ring2`, `slots.feet`, `slots.main_hand`, `slots.off_hand`, `slots.ammunition`, `actions.equip`, `actions.replace`, `actions.unequip`, `actions.details`, `picker.title`, `picker.empty`, `summary.spell_slots`, `progression.title`, `progression.tap_full_table`, `progression.no_data`, `progression.current_level`, `progression.swipe_hint`, `swiper.screen.hero`, `swiper.screen.equipment`, `swiper.screen.menu`.

---

## Phase 1 — Backend

### Task 1: Add `EquipmentSlot` enum + `Item.equipment_slot` column

**Files:**
- Modify: `core/db/models.py:382` (add field after `item_type`) and import `Enum as SAEnum` if not already imported
- Modify: `core/db/engine.py:62` (insert in `_MIGRATIONS` after the existing items entries)

- [ ] **Step 1: Add `EquipmentSlot` Python enum near top of `core/db/models.py`** (after existing imports/enum block; if no enum block exists, add `from enum import Enum`)

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
```

- [ ] **Step 2: Add SQLAlchemy import for `Enum`** at the top of `core/db/models.py` (if not already present)

```python
from sqlalchemy import Enum as SAEnum
```

- [ ] **Step 3: Add `equipment_slot` column to `Item` model** (insert immediately after `is_equipped` line, ~line 386)

```python
    equipment_slot: Mapped[Optional[EquipmentSlot]] = mapped_column(
        SAEnum(EquipmentSlot, native_enum=False, length=20),
        nullable=True,
        default=None,
    )
```

- [ ] **Step 4: Add migration entry to `core/db/engine.py`** — insert in `_MIGRATIONS` list immediately after the `("items", "is_equipped", ...)` entry (~line 62):

```python
    # Equipment slot for paper-doll
    ("items", "equipment_slot", "VARCHAR(20)", None),
```

- [ ] **Step 5: Verify backend imports compile** (ask user to run from Windows shell):

```
uv run python -c "from core.db.models import Item, EquipmentSlot; print(EquipmentSlot.HEAD.value)"
```

Expected output: `head`

- [ ] **Step 6: Verify migration applies on existing DB** (ask user to start API; tail logs for migration line):

```
uv run uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

Expected log line on first startup: `Migrating: ALTER TABLE items ADD COLUMN equipment_slot VARCHAR(20)`. On subsequent startups, no migration log for items.equipment_slot (idempotent).

- [ ] **Step 7: Commit**

```bash
git add core/db/models.py core/db/engine.py
git commit -m "feat(api): add EquipmentSlot enum and items.equipment_slot column"
```

---

### Task 2: Pydantic schemas + compat mapping

**Files:**
- Create: `api/services/equipment.py`
- Modify: `api/schemas/item.py:53-107` (add `equipment_slot` field to all three schemas + a validator)

- [ ] **Step 1: Create `api/services/equipment.py` with the compat mapping**

```python
"""Equipment slot business logic (compat mapping + atomic swap helper)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import EquipmentSlot, Item


# Mapping from item_type to set of allowed equipment slots.
EQUIPMENT_SLOT_COMPAT: dict[str, set[EquipmentSlot]] = {
    "weapon": {EquipmentSlot.MAIN_HAND, EquipmentSlot.OFF_HAND},
    "armor": {EquipmentSlot.BODY},
    "shield": {EquipmentSlot.OFF_HAND},
    "accessory": {EquipmentSlot.NECK, EquipmentSlot.CLOAK,
                  EquipmentSlot.RING1, EquipmentSlot.RING2},
    "gear": {EquipmentSlot.HEAD, EquipmentSlot.HANDS,
             EquipmentSlot.FEET, EquipmentSlot.AMMUNITION},
}


def slot_allowed_for_type(item_type: str, slot: EquipmentSlot) -> bool:
    """Return True if a slot can hold an item of the given type."""
    return slot in EQUIPMENT_SLOT_COMPAT.get(item_type, set())


async def swap_slot_occupant(
    session: AsyncSession,
    char_id: int,
    new_item_id: int,
    target_slot: EquipmentSlot,
) -> Optional[Item]:
    """Unset is_equipped/equipment_slot on any other item in the same slot.

    Returns the displaced item (if any), or None.
    Caller is responsible for committing the session.
    """
    result = await session.execute(
        select(Item).where(
            Item.character_id == char_id,
            Item.equipment_slot == target_slot,
            Item.id != new_item_id,
            Item.is_equipped.is_(True),
        )
    )
    displaced = result.scalar_one_or_none()
    if displaced is not None:
        displaced.is_equipped = False
        displaced.equipment_slot = None
    return displaced
```

- [ ] **Step 2: Update `api/schemas/item.py`** — add `EquipmentSlot` import, add field to `ItemRead`, `ItemCreate`, `ItemUpdate`, and add a validator class method on `ItemCreate` and `ItemUpdate` that rejects incompatible slots.

Add to top of file (after existing imports):

```python
from core.db.models import EquipmentSlot
from api.services.equipment import slot_allowed_for_type
```

In `ItemRead` (after `is_equipped`):

```python
    equipment_slot: Optional[EquipmentSlot] = None
```

In `ItemCreate` (after `is_equipped`):

```python
    equipment_slot: Optional[EquipmentSlot] = None
```

In `ItemUpdate` (after `is_equipped`):

```python
    equipment_slot: Optional[EquipmentSlot] = None
```

Add validator to `ItemCreate` (after the existing `validate_ability_mods` validator):

```python
    @field_validator("equipment_slot", mode="after")
    @classmethod
    def validate_slot(cls, v: Optional[EquipmentSlot], info) -> Optional[EquipmentSlot]:
        if v is None:
            return v
        item_type = info.data.get("item_type", "generic")
        if not slot_allowed_for_type(item_type, v):
            raise ValueError(
                f"equipment_slot {v.value!r} is not allowed for item_type {item_type!r}"
            )
        return v
```

Note: `ItemUpdate` cannot use `info.data` because `item_type` may not be in the partial body. Validation that requires `item_type` is performed in the router after loading the existing item (see Task 3).

- [ ] **Step 3: Verify import + schema parse** (Windows shell):

```
uv run python -c "from api.schemas.item import ItemUpdate; m = ItemUpdate(equipment_slot='head'); print(m.equipment_slot)"
```

Expected output: `EquipmentSlot.HEAD`

- [ ] **Step 4: Commit**

```bash
git add api/services/equipment.py api/schemas/item.py
git commit -m "feat(api): add equipment slot field and compat mapping to item schemas"
```

---

### Task 3: Atomic swap in PATCH endpoint

**Files:**
- Modify: `api/routers/items.py:140-196` (`update_item` function — replace existing armor/shield equip logic with slot-aware logic)

- [ ] **Step 1: Add imports at top of `api/routers/items.py`**

```python
from core.db.models import EquipmentSlot
from api.services.equipment import slot_allowed_for_type, swap_slot_occupant
```

- [ ] **Step 2: Replace the body of `update_item` from line 140 onward** with the version below. The new logic:
  - Validates slot/type compat against the *current* item's `item_type`
  - On equip with slot specified, calls `swap_slot_occupant` for atomic transfer
  - On unequip, clears `equipment_slot` defensively
  - Preserves the existing CON-mod HP recompute and AC update behavior, but the AC update is generalized to also set `shield_armor_class` when the off-hand item has type `weapon` (in which case shield AC stays whatever it was previously — i.e. the prior shield was already swapped out by `swap_slot_occupant`)

Replace the function body (everything between `async def update_item(...) -> Character:` and the closing `return char`) with:

```python
    char = await _get_owned_full(char_id, user_id, session)
    result = await session.execute(
        select(Item).where(Item.id == item_id, Item.character_id == char_id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    # Snapshot CON modifier BEFORE any item changes
    old_con_mod = effective_con_mod(char)

    data = body.model_dump(exclude_unset=True)
    if "item_metadata" in data:
        data["item_metadata"] = json.dumps(data["item_metadata"]) if data["item_metadata"] else None

    # Validate slot/type compatibility using the current (post-update) item_type.
    new_type = data.get("item_type", item.item_type)
    new_slot = data.get("equipment_slot", item.equipment_slot)
    if new_slot is not None and not slot_allowed_for_type(new_type, new_slot):
        raise HTTPException(
            status_code=422,
            detail=f"equipment_slot {new_slot.value!r} not allowed for item_type {new_type!r}",
        )

    # Apply the partial update.
    for field, value in data.items():
        setattr(item, field, value)

    # Equip flow: when is_equipped becomes true and we have a slot,
    # atomically displace any other item in that slot.
    if "is_equipped" in data or "equipment_slot" in data:
        if item.is_equipped and item.equipment_slot is not None:
            await swap_slot_occupant(session, char.id, item.id, item.equipment_slot)
        # Defensive: unequipping clears the slot so it never leaks.
        if not item.is_equipped:
            item.equipment_slot = None

    # Auto-update character AC when equipping/unequipping armor or shields.
    if "is_equipped" in data or "equipment_slot" in data:
        item_meta = json.loads(item.item_metadata) if item.item_metadata else {}
        if item.item_type == "armor":
            char.base_armor_class = item_meta.get("ac_value", 10) if item.is_equipped else 10
        elif item.item_type == "shield":
            char.shield_armor_class = item_meta.get("ac_bonus", 2) if item.is_equipped else 0

    # Auto-recompute HP when CON modifier changes due to equip/unequip
    settings = char.settings or {}
    if settings.get("hp_auto_calc", True):
        new_con_mod = effective_con_mod(char)
        delta = new_con_mod - old_con_mod
        if delta != 0:
            _apply_hp_delta(char, delta * char.total_level)

    char.recalculate_encumbrance()
    return char
```

Note: this **removes** the previous loop that unequipped sibling armor/shield items by `item_type`. That logic is now subsumed by `swap_slot_occupant` operating on `equipment_slot`. Existing items with `is_equipped=True` and `equipment_slot=NULL` (legacy data created before the column existed) will not be auto-displaced — the user must re-equip them via the new EquipmentScreen, which will assign slots.

- [ ] **Step 3: Manual smoke test the endpoint** (ask user to run from Windows; assumes dev API is up at port 8000 with `DEV_USER_ID` set):

```
curl -s -H "X-Telegram-Init-Data: dev:<DEV_USER_ID>" \
  -X PATCH "http://localhost:8000/characters/<charId>/items/<weaponId>" \
  -H "Content-Type: application/json" \
  -d '{"is_equipped": true, "equipment_slot": "main_hand"}' | jq '.items[] | {id, name, is_equipped, equipment_slot}'
```

Expected: target weapon shows `is_equipped: true, equipment_slot: "main_hand"`. Any prior item that was in `main_hand` shows `is_equipped: false, equipment_slot: null`.

Also verify the rejection case:

```
curl -s -H "X-Telegram-Init-Data: dev:<DEV_USER_ID>" \
  -X PATCH "http://localhost:8000/characters/<charId>/items/<armorId>" \
  -H "Content-Type: application/json" \
  -d '{"is_equipped": true, "equipment_slot": "main_hand"}'
```

Expected: HTTP 422 with detail mentioning "not allowed for item_type 'armor'".

- [ ] **Step 4: Commit**

```bash
git add api/routers/items.py
git commit -m "feat(api): atomic slot swap on item PATCH"
```

---

## Phase 2 — Frontend infrastructure

### Task 4: Extend `Item` type and `characterStore` state

**Files:**
- Modify: `webapp/src/types/index.ts:109-118`
- Modify: `webapp/src/store/characterStore.ts`

- [ ] **Step 1: Extend `Item` interface** in `webapp/src/types/index.ts`. Add `EquipmentSlot` literal and the optional field. Insert immediately above `export interface Item`:

```typescript
export type EquipmentSlot =
  | 'head' | 'neck' | 'cloak' | 'body' | 'hands'
  | 'ring1' | 'ring2' | 'feet'
  | 'main_hand' | 'off_hand' | 'ammunition'
```

Modify the `Item` interface to add `equipment_slot?: EquipmentSlot | null` after `is_equipped`:

```typescript
export interface Item {
  id: number
  name: string
  description?: string
  weight: number
  quantity: number
  item_type: string
  item_metadata?: Record<string, unknown>
  is_equipped: boolean
  equipment_slot?: EquipmentSlot | null
}
```

- [ ] **Step 2: Extend `characterStore.ts`** — add `activeScreen`, reset it on `setActiveCharId`, expose `setActiveScreen`. Replace the entire file contents with:

```typescript
/**
 * Zustand store for client-side UI state.
 * Server data (character lists, full character) is managed by TanStack Query.
 */

import { create } from 'zustand'
import { getLanguageCode } from '@/auth/telegram'

export type CharacterScreen = 0 | 1 | 2

interface CharacterStore {
  /** Currently selected character id (from URL, set by the router) */
  activeCharId: number | null
  setActiveCharId: (id: number | null) => void

  /** Active screen index in the 3-screen swiper (0=Hero, 1=Equipment, 2=Menu) */
  activeScreen: CharacterScreen
  setActiveScreen: (idx: CharacterScreen) => void

  /** UI language (detected from Telegram user profile) */
  locale: string
  setLocale: (locale: string) => void
}

export const useCharacterStore = create<CharacterStore>((set, get) => ({
  activeCharId: null,
  setActiveCharId: (id) => {
    if (get().activeCharId !== id) {
      set({ activeCharId: id, activeScreen: 0 })
    } else {
      set({ activeCharId: id })
    }
  },

  activeScreen: 0,
  setActiveScreen: (idx) => set({ activeScreen: idx }),

  locale: getLanguageCode().startsWith('it') ? 'it' : 'en',
  setLocale: (locale) => set({ locale }),
}))
```

- [ ] **Step 3: Run TypeScript type check** (the user can run this from Windows or WSL — `tsc` doesn't touch `.venv`):

```
cd webapp && npx tsc --noEmit
```

Expected: no errors. Existing references to `useCharacterStore` keep working because we only added properties.

- [ ] **Step 4: Commit**

```bash
git add webapp/src/types/index.ts webapp/src/store/characterStore.ts
git commit -m "feat(webapp): add EquipmentSlot type and activeScreen store state"
```

---

### Task 5: Equipment slot library helpers

**Files:**
- Create: `webapp/src/lib/equipmentSlots.ts`

- [ ] **Step 1: Create the helper file**

```typescript
/**
 * Equipment slot constants and helpers for the paper-doll UI.
 * Mirrors backend `api/services/equipment.py` and must stay in sync.
 */
import type { ComponentType, SVGAttributes } from 'react'
import {
  Crown, Gem, Shirt, Shield, HandMetal, Circle, Footprints,
  Sword, ShieldHalf, Feather,
} from 'lucide-react'
import type { EquipmentSlot } from '@/types'

type IconCmp = ComponentType<SVGAttributes<SVGElement> & { size?: number | string }>

export const ALL_SLOTS: EquipmentSlot[] = [
  'head', 'neck', 'cloak', 'body',
  'hands', 'ring1', 'ring2', 'feet',
  'main_hand', 'off_hand', 'ammunition',
]

/** Lucide icon shown in an empty slot to suggest what it accepts. */
export const SLOT_PLACEHOLDER_ICON: Record<EquipmentSlot, IconCmp> = {
  head: Crown,
  neck: Gem,
  cloak: Shirt,
  body: Shield,
  hands: HandMetal,
  ring1: Circle,
  ring2: Circle,
  feet: Footprints,
  main_hand: Sword,
  off_hand: ShieldHalf,
  ammunition: Feather,
}

/** Allowed slots per item_type. Mirrors EQUIPMENT_SLOT_COMPAT in the backend. */
export const ITEM_TYPE_TO_SLOTS: Record<string, EquipmentSlot[]> = {
  weapon: ['main_hand', 'off_hand'],
  armor: ['body'],
  shield: ['off_hand'],
  accessory: ['neck', 'cloak', 'ring1', 'ring2'],
  gear: ['head', 'hands', 'feet', 'ammunition'],
}

export function slotsAllowedFor(itemType: string): EquipmentSlot[] {
  return ITEM_TYPE_TO_SLOTS[itemType] ?? []
}

export function isSlotAllowed(itemType: string, slot: EquipmentSlot): boolean {
  return slotsAllowedFor(itemType).includes(slot)
}
```

- [ ] **Step 2: Run TypeScript type check**

```
cd webapp && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add webapp/src/lib/equipmentSlots.ts
git commit -m "feat(webapp): add equipment slot constants and icon mapping"
```

---

### Task 6: `CharacterSwiper` + `SwiperDots`

**Files:**
- Create: `webapp/src/components/character/SwiperDots.tsx`
- Create: `webapp/src/components/character/CharacterSwiper.tsx`

- [ ] **Step 1: Create `SwiperDots.tsx`**

```tsx
import { m } from 'framer-motion'
import type { CharacterScreen } from '@/store/characterStore'

interface Props {
  active: CharacterScreen
  onSelect: (idx: CharacterScreen) => void
  labels: [string, string, string]
}

export default function SwiperDots({ active, onSelect, labels }: Props) {
  return (
    <div
      role="tablist"
      aria-label="Character screens"
      className="absolute bottom-2 left-0 right-0 z-30 flex justify-center gap-2 pointer-events-auto"
    >
      {[0, 1, 2].map((idx) => {
        const isActive = idx === active
        return (
          <m.button
            key={idx}
            type="button"
            role="tab"
            aria-selected={isActive}
            aria-label={labels[idx]}
            onClick={() => onSelect(idx as CharacterScreen)}
            className="rounded-full border border-dnd-gold-dim/40"
            style={{
              width: isActive ? 24 : 8,
              height: 8,
              background: isActive
                ? 'var(--dnd-gold-bright, #d4af37)'
                : 'rgba(212,175,55,0.3)',
            }}
            transition={{ duration: 0.2 }}
            whileTap={{ scale: 0.9 }}
          />
        )
      })}
    </div>
  )
}
```

- [ ] **Step 2: Create `CharacterSwiper.tsx`**

```tsx
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { m, useMotionValue, animate, useReducedMotion } from 'framer-motion'
import { useTranslation } from 'react-i18next'
import { useCharacterStore, type CharacterScreen } from '@/store/characterStore'
import SwiperDots from './SwiperDots'

interface Props {
  hero: ReactNode
  equipment: ReactNode
  menu: ReactNode
}

const VELOCITY_THRESHOLD = 500
const OFFSET_RATIO = 0.2

export default function CharacterSwiper({ hero, equipment, menu }: Props) {
  const { t } = useTranslation()
  const activeScreen = useCharacterStore((s) => s.activeScreen)
  const setActiveScreen = useCharacterStore((s) => s.setActiveScreen)
  const reduced = useReducedMotion()

  const containerRef = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(0)
  const x = useMotionValue(0)

  // Track viewport width
  useEffect(() => {
    if (!containerRef.current) return
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width ?? 0
      setWidth(w)
    })
    ro.observe(containerRef.current)
    return () => ro.disconnect()
  }, [])

  // Sync x to active screen whenever activeScreen or width changes.
  useEffect(() => {
    if (width === 0) return
    const target = -activeScreen * width
    if (reduced) {
      x.set(target)
    } else {
      animate(x, target, { type: 'spring', stiffness: 320, damping: 32 })
    }
  }, [activeScreen, width, x, reduced])

  const handleDragEnd = (
    _e: unknown,
    info: { offset: { x: number }; velocity: { x: number } },
  ) => {
    const offset = info.offset.x
    const velocity = info.velocity.x
    let next: CharacterScreen = activeScreen
    if (velocity < -VELOCITY_THRESHOLD || offset < -width * OFFSET_RATIO) {
      next = Math.min(2, activeScreen + 1) as CharacterScreen
    } else if (velocity > VELOCITY_THRESHOLD || offset > width * OFFSET_RATIO) {
      next = Math.max(0, activeScreen - 1) as CharacterScreen
    }
    setActiveScreen(next)
  }

  const labels: [string, string, string] = [
    t('character.swiper.screen.hero', { defaultValue: 'Character' }),
    t('character.swiper.screen.equipment', { defaultValue: 'Equipment' }),
    t('character.swiper.screen.menu', { defaultValue: 'Menu' }),
  ]

  return (
    <div ref={containerRef} className="relative flex-1 overflow-hidden touch-pan-y">
      <m.div
        className="flex h-full"
        style={{ x, width: width * 3 }}
        drag="x"
        dragConstraints={{ left: -2 * width, right: 0 }}
        dragElastic={0.2}
        dragMomentum={false}
        onDragEnd={handleDragEnd}
      >
        <div style={{ width }} className="h-full overflow-y-auto">{hero}</div>
        <div style={{ width }} className="h-full overflow-y-auto">{equipment}</div>
        <div style={{ width }} className="h-full overflow-y-auto">{menu}</div>
      </m.div>
      <SwiperDots active={activeScreen} onSelect={setActiveScreen} labels={labels} />
    </div>
  )
}
```

- [ ] **Step 3: Run type check**

```
cd webapp && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add webapp/src/components/character/CharacterSwiper.tsx webapp/src/components/character/SwiperDots.tsx
git commit -m "feat(webapp): add CharacterSwiper carousel and SwiperDots indicator"
```

---

## Phase 3 — Frontend screens

### Task 7: Extract `MenuScreen` from `CharacterMain`

**Files:**
- Create: `webapp/src/pages/character/MenuScreen.tsx`

- [ ] **Step 1: Create `MenuScreen.tsx`** — paste the menu rendering block plus its supporting constants extracted from `CharacterMain.tsx`. Verbatim move; no logic changes.

```tsx
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import {
  BarChart3, User, CircleDot,
} from 'lucide-react'
import {
  GiHeartPlus, GiCheckedShield, GiShieldEchoes, GiSparkles, GiCutDiamond,
  GiArcheryTarget, GiLightningTrio, GiCrossedSwords, GiTwoCoins,
  GiScrollUnfurled, GiPolarStar, GiPerspectiveDiceSixFacesRandom,
  GiQuillInk, GiTreasureMap, GiOpenBook, GiPotionBall,
} from 'react-icons/gi'
import type { ComponentType, SVGAttributes } from 'react'
import SectionDivider from '@/components/ui/SectionDivider'
import Reveal from '@/components/ui/Reveal'
import { haptic } from '@/auth/telegram'
import { spring, stagger } from '@/styles/motion'

type IconCmp = ComponentType<SVGAttributes<SVGElement> & { size?: number | string }>

type MenuItem = {
  key: string
  icon: IconCmp
  path: string
  tone?: 'gold' | 'crimson' | 'arcane' | 'cobalt' | 'emerald' | 'amber'
}

type MenuSection = {
  labelKey: string
  icon: IconCmp
  items: MenuItem[]
}

const MENU_SECTIONS: MenuSection[] = [
  {
    labelKey: 'character.menu.sections.combat',
    icon: GiCrossedSwords,
    items: [
      { key: 'hp',    icon: GiHeartPlus,     path: 'hp',    tone: 'crimson' },
      { key: 'ac',    icon: GiCheckedShield, path: 'ac',    tone: 'gold' },
      { key: 'saves', icon: GiShieldEchoes,  path: 'saves', tone: 'cobalt' },
    ],
  },
  {
    labelKey: 'character.menu.sections.magic',
    icon: GiSparkles,
    items: [
      { key: 'spells', icon: GiSparkles,  path: 'spells', tone: 'arcane' },
      { key: 'slots',  icon: GiCutDiamond, path: 'slots',  tone: 'arcane' },
    ],
  },
  {
    labelKey: 'character.menu.sections.skills',
    icon: GiArcheryTarget,
    items: [
      { key: 'stats',     icon: BarChart3,        path: 'stats',     tone: 'gold' },
      { key: 'skills',    icon: GiArcheryTarget,  path: 'skills',    tone: 'cobalt' },
      { key: 'abilities', icon: GiLightningTrio,  path: 'abilities', tone: 'amber' },
    ],
  },
  {
    labelKey: 'character.menu.sections.equipment',
    icon: GiTwoCoins,
    items: [
      { key: 'inventory', icon: GiCrossedSwords, path: 'inventory', tone: 'gold' },
      { key: 'currency',  icon: GiTwoCoins,      path: 'currency',  tone: 'amber' },
    ],
  },
  {
    labelKey: 'character.menu.sections.character',
    icon: User,
    items: [
      { key: 'identity',   icon: User,            path: 'identity',   tone: 'gold' },
      { key: 'class',      icon: GiScrollUnfurled, path: 'class',     tone: 'gold' },
      { key: 'xp',         icon: GiPolarStar,     path: 'xp',         tone: 'amber' },
      { key: 'conditions', icon: CircleDot,       path: 'conditions', tone: 'crimson' },
    ],
  },
  {
    labelKey: 'character.menu.sections.tools',
    icon: GiPotionBall,
    items: [
      { key: 'dice',    icon: GiPerspectiveDiceSixFacesRandom, path: 'dice',    tone: 'gold' },
      { key: 'notes',   icon: GiQuillInk,                      path: 'notes',   tone: 'emerald' },
      { key: 'maps',    icon: GiTreasureMap,                   path: 'maps',    tone: 'cobalt' },
      { key: 'history', icon: GiOpenBook,                      path: 'history', tone: 'amber' },
    ],
  },
]

function toneIconClass(tone?: MenuItem['tone']): string {
  switch (tone) {
    case 'crimson': return 'text-[var(--dnd-crimson-bright)]'
    case 'arcane': return 'text-dnd-arcane-bright'
    case 'cobalt': return 'text-[var(--dnd-cobalt-bright)]'
    case 'emerald': return 'text-[var(--dnd-emerald-bright)]'
    case 'amber': return 'text-[var(--dnd-amber)]'
    case 'gold':
    default: return 'text-dnd-gold-bright'
  }
}

interface Props {
  charId: number
}

export default function MenuScreen({ charId }: Props) {
  const navigate = useNavigate()
  const { t } = useTranslation()

  return (
    <div className="p-4 space-y-4 pb-safe">
      {MENU_SECTIONS.map((section, sIdx) => {
        const SectionIcon = section.icon
        return (
          <m.div
            key={section.labelKey}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...spring.drift, delay: 0.05 + sIdx * 0.06 }}
          >
            <SectionDivider icon={<SectionIcon size={11} />} align="center">
              {t(section.labelKey)}
            </SectionDivider>
            <Reveal.Stagger stagger={stagger.listTight} delay={0} className="grid grid-cols-3 gap-2">
              {section.items.map((item) => {
                const Icon = item.icon
                return (
                  <Reveal.Item key={item.key}>
                    <m.button
                      onClick={() => {
                        haptic.light()
                        navigate(`/char/${charId}/${item.path}`)
                      }}
                      className="w-full flex flex-col items-center gap-1.5 px-2 py-3 rounded-2xl
                                 bg-dnd-surface border border-dnd-border
                                 hover:border-dnd-gold/60 hover:shadow-halo-gold
                                 transition-[box-shadow,border-color] duration-200"
                      whileTap={{ scale: 0.93 }}
                    >
                      <Icon size={22} strokeWidth={2} className={toneIconClass(item.tone)} />
                      <span className="text-[11px] text-dnd-text-muted font-body text-center leading-tight">
                        {t(`character.menu.${item.key}`)}
                      </span>
                    </m.button>
                  </Reveal.Item>
                )
              })}
            </Reveal.Stagger>
          </m.div>
        )
      })}
    </div>
  )
}
```

- [ ] **Step 2: Run type check**

```
cd webapp && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add webapp/src/pages/character/MenuScreen.tsx
git commit -m "feat(webapp): extract MenuScreen from CharacterMain"
```

---

### Task 8: `SpellSlotsSummary` component

**Files:**
- Create: `webapp/src/components/character/SpellSlotsSummary.tsx`

- [ ] **Step 1: Create `SpellSlotsSummary.tsx`** — read-only 9-column table styled with `Surface variant="tome"`, navigates to `/char/:id/slots` on tap. Hidden if no slots exist.

```tsx
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import Surface from '@/components/ui/Surface'
import { haptic } from '@/auth/telegram'
import type { SpellSlot } from '@/types'

interface Props {
  slots: SpellSlot[]
}

export default function SpellSlotsSummary({ slots }: Props) {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { t } = useTranslation()

  if (!slots || slots.length === 0) return null

  // Build a fixed 9-column display (level 1..9)
  const byLevel = new Map<number, number>(slots.map((s) => [s.level, s.total]))
  const cells = [1, 2, 3, 4, 5, 6, 7, 8, 9].map((lv) => ({
    level: lv,
    total: byLevel.get(lv) ?? 0,
  }))

  // Hide entirely if every level has zero slots.
  if (cells.every((c) => c.total === 0)) return null

  return (
    <Surface variant="tome" className="!p-2.5">
      <m.button
        type="button"
        onClick={() => {
          haptic.light()
          navigate(`/char/${id}/slots`)
        }}
        whileTap={{ scale: 0.99 }}
        className="w-full text-left"
        aria-label={t('character.equipment.summary.spell_slots', { defaultValue: 'Spell slots' })}
      >
        <div className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim mb-1">
          {t('character.equipment.summary.spell_slots', { defaultValue: 'Spell slots' })}
        </div>
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
      </m.button>
    </Surface>
  )
}
```

- [ ] **Step 2: Type check**

```
cd webapp && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add webapp/src/components/character/SpellSlotsSummary.tsx
git commit -m "feat(webapp): add SpellSlotsSummary read-only summary"
```

---

### Task 9: `ProgressionPreview` + `ProgressionFullTableModal` + `ClassTabs`

**Files:**
- Create: `webapp/src/components/character/ClassTabs.tsx`
- Create: `webapp/src/components/character/ProgressionPreview.tsx`
- Create: `webapp/src/components/character/ProgressionFullTableModal.tsx`

- [ ] **Step 1: Create `ClassTabs.tsx`** — segmented control over multi-class char's classes.

```tsx
import { m } from 'framer-motion'

interface ClassEntry {
  class_name: string
  level: number
}

interface Props {
  classes: ClassEntry[]
  selected: string
  onSelect: (className: string) => void
}

export default function ClassTabs({ classes, selected, onSelect }: Props) {
  if (classes.length <= 1) return null
  return (
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
            {c.class_name}
            <span className="ml-1 opacity-70">L{c.level}</span>
          </m.button>
        )
      })}
    </div>
  )
}
```

- [ ] **Step 2: Create `ProgressionPreview.tsx`** — 5-row window. Imports static `class-progression.json` and selects rows around current level. Tap any row → opens full-table modal.

```tsx
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import Surface from '@/components/ui/Surface'
import progressionData from '@/data/class-progression.json'
import ProgressionFullTableModal from './ProgressionFullTableModal'

interface ProgressionRow {
  features: string
  proficiency_bonus: number
  spell_slots: Record<string, number> | null
}

const PROGRESSION = progressionData as Record<string, ProgressionRow[]>

interface Props {
  className: string
  currentLevel: number
}

function computeWindow(currentLevel: number, max: number): number[] {
  // 5-row window: try [current-1 .. current+3], clamp to [1..20]
  const start = Math.max(1, Math.min(currentLevel - 1, max - 4))
  return [0, 1, 2, 3, 4].map((i) => start + i).filter((lv) => lv <= max)
}

export default function ProgressionPreview({ className, currentLevel }: Props) {
  const { t } = useTranslation()
  const [showFull, setShowFull] = useState(false)

  const rows = PROGRESSION[className]
  const windowLevels = useMemo(
    () => computeWindow(currentLevel, rows?.length ?? 20),
    [currentLevel, rows?.length],
  )

  if (!rows) {
    return (
      <Surface variant="tome" className="!p-3">
        <p className="text-xs text-dnd-text-faint italic">
          {t('character.equipment.progression.no_data', {
            className,
            defaultValue: `Progression data not available for ${className}`,
          })}
        </p>
      </Surface>
    )
  }

  return (
    <>
      <Surface variant="tome" className="!p-2.5">
        <div className="flex items-center justify-between mb-1.5">
          <div className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim">
            {t('character.equipment.progression.title', { defaultValue: 'Progression' })}
          </div>
          <div className="text-[9px] text-dnd-text-faint italic">
            {t('character.equipment.progression.tap_full_table', {
              defaultValue: 'Tap row for full table',
            })}
          </div>
        </div>
        <div className="space-y-0.5">
          {windowLevels.map((lv) => {
            const row = rows[lv - 1]
            const isCurrent = lv === currentLevel
            return (
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
            )
          })}
        </div>
      </Surface>
      {showFull && (
        <ProgressionFullTableModal
          className={className}
          currentLevel={currentLevel}
          onClose={() => setShowFull(false)}
        />
      )}
    </>
  )
}
```

- [ ] **Step 3: Create `ProgressionFullTableModal.tsx`** — sheet that scrolls to current level on open.

```tsx
import { useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { m, AnimatePresence } from 'framer-motion'
import { X } from 'lucide-react'
import progressionData from '@/data/class-progression.json'

interface ProgressionRow {
  features: string
  proficiency_bonus: number
  spell_slots: Record<string, number> | null
}

const PROGRESSION = progressionData as Record<string, ProgressionRow[]>

interface Props {
  className: string
  currentLevel: number
  onClose: () => void
}

export default function ProgressionFullTableModal({ className, currentLevel, onClose }: Props) {
  const { t } = useTranslation()
  const currentRowRef = useRef<HTMLTableRowElement>(null)
  const rows = PROGRESSION[className] ?? []

  useEffect(() => {
    currentRowRef.current?.scrollIntoView({ behavior: 'auto', block: 'center' })
  }, [])

  return (
    <AnimatePresence>
      <m.div
        className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/70 backdrop-blur-sm"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      >
        <m.div
          className="w-full max-w-md max-h-[85vh] overflow-y-auto bg-dnd-surface-raised border border-dnd-gold rounded-t-2xl sm:rounded-2xl"
          initial={{ y: 40, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 40, opacity: 0 }}
          onClick={(e) => e.stopPropagation()}
        >
          <header className="sticky top-0 z-10 flex items-center justify-between px-4 py-3 bg-dnd-surface-raised border-b border-dnd-gold-dim/40">
            <h2 className="text-sm font-cinzel uppercase tracking-widest text-dnd-gold-bright">
              {className} — {t('character.equipment.progression.title', { defaultValue: 'Progression' })}
            </h2>
            <button
              type="button"
              onClick={onClose}
              aria-label={t('common.close', { defaultValue: 'Close' })}
              className="w-8 h-8 flex items-center justify-center rounded-full border border-dnd-gold-dim/40"
            >
              <X size={16} className="text-dnd-gold" />
            </button>
          </header>
          <table className="w-full text-left text-[12px]">
            <thead className="text-[10px] uppercase tracking-wider text-dnd-gold-dim sticky top-12 bg-dnd-surface-raised">
              <tr>
                <th className="px-3 py-2 w-12">Lv</th>
                <th className="px-2 py-2 w-12">PB</th>
                <th className="px-3 py-2">Features</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => {
                const lv = i + 1
                const isCurrent = lv === currentLevel
                return (
                  <tr
                    key={lv}
                    ref={isCurrent ? currentRowRef : undefined}
                    className={
                      isCurrent
                        ? 'bg-dnd-gold/15 text-dnd-gold-bright'
                        : 'text-dnd-text-muted border-t border-dnd-gold-dim/10'
                    }
                  >
                    <td className="px-3 py-2 font-mono font-bold">L{lv}</td>
                    <td className="px-2 py-2 font-mono">+{r.proficiency_bonus}</td>
                    <td className="px-3 py-2">{r.features}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </m.div>
      </m.div>
    </AnimatePresence>
  )
}
```

- [ ] **Step 4: Type check**

```
cd webapp && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add webapp/src/components/character/ClassTabs.tsx \
        webapp/src/components/character/ProgressionPreview.tsx \
        webapp/src/components/character/ProgressionFullTableModal.tsx
git commit -m "feat(webapp): add progression preview, class tabs, full table modal"
```

---

### Task 10: `HeroScreen` skeleton (extract from CharacterMain)

**Files:**
- Create: `webapp/src/pages/character/HeroScreen.tsx`

This task moves the existing hero card + ability scores grid into its own component, drops the menu sections, and adds the new SpellSlotsSummary + ProgressionPreview blocks below. Multi-class detection picks the class with the most recent LEVEL_UP entry from `char.history`, falling back to alphabetic order.

- [ ] **Step 1: Create `HeroScreen.tsx`**

```tsx
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { CircleDot } from 'lucide-react'
import {
  GiHeartPlus, GiSparkles, GiLightningTrio, GiPotionBall, GiBootPrints,
} from 'react-icons/gi'
import { api } from '@/api/client'
import HPGauge from '@/components/ui/HPGauge'
import HeroXPBar from '@/components/ui/HeroXPBar'
import Surface from '@/components/ui/Surface'
import StatPill from '@/components/ui/StatPill'
import { ShieldEmblem } from '@/components/ui/Ornament'
import { haptic } from '@/auth/telegram'
import { spring } from '@/styles/motion'
import { formatCondition, CONDITION_ICONS } from '@/lib/conditions'
import ConditionDetailModal from '@/pages/conditions/ConditionDetailModal'
import PassiveAbilityDetailModal from '@/pages/abilities/PassiveAbilityDetailModal'
import SpellSlotsSummary from '@/components/character/SpellSlotsSummary'
import ProgressionPreview from '@/components/character/ProgressionPreview'
import ClassTabs from '@/components/character/ClassTabs'
import type { Ability, CharacterFull } from '@/types'

const ABILITY_COLORS: Record<string, string> = {
  strength: 'from-[var(--dnd-crimson-deep)]/30 to-transparent border-dnd-crimson/30 text-[var(--dnd-crimson-bright)]',
  dexterity: 'from-[var(--dnd-emerald-deep)]/30 to-transparent border-dnd-emerald/30 text-[var(--dnd-emerald-bright)]',
  constitution: 'from-[var(--dnd-amber)]/30 to-transparent border-dnd-amber/30 text-[var(--dnd-amber)]',
  intelligence: 'from-[var(--dnd-cobalt-deep)]/30 to-transparent border-dnd-cobalt/30 text-[var(--dnd-cobalt-bright)]',
  wisdom: 'from-[var(--dnd-arcane-deep)]/30 to-transparent border-dnd-arcane/30 text-[var(--dnd-arcane-bright)]',
  charisma: 'from-[var(--dnd-gold-deep)]/40 to-transparent border-dnd-gold/30 text-dnd-gold-bright',
}

interface Props {
  char: CharacterFull
}

function pickDefaultClass(char: CharacterFull): string {
  const classes = char.classes ?? []
  if (classes.length === 0) return ''
  if (classes.length === 1) return classes[0].class_name
  // Choose class with the most recent LEVEL_UP history entry; fallback alphabetic.
  const history = (char.history ?? []).filter((h) => h.kind === 'LEVEL_UP')
  const latest = [...history].sort((a, b) => b.created_at.localeCompare(a.created_at))[0]
  if (latest) {
    const meta = latest.meta as { class_name?: string } | undefined
    const fromMeta = meta?.class_name
    if (fromMeta && classes.some((c) => c.class_name === fromMeta)) return fromMeta
  }
  return [...classes].sort((a, b) => a.class_name.localeCompare(b.class_name))[0].class_name
}

export default function HeroScreen({ char }: Props) {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const qc = useQueryClient()

  const [detailCondKey, setDetailCondKey] = useState<string | null>(null)
  const [detailAbility, setDetailAbility] = useState<Ability | null>(null)
  const [selectedClass, setSelectedClass] = useState<string>(() => pickDefaultClass(char))

  const inspirationMutation = useMutation({
    mutationFn: (value: boolean) => api.characters.updateInspiration(char.id, value),
    onSuccess: (updated) => {
      qc.setQueryData(['character', char.id], updated)
      haptic.light()
    },
  })

  const hpPct = char.hit_points > 0
    ? Math.round((char.current_hit_points / char.hit_points) * 100)
    : 0

  const passiveAbilities = char.abilities?.filter((a) => a.is_passive) ?? []
  const activeConditions = char.conditions
    ? Object.entries(char.conditions).filter(([, v]) => v)
    : []

  const currentClassEntry = char.classes?.find((c) => c.class_name === selectedClass)
  const currentClassLevel = currentClassEntry?.level ?? 1

  // Show inspiration toggle only if not present in header — defer to parent.
  // Hero card content unchanged from CharacterMain pre-refactor.
  const inspirationToggle = useMemo(() => (
    <m.button
      onClick={() => inspirationMutation.mutate(!char.heroic_inspiration)}
      title={char.heroic_inspiration
        ? t('character.inspiration.tap_to_spend')
        : t('character.inspiration.tap_to_grant')}
      className={`absolute top-2 right-2 w-9 h-9 flex items-center justify-center rounded-full transition-all
        ${char.heroic_inspiration
          ? 'bg-dnd-gold/15 border border-dnd-gold animate-shimmer'
          : 'bg-transparent border border-dashed border-dnd-gold-dim/40 opacity-50'}`}
      whileTap={{ scale: 0.9 }}
      aria-label="Heroic Inspiration"
    >
      <GiSparkles size={18} className="text-dnd-gold" />
    </m.button>
  ), [char.heroic_inspiration, inspirationMutation, t])

  return (
    <div className="p-4 space-y-3 pb-safe">
      {/* Hero card */}
      <Surface
        variant="tome"
        ornamented
        layoutId={`char-hero-${char.id}`}
        className="relative overflow-hidden"
      >
        {inspirationToggle}
        <m.button
          type="button"
          onClick={() => { haptic.light(); navigate(`/char/${char.id}/identity`) }}
          whileTap={{ scale: 0.99 }}
          className="block w-full text-left pr-12"
          aria-label={t('character.identity.title', { defaultValue: 'Identity' })}
        >
          <p className="text-sm text-dnd-text-muted font-body italic mb-0.5">{char.class_summary}</p>
          {char.race && (
            <p className="text-xs text-dnd-text-faint font-body">{char.race}</p>
          )}
        </m.button>

        <div className="mt-4 flex items-center gap-3">
          <div className="flex-1 min-w-0">
            <m.button
              type="button"
              onClick={() => { haptic.light(); navigate(`/char/${char.id}/hp`) }}
              whileTap={{ scale: 0.99 }}
              className="w-full text-left"
              aria-label={t('character.hp.title', { defaultValue: 'Hit Points' })}
            >
              <div className="flex items-center justify-between text-sm mb-1.5">
                <span className="inline-flex items-center gap-1.5 font-mono">
                  <GiHeartPlus size={14} className="text-[var(--dnd-crimson-bright)]" />
                  <span className="text-dnd-text font-bold">
                    {char.current_hit_points}/{char.hit_points}
                  </span>
                  {char.temp_hp > 0 && (
                    <span className="text-[var(--dnd-cobalt-bright)]">(+{char.temp_hp} temp)</span>
                  )}
                </span>
                <span className="text-dnd-text-faint font-mono text-xs">{hpPct}%</span>
              </div>
              <HPGauge
                current={char.current_hit_points}
                max={char.hit_points}
                temp={char.temp_hp}
                size="md"
                segmented
              />
            </m.button>

            <HeroXPBar
              currentXP={char.experience_points}
              totalClassLevel={char.total_level}
              onLevelUpReady={() => navigate(`/char/${char.id}/xp`)}
            />
          </div>

          <m.button
            type="button"
            onClick={() => { haptic.light(); navigate(`/char/${char.id}/ac`) }}
            whileTap={{ scale: 0.95 }}
            className="shrink-0 relative opacity-90"
            aria-label={t('character.ac.title', { defaultValue: 'Armor Class' })}
          >
            <ShieldEmblem size={90} />
            <span className="absolute inset-0 flex flex-col items-center justify-center pb-1">
              <span className="text-2xl font-display font-black text-dnd-gold-bright leading-none"
                    style={{ textShadow: '0 1px 3px rgba(0,0,0,0.6)' }}>
                {char.ac}
              </span>
              <span className="text-[9px] font-cinzel uppercase tracking-widest text-dnd-gold-dim leading-none mt-0.5">
                {t('character.ac.short', { defaultValue: 'CA' })}
              </span>
            </span>
          </m.button>
        </div>

        {char.concentrating_spell_id && (() => {
          const spell = char.spells?.find((s) => s.id === char.concentrating_spell_id)
          return (
            <m.button
              onClick={() => navigate(`/char/${char.id}/spells`)}
              className="mt-3 w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl
                         bg-gradient-arcane-mist border border-dnd-arcane/50 text-dnd-arcane-bright
                         text-xs font-cinzel uppercase tracking-wider"
              whileTap={{ scale: 0.98 }}
            >
              <GiPotionBall size={14} />
              {spell?.name ?? t('character.spells.concentration')}
            </m.button>
          )
        })()}

        {passiveAbilities.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-3 overflow-x-auto scrollbar-hide max-h-14">
            {passiveAbilities.map((a) => (
              <StatPill
                key={a.id}
                icon={<GiLightningTrio size={10} />}
                value={a.name}
                tone="gold"
                size="sm"
                onClick={() => setDetailAbility(a)}
              />
            ))}
          </div>
        )}

        {activeConditions.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-2 overflow-x-auto scrollbar-hide max-h-14 pr-16">
            {activeConditions.map(([key, val]) => {
              const Icon = CONDITION_ICONS[key] ?? CircleDot
              return (
                <StatPill
                  key={key}
                  icon={<Icon size={14} />}
                  value={formatCondition(key, val, t)}
                  tone="crimson"
                  size="sm"
                  iconOnly
                  onClick={() => setDetailCondKey(key)}
                />
              )
            })}
          </div>
        )}

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

        {/* Ability scores anchored at the bottom of the hero card */}
        {char.ability_scores.length > 0 && (
          <div className="mt-4 pt-3 border-t border-dnd-gold-dim/30">
            <m.div
              className="grid grid-cols-6 gap-1.5 text-center"
              initial="initial"
              animate="animate"
              variants={{
                initial: {},
                animate: { transition: { staggerChildren: 0.04, delayChildren: 0.1 } },
              }}
            >
              {char.ability_scores.map((score) => {
                const key = score.name.toLowerCase()
                const colorCls = ABILITY_COLORS[key] ?? ABILITY_COLORS.charisma
                const modStr = `${score.modifier >= 0 ? '+' : ''}${score.modifier}`
                return (
                  <m.button
                    key={score.name}
                    type="button"
                    onClick={() => { haptic.light(); navigate(`/char/${char.id}/stats`) }}
                    aria-label={`${score.name}: ${score.value}, mod ${modStr}`}
                    className={`flex flex-col items-center rounded-lg p-1.5 border bg-gradient-to-b cursor-pointer hover:border-dnd-gold transition-colors ${colorCls}`}
                    variants={{ initial: { opacity: 0, y: 8 }, animate: { opacity: 1, y: 0 } }}
                    transition={spring.snappy}
                    whileTap={{ scale: 0.95 }}
                  >
                    <span className="text-[9px] font-cinzel uppercase tracking-widest opacity-80">
                      {score.name.slice(0, 3)}
                    </span>
                    <span className="text-xl font-display font-black leading-none mt-0.5">{score.value}</span>
                    <span className="text-[11px] font-mono font-bold mt-0.5 px-1.5 py-0.5 rounded-full bg-black/25">
                      {modStr}
                    </span>
                  </m.button>
                )
              })}
            </m.div>
          </div>
        )}
      </Surface>

      {/* Spell slots summary */}
      {char.spell_slots && <SpellSlotsSummary slots={char.spell_slots} />}

      {/* Class progression preview */}
      {char.classes && char.classes.length > 0 && (
        <div>
          <ClassTabs
            classes={char.classes}
            selected={selectedClass}
            onSelect={setSelectedClass}
          />
          <ProgressionPreview
            className={selectedClass}
            currentLevel={currentClassLevel}
          />
        </div>
      )}

      {/* Modals */}
      {detailCondKey !== null && (
        <ConditionDetailModal
          condKey={detailCondKey}
          exhaustionLevel={
            typeof (char.conditions as Record<string, unknown>)?.['exhaustion'] === 'number'
              ? ((char.conditions as Record<string, unknown>)['exhaustion'] as number)
              : 0
          }
          onClose={() => setDetailCondKey(null)}
        />
      )}
      {detailAbility !== null && (
        <PassiveAbilityDetailModal
          ability={detailAbility}
          onClose={() => setDetailAbility(null)}
        />
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify `CharacterFull` type has the fields used here** — `id`, `name`, `class_summary`, `race`, `hit_points`, `current_hit_points`, `temp_hp`, `experience_points`, `total_level`, `ac`, `speed`, `concentrating_spell_id`, `heroic_inspiration`, `ability_scores`, `abilities`, `conditions`, `spells`, `spell_slots`, `classes`, `history`. If any are missing from `webapp/src/types/index.ts`, add them as optional fields. The original `CharacterMain.tsx` already used most of these — only `history` may be new in this context.

```
cd webapp && grep -n "history" src/types/index.ts
```

If `history` is missing on `CharacterFull`, add `history?: Array<{ kind: string; created_at: string; meta?: Record<string, unknown> }>` to it.

- [ ] **Step 3: Type check**

```
cd webapp && npx tsc --noEmit
```

Expected: no errors. Fix any missing types in `webapp/src/types/index.ts` until the check passes.

- [ ] **Step 4: Commit**

```bash
git add webapp/src/pages/character/HeroScreen.tsx webapp/src/types/index.ts
git commit -m "feat(webapp): add HeroScreen with spell slots summary and progression preview"
```

---

### Task 11: `PaperDoll` silhouette + slot grid

**Files:**
- Create: `webapp/src/components/character/PaperDoll.tsx`

- [ ] **Step 1: Create `PaperDoll.tsx`** — Vitruvian SVG, 4-left + 4-right + 3-bottom slot layout. Each slot is delegated to a child `EquipmentSlotCell` (created in Task 12).

```tsx
import { useTranslation } from 'react-i18next'
import { ALL_SLOTS } from '@/lib/equipmentSlots'
import EquipmentSlotCell from './EquipmentSlotCell'
import type { EquipmentSlot, Item } from '@/types'

interface Props {
  items: Item[]
  onSlotTap: (slot: EquipmentSlot, equipped: Item | null) => void
}

const LEFT_SLOTS: EquipmentSlot[] = ['head', 'neck', 'cloak', 'body']
const RIGHT_SLOTS: EquipmentSlot[] = ['hands', 'ring1', 'ring2', 'feet']
const BOTTOM_SLOTS: EquipmentSlot[] = ['main_hand', 'off_hand', 'ammunition']

function findEquipped(items: Item[], slot: EquipmentSlot): Item | null {
  return items.find((i) => i.is_equipped && i.equipment_slot === slot) ?? null
}

export default function PaperDoll({ items, onSlotTap }: Props) {
  const { t } = useTranslation()
  // sanity: all 11 slots used exactly once
  void ALL_SLOTS

  return (
    <div
      className="relative w-full mx-auto rounded-2xl overflow-hidden p-3"
      style={{
        maxWidth: 420,
        background:
          'radial-gradient(ellipse at center, rgba(58,40,32,0.8) 0%, rgba(13,10,8,0.95) 100%)',
        border: '1px solid var(--dnd-gold-dim, #826635)',
      }}
      role="region"
      aria-label={t('character.equipment.equipment', { defaultValue: 'Equipment' })}
    >
      <div className="grid grid-cols-[56px_1fr_56px] gap-2 items-start">
        {/* Left column */}
        <div className="flex flex-col gap-2">
          {LEFT_SLOTS.map((slot) => (
            <EquipmentSlotCell
              key={slot}
              slot={slot}
              equipped={findEquipped(items, slot)}
              onTap={(item) => onSlotTap(slot, item)}
            />
          ))}
        </div>

        {/* Vitruvian silhouette */}
        <div className="flex items-center justify-center min-h-[280px]">
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
        </div>

        {/* Right column */}
        <div className="flex flex-col gap-2">
          {RIGHT_SLOTS.map((slot) => (
            <EquipmentSlotCell
              key={slot}
              slot={slot}
              equipped={findEquipped(items, slot)}
              onTap={(item) => onSlotTap(slot, item)}
            />
          ))}
        </div>
      </div>

      {/* Bottom weapon row */}
      <div className="mt-3 flex justify-center gap-3">
        {BOTTOM_SLOTS.map((slot) => (
          <EquipmentSlotCell
            key={slot}
            slot={slot}
            size="lg"
            equipped={findEquipped(items, slot)}
            onTap={(item) => onSlotTap(slot, item)}
          />
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit (compile happens after Task 12 since it imports `EquipmentSlotCell`)**

```bash
git add webapp/src/components/character/PaperDoll.tsx
git commit -m "feat(webapp): add PaperDoll Vitruvian silhouette and slot layout"
```

---

### Task 12: `EquipmentSlotCell`

**Files:**
- Create: `webapp/src/components/character/EquipmentSlotCell.tsx`

- [ ] **Step 1: Create `EquipmentSlotCell.tsx`**

```tsx
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { SLOT_PLACEHOLDER_ICON } from '@/lib/equipmentSlots'
import { haptic } from '@/auth/telegram'
import type { EquipmentSlot, Item } from '@/types'

interface Props {
  slot: EquipmentSlot
  equipped: Item | null
  size?: 'md' | 'lg'
  onTap: (equipped: Item | null) => void
}

export default function EquipmentSlotCell({ slot, equipped, size = 'md', onTap }: Props) {
  const { t } = useTranslation()
  const PlaceholderIcon = SLOT_PLACEHOLDER_ICON[slot]
  const dim = size === 'lg' ? 56 : 46
  const slotLabel = t(`character.equipment.slots.${slot}`, { defaultValue: slot })

  return (
    <m.button
      type="button"
      onClick={() => { haptic.light(); onTap(equipped) }}
      whileTap={{ scale: 0.92 }}
      style={{
        width: dim,
        height: dim,
        borderRadius: 6,
        border: equipped
          ? '2px solid var(--dnd-gold-bright, #d4af37)'
          : '2px solid var(--dnd-gold-dim, #826635)',
        background: equipped
          ? 'rgba(212,175,55,0.18)'
          : 'rgba(212,175,55,0.08)',
        boxShadow: equipped ? '0 0 6px rgba(212,175,55,0.35)' : undefined,
      }}
      className="relative flex items-center justify-center"
      aria-label={equipped ? `${slotLabel}: ${equipped.name}` : `${slotLabel} ${t('character.equipment.picker.empty', { defaultValue: 'empty' })}`}
    >
      {equipped ? (
        <span
          className="font-cinzel text-[10px] uppercase tracking-wider text-dnd-gold-bright text-center px-1 truncate"
          style={{ maxWidth: dim - 4 }}
        >
          {equipped.name.slice(0, 3)}
        </span>
      ) : (
        <PlaceholderIcon size={dim * 0.45} className="text-dnd-gold-dim" />
      )}
    </m.button>
  )
}
```

- [ ] **Step 2: Type check** (now that PaperDoll's import resolves)

```
cd webapp && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add webapp/src/components/character/EquipmentSlotCell.tsx
git commit -m "feat(webapp): add EquipmentSlotCell rendering empty/equipped/active"
```

---

### Task 13: `EquipItemPicker` modal

**Files:**
- Create: `webapp/src/components/character/EquipItemPicker.tsx`

- [ ] **Step 1: Create the modal**

```tsx
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m, AnimatePresence } from 'framer-motion'
import { X } from 'lucide-react'
import { api } from '@/api/client'
import { haptic } from '@/auth/telegram'
import { ITEM_TYPE_TO_SLOTS } from '@/lib/equipmentSlots'
import type { EquipmentSlot, Item, CharacterFull } from '@/types'

interface Props {
  charId: number
  slot: EquipmentSlot
  items: Item[]
  onClose: () => void
}

function compatibleItems(items: Item[], slot: EquipmentSlot): Item[] {
  return items.filter((i) => {
    const allowed = ITEM_TYPE_TO_SLOTS[i.item_type] ?? []
    return allowed.includes(slot)
  })
}

export default function EquipItemPicker({ charId, slot, items, onClose }: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()

  const equip = useMutation({
    mutationFn: (itemId: number) =>
      api.items.update(charId, itemId, { is_equipped: true, equipment_slot: slot }),
    onSuccess: (updated: CharacterFull) => {
      qc.setQueryData(['character', charId], updated)
      haptic.light()
      onClose()
    },
  })

  const candidates = compatibleItems(items, slot)
  const slotLabel = t(`character.equipment.slots.${slot}`, { defaultValue: slot })

  return (
    <AnimatePresence>
      <m.div
        className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/70 backdrop-blur-sm"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      >
        <m.div
          className="w-full max-w-md max-h-[85vh] overflow-y-auto bg-dnd-surface-raised border border-dnd-gold rounded-t-2xl sm:rounded-2xl"
          initial={{ y: 40, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 40, opacity: 0 }}
          onClick={(e) => e.stopPropagation()}
        >
          <header className="flex items-center justify-between px-4 py-3 border-b border-dnd-gold-dim/40">
            <h2 className="text-sm font-cinzel uppercase tracking-widest text-dnd-gold-bright">
              {t('character.equipment.picker.title', { defaultValue: 'Equip' })} — {slotLabel}
            </h2>
            <button
              type="button"
              onClick={onClose}
              aria-label={t('common.close', { defaultValue: 'Close' })}
              className="w-8 h-8 flex items-center justify-center rounded-full border border-dnd-gold-dim/40"
            >
              <X size={16} className="text-dnd-gold" />
            </button>
          </header>
          {candidates.length === 0 ? (
            <p className="p-6 text-center text-sm text-dnd-text-faint italic">
              {t('character.equipment.picker.empty', { defaultValue: 'No compatible items in inventory.' })}
            </p>
          ) : (
            <ul className="divide-y divide-dnd-gold-dim/20">
              {candidates.map((it) => (
                <li key={it.id}>
                  <button
                    type="button"
                    onClick={() => equip.mutate(it.id)}
                    disabled={equip.isPending}
                    className="w-full text-left px-4 py-3 hover:bg-dnd-surface flex flex-col gap-0.5"
                  >
                    <span className="text-sm font-bold text-dnd-text">{it.name}</span>
                    <span className="text-[11px] text-dnd-text-muted">
                      {it.item_type} · {it.weight} lb
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </m.div>
      </m.div>
    </AnimatePresence>
  )
}
```

- [ ] **Step 2: Type check**

```
cd webapp && npx tsc --noEmit
```

Expected: no errors. If `api.items.update` types don't yet accept `equipment_slot`, extend the helper signature in `webapp/src/api/client.ts:380` to:

```typescript
update: (charId: number, itemId: number, body: Partial<Item>) =>
  request<CharacterFull>(`/characters/${charId}/items/${itemId}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  }),
```

(Inheriting `Partial<Item>` automatically picks up the new `equipment_slot` field added in Task 4.)

- [ ] **Step 3: Commit**

```bash
git add webapp/src/components/character/EquipItemPicker.tsx webapp/src/api/client.ts
git commit -m "feat(webapp): add EquipItemPicker modal for slot equipping"
```

---

### Task 14: `SlotActionSheet`

**Files:**
- Create: `webapp/src/components/character/SlotActionSheet.tsx`

- [ ] **Step 1: Create the action sheet**

```tsx
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m, AnimatePresence } from 'framer-motion'
import { api } from '@/api/client'
import { haptic } from '@/auth/telegram'
import type { EquipmentSlot, Item, CharacterFull } from '@/types'

interface Props {
  charId: number
  slot: EquipmentSlot
  item: Item
  onClose: () => void
  onReplace: () => void
  onDetails: (item: Item) => void
}

export default function SlotActionSheet({ charId, slot, item, onClose, onReplace, onDetails }: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()

  const unequip = useMutation({
    mutationFn: () =>
      api.items.update(charId, item.id, { is_equipped: false, equipment_slot: null }),
    onSuccess: (updated: CharacterFull) => {
      qc.setQueryData(['character', charId], updated)
      haptic.light()
      onClose()
    },
  })

  const slotLabel = t(`character.equipment.slots.${slot}`, { defaultValue: slot })

  return (
    <AnimatePresence>
      <m.div
        className="fixed inset-0 z-50 flex items-end justify-center bg-black/70 backdrop-blur-sm"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      >
        <m.div
          className="w-full max-w-md bg-dnd-surface-raised border border-dnd-gold rounded-t-2xl pb-safe"
          initial={{ y: 100 }}
          animate={{ y: 0 }}
          exit={{ y: 100 }}
          transition={{ type: 'spring', stiffness: 260, damping: 28 }}
          onClick={(e) => e.stopPropagation()}
        >
          <header className="px-4 py-3 border-b border-dnd-gold-dim/40">
            <p className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim">{slotLabel}</p>
            <h2 className="text-sm font-bold text-dnd-gold-bright">{item.name}</h2>
          </header>
          <div className="flex flex-col">
            <button
              type="button"
              onClick={() => onDetails(item)}
              className="px-4 py-3 text-left hover:bg-dnd-surface text-dnd-text"
            >
              {t('character.equipment.actions.details', { defaultValue: 'Details' })}
            </button>
            <button
              type="button"
              onClick={onReplace}
              className="px-4 py-3 text-left hover:bg-dnd-surface text-dnd-text"
            >
              {t('character.equipment.actions.replace', { defaultValue: 'Replace' })}
            </button>
            <button
              type="button"
              onClick={() => unequip.mutate()}
              disabled={unequip.isPending}
              className="px-4 py-3 text-left hover:bg-dnd-surface text-[var(--dnd-crimson-bright)]"
            >
              {t('character.equipment.actions.unequip', { defaultValue: 'Unequip' })}
            </button>
          </div>
        </m.div>
      </m.div>
    </AnimatePresence>
  )
}
```

- [ ] **Step 2: Type check + commit**

```
cd webapp && npx tsc --noEmit
git add webapp/src/components/character/SlotActionSheet.tsx
git commit -m "feat(webapp): add SlotActionSheet for occupied-slot actions"
```

Expected: no type errors.

---

### Task 15: `EquipmentStatsFooter`

**Files:**
- Create: `webapp/src/components/character/EquipmentStatsFooter.tsx`

- [ ] **Step 1: Create the footer** — three `StatPill`s for AC total, main-hand damage, encumbrance.

```tsx
import { useTranslation } from 'react-i18next'
import { GiCheckedShield, GiCrossedSwords, GiWeight } from 'react-icons/gi'
import StatPill from '@/components/ui/StatPill'
import type { CharacterFull } from '@/types'

interface Props {
  char: CharacterFull
}

export default function EquipmentStatsFooter({ char }: Props) {
  const { t } = useTranslation()

  const mainHand = char.items?.find(
    (i) => i.is_equipped && i.equipment_slot === 'main_hand',
  )
  const damage =
    mainHand?.item_metadata && typeof mainHand.item_metadata === 'object'
      ? (mainHand.item_metadata as { damage_dice?: string }).damage_dice
      : null

  const encumbrance = char.items
    ?.filter((i) => i.is_equipped)
    .reduce((sum, i) => sum + (i.weight || 0) * (i.quantity || 1), 0) ?? 0

  const carryCap = (char.ability_scores.find((s) => s.name.toLowerCase() === 'strength')?.value ?? 10) * 15
  const overload = encumbrance > carryCap

  return (
    <div className="mt-3 flex flex-wrap gap-2 justify-center">
      <StatPill
        icon={<GiCheckedShield size={14} />}
        label={t('character.ac.short', { defaultValue: 'AC' })}
        value={String(char.ac)}
        tone="gold"
        size="sm"
      />
      <StatPill
        icon={<GiCrossedSwords size={14} />}
        label={t('character.equipment.slots.main_hand', { defaultValue: 'Weapon' })}
        value={damage ?? '—'}
        tone="crimson"
        size="sm"
      />
      <StatPill
        icon={<GiWeight size={14} />}
        label={t('character.equipment.summary.encumbrance', { defaultValue: 'Carry' })}
        value={`${encumbrance.toFixed(1)} / ${carryCap}`}
        tone={overload ? 'amber' : 'emerald'}
        size="sm"
      />
    </div>
  )
}
```

Note: `StatPill`'s `label` prop may not exist in the current API. If not, drop the `label` and put the descriptor in `value` (e.g., `value={`AC ${char.ac}`}`). Check `webapp/src/components/ui/StatPill.tsx` first; adapt the call accordingly.

- [ ] **Step 2: Type check + commit**

```
cd webapp && npx tsc --noEmit
git add webapp/src/components/character/EquipmentStatsFooter.tsx
git commit -m "feat(webapp): add EquipmentStatsFooter with AC/damage/carry pills"
```

Expected: no errors after StatPill adaptation.

---

### Task 16: `EquipmentScreen` wiring

**Files:**
- Create: `webapp/src/pages/character/EquipmentScreen.tsx`

- [ ] **Step 1: Create the screen** — wires PaperDoll + picker + action sheet.

```tsx
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import PaperDoll from '@/components/character/PaperDoll'
import EquipItemPicker from '@/components/character/EquipItemPicker'
import SlotActionSheet from '@/components/character/SlotActionSheet'
import EquipmentStatsFooter from '@/components/character/EquipmentStatsFooter'
import Surface from '@/components/ui/Surface'
import type { CharacterFull, EquipmentSlot, Item } from '@/types'

interface Props {
  char: CharacterFull
}

type SheetState =
  | { kind: 'closed' }
  | { kind: 'picker'; slot: EquipmentSlot }
  | { kind: 'actions'; slot: EquipmentSlot; item: Item }

export default function EquipmentScreen({ char }: Props) {
  const { t } = useTranslation()
  const [sheet, setSheet] = useState<SheetState>({ kind: 'closed' })

  const handleSlotTap = (slot: EquipmentSlot, equipped: Item | null) => {
    if (equipped) {
      setSheet({ kind: 'actions', slot, item: equipped })
    } else {
      setSheet({ kind: 'picker', slot })
    }
  }

  return (
    <div className="p-4 space-y-3 pb-safe">
      <Surface variant="elevated" className="!p-3 text-center">
        <h2 className="text-sm font-cinzel uppercase tracking-widest text-dnd-gold-bright">
          {t('character.equipment.equipment', { defaultValue: 'Equipment' })}
        </h2>
      </Surface>

      <PaperDoll items={char.items ?? []} onSlotTap={handleSlotTap} />

      <EquipmentStatsFooter char={char} />

      {sheet.kind === 'picker' && (
        <EquipItemPicker
          charId={char.id}
          slot={sheet.slot}
          items={char.items ?? []}
          onClose={() => setSheet({ kind: 'closed' })}
        />
      )}
      {sheet.kind === 'actions' && (
        <SlotActionSheet
          charId={char.id}
          slot={sheet.slot}
          item={sheet.item}
          onClose={() => setSheet({ kind: 'closed' })}
          onReplace={() => setSheet({ kind: 'picker', slot: sheet.slot })}
          onDetails={(_item) => {
            // Reuse existing item detail UX; for now, close. A future task
            // can hook into Inventory's existing detail modal if/when needed.
            setSheet({ kind: 'closed' })
          }}
        />
      )}
    </div>
  )
}
```

- [ ] **Step 2: Type check + commit**

```
cd webapp && npx tsc --noEmit
git add webapp/src/pages/character/EquipmentScreen.tsx
git commit -m "feat(webapp): add EquipmentScreen wiring paper-doll, picker, action sheet"
```

Expected: no errors.

---

### Task 17: i18n keys (it + en)

**Files:**
- Modify: `webapp/src/locales/it.json`
- Modify: `webapp/src/locales/en.json`

- [ ] **Step 1: Add `character.equipment.*` namespace and `character.swiper.*`** to both locale files. Insert under the existing `character` object.

For `webapp/src/locales/it.json`:

```json
"equipment": {
  "equipment": "Equipaggiamento",
  "slots": {
    "head": "Testa",
    "neck": "Collo",
    "cloak": "Mantello",
    "body": "Corpo",
    "hands": "Mani",
    "ring1": "Anello 1",
    "ring2": "Anello 2",
    "feet": "Piedi",
    "main_hand": "Mano principale",
    "off_hand": "Mano secondaria",
    "ammunition": "Munizioni"
  },
  "actions": {
    "details": "Dettagli",
    "replace": "Sostituisci",
    "unequip": "Rimuovi",
    "equip": "Equipaggia"
  },
  "picker": {
    "title": "Equipaggia",
    "empty": "Nessun oggetto compatibile nell'inventario."
  },
  "summary": {
    "spell_slots": "Slot incantesimi",
    "encumbrance": "Carico"
  },
  "progression": {
    "title": "Progressione",
    "tap_full_table": "Tocca per tabella completa",
    "no_data": "Dati di progressione non disponibili",
    "current_level": "Livello attuale"
  }
},
"swiper": {
  "screen": {
    "hero": "Personaggio",
    "equipment": "Equipaggiamento",
    "menu": "Menu"
  }
}
```

For `webapp/src/locales/en.json`, the same structure with English values:

```json
"equipment": {
  "equipment": "Equipment",
  "slots": {
    "head": "Head",
    "neck": "Neck",
    "cloak": "Cloak",
    "body": "Body",
    "hands": "Hands",
    "ring1": "Ring 1",
    "ring2": "Ring 2",
    "feet": "Feet",
    "main_hand": "Main hand",
    "off_hand": "Off hand",
    "ammunition": "Ammunition"
  },
  "actions": {
    "details": "Details",
    "replace": "Replace",
    "unequip": "Unequip",
    "equip": "Equip"
  },
  "picker": {
    "title": "Equip",
    "empty": "No compatible items in inventory."
  },
  "summary": {
    "spell_slots": "Spell slots",
    "encumbrance": "Carry"
  },
  "progression": {
    "title": "Progression",
    "tap_full_table": "Tap for full table",
    "no_data": "Progression data not available",
    "current_level": "Current level"
  }
},
"swiper": {
  "screen": {
    "hero": "Character",
    "equipment": "Equipment",
    "menu": "Menu"
  }
}
```

- [ ] **Step 2: Verify JSON parses**

```
cd webapp && node -e "console.log('it', !!require('./src/locales/it.json').character.equipment); console.log('en', !!require('./src/locales/en.json').character.equipment)"
```

Expected output:
```
it true
en true
```

- [ ] **Step 3: Commit**

```bash
git add webapp/src/locales/it.json webapp/src/locales/en.json
git commit -m "i18n(webapp): add character.equipment and character.swiper keys"
```

---

### Task 18: Wire `CharacterMain` to use `<CharacterSwiper>`

**Files:**
- Modify: `webapp/src/pages/CharacterMain.tsx` — replace the body with the slim wrapper

- [ ] **Step 1: Replace the entire `CharacterMain.tsx` file with**

```tsx
import { useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { ChevronLeft, Settings } from 'lucide-react'
import { GiSparkles } from 'react-icons/gi'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/client'
import { spring } from '@/styles/motion'
import { haptic } from '@/auth/telegram'
import Skeleton from '@/components/ui/Skeleton'
import InSessionBanner from '@/components/ui/InSessionBanner'
import { useCharacterStore } from '@/store/characterStore'
import CharacterSwiper from '@/components/character/CharacterSwiper'
import HeroScreen from '@/pages/character/HeroScreen'
import EquipmentScreen from '@/pages/character/EquipmentScreen'
import MenuScreen from '@/pages/character/MenuScreen'

export default function CharacterMain() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const navigate = useNavigate()
  const { t } = useTranslation()
  const qc = useQueryClient()
  const setActiveCharId = useCharacterStore((s) => s.setActiveCharId)

  useEffect(() => {
    if (!Number.isNaN(charId)) setActiveCharId(charId)
  }, [charId, setActiveCharId])

  const { data: char, isLoading, isError } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
    enabled: !!charId,
  })

  const inspirationMutation = useMutation({
    mutationFn: (value: boolean) => api.characters.updateInspiration(charId, value),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      haptic.light()
    },
  })

  if (isLoading) {
    return (
      <div className="min-h-screen p-4 space-y-4 pb-safe pt-safe">
        <Skeleton.Line width="180px" height="28px" />
        <Skeleton.Rect height="200px" />
        <Skeleton.Rect height="72px" delay={100} />
        <Skeleton.Rect height="240px" delay={200} />
      </div>
    )
  }

  if (isError || !char) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4 p-4">
        <p className="text-[var(--dnd-crimson-bright)] font-body">{t('common.error')}</p>
        <button onClick={() => navigate(-1)} className="underline text-dnd-gold font-cinzel">
          {t('common.back')}
        </button>
      </div>
    )
  }

  return (
    <div
      className="w-full flex flex-col"
      style={{ height: 'var(--tg-vh, 100vh)' }}
    >
      <m.header
        className="shrink-0 z-20 flex items-center gap-2 px-4 py-3 pt-safe
                   bg-dnd-surface-raised/95 backdrop-blur-sm border-b border-dnd-gold-dim/40 shadow-parchment-md"
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={spring.drift}
      >
        <m.button
          onClick={() => navigate(-1)}
          className="w-9 h-9 flex items-center justify-center rounded-full bg-dnd-surface border border-dnd-gold-dim/30"
          whileTap={{ scale: 0.9 }}
          aria-label={t('common.back')}
        >
          <ChevronLeft size={20} className="text-dnd-gold-bright" />
        </m.button>

        <h1 className="text-xl font-display font-bold text-dnd-gold-bright truncate flex-1"
            style={{ textShadow: '0 1px 4px var(--dnd-gold-glow)' }}>
          {char.name}
        </h1>

        <m.button
          onClick={() => inspirationMutation.mutate(!char.heroic_inspiration)}
          title={char.heroic_inspiration
            ? t('character.inspiration.tap_to_spend')
            : t('character.inspiration.tap_to_grant')}
          className={`w-9 h-9 flex items-center justify-center rounded-full transition-all
            ${char.heroic_inspiration
              ? 'bg-dnd-gold/15 border border-dnd-gold animate-shimmer'
              : 'bg-transparent border border-dashed border-dnd-gold-dim/40 opacity-50'}`}
          whileTap={{ scale: 0.9 }}
          aria-label="Heroic Inspiration"
        >
          <GiSparkles size={18} className="text-dnd-gold" />
        </m.button>

        <m.button
          onClick={() => navigate(`/char/${charId}/settings`)}
          className="w-9 h-9 flex items-center justify-center rounded-full bg-dnd-surface border border-dnd-gold-dim/30"
          whileTap={{ scale: 0.9 }}
          aria-label={t('character.menu.settings')}
        >
          <Settings size={18} className="text-dnd-gold-bright" />
        </m.button>
      </m.header>

      <InSessionBanner charId={charId} />

      <CharacterSwiper
        hero={<HeroScreen char={char} />}
        equipment={<EquipmentScreen char={char} />}
        menu={<MenuScreen charId={charId} />}
      />
    </div>
  )
}
```

The header keeps the inspiration toggle and Settings button to avoid duplication; the in-card inspiration button inside `HeroScreen` (added in Task 10) is therefore redundant. Remove it: in `HeroScreen.tsx`, delete the `inspirationToggle` block and the `pr-12` padding on the title button.

- [ ] **Step 2: Update `HeroScreen.tsx`** — remove the redundant inspiration toggle.

In `webapp/src/pages/character/HeroScreen.tsx`, delete:
- The entire `inspirationToggle` `useMemo`
- The `inspirationMutation` `useMutation`
- The `qc = useQueryClient()` line
- The `pr-12` className on the identity button (revert to `block w-full text-left`)
- The `{inspirationToggle}` usage inside the `Surface`

This leaves `HeroScreen` purely presentational for the inspiration concern (toggle stays in the header).

- [ ] **Step 3: Type check**

```
cd webapp && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add webapp/src/pages/CharacterMain.tsx webapp/src/pages/character/HeroScreen.tsx
git commit -m "feat(webapp): wire CharacterMain to CharacterSwiper with 3 screens"
```

---

### Task 19: Production build + manual verification

**Files:** none modified.

- [ ] **Step 1: Run production build** (handles env switching automatically per CLAUDE.md):

```
cd webapp && npm run build:prod
```

Expected: `tsc && vite build` succeed; `docs/app/` is updated and staged.

- [ ] **Step 2: Manual smoke test in dev mode**

```
# Terminal 1
uv run uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2
cd webapp && npm run dev
```

Open `http://localhost:5173/`. Visit a test character at `/char/<id>`.

Verify the checklist below:

- Initial render lands on screen 0 (Hero)
- Swipe left → screen 1 (Equipment); dot indicator updates; swipe again → screen 2 (Menu); swipe further does not advance past 2
- Swipe right reverses correctly
- Tap a dot indicator → animates to that screen
- HeroScreen click targets navigate correctly: name → identity, AC shield → ac, HP → hp, XP bar → xp, concentration banner → spells, condition chip → condition modal, passive chip → passive modal, stat cell → stats, spell-slots row → slots
- Spell-slots summary hidden if char has no slots; visible with correct totals when slots exist
- ProgressionPreview shows 5-row window with current level highlighted gold
- ProgressionFullTableModal opens, scrolls to current level, current row highlighted
- ClassTabs visible only for multi-class chars; selecting a tab switches the preview
- EquipmentScreen: tap empty slot → picker shows only compatible items; tap a candidate → equips it (item appears in slot, inventory shows `is_equipped=true`)
- Equipping a second item in the same slot displaces the previous one (previous shows `is_equipped=false`)
- Tap occupied slot → action sheet (Details / Replace / Unequip); Unequip clears the slot; Replace opens picker
- Validation: try equipping armor in main_hand via direct API (curl, see Task 3 step 3) — server returns 422
- Switching to a different character → swiper resets to screen 0
- DevTools Network: `prefers-reduced-motion: reduce` (toggle in DevTools Rendering panel) → carousel snaps without animation
- i18n: switch language to English (Telegram WebApp init) — all new labels render in English

- [ ] **Step 3: Final commit (if `docs/app/` was modified)**

```bash
git status
# If docs/app/ has staged changes:
git commit -m "chore(webapp): build for character menu 3-screens"
```

If there are no staged changes, skip this step. Push the branch and open a PR per CLAUDE.md instructions.

---

## Self-review

The plan covers all spec sections:

- **Architecture / Routing** → Tasks 6, 18 (single `/char/:id`, swiper inside)
- **Carousel mechanics** → Task 6 (framer-motion drag, snap, `prefers-reduced-motion`)
- **Zustand state** → Task 4 (`activeScreen` resets on `setActiveCharId`)
- **Screen 1 layout & click targets** → Task 10 (HeroScreen with all click targets)
- **Spell slots summary** → Task 8
- **Progression preview + modal + tabs** → Task 9
- **Multiclass default class** → Task 10 (`pickDefaultClass`, history-aware)
- **Screen 2 layout (PaperDoll + 4-left/4-right/3-bottom + footer)** → Tasks 11, 12, 15, 16
- **Slot UI states** → Task 12
- **Slot interactions (picker / action sheet, atomic swap)** → Tasks 13, 14, plus Task 3 server-side
- **Stats footer (AC/damage/encumbrance)** → Task 15
- **Screen 3 (verbatim extract)** → Task 7
- **Backend EquipmentSlot enum + migration** → Task 1
- **Pydantic schema + compat** → Task 2
- **Atomic swap endpoint** → Task 3
- **`item_type → equipment_slot` mapping (frontend mirror)** → Task 5
- **Lucide placeholder icons per slot** → Task 5
- **i18n keys** → Task 17
- **Verification (manual)** → Task 19

No placeholders remain. Type/method names are consistent across tasks: `CharacterScreen`, `setActiveScreen`, `EquipmentSlot`, `slotsAllowedFor`, `swap_slot_occupant`, `EQUIPMENT_SLOT_COMPAT`, `findEquipped`, `compatibleItems`, etc.
