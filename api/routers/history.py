"""Character history (audit log) endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.database import get_db
from core.db.models import Character, CharacterHistory
from api.schemas.common import HistoryEntryRead

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
