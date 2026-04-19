"""SQLAlchemy async engine and session factory.

Database file is stored at ``data/dnd_bot.db`` relative to the project root.
``init_db()`` must be called once at startup to create all tables.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import event, inspect as sa_inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.db.models import Base

logger = logging.getLogger(__name__)

_DB_PATH = os.environ.get("DB_PATH", "data/dnd_bot.db")
_DATABASE_URL = f"sqlite+aiosqlite:///{_DB_PATH}"

engine = create_async_engine(_DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
    """Enable FK enforcement (and cascade deletes) for every SQLite connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

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
    # Conditions feature
    ("characters", "conditions", "TEXT", None),
    # Skills feature
    ("characters", "skills", "TEXT", None),
    # Item type system
    ("items", "item_type", "VARCHAR(20)", "'generic'"),
    ("items", "item_metadata", "TEXT", None),
    ("items", "is_equipped", "BOOLEAN", "0"),
    # Heroic Inspiration
    ("characters", "heroic_inspiration", "BOOLEAN", "0"),
    # Saving throw proficiencies
    ("characters", "saving_throws", "TEXT", None),
    # Experience points
    ("characters", "experience_points", "INTEGER", "0"),
    # Death saving throws
    ("characters", "death_saves", "TEXT", None),
    # Temporary hit points
    ("characters", "temp_hp", "INTEGER", "0"),
    # Movement speed
    ("characters", "speed", "INTEGER", "30"),
    # Expanded identity
    ("characters", "background", "VARCHAR(200)", None),
    ("characters", "alignment", "VARCHAR(50)", None),
    ("characters", "personality", "TEXT", None),
    ("characters", "languages", "TEXT", None),
    ("characters", "general_proficiencies", "TEXT", None),
    ("characters", "damage_modifiers", "TEXT", None),
    # CharacterClass extensions
    ("character_classes", "spellcasting_ability", "VARCHAR(50)", None),
    ("character_classes", "hit_die", "INTEGER", None),
    # Spell damage fields
    ("spells", "damage_dice", "VARCHAR(100)", None),
    ("spells", "damage_type", "VARCHAR(100)", None),
    # Map local file upload support
    ("maps", "local_file_path", "VARCHAR(500)", None),
]

# Tables to drop if they exist (legacy feature cleanup)
_DROP_TABLES: list[str] = [
    "party_sessions",
    "group_members",
]

# Columns to drop if they exist: (table, column)
_DROP_COLUMNS: list[tuple[str, str]] = [
    ("characters", "is_party_active"),
]


def _migrate_schema(connection) -> None:
    """Add missing columns, drop legacy columns/tables (idempotent)."""
    inspector = sa_inspect(connection)
    existing_tables = set(inspector.get_table_names())
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

    for table, column in _DROP_COLUMNS:
        if table not in existing_tables:
            continue
        cols = column_cache.get(table)
        if cols is None:
            cols = {c["name"] for c in inspector.get_columns(table)}
            column_cache[table] = cols
        if column in cols:
            ddl = f"ALTER TABLE {table} DROP COLUMN {column}"
            logger.info("Migrating: %s", ddl)
            try:
                connection.execute(text(ddl))
                cols.discard(column)
            except Exception as exc:
                # SQLite < 3.35 does not support DROP COLUMN.
                logger.warning("DROP COLUMN failed for %s.%s: %s", table, column, exc)

    for table in _DROP_TABLES:
        if table in existing_tables:
            logger.info("Dropping legacy table: %s", table)
            connection.execute(text(f"DROP TABLE IF EXISTS {table}"))
            existing_tables.discard(table)


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
