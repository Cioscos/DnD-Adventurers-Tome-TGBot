# Chat & History Integrated Feed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the chat box in the session room with a unified chat+history feed, fetched from a new backend endpoint that merges `session_messages` + `character_history` events for the session, applying per-viewer redaction on HP events (heal → "si è curato", set → "ha modificato i PF", damage passthrough).

**Architecture:** Add a nullable `meta` JSON column to `character_history` for structured op tagging (migration + model change + helper signature). New endpoint `GET /sessions/{code}/feed` returns a mixed `items: list[SessionFeedItem]` sorted ASC with redaction applied server-side, supporting `since`/`before` cursor pagination. Frontend extracts `EVENT_META` to a shared lib, creates a `SessionFeed` component (polling + load-previous), and SessionRoom swaps the inline chat for `<SessionFeed />`.

**Tech Stack:** FastAPI + Pydantic + SQLAlchemy async, React + TypeScript + TanStack Query + Tailwind + framer-motion. SQLite DB (TEXT columns for JSON).

**Branch:** `feat/chat-history-gruppo-h`.

**Testing note:** No test suite in the repo (per `CLAUDE.md`). Verification = `cd webapp && npx tsc --noEmit` for frontend, manual verification via running dev server for backend. Do NOT run `uv sync`/`uv run`/`uv venv` from WSL; ask the user to run Python-side commands from their Windows shell.

**Commit convention:** conventional commits. Italian summaries aligned with recent history.

---

## Mappa dei file

### Nuovi
- `webapp/src/lib/eventMeta.ts` — shared `EVENT_META` record (icon + tone per event_type).
- `webapp/src/pages/session/SessionFeed.tsx` — unified feed component (polling, load-previous, send message, whisper, render mixed items).

### Modificati backend
- `core/db/models.py` (add `meta` column to `CharacterHistory`).
- `core/db/engine.py` (migration entry).
- `api/routers/characters.py` (`_add_history` signature + `meta=None` default).
- `api/routers/hp.py` (5 HP op branches + `/hp/recalc` pass `meta={"op": ...}`).
- `api/schemas/session.py` (`SessionFeedItem`, `SessionFeedResponse`).
- `api/routers/sessions.py` (new `GET /{code}/feed` endpoint).

### Modificati frontend
- `webapp/src/pages/History.tsx` (import `EVENT_META` da lib).
- `webapp/src/pages/SessionRoom.tsx` (swap inline chat with `<SessionFeed />`).
- `webapp/src/types/index.ts` (`SessionFeedItem`, `SessionFeedResponse`).
- `webapp/src/api/client.ts` (`api.sessions.getFeed`).
- `webapp/src/locales/it.json` + `en.json` (new keys).
- `docs/superpowers/roadmap.md` (mark Gruppo H done — final task).

### Invariati
- `api/routers/history.py` (`/characters/{id}/history` endpoint untouched).
- Bot.
- `POST /sessions/{id}/messages` (send message endpoint unchanged).

---

## Task 1: Aggiungere `meta` column a `character_history`

**Files:**
- Modify: `core/db/models.py` (around line 491-502: `CharacterHistory`)
- Modify: `core/db/engine.py` (line 40-93: `_MIGRATIONS`)

### Step 1: Add `meta` column to `CharacterHistory` model

In `core/db/models.py`, find the `CharacterHistory` class. Add a new column after `description`:

```python
class CharacterHistory(Base):
    """One entry in the character's modification history."""

    __tablename__ = "character_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    timestamp: Mapped[str] = mapped_column(String(20), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)   # new
```

Ensure `Optional` and `JSON` are imported at top of the file — they already are (used by other models).

### Step 2: Add migration entry

In `core/db/engine.py` `_MIGRATIONS` list, append (before the closing `]`):

```python
# Character history meta (for op tagging on hp_change, Gruppo H)
("character_history", "meta", "TEXT", None),
```

