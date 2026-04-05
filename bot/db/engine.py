"""SQLAlchemy async engine and session factory.

Database file is stored at ``data/dnd_bot.db`` relative to the project root.
``init_db()`` must be called once at startup to create all tables.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import inspect as sa_inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.db.models import Base

logger = logging.getLogger(__name__)

_DB_PATH = os.environ.get("DB_PATH", "data/dnd_bot.db")
_DATABASE_URL = f"sqlite+aiosqlite:///{_DB_PATH}"

engine = create_async_engine(_DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# ---------------------------------------------------------------------------
# Schema migration helpers
# ---------------------------------------------------------------------------

# Columns to ensure on existing tables: (table, column, DDL type, default)
_MIGRATIONS: list[tuple[str, str, str, str | None]] = [
    # Spell extended properties
    ("spells", "casting_time", "VARCHAR(100)", None),
    ("spells", "range_area", "VARCHAR(100)", None),
    ("spells", "components", "VARCHAR(200)", None),
    ("spells", "duration", "VARCHAR(100)", None),
    ("spells", "is_concentration", "BOOLEAN", "0"),
    ("spells", "is_ritual", "BOOLEAN", "0"),
    ("spells", "higher_level", "TEXT", None),
    ("spells", "attack_save", "VARCHAR(100)", None),
    ("spells", "is_pinned", "BOOLEAN", "0"),
    # Character concentration tracking
    ("characters", "concentrating_spell_id", "INTEGER REFERENCES spells(id) ON DELETE SET NULL", None),
    # CharacterClass subclass
    ("character_classes", "subclass", "VARCHAR(100)", None),
    # Party feature
    ("characters", "is_party_active", "BOOLEAN", "0"),
    # Conditions feature
    ("characters", "conditions", "TEXT", None),
]


def _migrate_schema(connection) -> None:
    """Add missing columns to existing tables (idempotent)."""
    inspector = sa_inspect(connection)
    column_cache: dict[str, set[str]] = {}

    for table, column, col_type, default in _MIGRATIONS:
        if table not in column_cache:
            try:
                cols = inspector.get_columns(table)
                column_cache[table] = {c["name"] for c in cols}
            except Exception:
                # Table doesn't exist yet — create_all will handle it
                column_cache[table] = set()
                continue

        if column not in column_cache[table]:
            default_clause = f" DEFAULT {default}" if default is not None else ""
            ddl = f"ALTER TABLE {table} ADD COLUMN {column} {col_type}{default_clause}"
            logger.info("Migrating: %s", ddl)
            connection.execute(text(ddl))
            column_cache[table].add(column)


async def init_db() -> None:
    """Create all tables and run schema migrations."""
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate_schema)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager that yields an ``AsyncSession``."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
