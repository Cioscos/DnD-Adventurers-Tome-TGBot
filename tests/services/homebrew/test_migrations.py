"""Idempotency tests: homebrew tables are created and surviving a second migration pass."""
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from core.db.engine import _migrate_schema
from core.db.models import Base


@pytest.mark.asyncio
async def test_migrations_create_homebrew_tables_idempotent():
    """`init_db` would call create_all + _migrate_schema. Verify that:

    1. After running both, the homebrew tables exist.
    2. Running `_migrate_schema` a second time is a no-op (no error).
    3. Expected indexes are present.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # First pass — should be a no-op for new homebrew tables (they were just created).
        await conn.run_sync(_migrate_schema)
        # Second pass — must not raise.
        await conn.run_sync(_migrate_schema)

    async with engine.connect() as conn:
        # Tables exist
        rows = await conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name IN ('homebrew_rules', 'homebrew_resources')"
        ))
        tables = {r[0] for r in rows}
        assert tables == {"homebrew_rules", "homebrew_resources"}

        # Expected indexes from `index=True` on the ORM models
        rows = await conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name IN ('homebrew_rules', 'homebrew_resources') "
            "AND name NOT LIKE 'sqlite_autoindex_%'"
        ))
        indexes = {r[0] for r in rows}
        # SQLAlchemy index names follow pattern ix_<table>_<col>
        assert "ix_homebrew_rules_character_id" in indexes
        assert "ix_homebrew_resources_character_id" in indexes
        assert "ix_homebrew_resources_rule_id" in indexes