(The column type is `TEXT` because SQLite stores JSON as TEXT; SQLAlchemy's `JSON` type handles serialization.)

### Step 3: Manual verify — ask user

Ask the user to:
1. Restart `uvicorn` so the `lifespan` runs `_migrate_schema()`.
2. Confirm no migration error in logs.
3. Check with SQLite client: `PRAGMA table_info(character_history)` should list `meta` column.

### Step 4: Commit

```bash
git add core/db/models.py core/db/engine.py
git commit -m "$(cat <<'EOF'
feat(db): add meta JSON column to character_history

Supports structured op tagging for hp_change events — used by
Gruppo H session feed redaction logic.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: `_add_history` accepts `meta` + HP ops tag

**Files:**
- Modify: `api/routers/characters.py` (line 73-79: `_add_history` helper)
- Modify: `api/routers/hp.py` (all `_add_history` callers with hp_change — lines 110, 123, 131, 137, 401)

### Step 1: Extend `_add_history` signature

In `api/routers/characters.py`, find `_add_history` around line 73. Replace with:

```python
def _add_history(
    session,
    char_id: int,
    event_type: str,
    description: str,
    meta: dict | None = None,
) -> None:
    session.add(CharacterHistory(
        character_id=char_id,
        timestamp=_now(),
        event_type=event_type,
        description=description,
        meta=meta,
    ))
```

Because `meta=None` is the default, existing callers (which don't pass it) keep working unchanged.

### Step 2: Update HP op loggers in `api/routers/hp.py`

The HP router logs `hp_change` at 5 sites. Update each to pass `meta={"op": "<OP>"}`:

**Line 110 (DAMAGE):**
```python
_add_history(session, char.id, "hp_change",
             f"Danni: -{body.value} HP ({old} → {char.current_hit_points})",
             meta={"op": "DAMAGE"})
```

**Line 123 (HEAL):**
```python
_add_history(session, char.id, "hp_change",
             f"Cura: +{body.value} HP ({old} → {char.current_hit_points})",
             meta={"op": "HEAL"})
```

**Line 131 (SET_MAX):**
```python
_add_history(session, char.id, "hp_change",
             f"HP max impostati: {old} → {char.hit_points}",
             meta={"op": "SET_MAX"})
```

**Line 137 (SET_CURRENT):**
```python
_add_history(session, char.id, "hp_change",
             f"HP correnti impostati: {old} → {char.current_hit_points}",
             meta={"op": "SET_CURRENT"})
```

**Line 401 (hp/recalc endpoint):**
```python
_add_history(session, char.id, "hp_change",
             f"HP ricalcolati da formula: {old_max} → {new_max}",
             meta={"op": "SET_MAX"})
```

Note: SET_TEMP branch (line 140-141) does **not** call `_add_history` currently (no log for temp_hp adjustments). Leave as-is — no event, no redaction concern.

### Step 3: Ask user to verify

1. Restart uvicorn (auto-reload).
2. In the webapp, trigger an HP op (e.g. damage 3 HP on a character).
3. Inspect DB with SQLite client: `SELECT id, event_type, description, meta FROM character_history WHERE event_type = 'hp_change' ORDER BY id DESC LIMIT 5`. The newest rows should have `meta = '{"op": "DAMAGE"}'` (or HEAL/SET_MAX/SET_CURRENT as appropriate).
4. Legacy rows (pre-migration) will have `meta = NULL` — expected.

### Step 4: Commit

```bash
git add api/routers/characters.py api/routers/hp.py
git commit -m "$(cat <<'EOF'
feat(api): tag hp_change events with op in history meta

_add_history now accepts a meta dict; HP router passes
{"op": "HEAL"|"DAMAGE"|"SET_MAX"|"SET_CURRENT"} and /hp/recalc
passes {"op": "SET_MAX"}. Legacy rows keep meta=NULL.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Schemi Pydantic `SessionFeedItem` + `SessionFeedResponse`

**Files:**
- Modify: `api/schemas/session.py`

### Step 1: Add schemas

Append to `api/schemas/session.py` (after existing `IdentityView`):

```python
from typing import Literal  # add to imports if missing


class SessionFeedItem(BaseModel):
    """Single item in the mixed chat+history feed."""

    type: Literal["message", "event"]
    timestamp: str

    # message-only
    message_id: Optional[int] = None
    user_id: Optional[int] = None
    display_name: Optional[str] = None
    role: Optional[str] = None
    body: Optional[str] = None
    recipient_user_id: Optional[int] = None

    # event-only
    event_id: Optional[int] = None
    character_id: Optional[int] = None
    character_name: Optional[str] = None
    owner_user_id: Optional[int] = None
    event_type: Optional[str] = None
    description: Optional[str] = None   # redacted per viewer
    op: Optional[str] = None             # from meta.op when present


class SessionFeedResponse(BaseModel):
    items: list[SessionFeedItem]
    has_more: bool = False
```

### Step 2: Commit

```bash
git add api/schemas/session.py
git commit -m "$(cat <<'EOF'
feat(api): add SessionFeedItem + SessionFeedResponse schemas

Mixed chat+history feed DTO used by /sessions/{code}/feed endpoint.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Endpoint `GET /sessions/{code}/feed`

**Files:**
- Modify: `api/routers/sessions.py`

### Step 1: Import new schemas + needed helpers

In the existing `from api.schemas.session import ...` block, add:

```python
from api.schemas.session import (
    # ...existing...
    SessionFeedItem,
    SessionFeedResponse,
)
```

Ensure these imports exist at the top of the file (most already are): `Annotated`, `Optional`, `Depends`, `HTTPException`, `status`, `Query` (from fastapi), `select`, `and_`, `desc`, `or_`, `asc` (from sqlalchemy), `AsyncSession` (from sqlalchemy.ext.asyncio), `CharacterHistory`, `SessionMessage`, `Character`, `SessionParticipant` (from `core.db.models`). Add missing ones.

### Step 2: Define allowed event types + redaction helper

Near the top of `sessions.py` (after the imports, before `_load_session`), add:

```python
_SESSION_FEED_EVENT_TYPES: set[str] = {
    "hp_change",
    "rest",
    "skill_roll",
    "saving_throw",
    "attack_roll",
    "death_save",
    "condition_change",
    "concentration_save",
    "hit_dice",
}


def _redact_event_description(
    event: CharacterHistory,
    character_name: str,
    viewer_user_id: int,
    owner_user_id: int,
    is_gm: bool,
) -> str:
    # Owner or GM → raw description.
    if viewer_user_id == owner_user_id or is_gm:
        return event.description

    # Only hp_change is redacted.
    if event.event_type != "hp_change":
        return event.description

    meta = event.meta or {}
    op = str(meta.get("op") or "").upper()

    if op == "HEAL":
        return f"{character_name} si è curato"
    if op in ("SET_CURRENT", "SET_MAX", "SET_TEMP"):
        return f"{character_name} ha modificato i PF"
    if op == "DAMAGE":
        return event.description  # passthrough (HP bucket already public)

    # Legacy fallback (meta missing): best-effort description sniff.
    desc_lower = event.description.lower()
    if "cura" in desc_lower or "heal" in desc_lower:
        return f"{character_name} si è curato"
    if "danni" in desc_lower or "danno" in desc_lower or "damage" in desc_lower:
        return event.description
    # Unknown → safe default.
    return f"{character_name} ha modificato i PF"
```

### Step 3: Add endpoint

Add at the end of the router (after `post_message` and `get_participant_identity`):

```python
@router.get(
    "/{code}/feed",
    response_model=SessionFeedResponse,
)
async def get_session_feed(
    code: str,
    caller_user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    since: Annotated[Optional[str], Query()] = None,
    before: Annotated[Optional[str], Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> SessionFeedResponse:
    if since is not None and before is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use either 'since' or 'before', not both",
        )

    session = await _load_session_by_code(code, db)
    _assert_participant(session, caller_user_id)

    is_gm = session.gm_user_id == caller_user_id
    session_start = session.created_at  # ISO string

    # Collect participants → char_id map with owner + name.
    char_ids: list[int] = []
    char_meta: dict[int, tuple[int, str]] = {}  # char_id -> (owner_user_id, name)
    for p in session.participants:
        if p.character_id is not None:
            char_ids.append(p.character_id)

    if char_ids:
        result = await db.execute(
            select(Character.id, Character.user_id, Character.name).where(
                Character.id.in_(char_ids)
            )
        )
        for cid, owner, name in result.all():
            char_meta[cid] = (owner, name)

    # --- Query messages ---
    msg_stmt = select(SessionMessage).where(
        SessionMessage.session_id == session.id,
        SessionMessage.sent_at >= session_start,
    )
    if since:
        msg_stmt = msg_stmt.where(SessionMessage.sent_at > since)
    if before:
        msg_stmt = msg_stmt.where(SessionMessage.sent_at < before)
    msg_stmt = msg_stmt.order_by(SessionMessage.sent_at.asc(), SessionMessage.id.asc())
    msg_result = await db.execute(msg_stmt)
    messages = list(msg_result.scalars().all())

    # --- Query history events ---
    events: list[CharacterHistory] = []
    if char_ids:
        ev_stmt = select(CharacterHistory).where(
            CharacterHistory.character_id.in_(char_ids),
            CharacterHistory.timestamp >= session_start,
            CharacterHistory.event_type.in_(_SESSION_FEED_EVENT_TYPES),
        )
        if since:
            ev_stmt = ev_stmt.where(CharacterHistory.timestamp > since)
        if before:
            ev_stmt = ev_stmt.where(CharacterHistory.timestamp < before)
        ev_stmt = ev_stmt.order_by(CharacterHistory.timestamp.asc(), CharacterHistory.id.asc())
        ev_result = await db.execute(ev_stmt)
        events = list(ev_result.scalars().all())

    # --- Build items (message visibility: whisper filter) ---
    items: list[SessionFeedItem] = []

    for m in messages:
        if m.recipient_user_id is not None:
            # Whisper: only sender, recipient, GM can see.
            if not (
                caller_user_id == m.user_id
                or caller_user_id == m.recipient_user_id
                or is_gm
            ):
                continue
        # Determine role of sender.
        sender_role = "game_master" if m.user_id == session.gm_user_id else "player"
        items.append(SessionFeedItem(
            type="message",
            timestamp=m.sent_at,
            message_id=m.id,
            user_id=m.user_id,
            display_name=m.sender_display_name,
            role=sender_role,
            body=m.body,
            recipient_user_id=m.recipient_user_id,
        ))

    for e in events:
        owner_id, char_name = char_meta.get(e.character_id, (None, f"#{e.character_id}"))
        if owner_id is None:
            continue
        redacted = _redact_event_description(e, char_name, caller_user_id, owner_id, is_gm)
        meta_op = None
        if e.meta and isinstance(e.meta, dict):
            op_val = e.meta.get("op")
            if isinstance(op_val, str):
                meta_op = op_val
        items.append(SessionFeedItem(
            type="event",
            timestamp=e.timestamp,
            event_id=e.id,
            character_id=e.character_id,
            character_name=char_name,
            owner_user_id=owner_id,
            event_type=e.event_type,
            description=redacted,
            op=meta_op,
        ))

    # Sort ASC by timestamp, tie-break by type then numeric id.
    def _sort_key(it: SessionFeedItem):
        sec = it.message_id if it.type == "message" else (it.event_id or 0)
        return (it.timestamp, 0 if it.type == "message" else 1, sec or 0)

    items.sort(key=_sort_key)

    # Apply pagination window:
    #  - with `before`: keep the LAST `limit` items (oldest chunk before cursor).
    #  - else (no filters or `since`): keep the LAST `limit` items (most recent chunk).
    # Then has_more = True if the pre-trim list was longer than limit.
    has_more = len(items) > limit
    if has_more:
        items = items[-limit:]

    return SessionFeedResponse(items=items, has_more=has_more)
```

### Step 4: Ask user to verify

1. Restart uvicorn.
2. Active session with messages + at least one char having recent hp_change events.
3. Browser console:
   ```js
   fetch('http://localhost:8000/sessions/<CODE>/feed?limit=50', {
     headers: { 'X-Telegram-Init-Data': '<devdata>' }
   }).then(r => r.json()).then(console.log)
   ```
4. Verify `items` array has both `type: "message"` and `type: "event"` entries, timestamp-sorted.
5. Test `?since=<ts>` → only new items.
6. Test `?before=<ts>` → older items.
7. Non-owner non-GM calling: heal events should show `description: "<name> si è curato"`; damage passthrough.

### Step 5: Commit

```bash
git add api/routers/sessions.py
git commit -m "$(cat <<'EOF'
feat(api): session feed endpoint with mixed chat + history + redaction

GET /sessions/{code}/feed returns chat messages + allowed-type
character history events for the session, with per-viewer redaction
on hp_change heal/set events. Supports since/before cursor
pagination (mutex) and a limit cap. GM sees all; owners see their
own events unredacted; others see heal → "si è curato" and set →
"ha modificato i PF"; damage passthrough.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Frontend TS types + API client method

**Files:**
- Modify: `webapp/src/types/index.ts`
- Modify: `webapp/src/api/client.ts`

### Step 1: Add types

In `webapp/src/types/index.ts`, append near the other session types:

```ts
export interface SessionFeedItem {
  type: 'message' | 'event'
  timestamp: string

  // message
  message_id?: number | null
  user_id?: number | null
  display_name?: string | null
  role?: string | null
  body?: string | null
  recipient_user_id?: number | null

  // event
  event_id?: number | null
  character_id?: number | null
  character_name?: string | null
  owner_user_id?: number | null
  event_type?: string | null
  description?: string | null
  op?: string | null
}

export interface SessionFeedResponse {
  items: SessionFeedItem[]
  has_more: boolean
}
```

### Step 2: Add API client method

In `webapp/src/api/client.ts`, add to the type imports at top:

```ts
import type {
  // ...existing...
  SessionFeedItem,
  SessionFeedResponse,
} from '@/types'
```

(If only `SessionFeedResponse` is consumed directly, still export both for component use — import only the one used by `api/client.ts` in this file. `SessionFeedItem` will be imported by `SessionFeed.tsx` later.)

Locate the `sessions:` object. Add:

```ts
getFeed: (
  code: string,
  opts?: { since?: string; before?: string; limit?: number }
) => {
  const params = new URLSearchParams()
  if (opts?.since) params.set('since', opts.since)
  if (opts?.before) params.set('before', opts.before)
  if (opts?.limit) params.set('limit', String(opts.limit))
  const q = params.toString()
  return request<SessionFeedResponse>(
    `/sessions/${encodeURIComponent(code)}/feed${q ? `?${q}` : ''}`
  )
},
```

### Step 3: Typecheck

```bash
cd webapp
npx tsc --noEmit
```

Expected: 0 errors.

### Step 4: Commit

```bash
git add webapp/src/types/index.ts webapp/src/api/client.ts
git commit -m "$(cat <<'EOF'
feat(webapp): SessionFeedItem/Response types + api.sessions.getFeed

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Estrarre `EVENT_META` in `webapp/src/lib/eventMeta.ts`

**Files:**
- Create: `webapp/src/lib/eventMeta.ts`
- Modify: `webapp/src/pages/History.tsx`

### Step 1: Create the shared module

Create `webapp/src/lib/eventMeta.ts`:

```ts
import {
  Heart, Moon, Shield, Swords, Gem, Sparkles, Backpack,
  Coins, Zap, Skull, CircleDot, Pin, Target, ShieldAlert,
  FlaskConical, Dices,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

export interface EventMeta {
  icon: LucideIcon
  tone: string
}

export const EVENT_META: Record<string, EventMeta> = {
  hp_change:          { icon: Heart,        tone: 'text-[var(--dnd-crimson-bright)] bg-dnd-surface-raised border-[var(--dnd-crimson)]' },
  rest:               { icon: Moon,         tone: 'text-[var(--dnd-cobalt-bright)] bg-dnd-surface-raised border-[var(--dnd-cobalt)]' },
  ac_change:          { icon: Shield,       tone: 'text-dnd-gold-bright bg-dnd-surface-raised border-dnd-gold' },
  level_change:       { icon: Swords,       tone: 'text-[var(--dnd-amber)] bg-dnd-surface-raised border-[var(--dnd-amber)]' },
  spell_slot_change:  { icon: Gem,          tone: 'text-dnd-arcane-bright bg-dnd-surface-raised border-[var(--dnd-arcane)]' },
  spell_change:       { icon: Sparkles,     tone: 'text-dnd-arcane-bright bg-dnd-surface-raised border-[var(--dnd-arcane)]' },
  bag_change:         { icon: Backpack,     tone: 'text-dnd-gold-bright bg-dnd-surface-raised border-dnd-gold' },
  currency_change:    { icon: Coins,        tone: 'text-[var(--dnd-amber)] bg-dnd-surface-raised border-[var(--dnd-amber)]' },
  ability_change:     { icon: Zap,          tone: 'text-[var(--dnd-amber)] bg-dnd-surface-raised border-[var(--dnd-amber)]' },
  death_save:         { icon: Skull,        tone: 'text-[var(--dnd-crimson-bright)] bg-dnd-surface-raised border-[var(--dnd-crimson)]' },
  condition_change:   { icon: CircleDot,    tone: 'text-[var(--dnd-crimson-bright)] bg-dnd-surface-raised border-[var(--dnd-crimson)]' },
  attack_roll:        { icon: Swords,       tone: 'text-[var(--dnd-crimson-bright)] bg-dnd-surface-raised border-[var(--dnd-crimson)]' },
  skill_roll:         { icon: Target,       tone: 'text-[var(--dnd-cobalt-bright)] bg-dnd-surface-raised border-[var(--dnd-cobalt)]' },
  saving_throw:       { icon: ShieldAlert,  tone: 'text-[var(--dnd-cobalt-bright)] bg-dnd-surface-raised border-[var(--dnd-cobalt)]' },
  concentration_save: { icon: FlaskConical, tone: 'text-dnd-arcane-bright bg-dnd-surface-raised border-[var(--dnd-arcane)]' },
  hit_dice:           { icon: Dices,        tone: 'text-[var(--dnd-emerald-bright)] bg-dnd-surface-raised border-[var(--dnd-emerald)]' },
  other:              { icon: Pin,          tone: 'text-dnd-text-muted bg-dnd-surface-raised border-dnd-border' },
}
```

### Step 2: Update `History.tsx` to import from lib

In `webapp/src/pages/History.tsx`:

1. Remove the inline `EVENT_META` constant and its accompanying lucide imports that are only used for it.

Replace the top import block that currently includes:
```tsx
import {
  Heart, Moon, Shield, Swords, Gem, Sparkles, Backpack,
  Coins, Zap, Skull, CircleDot, Pin, Trash2, BookOpen,
  Target, ShieldAlert, FlaskConical, Dices,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
```

Keep only icons still used in History.tsx directly (likely `Trash2`, `BookOpen`):
```tsx
import { Trash2, BookOpen } from 'lucide-react'
```

Add:
```tsx
import { EVENT_META } from '@/lib/eventMeta'
```

2. Delete the `const EVENT_META: Record<string, ...> = { ... }` block.

3. The rest of the file uses `EVENT_META[entry.event_type]` — no other changes needed.

### Step 3: Typecheck

```bash
cd webapp
npx tsc --noEmit
```

Expected: 0 errors.

### Step 4: Commit

```bash
git add webapp/src/lib/eventMeta.ts webapp/src/pages/History.tsx
git commit -m "$(cat <<'EOF'
refactor(webapp): extract EVENT_META to shared lib/eventMeta.ts

Same data, moved for reuse by SessionFeed (Gruppo H).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: i18n keys Gruppo H

**Files:**
- Modify: `webapp/src/locales/it.json`
- Modify: `webapp/src/locales/en.json`

### Step 1: Add keys to `it.json`

Inside `session` block (at top level, near other session.* keys):

```json
"chat_and_history": "Chat e cronologia",
"feed_empty": "Nessun messaggio o evento ancora",
"load_previous": "Carica precedenti",
"loading_previous": "Caricamento…"
```

Place these siblings of `chat`, `players`, etc. — not inside `identity` or `whisper`.

### Step 2: Mirror in `en.json`

```json
"chat_and_history": "Chat & History",
"feed_empty": "No messages or events yet",
"load_previous": "Load previous",
"loading_previous": "Loading…"
```

### Step 3: Validate JSON

```bash
cd webapp
node -e "require('./src/locales/it.json'); require('./src/locales/en.json'); console.log('ok')"
```

Expected: `ok`.

### Step 4: Commit

```bash
git add webapp/src/locales/it.json webapp/src/locales/en.json
git commit -m "$(cat <<'EOF'
feat(webapp): i18n keys for session chat+history feed (Gruppo H)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Componente `SessionFeed`

**Files:**
- Create: `webapp/src/pages/session/SessionFeed.tsx`

### Step 1: Ensure session sub-directory exists (already does from Gruppo E)

```bash
ls webapp/src/pages/session/
```

### Step 2: Write the component

Create `webapp/src/pages/session/SessionFeed.tsx`:

```tsx
import { useEffect, useMemo, useRef, useState } from 'react'
import { useQueryClient, useMutation } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Lock, Send, Crown, User as UserIcon } from 'lucide-react'
import { api } from '@/api/client'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import type { SessionFeedItem, SessionFeedResponse, SessionParticipant } from '@/types'
import { haptic } from '@/auth/telegram'
import { EVENT_META } from '@/lib/eventMeta'

interface Props {
  code: string
  sessionId: number
  amGm: boolean
  gmUserId: number | null
  myUserId: number
  participants: SessionParticipant[]
}

const POLL_MS = 3000

function formatTime(iso: string) {
  const d = new Date(iso)
  return d.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' })
}

export default function SessionFeed({
  code,
  sessionId,
  amGm,
  gmUserId,
  myUserId,
  participants,
}: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()

  const [items, setItems] = useState<SessionFeedItem[]>([])
  const [hasMoreBefore, setHasMoreBefore] = useState(false)
  const [loadingPrev, setLoadingPrev] = useState(false)
  const [chatInput, setChatInput] = useState('')
  const [whisperTo, setWhisperTo] = useState<number | null>(null)

  const scrollerRef = useRef<HTMLDivElement | null>(null)
  const initialisedRef = useRef(false)

  const oldestTs = items.length > 0 ? items[0].timestamp : null
  const latestTs = items.length > 0 ? items[items.length - 1].timestamp : null

  // Initial fetch + incremental polling
  useEffect(() => {
    let cancelled = false

    async function initial() {
      try {
        const res = await api.sessions.getFeed(code, { limit: 100 })
        if (cancelled) return
        setItems(res.items)
        setHasMoreBefore(res.has_more)
        initialisedRef.current = true
        // initial scroll to bottom
        requestAnimationFrame(() => {
          scrollerRef.current?.scrollTo({ top: scrollerRef.current.scrollHeight })
        })
      } catch {
        /* surface error in UI as empty state for now */
      }
    }

    initial()

    const tick = async () => {
      if (cancelled || !initialisedRef.current) return
      try {
        const since = latestTs ?? undefined
        const res = await api.sessions.getFeed(code, since ? { since, limit: 100 } : { limit: 100 })
        if (cancelled) return
        if (res.items.length > 0) {
          setItems((prev) => {
            const seen = new Set<string>(
              prev.map((it) =>
                it.type === 'message' ? `m:${it.message_id}` : `e:${it.event_id}`,
              ),
            )
            const fresh = res.items.filter((it) => {
              const key = it.type === 'message' ? `m:${it.message_id}` : `e:${it.event_id}`
              return !seen.has(key)
            })
            if (fresh.length === 0) return prev
            const next = [...prev, ...fresh]
            requestAnimationFrame(() => {
              scrollerRef.current?.scrollTo({ top: scrollerRef.current.scrollHeight, behavior: 'smooth' })
            })
            return next
          })
        }
      } catch {
        /* swallow — next tick retries */
      }
    }

    const id = window.setInterval(tick, POLL_MS)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
    // code dep + latestTs dep is load-bearing for the since cursor
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code])

  // Send message
  const sendMutation = useMutation({
    mutationFn: async (body: string) =>
      api.sessions.sendMessage(sessionId, body, whisperTo ?? undefined),
    onSuccess: () => {
      setChatInput('')
      haptic.success()
      // Force immediate refetch so we see our message without waiting 3s.
      qc.invalidateQueries({ queryKey: ['session-feed', code] })
      // Trigger a direct re-poll by nudging state (simplest: call getFeed directly)
      ;(async () => {
        try {
          const res = await api.sessions.getFeed(code, latestTs ? { since: latestTs, limit: 100 } : { limit: 100 })
          setItems((prev) => {
            const seen = new Set<string>(
              prev.map((it) =>
                it.type === 'message' ? `m:${it.message_id}` : `e:${it.event_id}`,
              ),
            )
            const fresh = res.items.filter((it) => {
              const key = it.type === 'message' ? `m:${it.message_id}` : `e:${it.event_id}`
              return !seen.has(key)
            })
            if (fresh.length === 0) return prev
            const next = [...prev, ...fresh]
            requestAnimationFrame(() => {
              scrollerRef.current?.scrollTo({ top: scrollerRef.current.scrollHeight, behavior: 'smooth' })
            })
            return next
          })
        } catch { /* noop */ }
      })()
    },
    onError: () => haptic.error(),
  })

  const loadPrevious = async () => {
    if (!oldestTs || loadingPrev) return
    setLoadingPrev(true)
    try {
      const res: SessionFeedResponse = await api.sessions.getFeed(code, { before: oldestTs, limit: 50 })
      setItems((prev) => [...res.items, ...prev])
      setHasMoreBefore(res.has_more)
    } catch {
      /* noop */
    } finally {
      setLoadingPrev(false)
    }
  }

  const playerParticipants = useMemo(
    () => participants.filter((p) => p.role !== 'game_master'),
    [participants],
  )

  const senderLabel = (it: SessionFeedItem) => {
    if (it.role === 'game_master') return t('session.game_master')
    return it.display_name ?? `#${it.user_id}`
  }

  const recipientName = (rid: number | null | undefined) => {
    if (rid == null) return null
    if (rid === gmUserId) return t('session.game_master')
    const p = participants.find((pp) => pp.user_id === rid)
    return p?.display_name ?? `#${rid}`
  }

  return (
    <Surface variant="elevated">
      {hasMoreBefore && (
        <div className="flex justify-center mb-2">
          <button
            type="button"
            onClick={loadPrevious}
            disabled={loadingPrev}
            className="text-xs font-cinzel uppercase tracking-wider text-dnd-gold-dim hover:text-dnd-gold-bright disabled:opacity-50 px-3 py-1 rounded border border-dnd-border"
          >
            {loadingPrev ? t('session.loading_previous') : t('session.load_previous')}
          </button>
        </div>
      )}

      <div
        ref={scrollerRef}
        className="space-y-2 max-h-[320px] overflow-y-auto pr-1"
      >
        {items.length === 0 ? (
          <p className="text-xs text-dnd-text-faint font-body italic text-center py-4">
            {t('session.feed_empty')}
          </p>
        ) : (
          items.map((it) => {
            if (it.type === 'event') {
              const meta = EVENT_META[it.event_type ?? 'other'] ?? EVENT_META.other
              const Icon = meta.icon
              return (
                <div
                  key={`e-${it.event_id}`}
                  className="flex items-center justify-center gap-2 text-xs italic opacity-80 px-3 py-1.5"
                >
                  <Icon size={12} className={meta.tone.split(' ')[0]} />
                  <span className="font-body text-dnd-text-muted">{it.description}</span>
                  <span className="font-mono text-[10px] text-dnd-text-faint">
                    {formatTime(it.timestamp)}
                  </span>
                </div>
              )
            }

            // message
            const mine = it.user_id === myUserId
            const isWhisper = !!it.recipient_user_id
            const recName = isWhisper ? recipientName(it.recipient_user_id ?? null) : null
            return (
              <div
                key={`m-${it.message_id}`}
                className={`max-w-[80%] rounded-lg px-3 py-2 text-sm font-body
                  ${isWhisper
                    ? 'bg-[var(--dnd-amber)]/15 border border-[var(--dnd-amber)]/40 italic'
                    : mine
                      ? 'ml-auto bg-gradient-gold text-dnd-ink'
                      : 'bg-dnd-surface border border-dnd-border text-dnd-text'}
                  ${mine && isWhisper ? 'ml-auto' : ''}`}
              >
                {(!mine || isWhisper) && (
                  <p className="text-[10px] uppercase tracking-wider opacity-70 mb-0.5 font-cinzel flex items-center gap-1">
                    {isWhisper && <Lock size={10} />}
                    {it.role === 'game_master' && <Crown size={10} />}
                    {it.role === 'player' && !isWhisper && <UserIcon size={10} />}
                    {mine ? t('session.you') : senderLabel(it)}
                    {isWhisper && recName && (
                      <span className="text-[var(--dnd-amber)]">
                        {' '}{t('session.whisper.recipient_prefix', { name: recName })}
                      </span>
                    )}
                  </p>
                )}
                <p className="whitespace-pre-wrap break-words">{it.body}</p>
              </div>
            )
          })
        )}
      </div>

      {amGm ? (
        <div className="flex items-center gap-2 mt-3 mb-2">
          <Lock size={12} className="text-dnd-gold-dim shrink-0" />
          <select
            value={whisperTo ?? ''}
            onChange={(e) => setWhisperTo(e.target.value === '' ? null : Number(e.target.value))}
            className="flex-1 px-2 py-1 rounded bg-dnd-surface border border-dnd-border text-dnd-text font-body text-sm"
          >
            <option value="">{t('session.whisper.broadcast')}</option>
            {playerParticipants.map((p) => (
              <option key={p.user_id} value={p.user_id}>
                {p.display_name ?? `#${p.user_id}`}
              </option>
            ))}
          </select>
        </div>
      ) : (
        <div className="mt-3 mb-2">
          <button
            type="button"
            onClick={() => setWhisperTo(whisperTo === null ? gmUserId : null)}
            disabled={gmUserId === null}
            className={`flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-cinzel uppercase tracking-wider transition-colors
              ${whisperTo !== null
                ? 'bg-[var(--dnd-amber)]/30 text-[var(--dnd-amber)] border border-[var(--dnd-amber)]/60'
                : 'bg-dnd-surface text-dnd-text-muted border border-dnd-border hover:text-dnd-gold-bright'}`}
          >
            <Lock size={12} />
            {t('session.whisper.to_gm')}
          </button>
        </div>
      )}

      <div className="flex items-center gap-2">
        <input
          type="text"
          value={chatInput}
          onChange={(e) => setChatInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && chatInput.trim().length > 0) {
              sendMutation.mutate(chatInput.trim())
            }
          }}
          placeholder={t('session.message_placeholder')}
          className="flex-1 px-3 py-2 rounded bg-dnd-surface border border-dnd-border text-dnd-text font-body text-sm"
        />
        <Button
          variant="primary"
          size="sm"
          onClick={() => chatInput.trim() && sendMutation.mutate(chatInput.trim())}
          disabled={!chatInput.trim() || sendMutation.isPending}
          icon={<Send size={14} />}
        >
          {t('session.send')}
        </Button>
      </div>
    </Surface>
  )
}
```

**Note on `api.sessions.sendMessage`:** verify the signature in `webapp/src/api/client.ts`. Earlier session code uses something like `api.sessions.sendMessage(sessionId, body, recipientUserId)`. If the parameter name differs (e.g., `api.sessions.postMessage(...)`), adapt. Use the exact name that exists in `client.ts` at the time of implementation.

### Step 3: Typecheck

```bash
cd webapp
npx tsc --noEmit
```

Expected: 0 errors.

### Step 4: Commit

```bash
git add webapp/src/pages/session/SessionFeed.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): SessionFeed — unified chat + history feed component

