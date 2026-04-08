"""Character history helper — logs modification events to the ``character_history`` table.

Each event is stored with a UTC timestamp, an event-type slug (e.g. ``"hp_change"``)
and a plain-text description.  Old entries are pruned automatically so that at most
``MAX_HISTORY`` entries are kept per character.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import delete, func, select

from bot.db.engine import get_session
from bot.db.models import CharacterHistory

logger = logging.getLogger(__name__)

MAX_HISTORY = 50


async def log_history_event(
    char_id: int,
    event_type: str,
    description: str,
) -> None:
    """Insert a history record and prune old entries to keep at most MAX_HISTORY."""
    try:
        async with get_session() as session:
            ts = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M")
            session.add(CharacterHistory(
                character_id=char_id,
                timestamp=ts,
                event_type=event_type,
                description=description,
            ))
            await session.flush()

            # Count current entries
            count_result = await session.execute(
                select(func.count()).where(CharacterHistory.character_id == char_id)
            )
            count = count_result.scalar_one()

            if count > MAX_HISTORY:
                # Find the cutoff ID (keep the MAX_HISTORY newest)
                oldest_ids_result = await session.execute(
                    select(CharacterHistory.id)
                    .where(CharacterHistory.character_id == char_id)
                    .order_by(CharacterHistory.id.asc())
                    .limit(count - MAX_HISTORY)
                )
                ids_to_delete = [row[0] for row in oldest_ids_result]
                if ids_to_delete:
                    await session.execute(
                        delete(CharacterHistory).where(CharacterHistory.id.in_(ids_to_delete))
                    )
    except Exception as exc:
        logger.warning("Failed to log history event for char %s: %s", char_id, exc)


async def get_history(char_id: int) -> list[CharacterHistory]:
    """Return all history entries for a character, newest first."""
    async with get_session() as session:
        result = await session.execute(
            select(CharacterHistory)
            .where(CharacterHistory.character_id == char_id)
            .order_by(CharacterHistory.id.desc())
        )
        return list(result.scalars().all())


async def clear_history(char_id: int) -> None:
    """Delete all history entries for a character."""
    async with get_session() as session:
        await session.execute(
            delete(CharacterHistory).where(CharacterHistory.character_id == char_id)
        )
