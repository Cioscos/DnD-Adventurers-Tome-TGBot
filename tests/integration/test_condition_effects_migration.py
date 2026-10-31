"""Data migration: condition_durations -> condition_effects, PC tracker conditions -> sheet."""
from __future__ import annotations

from sqlalchemy import select

from core.db.engine import _migrate_condition_state
from core.db.models import Character, Combatant, ConditionEffect, Encounter, GameSession, SessionStatus

NOW = "2026-06-09T10:00:00"


async def _run(factory) -> None:
    async with factory() as s:
        conn = await s.connection()
        await conn.run_sync(_migrate_condition_state)
        await s.commit()


async def test_durations_become_effects(test_session_factory):
    async with test_session_factory() as s:
        pg = Character(
            user_id=1, name="Eroe",
            settings={"condition_durations": {"poisoned": 3}},
            conditions={"poisoned": True},
        )
        s.add(pg)
        await s.commit()
        pg_id = pg.id

    await _run(test_session_factory)

    async with test_session_factory() as s:
        eff = (await s.execute(select(ConditionEffect))).scalars().all()
        assert len(eff) == 1
        e = eff[0]
        assert (e.character_id, e.slug, e.expiry_anchor, e.expiry_edge, e.expiry_count, e.applied_by_gm) == (
            pg_id, "poisoned", "owner", "start", 3, False)
        pg = await s.get(Character, pg_id)
        assert "condition_durations" not in pg.settings


async def test_pc_tracker_conditions_merge_into_sheet(test_session_factory):
    async with test_session_factory() as s:
        pg = Character(user_id=1, name="Eroe", conditions={"poisoned": True, "stunned": 1})
        s.add(pg)
        gm = GameSession(code="ABC123", gm_user_id=9, status=SessionStatus.ACTIVE,
                         created_at=NOW, last_activity_at=NOW)
        s.add(gm)
        await s.flush()
        enc = Encounter(session_id=gm.id, mode="light", status="active", created_at=NOW)
        s.add(enc)
        await s.flush()
        cb = Combatant(encounter_id=enc.id, kind="pc", character_id=pg.id, name="Eroe",
                       conditions={"prone": True, "stunned": 5}, created_at=NOW)
        s.add(cb)
        await s.commit()
        pg_id, cb_id = pg.id, cb.id

    await _run(test_session_factory)

    async with test_session_factory() as s:
        assert (await s.get(Character, pg_id)).conditions == {"poisoned": True, "stunned": 1, "prone": True}
        assert (await s.get(Combatant, cb_id)).conditions == {}


async def test_migration_is_idempotent(test_session_factory):
    async with test_session_factory() as s:
        s.add(Character(user_id=1, name="Eroe",
                        settings={"condition_durations": {"poisoned": 3}},
                        conditions={"poisoned": True}))
        await s.commit()

    await _run(test_session_factory)
    await _run(test_session_factory)

    async with test_session_factory() as s:
        assert len((await s.execute(select(ConditionEffect))).scalars().all()) == 1