3s polling via since cursor, "Carica precedenti" via before cursor,
send message with whisper target, mixed render (chat bubbles +
system event bubbles styled from EVENT_META).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Integrare `SessionFeed` in `SessionRoom.tsx`

**Files:**
- Modify: `webapp/src/pages/SessionRoom.tsx`

### Step 1: Add import

At top of `webapp/src/pages/SessionRoom.tsx`:

```tsx
import SessionFeed from '@/pages/session/SessionFeed'
```

### Step 2: Remove inline chat state/logic

Delete the following state declarations from the `SessionRoom` body (they move into SessionFeed):

```tsx
const [chatInput, setChatInput] = useState('')
const [whisperTo, setWhisperTo] = useState<number | null>(null)
const [lastSeenMsgId, setLastSeenMsgId] = useState(0)   // if present
const [chatCache, setChatCache] = useState<SessionMessage[]>([])   // if present
const scrollerRef = useRef<HTMLDivElement | null>(null)   // if used only for chat
```

Delete the chat polling `useQuery`/`useEffect` block for `/messages`.
Delete the `sendMutation` definition.
Delete the `playerParticipants` memo if only used for whisper select (SessionFeed redefines internally from props).
Delete unused imports (SessionMessage type, `Send`, `Lock`, `Crown`, `Sparkles` icons if only used in chat — keep those still used elsewhere in the file).

