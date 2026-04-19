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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import get_current_user
from api.database import get_db
from api.schemas.session import (
    CharacterLiveSnapshot,
    GameSessionLiveRead,
    GameSessionRead,
    SessionCreateRequest,
    SessionJoinRequest,
    SessionMessageCreate,
    SessionMessageRead,
)
from core.db.models import (
    Character,
    GameSession,
    SessionMessage,
    SessionParticipant,
    SessionRole,
    SessionStatus,
)
from core.utils.session_code import generate_session_code

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["sessions"])


_MAX_CODE_RETRIES = 10


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
) -> list[CharacterLiveSnapshot]:
    if not char_ids:
        return []
    result = await db.execute(
        select(Character)
        .options(selectinload(Character.classes))
        .where(Character.id.in_(char_ids))
    )
    snapshots: list[CharacterLiveSnapshot] = []
    for char in result.scalars().all():
        last_roll = None
        history = char.rolls_history or []
        if history:
            last = history[-1]
            if isinstance(last, dict):
                last_roll = last
        snapshots.append(CharacterLiveSnapshot(
            id=char.id,
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
        ))
    return snapshots


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
    snapshots = await _load_live_characters(char_ids, db)
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
    stmt = select(SessionMessage).where(SessionMessage.session_id == session_id)
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
