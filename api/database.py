"""Async database engine and session factory for the FastAPI backend.

Shares the same SQLite database file used by the Telegram bot
(``data/dnd_bot.db`` by default, overridable via the ``DB_PATH`` env var).
Both the bot and the API must NOT write to the same rows concurrently;
SQLite's default journal mode handles this safely for typical usage.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_DB_PATH = os.environ.get("DB_PATH", "data/dnd_bot.db")
_DATABASE_URL = f"sqlite+aiosqlite:///{_DB_PATH}"

# Ensure the parent directory exists (e.g. data/ is gitignored and won't be
# present on a fresh clone or local dev environment).
_db_dir = os.path.dirname(_DB_PATH)
if _db_dir:
    os.makedirs(_db_dir, exist_ok=True)

engine = create_async_engine(_DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
    """Enable FK enforcement for every SQLite connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager yielding a committed-or-rolled-back ``AsyncSession``."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an ``AsyncSession``."""
    async with get_session() as session:
        yield session
