"""Integration test: unarmed strike endpoint (base + Monk Martial Arts)."""
from __future__ import annotations

import pytest


async def _add_monk(client, char_id: int, level: int) -> None:
    r = await client.post(
        f"/characters/{char_id}/classes",
        json={"class_name": "Monaco", "level": level, "hit_die": 8},
    )
    assert r.status_code == 201, r.text


@pytest.mark.asyncio
async def test_monk_unarmed_uses_martial_arts_die(client, char_id, patch_random_roll):
    """Monk lvl5: damage die 1d6; to-hit = mod + proficiency (pb +3 at total level 5)."""
    await _add_monk(client, char_id, 5)
    patch_random_roll([15, 4])  # [15] to-hit die (no crit/fumble), [4] damage die roll

    r = await client.post(f"/characters/{char_id}/attack/unarmed")
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["weapon_name"] == "Attacco a mano libera"
    assert body["damage_dice"] == "1d6"
    assert body["to_hit_die"] == 15
    assert body["is_critical"] is False
    assert body["is_fumble"] is False
    assert body["to_hit_bonus"] == 3   # mod 0 + pb 3
    assert body["to_hit_total"] == 18
    assert body["damage_rolls"] == [4]
    assert body["damage_total"] == 4   # 1d6 roll(4) + mod 0


@pytest.mark.asyncio
async def test_non_monk_unarmed_is_flat_one(client, char_id, patch_random_roll):
    """No class -> flat 1 + STR mod (0 by default), bludgeoning, no die roll."""
    patch_random_roll([12])  # to-hit die only
    r = await client.post(f"/characters/{char_id}/attack/unarmed")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["damage_dice"] == "1"
    assert body["damage_rolls"] == [1]
    assert body["damage_total"] == 1   # 1 + 0
    assert body["is_critical"] is False


@pytest.mark.asyncio
async def test_unarmed_fumble_does_not_wear_owned_items(
    client, char_id, test_session_factory, patch_random_roll,
):
    """#3 regression: a nat-1 *unarmed* strike must NOT wear any owned item.

    ``attack_unarmed`` emits ``attack_rolled`` with ``item_id=None``. An
    item-scoped rule (quality_wear) must not fan-out onto every owned item: the
    dispatcher now skips the fan-out for item-originated events without an
    item_id, and the template's ``attack_rolled`` trigger also requires
    ``$subject.is_equipped == True``. Either guard alone keeps the weapon intact.
    """
    import json

    from sqlalchemy import select

    from core.db.models import Item

    # Equipped weapon carrying the quality property.
    async with test_session_factory() as s:
        weapon = Item(
            character_id=char_id, name="Spada", item_type="weapon", quantity=1,
            item_metadata=json.dumps({"damage_dice": "1d8", "weapon_type": "melee"}),
            is_equipped=True,
        )
        s.add(weapon)
        await s.commit()
        await s.refresh(weapon)
        weapon_id = weapon.id

    inst = await client.post(
        f"/characters/{char_id}/homebrew/templates/quality_wear/install"
    )
    assert inst.status_code == 201, inst.text

    # Worst quality: any wear roll maps to a damaging cell, so if the rule fired
    # on the unarmed strike we would observe damage_state changing.
    async with test_session_factory() as s:
        w = (await s.execute(select(Item).where(Item.id == weapon_id))).scalar_one()
        md = json.loads(w.item_metadata)
        md["hb_quality"] = "pessima"
        w.item_metadata = json.dumps(md)
        await s.commit()

    # nat-1 unarmed strike → is_fumble True. fallback=10 would map a (wrongly
    # fired) wear roll to a "D" cell for pessima, which we assert does NOT happen.
    patch_random_roll([1])
    r = await client.post(f"/characters/{char_id}/attack/unarmed")
    assert r.status_code == 200, r.text
    assert r.json()["is_fumble"] is True

    async with test_session_factory() as s:
        w = (await s.execute(select(Item).where(Item.id == weapon_id))).scalar_one()
        md = json.loads(w.item_metadata)
    assert md["hb_damage_state"] == "integra"  # untouched — no fan-out
    assert w.is_equipped is True
