"""Scritture del bot su ``bot_users``: registrazione allo /start e opt-out annunci."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import BotUser


async def _get_or_create(session: AsyncSession, user_id: int) -> BotUser:
    row = await session.get(BotUser, user_id)
    if row is None:
        row = BotUser(
            user_id=user_id,
            announcements=True,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        session.add(row)
    return row


async def register_start(session: AsyncSession, user_id: int, language_code: str | None) -> None:
    """Crea la riga se manca; aggiorna solo la lingua (non riattiva gli annunci)."""
    row = await _get_or_create(session, user_id)
    if language_code:
        row.language_code = language_code
    await session.commit()


async def set_announcements(
    session: AsyncSession, user_id: int, enabled: bool, language_code: str | None
) -> None:
    row = await _get_or_create(session, user_id)
    row.announcements = enabled
    if language_code:
        row.language_code = language_code
    await session.commit()
