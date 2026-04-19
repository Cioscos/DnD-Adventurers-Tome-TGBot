"""Background task that closes idle game sessions.

Runs inside the FastAPI lifespan. A session is considered idle when its
``last_activity_at`` is older than ``SESSION_IDLE_TIMEOUT_SECONDS``.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select

from api.database import AsyncSessionLocal
from bot.db.models import GameSession, SessionStatus

logger = logging.getLogger(__name__)

SESSION_IDLE_TIMEOUT_SECONDS = 24 * 60 * 60  # 24h
_SWEEP_INTERVAL_SECONDS = 10 * 60  # 10min


async def _sweep_once() -> int:
    cutoff = datetime.utcnow() - timedelta(seconds=SESSION_IDLE_TIMEOUT_SECONDS)
    cutoff_iso = cutoff.isoformat(timespec="seconds")
    closed = 0
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(GameSession).where(
                GameSession.status == SessionStatus.ACTIVE,
                GameSession.last_activity_at < cutoff_iso,
            )
        )
        for session in result.scalars().all():
            session.status = SessionStatus.CLOSED
            session.closed_at = datetime.utcnow().isoformat(timespec="seconds")
            closed += 1
        if closed:
            await db.commit()
    return closed


async def run_session_cleanup() -> None:
    """Forever loop — sweeps idle sessions every 10 minutes."""
    while True:
        try:
            closed = await _sweep_once()
            if closed:
                logger.info("Closed %d idle session(s)", closed)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Session cleanup sweep failed")
        await asyncio.sleep(_SWEEP_INTERVAL_SECONDS)
