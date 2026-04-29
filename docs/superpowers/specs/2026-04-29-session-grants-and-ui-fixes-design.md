# Session Grants & UI Fixes — Design

Date: 2026-04-29
Branch: `feat/character-menu-3-screens` (or successor branch)
Author: cioscos

## Summary

Four user-reported fixes/features bundled as one spec:

1. **Equipment dialogs cropped on Equipment screen** — `SlotActionSheet` and `EquipItemPicker` modals render outside the visible viewport because they live inside the `CharacterSwiper` transformed track.
2. **Session chat — too little spacing between last message and input** — visual polish in `SessionFeed`.
3. **Session — reward popup on item grant** — when a player receives a granted item from the GM, show a centered modal "you received an item" with a CTA into the inventory.
4. **Session — clickable grant message → inventory highlight** — tapping the GM-grant chat message takes the player to their inventory and highlights the granted item with a pulse glow.

Fixes #3 and #4 share data plumbing: the backend is extended so each GM-grant `SessionMessage` carries `item_id`, `item_name`, `item_quantity`. Fixes #1 and #2 are isolated frontend tweaks.

## Architecture changes

### Backend
- `core/db/models.py` — `SessionMessage` gets three nullable columns: `item_id BIGINT`, `item_name VARCHAR(120)`, `item_quantity INTEGER`.
- `core/db/engine.py` — three new entries in `_MIGRATIONS` (idempotent `ALTER TABLE ADD COLUMN`).
- `api/routers/sessions.py:gm_grant_item` — populate the three fields on the whisper it creates.
- `api/routers/sessions.py:get_session_feed` — include the three fields in the feed response.
- `api/schemas/sessions.py` — extend `SessionFeedItemSchema` (and any related grant response schemas as needed).

### Frontend
- `webapp/src/types/index.ts` — extend `SessionFeedItem` with `item_id`, `item_name`, `item_quantity`.
- `webapp/src/components/character/SlotActionSheet.tsx` — wrap return in `createPortal(..., document.body)`.
- `webapp/src/components/character/EquipItemPicker.tsx` — same.
- `webapp/src/pages/session/SessionFeed.tsx` — `mt-4` spacing on input row, detect grant messages addressed to me on incremental fetch and `enqueue` to reward queue, render grant whispers as clickable.
- **NEW** `webapp/src/components/session/RewardPopup.tsx` — centered modal portal'd to body, "you received an item" UI with CTA "Vedi nell'inventario" + "OK".
- **NEW** `webapp/src/lib/rewardQueue.ts` — sessionStorage-backed FIFO queue helpers (`enqueue`, `peek`, `dequeue`, `clear`).
- `webapp/src/pages/SessionRoom.tsx` — on mount, peek queue and render `<RewardPopup>` if non-empty; cycle through queue on dismiss.
- `webapp/src/pages/Inventory.tsx` — read `location.state.highlightItemId`, expand the matched item, ensure its type group is not collapsed, scroll into view, apply a temporary pulse-glow class for ~3s, `replace` history state.
- `webapp/src/pages/inventory/InventoryItem.tsx` — accept optional `highlighted?: boolean` prop and apply the pulse-glow class.
- `webapp/src/index.css` (or a tailwind plugin file) — define `@keyframes pulse-glow` animation.
- `webapp/src/locales/it.json` + `webapp/src/locales/en.json` — new keys.

## Data flow

### Grant (GM side)
1. GM taps "Consegna oggetto" → `GrantItemModal` runs the existing two-step form.
2. POST `/sessions/{id}/gm/grant_item` with item payload + recipient list.
3. For each recipient the backend creates/merges the `Item` and creates a `SessionMessage` whisper. With this change, that whisper now also stores `item_id`, `item_name`, `item_quantity`.
4. 201 returned.

### Recipient feed polling
1. `SessionFeed` polls every 3 s with `since=<latestTs>`.
2. `mergeIncoming(fresh)` adds new items.
3. **New step**: for each `fresh` entry where `type === 'message'`, `item_id != null`, and `recipient_user_id === myUserId`, push `{message_id, item_id, item_name, item_quantity, char_id, granted_at}` to the reward queue. Skip enqueueing on the very first (initial) fetch — only items arriving via the `since` cursor are treated as new rewards.

### Reward popup
- `SessionRoom` mounts → `peek()`. If non-null, render `<RewardPopup>`.
- "Vedi nell'inventario" → `dequeue()` + `navigate('/char/:charId/inventory', { state: { highlightItemId } })`.
- "OK" or scrim → `dequeue()`. After dequeue, `peek()` again; if non-null, immediately render the next popup. Repeat until queue empty.
- Stale-queue cleanup: on `SessionRoom` mount, if any queue entry's `granted_at` is older than 24 h, drop it before peeking.

