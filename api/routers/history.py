"""Character history (audit log) endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.database import get_db
from core.db.models import Character, CharacterHistory
from api.schemas.common import HistoryEntryRead, HistoryRetentionPreview

router = APIRouter(prefix="/characters", tags=["history"])


async def _verify_ownership(char_id: int, user_id: int, session: AsyncSession) -> None:
    result = await session.execute(
        select(Character.user_id).where(Character.id == char_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Character not found")
    if row != user_id:
        raise HTTPException(status_code=403, detail="Not your character")


@router.get("/{char_id}/history", response_model=list[HistoryEntryRead])
async def get_history(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[CharacterHistory]:
    await _verify_ownership(char_id, user_id, session)
    result = await session.execute(
        select(CharacterHistory)
        .where(CharacterHistory.character_id == char_id)
        .order_by(CharacterHistory.timestamp.desc())
        .limit(200)
    )
    return list(result.scalars().all())


@router.get(
    "/{char_id}/history/retention-preview",
    response_model=HistoryRetentionPreview,
)
async def history_retention_preview(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    events: int = Query(100, ge=1, le=10000),
    days: int = Query(30, ge=1, le=3650),
) -> HistoryRetentionPreview:
    """Return the row counts that retention modes would purge right now."""
    await _verify_ownership(char_id, user_id, session)
    total = (
        await session.execute(
            select(func.count(CharacterHistory.id)).where(
                CharacterHistory.character_id == char_id
            )
        )
    ).scalar() or 0

    would_purge_events = max(0, total - events)

    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat(timespec="seconds")
    would_purge_days = (
        await session.execute(
            select(func.count(CharacterHistory.id)).where(
                CharacterHistory.character_id == char_id,
                CharacterHistory.timestamp < cutoff,
            )
        )
    ).scalar() or 0

    return HistoryRetentionPreview(
        total=total,
        events_keep=events,
        days_window=days,
        would_purge_events=would_purge_events,
        would_purge_days=would_purge_days,
    )


@router.delete("/{char_id}/history", status_code=status.HTTP_204_NO_CONTENT)
async def clear_history(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await _verify_ownership(char_id, user_id, session)
    await session.execute(
        delete(CharacterHistory).where(CharacterHistory.character_id == char_id)
    )
