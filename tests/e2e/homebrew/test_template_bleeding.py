"""E2E lifecycle test for the Sanguinamento template via HTTP API.

Install bleeding → apply custom:bleeding condition → POST /turn-start →
assert HP drops by the rolled 1d4 + notification fires.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select


async def _seed_character(test_session_factory, char_id: int, *, hp: int = 20) -> None:
    """Bootstrap HP via DB session — same pattern used by integration tests.

    The PATCH /hp surface is verified by integration tests; here we only need
    to put the character in a known HP state so the turn_started event has a
    deterministic 'before' value.
    """
    from core.db.models import Character
    async with test_session_factory() as s:
        char = (await s.execute(select(Character).where(Character.id == char_id))).scalar_one()
        char.hit_points = hp
        char.current_hit_points = hp
        await s.commit()


@pytest.mark.asyncio
async def test_bleeding_template_drains_hp_each_turn(
    client, char_id, test_session_factory, patch_random_roll,
):
    """End-to-end milestone: install bleeding → tick turn → 1d4 damage + notify."""
    # ─── Setup: HP 20/20 (DB-side, no public PATCH /hp needed)
    await _seed_character(test_session_factory, char_id, hp=20)

    # Install bleeding template
    inst = await client.post(
        f"/characters/{char_id}/homebrew/templates/bleeding/install",
    )
    assert inst.status_code == 201
    rule_id = inst.json()["id"]

    # Apply custom:bleeding condition directly on the character row.
    # NOTE: PATCH /characters/{id}/conditions accepts arbitrary keys via
    # ``dict[str, Any]``, but its response validation (``CharacterFull``)
    # exercises additional un-loaded columns on the bare ``char_id`` fixture
    # and fails before we can reach the homebrew event we care about. Setting
    # the condition via the DB skips that orthogonal surface — the dispatcher
    # reads ``char.conditions`` from the same row, so the trigger filter still
    # sees ``custom:bleeding`` and ``has_property`` checks key presence only.
    from core.db.models import Character
    async with test_session_factory() as s:
        char = (await s.execute(select(Character).where(Character.id == char_id))).scalar_one()
        char.conditions = {"custom:bleeding": {"rule_id": rule_id}}
        await s.commit()

    # Patch the 1d4 roll to a deterministic value
    patch_random_roll(3)

    # ─── Act: turn_started fires → damage_character $blood=3
    turn = await client.post(f"/characters/{char_id}/homebrew/turn-start")
    assert turn.status_code == 200
    notifs = turn.json().get("notifications", [])
    assert len(notifs) == 1
    assert "Sanguinamento" in notifs[0]["message"]
    assert "3" in notifs[0]["message"]  # $blood = 3

    # Verify HP dropped from 20 to 17
    async with test_session_factory() as s:
        from core.db.models import Character
        char = (await s.execute(select(Character).where(Character.id == char_id))).scalar_one()
    assert char.current_hit_points == 17


@pytest.mark.asyncio
async def test_bleeding_template_no_condition_no_damage(
    client, char_id, test_session_factory, patch_random_roll,
):
    """Without the condition applied, turn-start must not drain HP."""
    await _seed_character(test_session_factory, char_id, hp=20)

    inst = await client.post(
        f"/characters/{char_id}/homebrew/templates/bleeding/install",
    )
    assert inst.status_code == 201

    # NB: condition NOT applied — has_property filter must reject
    patch_random_roll(3)

    turn = await client.post(f"/characters/{char_id}/homebrew/turn-start")
    assert turn.status_code == 200
    assert turn.json().get("notifications", []) == []

    async with test_session_factory() as s:
        from core.db.models import Character
        char = (await s.execute(select(Character).where(Character.id == char_id))).scalar_one()
    assert char.current_hit_points == 20