### Click whisper → inventory
1. Tap a whisper bubble where `item_id != null` and `recipient_user_id === myUserId`.
2. Lookup `char.items` (cached query data) for that `item_id`.
3. Missing → `toast.warning(t('session.reward.item_not_found_toast'))`, no navigation.
4. Present → `navigate('/char/:charId/inventory', { state: { highlightItemId } })`.

### Inventory highlight
1. `Inventory.tsx` reads `useLocation().state?.highlightItemId` on mount.
2. If set and the item is present:
   - `setExpanded(itemId)`
   - Remove the item's `item_type` from `collapsedTypes` if present.
   - `requestAnimationFrame` then `itemRefs.current[itemId]?.scrollIntoView({ block: 'center', behavior: 'smooth' })`.
   - `setTimeout(() => setHighlight(null), 3000)`.
   - `navigate(pathname, { replace: true, state: null })` to prevent re-trigger on browser back.

## Components — detail

### `RewardPopup.tsx` (~80 LOC)
- Props: `reward: { item_id, item_name, item_quantity, char_id }`, `onDismiss()`, `onGoToInventory()`.
- Render: `createPortal(document.body)` with scrim `bg-black/70 backdrop-blur-sm`, centered card `bg-dnd-surface-raised border border-dnd-gold rounded-2xl`, max-w-sm.
- Header: `<Gift>` icon (sized ~32) + `t('session.reward.title')`.
- Body: `item_name` (display font, gold), `× quantity` pill, optional description (truncated to ~120 chars).
- Footer: primary `Button` "Vedi nell'inventario" + secondary "OK".
- Entry animation: `m.div` scale 0.9→1 + opacity 0→1, spring (220, 26).
- ESC + scrim click → `onDismiss`.

### `rewardQueue.ts` (~30 LOC)
- `KEY = 'reward-queue'`.
- All operations wrapped in try/catch (private mode / quota exceeded → no-op + console.warn).
- API:
  ```ts
  type Reward = {
    message_id: number
    item_id: number
    item_name: string
    item_quantity: number
    char_id: number
    granted_at: string // ISO
  }

  enqueue(r: Reward): void
  peek(): Reward | null
  dequeue(): Reward | null
  clear(): void
  pruneOlderThan(ms: number): void
  ```

### `SessionFeed.tsx` changes
1. Spacing: input row wrapper becomes `<div className="mt-4 flex items-center gap-2">`.
2. After dedup in `mergeIncoming`, iterate `fresh` and call `enqueue` for grant-to-me items.
3. Render whisper bubble: when `it.item_id != null`, attach `cursor-pointer` + `onClick={handleGrantClick(it)}`, prepend a small `<Gift size={12}>` icon, append a faded chip "Tap per inventario" (tooltip-like).
4. `handleGrantClick(it)`:
   ```ts
   const item = char?.items?.find((i) => i.id === it.item_id)
   if (!item) {
     toast.warning(t('session.reward.item_not_found_toast'))
     return
   }
   navigate(`/char/${charId}/inventory`, { state: { highlightItemId: item.id } })
   ```
   `charId` resolved from `useCharacterStore` (or session-me query), since `SessionFeed` does not currently know the player's char id directly — pass it down as a prop from `SessionRoom`.

### `SessionRoom.tsx` changes
- On mount: `pruneOlderThan(24h)` then `peek()`. If non-null, set local state `currentReward` and render `<RewardPopup>`.
- onDismiss / onGoToInventory: `dequeue()`, `peek()` again, set `currentReward` (drives next popup) or null.
- Pass `myCharId` down to `SessionFeed` so the click handler can build the navigate target.

### `Inventory.tsx` changes
- New state `highlightId: number | null` initialised from `location.state?.highlightItemId ?? null`.
- New ref map `itemRefs = useRef<Record<number, HTMLDivElement | null>>({})`.
- `useEffect` keyed on `[highlightId, items]`:
  - If `highlightId` and item present: setExpanded, remove type from collapsed, rAF→scrollIntoView, setTimeout 3 s → `setHighlightId(null)`, `navigate(pathname, { replace: true, state: null })`.
  - If `highlightId` set but item not in list (race): `setHighlightId(null)` silently.
- Pass `highlighted={item.id === highlightId}` to `InventoryItem`.

### `InventoryItem.tsx` changes
- New optional prop `highlighted?: boolean`.
- When true add class `animate-pulse-glow` (3 cycles, 1 s each, ease-out, fades to transparent).

### Pulse-glow CSS
```css
@keyframes pulse-glow {
  0%   { box-shadow: 0 0 0 0 rgba(212, 175, 55, 0.0); }
  20%  { box-shadow: 0 0 12px 4px rgba(212, 175, 55, 0.7); }
  100% { box-shadow: 0 0 0 0 rgba(212, 175, 55, 0.0); }
}
.animate-pulse-glow {
  animation: pulse-glow 1s ease-out 0s 3;
  border-color: var(--dnd-gold-bright);
}
```

