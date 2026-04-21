# Session Room UX & Privacy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship seven UX/privacy improvements to the live session room: clickable own character, HP/armor privacy buckets, GM↔player whispers, GM-only invite-code display, gated join button, correct message sender labels, auto-leave on character delete. Plus carry: interpolated exhaustion pill in `ParticipantRow`.

**Architecture:** Additive DB migration on `session_messages` (two nullable columns + index). Per-viewer redaction layer in the FastAPI session routes computing `hp_bucket` + `armor_category` and nulling raw stats for non-owners / non-GM. New whisper pathway using `recipient_user_id` with GM-only-involved validation. Frontend adds whisper UI, redacted snapshot rendering, code-hiding for players, and a gated join button.

**Tech Stack:** FastAPI + SQLAlchemy (async, aiosqlite), Pydantic v2, React 18 + TanStack Query + react-i18next + framer-motion + lucide-react + Tailwind, Vite build, Telegram Mini App shell.

---

## Environment notes

- Start from a fresh feature branch `feat/session-room-ux-privacy` branched off of **main** (not off of `docs/session-and-conditions-specs`, because this plan depends on Plan B's `formatCondition` helper being merged first). If Plan B hasn't landed to main yet, branch off the merged-PR commit or cherry-pick Plan B's helper commit.
- The user runs Python commands (`uv run …`) from **Windows PowerShell**. If the agent is inside WSL, **do not run `uv sync` / `uv run`** — per `CLAUDE.md` it corrupts `.venv`. Ask the user to restart the API instead.
- No automated test suite exists. Verification per task is TypeScript `tsc --noEmit` + `curl` checks against the running API + two-browser manual testing (Chrome + incognito or Firefox) with `DEV_USER_ID` swap.
- Before the final PR commit, run `cd webapp && npm run build:prod` to refresh `docs/app/`.

---

## File structure

### Backend (FastAPI + SQLAlchemy)
| File | Action | Responsibility |
|---|---|---|
| `core/db/models.py` | Modify | Add `recipient_user_id`, `sender_display_name` columns to `SessionMessage`. |
| `core/db/engine.py` | Modify | Register the new columns in `_MIGRATIONS` and create index after `_migrate_schema` runs. |
| `api/schemas/session.py` | Modify | Make raw stats `Optional` on `CharacterLiveSnapshot`, add `hp_bucket`/`armor_category` fields, extend `SessionMessageCreate`/`SessionMessageRead`. |
| `api/routers/sessions.py` | Modify | Per-viewer redaction in `/live`, whisper validation + `sender_display_name` capture in POST `/messages`, visibility filter on GET `/messages`. |
| `api/routers/characters.py` | Modify | Auto-leave active session when deleting a character. |
| `core/utils/session_view.py` | Create | Pure helpers `hp_bucket(char)` + `armor_category(char)` — kept in `core/` so they stay portable. |

### Frontend (React + Vite)
| File | Action | Responsibility |
|---|---|---|
| `webapp/src/types/index.ts` | Modify | `CharacterLiveSnapshot` fields nullable + `hp_bucket`/`armor_category`; `SessionMessage` gains whisper fields. |
| `webapp/src/api/client.ts` | Modify | `sendMessage` accepts optional `recipientUserId`. |
| `webapp/src/locales/it.json` | Modify | New `session.hp_bucket.*`, `session.armor_category.*`, `session.whisper.*`, `session.unknown_sender` keys. |
| `webapp/src/locales/en.json` | Modify | Same keys in English. |
| `webapp/src/pages/SessionRoom.tsx` | Modify | Hide code for non-GM, `ParticipantRow` redacted render + `isOwn` click, chat sender label, whisper UI. |
| `webapp/src/pages/SessionJoin.tsx` | Modify | Disable join button until code + character both valid. |

---

## Task 1: DB schema — add whisper columns to `SessionMessage`

**Files:**
- Modify: `core/db/models.py` (around lines 555-569, the `SessionMessage` class)
- Modify: `core/db/engine.py` (extend `_MIGRATIONS` and `_migrate_schema`)

- [ ] **Step 1: Extend the `SessionMessage` SQLAlchemy model**

In `core/db/models.py`, the `SessionMessage` class currently ends with:

```python
class SessionMessage(Base):
    """A chat message exchanged inside a game session."""

    __tablename__ = "session_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("game_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    role: Mapped[str] = mapped_column(Enum(SessionRole), nullable=False)
    body: Mapped[str] = mapped_column(String(1000), nullable=False)
    sent_at: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    session: Mapped["GameSession"] = relationship(back_populates="messages")
```

Add two new columns before the `session:` relationship:

```python
    recipient_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, index=True
    )
    sender_display_name: Mapped[Optional[str]] = mapped_column(
        String(120), nullable=True
    )

    session: Mapped["GameSession"] = relationship(back_populates="messages")
```

`Optional` and `BigInteger` are already imported at the top of the file.

- [ ] **Step 2: Register the additive column migrations**

In `core/db/engine.py`, append to the `_MIGRATIONS` list (before the closing `]`):

```python
    # Session whisper support
    ("session_messages", "recipient_user_id", "BIGINT", None),
    ("session_messages", "sender_display_name", "VARCHAR(120)", None),
```

- [ ] **Step 3: Create the recipient index inside `_migrate_schema`**

Still in `core/db/engine.py`, inside the `_migrate_schema` function, after the existing migration loop (just before `for table, column in _DROP_COLUMNS:`), add:

```python
    # Ad-hoc index for whisper filter queries
    try:
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_session_messages_recipient "
            "ON session_messages(recipient_user_id)"
        ))
    except Exception as exc:
        logger.warning("CREATE INDEX failed for session_messages.recipient_user_id: %s", exc)
```

`text` is already imported at the top.

- [ ] **Step 4: Ask the user to restart the API and confirm migration logs**

Prompt the user:

> Please restart the API in PowerShell:
> ```
> uv run uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
> ```
> and paste the startup log lines that contain "Migrating:" or "CREATE INDEX".

Expected lines:
```
Migrating: ALTER TABLE session_messages ADD COLUMN recipient_user_id BIGINT
Migrating: ALTER TABLE session_messages ADD COLUMN sender_display_name VARCHAR(120)
```
(Index line is quiet unless already existing — that's fine.)

- [ ] **Step 5: Verify idempotency by asking the user to restart a second time**

On a second restart the Migrating lines must NOT appear (columns already present). If they do, the duplicate-column error means `_MIGRATIONS` mis-registered or `column_cache` didn't reload — investigate before proceeding.

- [ ] **Step 6: Commit**

```bash
git add core/db/models.py core/db/engine.py
git commit -m "feat(api): add whisper columns + index to session_messages"
```

---

## Task 2: API — per-viewer snapshot schema

**Files:**
- Modify: `api/schemas/session.py`

- [ ] **Step 1: Loosen snapshot fields + add new bucket / category**

Replace the `CharacterLiveSnapshot` class (currently lines 33-48 of `api/schemas/session.py`):

```python
class CharacterLiveSnapshot(BaseModel):
    """Lightweight character state shown in the live session view.

    Raw HP/AC/death_saves fields are nullable: they are populated for the GM
    and for the character's owner, but redacted to None for other players.
    hp_bucket / armor_category are always populated and carry the redacted
    summary.
    """

    id: int
    name: str
    race: Optional[str] = None
    class_summary: str = ""
    total_level: int = 0
    hit_points: Optional[int] = None
    current_hit_points: Optional[int] = None
    temp_hp: Optional[int] = None
    ac: Optional[int] = None
    conditions: Optional[dict[str, Any]] = None
    death_saves: Optional[dict[str, Any]] = None
    heroic_inspiration: bool = False
    last_roll: Optional[dict[str, Any]] = None
    hp_bucket: Optional[str] = None
    armor_category: Optional[str] = None
```

- [ ] **Step 2: Extend the whisper schemas**

Replace `SessionMessageCreate` and `SessionMessageRead` (currently lines 19-30):

```python
class SessionMessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=1000)
    recipient_user_id: Optional[int] = None


class SessionMessageRead(BaseModel):
    id: int
    user_id: int
    role: str
    body: str
    sent_at: str
    recipient_user_id: Optional[int] = None
    sender_display_name: Optional[str] = None

    model_config = {"from_attributes": True}
```

- [ ] **Step 3: Confirm schemas import cleanly**

Ask the user to run in PowerShell:
```
uv run python -c "from api.schemas.session import CharacterLiveSnapshot, SessionMessageCreate, SessionMessageRead; print('ok')"
```
Expected output: `ok`.

- [ ] **Step 4: Commit**

```bash
git add api/schemas/session.py
git commit -m "feat(api): extend session schemas with whisper + hp bucket fields"
```

---

## Task 3: Backend helper — `hp_bucket` + `armor_category`

**Files:**
- Create: `core/utils/session_view.py`

- [ ] **Step 1: Create the helper module**

```python
"""Pure helpers computing redacted session-view properties for a Character.

These helpers are consumed by the FastAPI session endpoints when serving the
privacy-redacted live snapshot to non-GM, non-owner viewers. They live in
core/utils/ so they can be shared by future bot/webapp code without a
FastAPI or Pydantic dependency.
"""

from __future__ import annotations

import json
from typing import Literal

from core.db.models import Character

HpBucket = Literal["healthy", "lightly_wounded", "badly_wounded", "dying", "dead"]
ArmorCategory = Literal["unarmored", "light", "medium", "heavy"]


def hp_bucket(char: Character) -> HpBucket:
    """Return the bucket label that summarises the character's HP."""
    death_saves = char.death_saves or {}
    if int(death_saves.get("failures", 0) or 0) >= 3:
        return "dead"
    current = int(char.current_hit_points or 0)
    if current <= 0:
        return "dying"
    total = int(char.hit_points or 0)
    if total <= 0:
        return "healthy"
    pct = (current / total) * 100
    if pct >= 76:
        return "healthy"
    if pct >= 51:
        return "lightly_wounded"
    return "badly_wounded"


def armor_category(char: Character) -> ArmorCategory:
    """Return the category of the currently equipped armor, or 'unarmored'."""
    for item in char.items or []:
        if item.item_type != "armor" or not item.is_equipped:
            continue
        raw = item.item_metadata or ""
        if not raw:
            continue
        try:
            meta = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        category = meta.get("armor_type")
        if category in ("light", "medium", "heavy"):
            return category
        return "unarmored"
    return "unarmored"
```

- [ ] **Step 2: Confirm the module imports**

Ask the user to run:
```
uv run python -c "from core.utils.session_view import hp_bucket, armor_category; print('ok')"
```
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add core/utils/session_view.py
git commit -m "feat(core): add hp_bucket and armor_category session helpers"
```

---

## Task 4: API — redact `/live` per viewer

**Files:**
- Modify: `api/routers/sessions.py` (helper `_load_live_characters` + endpoint `get_session_live`)

- [ ] **Step 1: Update imports and extend `_load_live_characters`**

At the top of `api/routers/sessions.py`, add the helper imports:

```python
from core.utils.session_view import hp_bucket, armor_category
```

Change the selectinload to also fetch items (needed for `armor_category`). Replace the existing `_load_live_characters` function body:

```python
async def _load_live_characters(
    char_ids: list[int], db: AsyncSession
) -> dict[int, dict]:
    """Return raw snapshot dicts keyed by character id.

    Full (un-redacted) data is returned here; redaction happens per viewer
    in get_session_live.
    """
    if not char_ids:
        return {}
    result = await db.execute(
        select(Character)
        .options(
            selectinload(Character.classes),
            selectinload(Character.items),
        )
        .where(Character.id.in_(char_ids))
    )
    out: dict[int, dict] = {}
    for char in result.scalars().all():
        last_roll = None
        history = char.rolls_history or []
        if history and isinstance(history[-1], dict):
            last_roll = history[-1]
        out[char.id] = dict(
            id=char.id,
            user_id=char.user_id,
            name=char.name,
            race=char.race,
            class_summary=char.class_summary,
            total_level=char.total_level,
            hit_points=char.hit_points,
            current_hit_points=char.current_hit_points,
            temp_hp=char.temp_hp or 0,
            ac=char.ac,
            conditions=char.conditions or {},
            death_saves=char.death_saves or {},
            heroic_inspiration=bool(char.heroic_inspiration),
            last_roll=last_roll,
            hp_bucket=hp_bucket(char),
            armor_category=armor_category(char),
        )
    return out
```

Note the return type changed from `list[CharacterLiveSnapshot]` to `dict[int, dict]` — this removes the Pydantic conversion so the endpoint can redact before serialising. Remove the `CharacterLiveSnapshot` import from the top if it's no longer used elsewhere in the file (it *is* still used by the endpoint response model — keep it).

- [ ] **Step 2: Rewrite `get_session_live` to redact per viewer**

Replace the endpoint (currently lines 260-292):

```python
@router.get("/{session_id}/live", response_model=GameSessionLiveRead)
async def get_session_live(
    session_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GameSessionLiveRead:
    session = await _load_session(session_id, db)
    _assert_participant(session, user_id)

    char_ids = [p.character_id for p in session.participants if p.character_id is not None]
    raw_map = await _load_live_characters(char_ids, db)
    viewer_is_gm = (user_id == session.gm_user_id)

    snapshots: list[CharacterLiveSnapshot] = []
    for raw in raw_map.values():
        owner_id = raw["user_id"]
        full = viewer_is_gm or (owner_id == user_id)
        if full:
            snapshots.append(CharacterLiveSnapshot(
                id=raw["id"],
                name=raw["name"],
                race=raw["race"],
                class_summary=raw["class_summary"],
                total_level=raw["total_level"],
                hit_points=raw["hit_points"],
                current_hit_points=raw["current_hit_points"],
                temp_hp=raw["temp_hp"],
                ac=raw["ac"],
                conditions=raw["conditions"],
                death_saves=raw["death_saves"],
                heroic_inspiration=raw["heroic_inspiration"],
                last_roll=raw["last_roll"],
                hp_bucket=raw["hp_bucket"],
                armor_category=raw["armor_category"],
            ))
        else:
            snapshots.append(CharacterLiveSnapshot(
                id=raw["id"],
                name=raw["name"],
                race=raw["race"],
                class_summary=raw["class_summary"],
                total_level=raw["total_level"],
                hit_points=None,
                current_hit_points=None,
                temp_hp=None,
                ac=None,
                conditions=raw["conditions"],
                death_saves=None,
                heroic_inspiration=raw["heroic_inspiration"],
                last_roll=raw["last_roll"],
                hp_bucket=raw["hp_bucket"],
                armor_category=raw["armor_category"],
            ))

    if session.status == SessionStatus.ACTIVE:
        _touch(session)

    return GameSessionLiveRead(
        id=session.id,
        code=session.code,
        gm_user_id=session.gm_user_id,
        status=session.status.value if hasattr(session.status, "value") else str(session.status),
        title=session.title,
        created_at=session.created_at,
        last_activity_at=session.last_activity_at,
        closed_at=session.closed_at,
        participants=[
            {
                "user_id": p.user_id,
                "role": p.role.value if hasattr(p.role, "value") else str(p.role),
                "character_id": p.character_id,
                "display_name": p.display_name,
                "joined_at": p.joined_at,
            }
            for p in session.participants
        ],
        live_characters=snapshots,
    )
```

- [ ] **Step 3: Ask the user to restart the API and verify with curl**

After the API reloads, the user can copy the dev init-data from a logged-in browser session (F12 → Network → any request → `X-Telegram-Init-Data` header), OR use the `DEV_USER_ID` bypass by logging in twice.

Minimal smoke check (no auth, should 401/403 — but confirms route exists):

```bash
curl -i http://127.0.0.1:8000/sessions/1/live
```

Expected: `401` or `403`, NOT `500`.

Full verification requires a running two-browser session — defer to Task 13's manual test plan.

- [ ] **Step 4: Commit**

```bash
git add api/routers/sessions.py
git commit -m "feat(api): redact live snapshot for non-owner non-GM viewers"
```

---

## Task 5: API — whisper validation on POST `/messages`

**Files:**
- Modify: `api/routers/sessions.py` (the `post_message` endpoint)

- [ ] **Step 1: Replace `post_message` with the validating version**

Currently (lines 352-377):

```python
@router.post(
    "/{session_id}/messages",
    response_model=SessionMessageRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_message(
    session_id: int,
    body: SessionMessageCreate,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SessionMessage:
    session = await _load_session(session_id, db)
    participant = _assert_participant(session, user_id)
    if session.status != SessionStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Session is closed")
    msg = SessionMessage(
        session_id=session_id,
        user_id=user_id,
        role=participant.role,
        body=body.body.strip(),
        sent_at=_now(),
    )
    db.add(msg)
    _touch(session)
    await db.flush()
    return msg
```

Replace with:

```python
@router.post(
    "/{session_id}/messages",
    response_model=SessionMessageRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_message(
    session_id: int,
    body: SessionMessageCreate,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SessionMessage:
    session = await _load_session(session_id, db)
    sender = _assert_participant(session, user_id)
    if session.status != SessionStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Session is closed")

    recipient_id: Optional[int] = body.recipient_user_id
    if recipient_id is not None:
        recipient = next((p for p in session.participants if p.user_id == recipient_id), None)
        if recipient is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Recipient not in session")
        if recipient_id == user_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot whisper to yourself")
        if sender.role != SessionRole.GAME_MASTER and recipient.role != SessionRole.GAME_MASTER:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Whispers are GM-only")

    if sender.role == SessionRole.GAME_MASTER:
        sender_display_name = "__GM__"
    else:
        sender_display_name = sender.display_name or f"#{user_id}"

    msg = SessionMessage(
        session_id=session_id,
        user_id=user_id,
        role=sender.role,
        body=body.body.strip(),
        sent_at=_now(),
        recipient_user_id=recipient_id,
        sender_display_name=sender_display_name,
    )
    db.add(msg)
    _touch(session)
    await db.flush()
    return msg
```

- [ ] **Step 2: Smoke-test the whisper validation with curl**

Ask the user to: (a) have an active session with a GM and at least one player; (b) copy the init-data from the GM's browser tab Network pane; (c) substitute `<SESSION_ID>`, `<INIT_DATA>`, and `<PLAYER_USER_ID>` and run:

```bash
# valid GM → player whisper
curl -X POST -H "X-Telegram-Init-Data: <INIT_DATA>" -H "Content-Type: application/json" \
  -d '{"body":"psst","recipient_user_id":<PLAYER_USER_ID>}' \
  http://127.0.0.1:8000/sessions/<SESSION_ID>/messages
# expect 201, body includes sender_display_name="__GM__", recipient_user_id=<PLAYER_USER_ID>

# self-whisper → 400
curl -X POST -H "X-Telegram-Init-Data: <INIT_DATA>" -H "Content-Type: application/json" \
  -d '{"body":"psst","recipient_user_id":<GM_USER_ID>}' \
  http://127.0.0.1:8000/sessions/<SESSION_ID>/messages
# expect 400 "Cannot whisper to yourself"

# player-to-player whisper (using player A's init-data, recipient = player B) → 403
# (test this from the second browser tab)
```

- [ ] **Step 3: Commit**

```bash
git add api/routers/sessions.py
git commit -m "feat(api): validate and record whisper recipient on POST /messages"
```

---

## Task 6: API — whisper visibility filter on GET `/messages`

**Files:**
- Modify: `api/routers/sessions.py` (the `list_messages` endpoint)

- [ ] **Step 1: Update `list_messages` query**

Currently (lines 334-349):

```python
@router.get("/{session_id}/messages", response_model=list[SessionMessageRead])
async def list_messages(
    session_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    after_id: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[SessionMessage]:
    session = await _load_session(session_id, db)
    _assert_participant(session, user_id)
    stmt = select(SessionMessage).where(SessionMessage.session_id == session_id)
    if after_id > 0:
        stmt = stmt.where(SessionMessage.id > after_id)
    stmt = stmt.order_by(SessionMessage.id.asc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())
```

Replace with:

```python
from sqlalchemy import or_  # (add to existing sqlalchemy imports at top if not present)

@router.get("/{session_id}/messages", response_model=list[SessionMessageRead])
async def list_messages(
    session_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    after_id: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[SessionMessage]:
    session = await _load_session(session_id, db)
    _assert_participant(session, user_id)
    stmt = (
        select(SessionMessage)
        .where(SessionMessage.session_id == session_id)
        .where(
            or_(
                SessionMessage.recipient_user_id.is_(None),
                SessionMessage.recipient_user_id == user_id,
                SessionMessage.user_id == user_id,
            )
        )
    )
    if after_id > 0:
        stmt = stmt.where(SessionMessage.id > after_id)
    stmt = stmt.order_by(SessionMessage.id.asc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())
```

(Note: `or_` is likely already imported; if not, add it to the `from sqlalchemy import …` line.)

- [ ] **Step 2: Verify whisper isolation with curl**

After sending a GM→playerA whisper from Task 5:

```bash
# GM lists messages → should include the whisper row
curl -H "X-Telegram-Init-Data: <GM_INIT_DATA>" \
  http://127.0.0.1:8000/sessions/<SESSION_ID>/messages

# Player B lists messages → whisper row MUST NOT appear
curl -H "X-Telegram-Init-Data: <PLAYER_B_INIT_DATA>" \
  http://127.0.0.1:8000/sessions/<SESSION_ID>/messages
```

- [ ] **Step 3: Commit**

```bash
git add api/routers/sessions.py
git commit -m "feat(api): filter whispers by recipient/sender in GET /messages"
```

---

## Task 7: API — character delete auto-leaves active session

**Files:**
- Modify: `api/routers/characters.py` (the `delete_character` endpoint)

- [ ] **Step 1: Add imports at the top of the file**

After the existing `from core.db.models import (…)` block, append `GameSession`, `SessionParticipant`, `SessionStatus`:

```python
from core.db.models import (
    AbilityScore,
    ABILITY_NAMES,
    Character,
    CharacterClass,
    CharacterHistory,
    ClassResource,
    Currency,
    GameSession,
    SessionParticipant,
    SessionStatus,
)
```

- [ ] **Step 2: Rewrite `delete_character`**

Currently (lines 195-202):

```python
@router.delete("/{char_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_character(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    char = await _get_owned(char_id, user_id, session)
    await session.delete(char)
```

Replace with:

```python
@router.delete("/{char_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_character(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    char = await _get_owned(char_id, user_id, session)

    # Auto-leave any active session where this character is pinned as a player.
    # GM participants have character_id=None so they're never matched here.
    participant_q = (
        select(SessionParticipant)
        .join(GameSession, GameSession.id == SessionParticipant.session_id)
        .where(
            SessionParticipant.user_id == user_id,
            SessionParticipant.character_id == char.id,
            GameSession.status == SessionStatus.ACTIVE,
        )
    )
    participant = (await session.execute(participant_q)).scalar_one_or_none()
    if participant is not None:
        game_session = await session.get(GameSession, participant.session_id)
        await session.delete(participant)
        if game_session is not None:
            game_session.last_activity_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M")

    await session.delete(char)
```

- [ ] **Step 3: Verify with curl**

Ask the user: (a) log in as player in an active session, (b) `DELETE /characters/{id}` using that character's id, (c) hit `GET /sessions/me` — should now return `null` (user is no longer in any active session).

- [ ] **Step 4: Commit**

```bash
git add api/routers/characters.py
git commit -m "feat(api): auto-leave active session when deleting character"
```

---

## Task 8: Frontend — extend TypeScript types

**Files:**
- Modify: `webapp/src/types/index.ts`

- [ ] **Step 1: Extend `CharacterLiveSnapshot` (currently lines 190-204)**

Replace:

```ts
export interface CharacterLiveSnapshot {
  id: number
  name: string
  race?: string | null
  class_summary: string
  total_level: number
  hit_points: number
  current_hit_points: number
  temp_hp: number
  ac: number
  conditions?: Record<string, unknown>
  death_saves?: Record<string, unknown>
  heroic_inspiration: boolean
  last_roll?: DiceRollResult | null
}
```

With:

```ts
export type HpBucket = 'healthy' | 'lightly_wounded' | 'badly_wounded' | 'dying' | 'dead'
export type ArmorCategory = 'unarmored' | 'light' | 'medium' | 'heavy'

export interface CharacterLiveSnapshot {
  id: number
  name: string
  race?: string | null
  class_summary: string
  total_level: number
  hit_points: number | null
  current_hit_points: number | null
  temp_hp: number | null
  ac: number | null
  conditions?: Record<string, unknown> | null
  death_saves?: Record<string, unknown> | null
  heroic_inspiration: boolean
  last_roll?: DiceRollResult | null
  hp_bucket: HpBucket | null
  armor_category: ArmorCategory | null
}
```

- [ ] **Step 2: Extend `SessionMessage` (currently lines 210-216)**

Replace:

```ts
export interface SessionMessage {
  id: number
  user_id: number
  role: SessionRole
  body: string
  sent_at: string
}
```

With:

```ts
export interface SessionMessage {
  id: number
  user_id: number
  role: SessionRole
  body: string
  sent_at: string
  recipient_user_id?: number | null
  sender_display_name?: string | null
}
```

- [ ] **Step 3: Type-check**

```bash
cd webapp && npx tsc --noEmit
```

Expected: errors on the existing SessionRoom code that reads `hit_points / ac` without null-checking — that's expected. These are fixed in later tasks. For now, make sure the errors are ONLY about null-checks, nothing else.

- [ ] **Step 4: Commit**

```bash
git add webapp/src/types/index.ts
git commit -m "feat(webapp): extend session types with whisper + bucket fields"
```

---

## Task 9: Frontend — client `sendMessage` signature

**Files:**
- Modify: `webapp/src/api/client.ts` (the `sessions.sendMessage` entry around line 483)

- [ ] **Step 1: Update signature**

Currently:

```ts
    sendMessage: (id: number, body: string) =>
      request<SessionMessage>(`/sessions/${id}/messages`, {
        method: 'POST',
        body: JSON.stringify({ body }),
      }),
```

Replace with:

```ts
    sendMessage: (id: number, body: string, recipientUserId?: number | null) =>
      request<SessionMessage>(`/sessions/${id}/messages`, {
        method: 'POST',
        body: JSON.stringify({
          body,
          recipient_user_id: recipientUserId ?? null,
        }),
      }),
```

- [ ] **Step 2: Type-check**

```bash
cd webapp && npx tsc --noEmit
```

Existing callers pass only 2 args — still valid because the 3rd is optional.

- [ ] **Step 3: Commit**

```bash
git add webapp/src/api/client.ts
git commit -m "feat(webapp): accept optional whisper recipient in sendMessage"
```

---

## Task 10: Frontend — i18n keys for session room

**Files:**
- Modify: `webapp/src/locales/it.json`
- Modify: `webapp/src/locales/en.json`

- [ ] **Step 1: Add new keys to the Italian `session` block**

Find the closing `}` of the `"session"` object in `webapp/src/locales/it.json` (shortly after `"closed_notice"`). Insert new keys before it. The existing last entry may end `"closed_notice": "La sessione è stata chiusa"`. Add after it:

```jsonc
    "unknown_sender": "Sconosciuto",
    "hp_bucket": {
      "healthy": "In salute",
      "lightly_wounded": "Lievemente ferito",
      "badly_wounded": "Gravemente ferito",
      "dying": "Morente",
      "dead": "Morto"
    },
    "armor_category": {
      "unarmored": "Senza armatura",
      "light": "Armatura leggera",
      "medium": "Armatura media",
      "heavy": "Armatura pesante"
    },
    "whisper": {
      "to_gm": "Sussurra al GM",
      "broadcast": "Tutti",
      "recipient_prefix": "→ {{name}}"
    }
```

Keep a trailing comma on the preceding entry if it didn't already have one.

- [ ] **Step 2: Add the same keys in English `webapp/src/locales/en.json`**

```jsonc
    "unknown_sender": "Unknown",
    "hp_bucket": {
      "healthy": "Healthy",
      "lightly_wounded": "Lightly wounded",
      "badly_wounded": "Badly wounded",
      "dying": "Dying",
      "dead": "Dead"
    },
    "armor_category": {
      "unarmored": "Unarmored",
      "light": "Light armor",
      "medium": "Medium armor",
      "heavy": "Heavy armor"
    },
    "whisper": {
      "to_gm": "Whisper to GM",
      "broadcast": "Everyone",
      "recipient_prefix": "→ {{name}}"
    }
```

- [ ] **Step 3: Validate JSON**

```bash
node -e "JSON.parse(require('fs').readFileSync('webapp/src/locales/it.json','utf8'))"
node -e "JSON.parse(require('fs').readFileSync('webapp/src/locales/en.json','utf8'))"
```

Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add webapp/src/locales/it.json webapp/src/locales/en.json
git commit -m "feat(webapp): add i18n keys for session privacy + whispers"
```

---

## Task 11: Frontend — SessionRoom hero hides code from players

**Files:**
- Modify: `webapp/src/pages/SessionRoom.tsx` (around lines 242-256, the `Surface variant="sigil"` hero block)

- [ ] **Step 1: Wrap the hero block in a GM check**

Find:

```tsx
<Surface variant="sigil" ornamented>
  <div className="text-center">
    <p className="text-xs uppercase tracking-widest text-dnd-gold-dim font-cinzel">
      {t('session.code_label')}
    </p>
    <p className="font-display font-bold text-3xl text-dnd-gold-bright tracking-[0.3em] mt-1">
      {live.code}
    </p>
    {live.title && (
      <p className="text-sm text-dnd-text-muted font-body italic mt-1">
        {live.title}
      </p>
    )}
  </div>
</Surface>
```

Replace with:

```tsx
{amGm ? (
  <Surface variant="sigil" ornamented>
    <div className="text-center">
      <p className="text-xs uppercase tracking-widest text-dnd-gold-dim font-cinzel">
        {t('session.code_label')}
      </p>
      <p className="font-display font-bold text-3xl text-dnd-gold-bright tracking-[0.3em] mt-1">
        {live.code}
      </p>
      {live.title && (
        <p className="text-sm text-dnd-text-muted font-body italic mt-1">
          {live.title}
        </p>
      )}
    </div>
  </Surface>
) : (
  <Surface variant="sigil" ornamented>
    <div className="text-center">
      <p className="text-xs uppercase tracking-widest text-dnd-gold-dim font-cinzel">
        {t('session.role_player')}
      </p>
      <p className="font-display font-bold text-xl text-dnd-gold-bright mt-1">
        {live.title || t('session.active_session_banner')}
      </p>
    </div>
  </Surface>
)}
```

- [ ] **Step 2: Type-check**

```bash
cd webapp && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add webapp/src/pages/SessionRoom.tsx
git commit -m "feat(webapp): hide invite code from non-GM viewers"
```

---

## Task 12: Frontend — `ParticipantRow` refactor (isOwn click + redacted render)

**Files:**
- Modify: `webapp/src/pages/SessionRoom.tsx` (the `ParticipantRow` component + the mapping call site)

This is the biggest frontend change. ParticipantRow becomes: outer `div` → clickable `<button>` wrapper only when `isOwn`, body layout moved into the wrapper.

- [ ] **Step 1: Add imports**

At the top of the file, `useNavigate` is already imported. `formatCondition` needs to come from the new shared module. Extend the imports:

```tsx
import { formatCondition } from '@/lib/conditions'
```

(Assumes Plan B has landed; if not, copy the helper inline into this file and remove the import.)

- [ ] **Step 2: Replace `conditionLabels` helper**

Replace the existing helper at the top of the file:

```ts
function conditionLabels(conditions?: Record<string, unknown>): string[] {
  if (!conditions) return []
  return Object.entries(conditions)
    .filter(([, v]) => Boolean(v))
    .map(([k, v]) => {
      if (typeof v === 'number' && v > 0) return `${k} ${v}`
      return k
    })
}
```

with an i18n-aware version using `formatCondition` (note the hook access — we'll need `t`, so this becomes a function that takes `t`):

```ts
import type { TFunction } from 'i18next'

function conditionLabels(
  conditions: Record<string, unknown> | null | undefined,
  t: TFunction,
): string[] {
  if (!conditions) return []
  return Object.entries(conditions)
    .filter(([, v]) => Boolean(v))
    .map(([key, val]) => formatCondition(key, val, t))
}
```

- [ ] **Step 3: Rewrite `ParticipantRow`**

Replace the entire `ParticipantRow` component (lines 25-99 of the original file):

```tsx
function ParticipantRow({
  participant,
  snapshot,
  isGm,
  isMe,
  isOwn,
  onOwnClick,
  t,
}: {
  participant: SessionParticipant
  snapshot?: CharacterLiveSnapshot
  isGm: boolean
  isMe: boolean
  isOwn: boolean
  onOwnClick: (charId: number) => void
  t: TFunction
}) {
  const roleIcon = isGm
    ? <Crown size={14} className="text-dnd-gold-bright" />
    : <User size={14} className="text-dnd-text-muted" />

  const redacted = !!snapshot && snapshot.hit_points === null
  const hpPct = snapshot && !redacted && (snapshot.hit_points ?? 0) > 0
    ? Math.max(0, Math.min(100, Math.round(
        ((snapshot.current_hit_points ?? 0) / (snapshot.hit_points ?? 1)) * 100
      )))
    : 0
  const conds = conditionLabels(snapshot?.conditions, t)

  const bucketColorClass: Record<string, string> = {
    healthy:          'bg-[var(--dnd-emerald-bright)]',
    lightly_wounded:  'bg-dnd-gold-bright',
    badly_wounded:    'bg-[var(--dnd-amber)]',
    dying:            'bg-[var(--dnd-crimson-bright)]',
    dead:             'bg-black',
  }

  const handleClick = () => {
    if (isOwn && snapshot) onOwnClick(snapshot.id)
  }

  const Wrapper: any = isOwn ? 'button' : 'div'
  const wrapperProps = isOwn
    ? { type: 'button', onClick: handleClick, className: 'w-full text-left cursor-pointer' }
    : {}

  return (
    <Wrapper {...wrapperProps}>
      <div className={`rounded-lg border p-3 transition-colors
        ${isMe ? 'border-dnd-gold bg-dnd-surface-raised' : 'border-dnd-border bg-dnd-surface'}
        ${isOwn ? 'hover:border-dnd-gold-bright' : ''}`}>

        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            {roleIcon}
            <p className="font-display font-bold text-dnd-gold-bright truncate">
              {isGm ? t('session.game_master') : (snapshot?.name ?? participant.display_name ?? `#${participant.user_id}`)}
            </p>
            {isMe && (
              <span className="text-[10px] uppercase tracking-wider text-dnd-text-muted font-cinzel">
                {t('session.you')}
              </span>
            )}
          </div>
          {snapshot?.heroic_inspiration && (
            <Sparkles size={14} className="text-dnd-amber animate-shimmer shrink-0" />
          )}
        </div>

        {snapshot && (
          <>
            <p className="text-xs text-dnd-text-muted font-body italic mt-0.5">
              {snapshot.class_summary || '—'}
            </p>

            {redacted ? (
              <>
                <div className="mt-2 flex items-center justify-between text-xs font-cinzel">
                  <div className="flex items-center gap-1.5">
                    <Heart size={12} className="text-[var(--dnd-crimson-bright)]" />
                    <span className="uppercase tracking-wider">
                      {snapshot.hp_bucket
                        ? t(`session.hp_bucket.${snapshot.hp_bucket}`)
                        : t('session.hp_bucket.healthy')}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Shield size={12} className="text-dnd-gold-bright" />
                    <span className="uppercase tracking-wider">
                      {t(`session.armor_category.${snapshot.armor_category ?? 'unarmored'}`)}
                    </span>
                  </div>
                </div>
                <div className="mt-1.5 h-1.5 w-full rounded-full bg-dnd-surface overflow-hidden">
                  <div className={`h-full ${bucketColorClass[snapshot.hp_bucket ?? 'healthy']}`} style={{ width: '100%' }} />
                </div>
              </>
            ) : (
              <>
                <div className="mt-2 grid grid-cols-2 gap-2 text-xs font-mono">
                  <div className="flex items-center gap-1.5">
                    <Heart size={12} className="text-[var(--dnd-crimson-bright)]" />
                    <span>{snapshot.current_hit_points}/{snapshot.hit_points}</span>
                    {(snapshot.temp_hp ?? 0) > 0 && <span className="text-dnd-arcane-bright">+{snapshot.temp_hp}</span>}
                  </div>
                  <div className="flex items-center gap-1.5 justify-end">
                    <Shield size={12} className="text-dnd-gold-bright" />
                    <span>{snapshot.ac}</span>
                  </div>
                </div>
                <div className="mt-1.5 h-1.5 w-full rounded-full bg-dnd-surface overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-[var(--dnd-crimson)] via-[var(--dnd-amber)] to-[var(--dnd-emerald-bright)]"
                    style={{ width: `${hpPct}%` }}
                  />
                </div>
              </>
            )}

            {conds.length > 0 && (
              <p className="mt-2 text-[11px] text-[var(--dnd-amber)] font-body">
                ⚠ {conds.join(', ')}
              </p>
            )}
            {snapshot.last_roll && (
              <div className="mt-1 text-[11px] text-dnd-text-muted flex items-center gap-1">
                <Dices size={11} />
                <span>{snapshot.last_roll.notation} → {snapshot.last_roll.total}</span>
              </div>
            )}
          </>
        )}
      </div>
    </Wrapper>
  )
}
```

- [ ] **Step 4: Update the map call site to pass `isOwn`, `onOwnClick`, `t`**

Find the existing mapping (around line 262):

```tsx
{live.participants.map((p) => (
  <ParticipantRow
    key={`${p.user_id}-${p.joined_at}`}
    participant={p}
    snapshot={p.character_id ? snapshotsById.get(p.character_id) : undefined}
    isGm={p.role === 'game_master'}
    isMe={p.user_id === myUserId}
  />
))}
```

Replace with:

```tsx
{live.participants.map((p) => {
  const isMe = p.user_id === myUserId
  const snap = p.character_id ? snapshotsById.get(p.character_id) : undefined
  const isOwn = isMe && !!snap && snap.hit_points !== null
  return (
    <ParticipantRow
      key={`${p.user_id}-${p.joined_at}`}
      participant={p}
      snapshot={snap}
      isGm={p.role === 'game_master'}
      isMe={isMe}
      isOwn={isOwn}
      onOwnClick={(cid) => navigate(`/char/${cid}`)}
      t={t}
    />
  )
})}
```

- [ ] **Step 5: Type-check**

```bash
cd webapp && npx tsc --noEmit
```

Fix any remaining errors inline (most likely missed imports: `TFunction` from `'i18next'`).

- [ ] **Step 6: Commit**

```bash
git add webapp/src/pages/SessionRoom.tsx
git commit -m "feat(webapp): redact participant row + make own card clickable"
```

---

## Task 13: Frontend — chat sender label uses snapshot display name

**Files:**
- Modify: `webapp/src/pages/SessionRoom.tsx` (chat message rendering around line 288)

- [ ] **Step 1: Add a sender-label helper inside the component**

Just after the existing `snapshotsById` memo (around line 192), add:

```ts
const senderLabel = (m: SessionMessage): string => {
  if (m.sender_display_name === '__GM__' || (m.role === 'game_master' && !m.sender_display_name))
    return t('session.game_master')
  return m.sender_display_name ?? t('session.unknown_sender')
}
```

- [ ] **Step 2: Swap the inline rendering**

Find the mapping (around line 298):

```tsx
{!mine && (
  <p className="text-[10px] uppercase tracking-wider opacity-70 mb-0.5 font-cinzel">
    {m.role === 'game_master' ? t('session.game_master') : `#${m.user_id}`}
  </p>
)}
```

Replace with:

```tsx
{!mine && (
  <p className="text-[10px] uppercase tracking-wider opacity-70 mb-0.5 font-cinzel">
    {senderLabel(m)}
  </p>
)}
```

- [ ] **Step 3: Type-check**

```bash
cd webapp && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add webapp/src/pages/SessionRoom.tsx
git commit -m "feat(webapp): render chat sender from sender_display_name snapshot"
```

---

## Task 14: Frontend — whisper UI (recipient selector + styled bubble)

**Files:**
- Modify: `webapp/src/pages/SessionRoom.tsx`

Two sub-parts: (a) recipient selector above/next to the input, (b) visual style on whisper bubbles.

- [ ] **Step 1: Add `Lock` icon import**

Top of file:

```tsx
import { Crown, Heart, LogOut, Lock, Send, Shield, Sparkles, User, XOctagon, Dices } from 'lucide-react'
```

- [ ] **Step 2: Add whisper-recipient state near the existing `chatInput` state**

```tsx
const [whisperTo, setWhisperTo] = useState<number | null>(null)
```

- [ ] **Step 3: Compute `playerParticipants` and `gmUserId` memos near `amGm`**

```tsx
const playerParticipants = useMemo(
  () => live?.participants.filter((p) => p.role !== 'game_master') ?? [],
  [live],
)
const gmUserId = live?.gm_user_id ?? null
```

- [ ] **Step 4: Reset whisper selection whenever it's no longer valid**

Under the existing `useEffect`s:

```ts
useEffect(() => {
  if (whisperTo === null) return
  const stillPresent = live?.participants.some((p) => p.user_id === whisperTo)
  if (!stillPresent) setWhisperTo(null)
}, [live, whisperTo])
```

- [ ] **Step 5: Update `sendMutation` to pass the recipient**

Replace:

```ts
const sendMutation = useMutation({
  mutationFn: (body: string) => api.sessions.sendMessage(sessionId, body),
  onSuccess: (msg) => {
    setChatCache((prev) => [...prev, msg])
    setLastSeenMsgId(msg.id)
    setChatInput('')
    haptic.light()
  },
  onError: () => haptic.error(),
})
```

with:

```ts
const sendMutation = useMutation({
  mutationFn: (body: string) => api.sessions.sendMessage(sessionId, body, whisperTo),
  onSuccess: (msg) => {
    setChatCache((prev) => [...prev, msg])
    setLastSeenMsgId(msg.id)
    setChatInput('')
    haptic.light()
  },
  onError: () => haptic.error(),
})
```

- [ ] **Step 6: Add the recipient selector above the input**

Find the input row (currently `<div className="mt-3 flex items-center gap-2">`) and insert this block directly above it, still inside the `<Surface>`:

```tsx
{amGm ? (
  <div className="flex items-center gap-2 mb-2">
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
  <div className="mb-2">
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
```

- [ ] **Step 7: Restyle whisper bubbles in the message list**

Replace the message-list map body (around line 288):

```tsx
chatCache.map((m) => {
  const mine = m.user_id === myUserId
  return (
    <div
      key={m.id}
      className={`max-w-[80%] rounded-lg px-3 py-2 text-sm font-body
        ${mine
          ? 'ml-auto bg-gradient-gold text-dnd-ink'
          : 'bg-dnd-surface border border-dnd-border text-dnd-text'}`}
    >
      {!mine && (
        <p className="text-[10px] uppercase tracking-wider opacity-70 mb-0.5 font-cinzel">
          {senderLabel(m)}
        </p>
      )}
      <p className="whitespace-pre-wrap break-words">{m.body}</p>
    </div>
  )
})
```

With whisper-aware rendering:

```tsx
chatCache.map((m) => {
  const mine = m.user_id === myUserId
  const isWhisper = !!m.recipient_user_id
  const recipientName = isWhisper
    ? (live.participants.find((p) => p.user_id === m.recipient_user_id)?.display_name
       ?? (m.recipient_user_id === live.gm_user_id ? t('session.game_master') : `#${m.recipient_user_id}`))
    : null
  return (
    <div
      key={m.id}
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
          {mine ? t('session.you') : senderLabel(m)}
          {isWhisper && recipientName && (
            <span className="text-[var(--dnd-amber)]">
              {' '}{t('session.whisper.recipient_prefix', { name: recipientName })}
            </span>
          )}
        </p>
      )}
      <p className="whitespace-pre-wrap break-words">{m.body}</p>
    </div>
  )
})
```

- [ ] **Step 8: Type-check**

```bash
cd webapp && npx tsc --noEmit
```

- [ ] **Step 9: Manual verification**

Ask the user to run the two-browser local test:

1. Chrome as GM, incognito as Player A. Optionally Firefox as Player B.
2. GM creates session, players join.
3. GM picks Player A in the dropdown, types "psst", sends. Input resets. Bubble appears with amber tint + lock icon + `→ {playerA.character_name}` prefix.
4. Player A sees the whisper (amber styled) in their chat.
5. Player B does NOT see the whisper (inspect their Network → `/messages` response — no row with `recipient_user_id`).
6. Player A flips the "Sussurra al GM" chip, sends "ok". Chip goes amber, GM sees it.
7. Player B's chip — should work the same for Player B whispering the GM.
8. Player B cannot whisper Player A — confirm with devtools: call `api.sessions.sendMessage(sessionId, "x", playerA_user_id)` in the console → expect 403 thrown.

- [ ] **Step 10: Commit**

```bash
git add webapp/src/pages/SessionRoom.tsx
git commit -m "feat(webapp): add GM↔player whisper UI in session chat"
```

---

## Task 15: Frontend — gate SessionJoin submit button

**Files:**
- Modify: `webapp/src/pages/SessionJoin.tsx`

- [ ] **Step 1: Derive `canJoin` and disable the button**

Inside the component body (before the `return`), after `effectiveCharId`, add:

```ts
const canJoin = code.trim().length === 6 && effectiveCharId !== null
```

- [ ] **Step 2: Remove the two validation branches inside `submit()`**

Replace:

```ts
const submit = () => {
  setError(null)
  if (code.trim().length !== 6) {
    setError(t('session.error_invalid_code'))
    return
  }
  if (!effectiveCharId) {
    setError(t('session.error_pick_character'))
    return
  }
  joinMutation.mutate()
}
```

with:

```ts
const submit = () => {
  setError(null)
  if (!canJoin) return  // UI already prevents this via disabled button
  joinMutation.mutate()
}
```

- [ ] **Step 3: Wire `disabled` on the button**

Replace the existing Button:

```tsx
<Button
  variant="primary"
  size="lg"
  fullWidth
  loading={joinMutation.isPending}
  onClick={submit}
>
  {t('session.join_button')}
</Button>
```

with:

```tsx
<Button
  variant="primary"
  size="lg"
  fullWidth
  disabled={!canJoin || joinMutation.isPending}
  loading={joinMutation.isPending}
  onClick={submit}
>
  {t('session.join_button')}
</Button>
```

- [ ] **Step 4: Type-check + manual test**

```bash
cd webapp && npx tsc --noEmit
```

Manual: go to `/session/join` with no input — button greyed out. Type 3 chars — still greyed. Type 6 chars + select char (or single-char auto-fills) → button becomes active.

- [ ] **Step 5: Commit**

```bash
git add webapp/src/pages/SessionJoin.tsx
git commit -m "feat(webapp): gate join button until code + character valid"
```

---

## Task 16: Final production build + PR

**Files:**
- Modify: `docs/app/`

- [ ] **Step 1: Run the production build**

```bash
cd webapp && npm run build:prod
```

Expected: build succeeds, `docs/app/` refreshed and staged by the script.

- [ ] **Step 2: Verify staged diff**

```bash
git status
```

Expected: `docs/app/...` files staged. No untracked files in source dirs.

- [ ] **Step 3: Commit the production build**

```bash
git commit -m "chore(webapp): rebuild docs/app for session room UX + privacy"
```

- [ ] **Step 4: Push and open PR**

```bash
git push -u origin feat/session-room-ux-privacy
gh pr create --title "feat: session room UX, privacy, whispers, auto-leave" --body "$(cat <<'EOF'
## Summary
- **Privacy**: non-GM non-owner viewers see HP as buckets (healthy / lightly wounded / badly wounded / dying / dead) and armor as category (unarmored / light / medium / heavy); raw HP/AC/death_saves are nulled in the API response
- **Whispers**: GM↔player private 1:1 chat; persisted on the session (cascades on close); player↔player blocked with 403
- **UX**: invite code hidden for players, own participant card is clickable (→ character sheet), GM cannot click player rows
- **Fix**: chat sender now renders from `sender_display_name` snapshot (stored at send-time) instead of `#{user_id}`
- **Lifecycle**: deleting a character while in an active session automatically removes the participant row
- **Polish**: exhaustion condition pill in ParticipantRow now uses the interpolated `Spossatezza (livello N)` format (via the shared `formatCondition` helper from the prior condition-modal PR)
- **Gating**: Join button disabled until 6-char code + character selected

## Test plan
- [ ] GM creates session; Player joins; Player view shows no invite code
- [ ] Damage GM char; Player sees bucket transitions healthy → lightly → badly → dying
- [ ] Equip/unequip armor on GM char; Player view reflects category
- [ ] GM whispers Player A; Player B's `/messages` response has no whisper row (Network tab)
- [ ] Player A whispers GM; GM sees it with lock icon + amber tint
- [ ] Player B tries to whisper Player A via devtools → 403
- [ ] Historical messages keep character name after participant leaves
- [ ] Deleting an in-session character drops the participant row
- [ ] Own participant card navigates to `/char/{id}`; others don't
- [ ] Join button stays disabled until 6-char code AND character selected
- [ ] Migration idempotent: restart API twice, no ALTER errors

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-review notes

**Coverage vs. spec:**
- Feature #1 (clickable own character) — Task 12 step 4.
- Feature #3 (HP/armor privacy bucket) — Tasks 2, 3, 4 (API), 8 (types), 10 (i18n), 12 (UI render).
- Feature #4 (whispers) — Tasks 1, 2, 5, 6 (API), 9 (client), 10 (i18n), 14 (UI).
- Feature #5 (hide code for players) — Task 11.
- Feature #6 (gated join button) — Task 15.
- Feature #7 (correct chat sender label) — Tasks 1 (column), 5 (capture), 8 (types), 13 (UI).
- Feature #8 (auto-leave on character delete) — Task 7.
- Carry (exhaustion pill) — Task 12 step 2 via `formatCondition`.

**No placeholders:** every code block is complete, every command has expected output. Two explicit ask-the-user gates for Python commands (Task 1 step 4, Task 3 step 2) because the agent running inside WSL cannot `uv run` per CLAUDE.md.

**Type consistency:**
- `HpBucket` / `ArmorCategory` literal types mirror exact server enum strings.
- `CharacterLiveSnapshot.hit_points` nullable on both sides; `redacted = snapshot.hit_points === null` is the canonical redaction check used in the UI.
- `SessionMessage.recipient_user_id`, `sender_display_name` nullable on both sides.
- `sendMessage` signature `(id, body, recipientUserId?)` matches the call sites in Task 14 step 5.
- `formatCondition(key, val, t)` signature matches the one created in Plan B (`2026-04-22-character-sheet-conditions.md` Task 1).
- `__GM__` sentinel matches the server producer (Task 5 step 1) and the client consumer (Task 13 step 1).

**Plan-B dependency:** Task 12 imports `formatCondition` from `@/lib/conditions`. Plan B must land first. If it hasn't, copy the helper inline and track a follow-up cleanup.
