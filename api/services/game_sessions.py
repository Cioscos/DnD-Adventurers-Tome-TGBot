"""Sessioni di gioco: caricamento, controllo dei partecipanti e attività, condivisi dai router."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.db.models import GameSession, SessionParticipant, SessionStatus


def utc_now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


async def load_session(session_id: int, db: AsyncSession) -> GameSession:
    result = await db.execute(
        select(GameSession)
        .options(selectinload(GameSession.participants).selectinload(SessionParticipant.character))
        .where(GameSession.id == session_id)
    )
    obj = result.scalar_one_or_none()
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return obj


def assert_participant(session: GameSession, user_id: int) -> SessionParticipant:
    for p in session.participants:
        if p.user_id == user_id:
            return p
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a session participant")


async def find_active_session_for_user(user_id: int, db: AsyncSession) -> Optional[GameSession]:
    """Active session where user is GM or player."""
    result = await db.execute(
        select(GameSession)
        .join(SessionParticipant, SessionParticipant.session_id == GameSession.id)
        .options(selectinload(GameSession.participants).selectinload(SessionParticipant.character))
        .where(
            GameSession.status == SessionStatus.ACTIVE,
            SessionParticipant.user_id == user_id,
        )
    )
    return result.scalars().first()


def touch(session: GameSession) -> None:
    session.last_activity_at = utc_now_iso()


async def active_session_id(db: AsyncSession, campaign_id: int) -> Optional[int]:
    return (await db.execute(
        select(GameSession.id).where(
            GameSession.campaign_id == campaign_id, GameSession.status == SessionStatus.ACTIVE
        )
    )).scalars().first()