### Step 3: Replace chat `<Surface>` with `<SessionFeed />`

Find the block starting with:
```tsx
<SectionDivider>
  {t('session.chat')}
</SectionDivider>

<Surface variant="elevated">
  <div ref={scrollerRef} ...>
    {/* chat cache render */}
  </div>
  ...
</Surface>
```

Replace entirely with:

```tsx
<SectionDivider>
  {t('session.chat_and_history')}
</SectionDivider>

<SessionFeed
  code={live.code}
  sessionId={live.id}
  amGm={amGm}
  gmUserId={gmUserId}
  myUserId={myUserId}
  participants={live.participants}
/>
```

Verify these vars exist in scope:
- `live.code` (string) — present via GameSessionLive type.
- `live.id` (number) — present.
- `amGm` / `gmUserId` / `myUserId` — already defined above in the component (inspect local vars).
- `live.participants` — present.

### Step 4: Typecheck

```bash
cd webapp
npx tsc --noEmit
```

Expected: 0 errors. Common leftover: unused imports. Remove any flagged.

### Step 5: Ask user to verify

With 2 participants + active session:

1. Open session-room: feed shows existing messages + events mixed.
2. Send message → appears immediately, not after 3s.
3. HP damage from another browser/device: appears as event bubble, description includes numbers (damage = passthrough).
4. HP heal from another user: for non-owner non-GM, appears as `"<name> si è curato"`.
5. GM view: sees raw description for heal too.
6. Whisper: visible only to sender / recipient / GM.
7. "Carica precedenti" button: appears only if `has_more`.
8. Tap "Carica precedenti": older items prepended; scroll position preserved.

