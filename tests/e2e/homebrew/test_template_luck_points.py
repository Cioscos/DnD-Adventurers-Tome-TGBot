"""E2E lifecycle test for the Punti Fortuna template via HTTP API.

Install luck_points → GET /resources shows 3/3 →
POST /manual-trigger decrements to 2 + notification →
POST /rest long restores to 3 + notification.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select


async def _seed_character(test_session_factory, char_id: int) -> None:
    """Bootstrap minimum AC + HP defaults so ``CharacterFull`` response
    validation (used by POST /rest) doesn't fail on the bare ``char_id``
    fixture's un-loaded columns. The defaults mirror the model column
    ``default=`` values; setting them explicitly forces them onto the row.
    """
    from core.db.models import Character
    async with test_session_factory() as s:
        char = (await s.execute(select(Character).where(Character.id == char_id))).scalar_one()
        char.hit_points = 10
        char.current_hit_points = 10
        char.base_armor_class = 10
        char.shield_armor_class = 0
        char.magic_armor = 0
        char.carry_capacity = 150
        await s.commit()


@pytest.mark.asyncio
async def test_luck_points_lifecycle(
    client, char_id, test_session_factory,
):
    """End-to-end milestone: install → spend (manual_trigger) → restore (long rest)."""
    await _seed_character(test_session_factory, char_id)

    # ─── Install template
    inst = await client.post(
        f"/characters/{char_id}/homebrew/templates/luck_points/install",
    )
    assert inst.status_code == 201
    rule_id = inst.json()["id"]

    # Verify resource was materialized at the declared max
    res_list = (await client.get(f"/characters/{char_id}/homebrew/resources")).json()
    assert len(res_list) == 1
    res0 = res_list[0]
    assert res0["key"] == "luck_points"
    assert res0["current"] == 3
    assert res0["max"] == 3
    assert res0["restoration_type"] == "long_rest"

    # ─── Spend a luck point via manual_trigger
    mt = await client.post(
        f"/characters/{char_id}/homebrew/manual-trigger/{rule_id}",
    )
    assert mt.status_code == 200
    notifs = mt.json()["notifications"]
    assert any("Punto Fortuna usato" in n["message"] for n in notifs)

    # Verify resource is now 2/3
    res_after_spend = (await client.get(f"/characters/{char_id}/homebrew/resources")).json()[0]
    assert res_after_spend["current"] == 2

    # ─── Long rest restores
    rest = await client.post(
        f"/characters/{char_id}/rest", json={"rest_type": "long"},
    )
    assert rest.status_code == 200

    # Resource should be back to 3/3
    res_after_rest = (await client.get(f"/characters/{char_id}/homebrew/resources")).json()[0]
    assert res_after_rest["current"] == 3

    # Long rest also surfaces the restore notification
    rest_notifs = rest.json().get("homebrew_notifications", []) or []
    assert any("Punti Fortuna ripristinati" in n.get("message", "") for n in rest_notifs)
