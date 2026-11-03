"""Campaign data model: stash character, codes, membership, migration."""
from __future__ import annotations

import re

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

import api.services.release_announce as ra
from api.services.campaigns import STASH_USER_ID, create_campaign
from core.db.engine import _migrate_schema
from core.db.models import Base, BotUser, Campaign, CampaignMember, Character

from ._encounter_helpers import GM_ID, PLAYER_ID

NOW = "2026-11-03T10:00:00"


async def _member(s, campaign, user_id=PLAYER_ID, name="Eroe"):
    char = Character(user_id=user_id, name=name)
    s.add(char)
    await s.flush()
    m = CampaignMember(campaign_id=campaign.id, character_id=char.id, user_id=user_id, joined_at=NOW)
    s.add(m)
    await s.flush()
    return char, m


async def test_create_campaign_makes_stash(test_session_factory):
    async with test_session_factory() as s:
        camp = await create_campaign(s, GM_ID, "Sette Torri")
        await s.commit()
        stash = await s.get(Character, camp.stash_character_id)
    assert stash.user_id == STASH_USER_ID == 0
    assert stash.name == "Sette Torri"
    assert re.fullmatch(r"[A-Z0-9]{8}", camp.invite_code)


async def test_codes_unique(test_session_factory):
    async with test_session_factory() as s:
        codes = {(await create_campaign(s, GM_ID, f"C{i}")).invite_code for i in range(20)}
    assert len(codes) == 20


async def test_member_character_unique(test_session_factory):
    async with test_session_factory() as s:
        c1 = await create_campaign(s, GM_ID, "A")
        c2 = await create_campaign(s, GM_ID, "B")
        char, _ = await _member(s, c1)
        s.add(CampaignMember(campaign_id=c2.id, character_id=char.id, user_id=PLAYER_ID, joined_at=NOW))
        with pytest.raises(IntegrityError):
            await s.flush()


async def test_deleting_character_removes_membership(client, test_session_factory):
    async with test_session_factory() as s:
        camp = await create_campaign(s, GM_ID, "A")
        char, _ = await _member(s, camp, user_id=GM_ID)
        await s.commit()
        cid, camp_id = char.id, camp.id
    r = await client.delete(f"/characters/{cid}")
    assert r.status_code == 204, r.text
    async with test_session_factory() as s:
        assert (await s.execute(select(CampaignMember))).first() is None
        assert await s.get(Campaign, camp_id) is not None


async def test_stash_hidden_everywhere(client, test_session_factory):
    async with test_session_factory() as s:
        camp = await create_campaign(s, GM_ID, "Deposito")
        s.add(BotUser(user_id=99, language_code=None, announcements=True, created_at="x"))
        await s.commit()
        stash_id = camp.stash_character_id
    # GET /characters (per-user filter)
    r = await client.get("/characters")
    assert r.status_code == 200
    assert stash_id not in [c["id"] for c in r.json()]
    # release announcements: global sweep over Character owners
    async with test_session_factory() as s:
        assert STASH_USER_ID not in await ra.recipients(s)
    # (core/db/engine.py s.query(Character).all() is a one-off data migration: left as is.)


async def test_migration_adds_session_campaign_id():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("ALTER TABLE game_sessions DROP COLUMN campaign_id"))
        await conn.run_sync(_migrate_schema)
        await conn.run_sync(_migrate_schema)  # idempotente
        cols = {r[1] for r in await conn.execute(text("PRAGMA table_info(game_sessions)"))}
    assert "campaign_id" in cols
