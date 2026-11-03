"""core/db/bot_users.py: registrazione allo /start e opt-out degli annunci."""
from __future__ import annotations

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.db.bot_users import register_start, set_announcements
from core.db.models import Base, BotUser


@pytest_asyncio.fixture
async def session(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 't.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        yield s
    await engine.dispose()


async def _row(s, uid):
    s.expire_all()
    return await s.get(BotUser, uid)


async def test_register_start_creates_row(session):
    await register_start(session, 1, "en")
    row = await _row(session, 1)
    assert row.language_code == "en"
    assert row.announcements is True


async def test_register_start_keeps_optout(session):
    await set_announcements(session, 1, False, "it")
    await register_start(session, 1, "en")
    row = await _row(session, 1)
    assert row.announcements is False
    assert row.language_code == "en"


async def test_set_announcements_creates_row(session):
    await set_announcements(session, 2, False, None)
    assert (await _row(session, 2)).announcements is False


async def test_set_announcements_toggles(session):
    await set_announcements(session, 3, False, None)
    await set_announcements(session, 3, True, None)
    assert (await _row(session, 3)).announcements is True