### Migration entries
```python
# core/db/engine.py — add to _MIGRATIONS
("session_messages", "item_id",       "BIGINT"),
("session_messages", "item_name",     "VARCHAR(120)"),
("session_messages", "item_quantity", "INTEGER"),
```

### `gm_grant_item` change
After `granted_item_id` is known and `whisper_body` is composed, build the `SessionMessage` with the new fields:
```python
msg = SessionMessage(
    session_id=session_obj.id,
    user_id=user_id,
    role=SessionRole.GAME_MASTER,
    body=whisper_body,
    sent_at=now_iso,
    recipient_user_id=rid,
    sender_display_name="__GM__",
    item_id=granted_item_id,
    item_name=body.item.name,
    item_quantity=body.item.quantity,
)
```

### Feed schema change
- `SessionFeedItemSchema`: add `item_id: Optional[int] = None`, `item_name: Optional[str] = None`, `item_quantity: Optional[int] = None`.
- The aggregator that maps `SessionMessage` → `SessionFeedItemSchema` populates the three fields verbatim (None for non-grant messages).

## Edge cases

- **Multiple grants on return**: queue is FIFO, popups shown sequentially. ✓
- **Reload while popup open**: state lost, queue persists in sessionStorage, popup re-shown on next mount.
- **Stale queue (>24 h)**: dropped on next `SessionRoom` mount.
- **sessionStorage quota / disabled**: try/catch wraps all ops; degraded silently (no popup, no crash).
- **Item deleted between grant and click**: lookup fails → toast "Oggetto non più presente", no navigation.
- **Item present but in collapsed type group**: `Inventory` removes the type from `collapsedTypes` before scrolling.
- **Highlight target not in DOM yet**: `useEffect` deps include `items`; once items load, scroll fires.
- **Browser back after highlight**: `replace: true` clears `location.state` so re-mount does not re-trigger.
- **Equipment portal stacking**: `z-50`, only one EquipmentScreen sheet open at a time; consistent with `ProgressionFullTableModal`.
- **Migration idempotency**: `_migrate_schema` already guards on existing columns; safe on re-runs.
- **Generic-stack merge edge**: when grant merges into an existing generic stack, `granted_item_id` points to the existing item — highlight still works correctly.
- **GM also receiving (not possible)**: backend skips `participant.role != PLAYER`, so GM never gets a grant whisper to themselves.
- **Whisper chip click for non-recipient (GM viewing the whisper)**: only the recipient sees the message, so non-issue.

## i18n keys

```json
// it.json
"session.reward.title": "Hai ricevuto un oggetto!",
"session.reward.cta_inventory": "Vedi nell'inventario",
"session.reward.cta_dismiss": "OK",
"session.reward.item_not_found_toast": "Oggetto non più presente nel tuo inventario",
"session.feed.grant_chip": "Tocca per aprire nell'inventario"

// en.json
"session.reward.title": "You received an item!",
"session.reward.cta_inventory": "View in inventory",
"session.reward.cta_dismiss": "OK",
"session.reward.item_not_found_toast": "Item is no longer in your inventory",
"session.feed.grant_chip": "Tap to open in inventory"
```

## Testing strategy

No automated test suite. Manual verification (desktop + Telegram Android):

1. **Modal portal** — open Equipment screen, swipe to screens 0/1/2, tap each slot. Confirm picker + action sheet sit centered on viewport at all 3 swiper positions, no clipping.
2. **Spacing** — open Session chat, send a few messages, confirm visible breathing room above input.
3. **Reward popup happy path** — GM grants 1 item; recipient is in SessionRoom → modal appears immediately on next poll. Confirm icon, name, qty, description, two buttons.
4. **Reward popup stacking** — GM grants 3 items in quick succession to a recipient who is on `/inventory`. Recipient navigates back to SessionRoom → 3 popups appear sequentially as user dismisses each.
5. **Reward popup CTA** — click "Vedi nell'inventario" → lands on Inventory, item expanded, glowing for ~3 s, then back to normal.
6. **Stale queue prune** — manually set a >24 h-old reward in sessionStorage, mount SessionRoom, confirm it's dropped.
7. **Chat click** — tap a grant whisper, confirm navigation + highlight.
8. **Item-deleted edge** — GM grants, recipient deletes the item, then taps the chat message → toast appears, no navigation.
9. **Migration** — start API on existing DB; confirm `_migrate_schema` adds the three columns without error; rerun, confirm idempotent.

## Out of scope

- Notifications outside the Mini App (Telegram push, sound).
- Reward popup outside SessionRoom (per choice C — only resurfaces on return).
- Backend dispatch of multiple grants in a single API call (already supported via `recipient_user_ids`).
- Refactor of existing event-vs-message rendering (no change to that path).
