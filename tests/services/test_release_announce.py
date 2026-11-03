"""api/services/release_announce.py: testo, destinatari, invio una volta per versione."""
from __future__ import annotations

import json

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import api.services.release_announce as ra
from core.db.models import AppMeta, Base, BotUser, Character

ENTRY = {
    "version": "9.9.9",
    "date": "2026-11-03",
    "added": {"it": ["Cosa nuova"], "en": ["New thing"]},
    "fixed": {"it": ["Bug sistemato"], "en": ["Bug fixed"]},
}


@pytest_asyncio.fixture
async def factory(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 't.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
def changelog(tmp_path):
    path = tmp_path / "changelog.json"
    path.write_text(json.dumps({"entries": [ENTRY]}), encoding="utf-8")
    return path


@pytest.fixture
def sent(monkeypatch):
    calls: list[tuple[int, str]] = []

    async def fake(chat_id, text, **kwargs):
        calls.append((chat_id, text))
        return True

    monkeypatch.setattr(ra, "send_telegram_message", fake)
    return calls


def _bu(uid, lang=None, on=True):
    return BotUser(user_id=uid, language_code=lang, announcements=on, created_at="x")


async def _seed(factory):
    async with factory() as s:
        s.add_all([
            Character(user_id=1, name="A"), _bu(1, "en"),
            _bu(2),
            Character(user_id=3, name="C"), _bu(3, on=False),
        ])
        await s.commit()


def test_format_only_present_sections():
    text = ra.format_announcement({"version": "1.0.0", "fixed": ENTRY["fixed"]}, "it")
    assert "Correzioni" in text
    assert "Miglioramenti" not in text
    assert "\nNovità\n" not in text
    assert text.endswith("/unsubscribe")


def test_format_english():
    text = ra.format_announcement(ENTRY, "en")
    assert text.startswith("What's new in v9.9.9")
    assert "• New thing" in text


async def test_recipients_dedup_and_optout(factory):
    await _seed(factory)
    async with factory() as s:
        assert await ra.recipients(s) == {1: "en", 2: "it"}


async def test_announce_sends_once_and_records_version(factory, changelog, sent):
    await _seed(factory)
    assert await ra.announce_latest_release(factory, changelog, delay=0) == 2
    assert sorted(c for c, _ in sent) == [1, 2]
    async with factory() as s:
        assert (await s.get(AppMeta, "last_announced_version")).value == "9.9.9"


async def test_announce_skips_when_already_announced(factory, changelog, sent):
    await _seed(factory)
    await ra.announce_latest_release(factory, changelog, delay=0)
    assert await ra.announce_latest_release(factory, changelog, delay=0) == 0
    assert len(sent) == 2
