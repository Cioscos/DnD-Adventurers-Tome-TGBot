"""Shared fixtures for homebrew router integration tests.

Fresh per-test SQLite file under pytest tmp_path. FastAPI deps for db + auth are
overridden so the test doesn't depend on env vars or production DB.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.auth import get_current_user
from api.database import get_db
from api.main import app
from core.db.models import Base, Character

TEST_USER_ID = 1234


@pytest_asyncio.fixture
async def test_session_factory(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def client(test_session_factory):
    async def _override_get_db():
        async with test_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    def _override_get_user():
        return TEST_USER_ID

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_user
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
        ) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def char_id(test_session_factory) -> int:
    """Create a Character owned by TEST_USER_ID and return its id."""
    async with test_session_factory() as session:
        char = Character(user_id=TEST_USER_ID, name="Test")
        session.add(char)
        await session.commit()
        await session.refresh(char)
        return char.id