### Step 6: Commit

```bash
git add webapp/src/pages/SessionRoom.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): SessionRoom uses SessionFeed for chat+history

Inline chat state + polling + render replaced by <SessionFeed /> — a
dedicated component that merges chat messages and redacted
character history events from the new /feed endpoint.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Build prod + roadmap + commit finale

**Files:**
- Modify: `docs/superpowers/roadmap.md`
- Build: `docs/app/*` (via `npm run build:prod`)

### Step 1: Build prod

```bash
cd webapp
npm run build:prod
```

Script switches `.env.local` to prod URL, runs `tsc && vite build`, restores `.env.local`, stages `docs/app/`.

If it fails on TS: fix and re-run. Do NOT skip.

### Step 2: Update `docs/superpowers/roadmap.md`

Three edits:

**a) Line 5 (Stato globale):** change
```
**Stato globale:** Gruppi A, B, C, D, E, F, G completati e mergeati; H pending.
```
to
```
**Stato globale:** Gruppi A, B, C, D, E, F, G, H completati e mergeati.
```

**b) Row for Gruppo H (around line 22):** change
```
| H | Chat/cronologia integrata | §3 | ⬜ Pending | — |
```
to
```
| H | Chat/cronologia integrata | §3 | ✅ Done (PR #XX merged → main) | `feat/chat-history-gruppo-h` |
```

(`#XX` placeholder — user fills after merge.)

**c) "Ordine consigliato" block (around line 284):** change
```
✅ A → ✅ B → ✅ F → ✅ G → ✅ C → ✅ D → ✅ E → H
```
to
```
✅ A → ✅ B → ✅ F → ✅ G → ✅ C → ✅ D → ✅ E → ✅ H
```

### Step 3: Commit

```bash
git add docs/app/ docs/superpowers/roadmap.md
git commit -m "$(cat <<'EOF'
docs(roadmap): mark Gruppo H as done + prod build

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Step 4: Do NOT push or open PR

User handles manually.

### Step 5: Verify final state

```bash
git log --oneline main..HEAD | head -25
git status
cat webapp/.env.local
```

Confirm:
- HEAD is the docs+build commit.
- Working tree clean (only gitignored untracked files).
- `.env.local` = `VITE_API_BASE_URL=http://localhost:8000`.

### Step 6: End-to-end manual verification

- [ ] `/sessions/{code}/feed` returns mixed items; `since` and `before` work; `limit` capped; 400 if both `since` and `before`.
- [ ] `hp_change` events from DB post-Task 2 have `meta = '{"op": "..."}'`.
- [ ] Legacy `hp_change` events with `meta = NULL` get sensible fallback descriptions when rendered in session-feed for non-owner non-GM.
- [ ] GM in session sees raw description for all events.
- [ ] Owner sees raw description for own events.
- [ ] Other players see "si è curato" / "ha modificato i PF" per redaction mapping; damage passthrough.
- [ ] SessionRoom renders `<SessionFeed />` instead of inline chat.
- [ ] Send message appears immediately.
- [ ] "Carica precedenti" visible only if `has_more`.
- [ ] `/char/:id/history` (Gestore Personaggio) unchanged — still shows full own history.
- [ ] No regression in whisper visibility rules.

---

## Self-review

**Spec coverage:**
- §3 integrated feed → Tasks 3-4 (endpoint) + Task 8 (SessionFeed) + Task 9 (SessionRoom integration).
- §3 "solo sessione corrente" → Task 4 `timestamp >= session.created_at` filter.
- §3 heal redaction → Task 2 (meta) + Task 4 (`_redact_event_description`).
- §3 GM sees all → Task 4 `is_gm` branch.
- §3 Gestore Personaggio cronologia completa invariata → no task touches `/char/:id/history`.
- Carica precedenti → Task 4 `before` cursor + Task 8 button.
- Scelta 5A mixed endpoint → Task 4.

**Placeholder scan:** no TBD/TODO. `#XX` PR placeholder is intentional convention.

**Type consistency:**
- `SessionFeedItem` (Pydantic Task 3) ↔ TS (Task 5): field names identical including `op`, `role`, `recipient_user_id`, `op`.
- `_redact_event_description` signature (Task 4) uses `character_name: str`, `viewer_user_id: int`, `owner_user_id: int`, `is_gm: bool` — consistent with caller in endpoint.
- `EVENT_META` export (Task 6) imported by `SessionFeed` (Task 8) and `History.tsx` (Task 6).
- Polling key `['session-feed', code]` — `qc.invalidateQueries` in send-mutation (Task 8) uses prefix match (`['session-feed', code]`) — correct.

**Edge cases coverage:**
- `since` + `before` both → 400 (Task 4 explicit check).
- Empty feed → placeholder (Task 8 `items.length === 0`).
- Whisper filter server-side (Task 4).
- Legacy meta fallback heuristic (Task 4).
- Character cascade delete → events disappear (FK cascade already set).
- Tie-breaker sort stability (Task 4 `_sort_key`).

**Risks:**
- `sendMutation.mutationFn` references `api.sessions.sendMessage` — verify signature matches actual client (Task 8 step has note). If `sendMessage` accepts `(sessionId, body, recipientUserId?)` as positional, fine. If different, adapt inline during implementation.
- The refetch-after-send implementation inside `onSuccess` duplicates a bit of the `tick` logic. Acceptable for simplicity.

No gaps.
