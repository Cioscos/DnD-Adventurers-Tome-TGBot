"""Game session endpoints (invite-code based, replaces the bot /party command).

A Game Master creates a session and obtains a 6-character invite code. Players
join with the code and pick one of their characters. The webapp polls `/live`
for HP/AC/conditions snapshots and `/messages` for the in-session chat.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import get_current_user
from api.database import get_db
from api.schemas.session import (
    CharacterLiveSnapshot,
    GameSessionLiveRead,
    GameSessionRead,
    IdentityView,
    SessionCreateRequest,
    SessionFeedItem,
    SessionFeedResponse,
    SessionJoinRequest,
    SessionMessageCreate,
    SessionMessageRead,
)
from core.db.models import (
    Character,
    CharacterHistory,
    GameSession,
    SessionMessage,
    SessionParticipant,
    SessionRole,
    SessionStatus,
)
from core.utils.session_code import generate_session_code
from core.utils.session_view import hp_bucket, armor_category

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["sessions"])


_MAX_CODE_RETRIES = 10


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
        return event.description

    # Legacy fallback (meta missing): best-effort sniff on description.
    desc_lower = event.description.lower()
    if "cura" in desc_lower or "heal" in desc_lower:
        return f"{character_name} si è curato"
    if "danni" in desc_lower or "danno" in desc_lower or "damage" in desc_lower:
        return event.description
    return f"{character_name} ha modificato i PF"


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _load_session(session_id: int, db: AsyncSession) -> GameSession:
    result = await db.execute(
        select(GameSession)
        .options(selectinload(GameSession.participants))
        .where(GameSession.id == session_id)
    )
    obj = result.scalar_one_or_none()
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return obj


async def _load_session_by_code(code: str, db: AsyncSession) -> GameSession:
    result = await db.execute(
        select(GameSession)
        .options(selectinload(GameSession.participants))
        .where(GameSession.code == code.upper())
    )
    obj = result.scalar_one_or_none()
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return obj


def _assert_participant(session: GameSession, user_id: int) -> SessionParticipant:
    for p in session.participants:
        if p.user_id == user_id:
            return p
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a session participant")


async def _find_active_session_for_user(user_id: int, db: AsyncSession) -> Optional[GameSession]:
    """Active session where user is GM or player."""
    result = await db.execute(
        select(GameSession)
        .join(SessionParticipant, SessionParticipant.session_id == GameSession.id)
        .options(selectinload(GameSession.participants))
        .where(
            GameSession.status == SessionStatus.ACTIVE,
            SessionParticipant.user_id == user_id,
        )
    )
    return result.scalars().first()


async def _generate_unique_code(db: AsyncSession) -> str:
    for _ in range(_MAX_CODE_RETRIES):
        code = generate_session_code()
        existing = await db.execute(select(GameSession.id).where(GameSession.code == code))
        if existing.scalar_one_or_none() is None:
            return code
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Could not generate a unique session code. Try again.",
    )


def _touch(session: GameSession) -> None:
    session.last_activity_at = _now()


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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/me", response_model=Optional[GameSessionRead])
async def my_active_session(
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Optional[GameSession]:
    return await _find_active_session_for_user(user_id, db)


@router.post("", response_model=GameSessionRead, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: SessionCreateRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GameSession:
    # Users can only be in one active session at a time (regardless of role)
    existing = await _find_active_session_for_user(user_id, db)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have an active session",
        )

    code = await _generate_unique_code(db)
    now = _now()
    session = GameSession(
        code=code,
        gm_user_id=user_id,
        status=SessionStatus.ACTIVE,
        title=body.title,
        created_at=now,
        last_activity_at=now,
    )
    db.add(session)
    await db.flush()
    db.add(SessionParticipant(
        session_id=session.id,
        user_id=user_id,
        role=SessionRole.GAME_MASTER,
        character_id=None,
        joined_at=now,
    ))
    await db.flush()
    await db.refresh(session, attribute_names=["participants"])
    return session


@router.post("/join", response_model=GameSessionRead)
async def join_session(
    body: SessionJoinRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GameSession:
    # Users can only be in one active session at a time
    existing = await _find_active_session_for_user(user_id, db)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have an active session",
        )

    session = await _load_session_by_code(body.code, db)
    if session.status != SessionStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Session is closed",
        )

    # Verify character ownership
    char_result = await db.execute(
        select(Character).where(Character.id == body.character_id)
    )
    char = char_result.scalar_one_or_none()
    if char is None or char.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Character not found or not yours",
        )

    db.add(SessionParticipant(
        session_id=session.id,
        user_id=user_id,
        role=SessionRole.PLAYER,
        character_id=char.id,
        display_name=char.name,
        joined_at=_now(),
    ))
    _touch(session)
    await db.flush()
    await db.refresh(session, attribute_names=["participants"])
    return session


@router.get("/{session_id}", response_model=GameSessionRead)
async def get_session(
    session_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GameSession:
    session = await _load_session(session_id, db)
    _assert_participant(session, user_id)
    return session


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


@router.post("/{session_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_session(
    session_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    session = await _load_session(session_id, db)
    participant = _assert_participant(session, user_id)
    if session.status != SessionStatus.ACTIVE:
        return None

    # GM leaving closes the whole session
    if user_id == session.gm_user_id:
        session.status = SessionStatus.CLOSED
        session.closed_at = _now()
    else:
        await db.delete(participant)
    _touch(session)
    return None


@router.post("/{session_id}/close", status_code=status.HTTP_204_NO_CONTENT)
async def close_session(
    session_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    session = await _load_session(session_id, db)
    if user_id != session.gm_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the Game Master can close the session",
        )
    if session.status == SessionStatus.ACTIVE:
        session.status = SessionStatus.CLOSED
        session.closed_at = _now()
    return None


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


@router.get(
    "/{code}/participants/{user_id}/identity",
    response_model=IdentityView,
)
async def get_participant_identity(
    code: str,
    user_id: int,
    caller_user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> IdentityView:
    session = await _load_session_by_code(code, db)
    _assert_participant(session, caller_user_id)

    target = next((p for p in session.participants if p.user_id == user_id), None)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participant not found",
        )
    if target.character_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participant has no character",
        )

    result = await db.execute(
        select(Character).where(Character.id == target.character_id)
    )
    char = result.scalar_one_or_none()
    if char is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found",
        )

    settings_ = char.settings or {}
    show_private = bool(settings_.get("show_private_identity")) or caller_user_id == user_id

    def _join_list(val) -> Optional[str]:
        if not val:
            return None
        if isinstance(val, list):
            cleaned = [str(x).strip() for x in val if str(x).strip()]
            return ", ".join(cleaned) if cleaned else None
        return str(val) or None

    personality = char.personality or {}

    return IdentityView(
        user_id=target.user_id,
        character_id=char.id,
        name=char.name,
        race=char.race,
        gender=char.gender,
        alignment=char.alignment,
        speed=char.speed,
        languages=_join_list(char.languages),
        general_proficiencies=_join_list(char.general_proficiencies),
        background=char.background if show_private else None,
        personality_traits=(personality.get("traits") or None) if show_private else None,
        ideals=(personality.get("ideals") or None) if show_private else None,
        bonds=(personality.get("bonds") or None) if show_private else None,
        flaws=(personality.get("flaws") or None) if show_private else None,
        show_private=show_private,
    )


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
    session_start = session.created_at

    char_ids: list[int] = []
    char_meta: dict[int, tuple[int, str]] = {}
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

    # Messages
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

    # Events
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

    items: list[SessionFeedItem] = []

    for m in messages:
        if m.recipient_user_id is not None:
            if not (
                caller_user_id == m.user_id
                or caller_user_id == m.recipient_user_id
                or is_gm
            ):
                continue
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

    def _sort_key(it: SessionFeedItem):
        sec = it.message_id if it.type == "message" else (it.event_id or 0)
        return (it.timestamp, 0 if it.type == "message" else 1, sec or 0)

    items.sort(key=_sort_key)

    has_more = len(items) > limit
    if has_more:
        items = items[-limit:]

    return SessionFeedResponse(items=items, has_more=has_more)
