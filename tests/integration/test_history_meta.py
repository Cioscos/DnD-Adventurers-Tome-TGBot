"""Structured `meta` on character_history rows (feeds the evening recap stats)."""
from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine

from core.db.engine import _migrate_schema
from core.db.models import Base, Character, CharacterHistory, SessionParticipant
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID
from tests.integration.test_campaigns_api import _char, act


async def _new(client) -> int:
    r = await client.post("/characters", json={"name": "Meta"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _hp(client, cid, op, value):
    r = await client.patch(f"/characters/{cid}/hp", json={"op": op, "value": value})
    assert r.status_code == 200, r.text


async def _rows(factory, cid, event_type):
    async with factory() as s:
        res = await s.execute(
            select(CharacterHistory).where(
                CharacterHistory.character_id == cid, CharacterHistory.event_type == event_type
            ).order_by(CharacterHistory.id)
        )
        return [r.meta for r in res.scalars()]


async def _setup_hp(client, cid, hp=20):
    await _hp(client, cid, "set_max", hp)
    await _hp(client, cid, "set_current", hp)


async def test_damage_meta_amount_and_to_zero(client, test_session_factory):
    cid = await _new(client)
    await _setup_hp(client, cid)
    await _hp(client, cid, "damage", 5)
    await _hp(client, cid, "damage", 15)
    metas = [m for m in await _rows(test_session_factory, cid, "hp_change") if m and m.get("op") == "DAMAGE"]
    assert metas[-2:] == [
        {"op": "DAMAGE", "amount": 5, "to_zero": False},
        {"op": "DAMAGE", "amount": 15, "to_zero": True},
    ]


async def test_damage_at_zero_logs_failure_meta(client, test_session_factory):
    cid = await _new(client)
    await _setup_hp(client, cid)
    await _hp(client, cid, "damage", 20)
    await _hp(client, cid, "damage", 1)
    metas = await _rows(test_session_factory, cid, "death_save")
    assert {"ds": "failure", "n": 1} in metas


async def test_heal_meta_amount_clamped(client, test_session_factory):
    cid = await _new(client)
    await _setup_hp(client, cid)
    await _hp(client, cid, "damage", 4)
    await _hp(client, cid, "heal", 10)  # only 4 effective
    metas = [m for m in await _rows(test_session_factory, cid, "hp_change") if m and m.get("op") == "HEAL"]
    assert metas[-1] == {"op": "HEAL", "amount": 4}


async def test_death_save_roll_meta_nat1_two_failures(client, test_session_factory):
    cid = await _new(client)
    for die in (1, 20, 12, 5):
        r = await client.post(f"/characters/{cid}/death_saves/roll", json={"die": die})
        assert r.status_code == 200, r.text
    metas = [m for m in await _rows(test_session_factory, cid, "death_save") if m and "ds" in m]
    assert metas[:4] == [
        {"ds": "failure", "n": 2}, {"ds": "success", "n": 1},
        {"ds": "success", "n": 1}, {"ds": "failure", "n": 1},
    ]


async def test_manual_death_save_meta(client, test_session_factory):
    cid = await _new(client)
    for action in ("success", "failure", "stabilize"):
        r = await client.patch(f"/characters/{cid}/death_saves", json={"action": action})
        assert r.status_code == 200, r.text
    rows = await _rows(test_session_factory, cid, "death_save")
    assert rows[0] == {"ds": "success", "n": 1}
    assert rows[1] == {"ds": "failure", "n": 1}
    assert rows[2] is None  # "Stabilizzato": no ds


async def test_rest_meta_kind(client, test_session_factory):
    cid = await _new(client)
    for kind in ("short", "long"):
        r = await client.post(f"/characters/{cid}/rest", json={"rest_type": kind})
        assert r.status_code == 200, r.text
    assert await _rows(test_session_factory, cid, "rest") == [{"kind": "short"}, {"kind": "long"}]


async def test_spell_slot_use_logs_spell_cast(client, test_session_factory):
    cid = await _new(client)
    r = await client.post(f"/characters/{cid}/spell_slots", json={"level": 2, "total": 2})
    assert r.status_code == 201, r.text
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Dardo", "level": 2})
    sid = r.json()["id"]
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"slot_level": 2})
    assert r.status_code == 200, r.text
    async with test_session_factory() as s:
        rows = (await s.execute(select(CharacterHistory).where(
            CharacterHistory.character_id == cid, CharacterHistory.event_type == "spell_cast"
        ))).scalars().all()
    assert [(x.description, x.meta) for x in rows] == [("Lanciato Dardo (slot 2)", {"slot_level": 2})]


async def test_condition_meta(client, test_session_factory):
    cid = await _new(client)
    for cond in ({"poisoned": True}, {"poisoned": False}, {"exhaustion": 2}, {"exhaustion": 1}):
        r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": cond})
        assert r.status_code == 200, r.text
    assert await _rows(test_session_factory, cid, "condition_change") == [
        {"slug": "poisoned", "active": True}, {"slug": "poisoned", "active": False},
        {"slug": "exhaustion", "active": True}, {"slug": "exhaustion", "active": False},
    ]


async def test_participant_dice_snapshot_on_join(client, test_session_factory):
    cid = await _char(test_session_factory, PLAYER_ID)
    stats = {"d20": {"20": 2, "1": 1}}
    async with test_session_factory() as s:
        (await s.get(Character, cid)).dice_stats = stats
        await s.commit()
    act(GM_ID)
    code = (await client.post("/sessions", json={"title": "S"})).json()["code"]
    act(PLAYER_ID)
    r = await client.post("/sessions/join", json={"code": code, "character_id": cid})
    assert r.status_code == 200, r.text
    async with test_session_factory() as s:
        p = (await s.execute(select(SessionParticipant).where(
            SessionParticipant.character_id == cid))).scalar_one()
    assert p.dice_stats_start == stats


async def test_migration_adds_dice_stats_start():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("ALTER TABLE session_participants DROP COLUMN dice_stats_start"))
        await conn.run_sync(_migrate_schema)
        await conn.run_sync(_migrate_schema)
        cols = {r[1] for r in await conn.execute(text("PRAGMA table_info(session_participants)"))}
    assert "dice_stats_start" in cols
