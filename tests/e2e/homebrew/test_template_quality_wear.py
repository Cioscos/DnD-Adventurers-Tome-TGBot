"""End-to-end lifecycle test for the Qualità & Usura template via HTTP."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import select


@pytest.mark.asyncio
async def test_quality_wear_complete_lifecycle(
    client, char_id, test_session_factory, patch_random_roll,
):
    """End-to-end milestone: install template → quality=pessima → 1st fumble damages → 2nd destroys + unequips."""
    from core.db.models import Item

    # ─── Setup: create equipped weapon
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

    # Install template
    inst = await client.post(f"/characters/{char_id}/homebrew/templates/quality_wear/install")
    assert inst.status_code == 201

    # Verify defaults materialized (quality=ordinaria, damage_state=integra by template)
    async with test_session_factory() as s:
        w = (await s.execute(select(Item).where(Item.id == weapon_id))).scalar_one()
        md = json.loads(w.item_metadata)
    assert md["hb_quality"] == "ordinaria"
    assert md["hb_damage_state"] == "integra"

    # Override quality directly via DB (no public PATCH to item_metadata via API here for simplicity)
    async with test_session_factory() as s:
        w = (await s.execute(select(Item).where(Item.id == weapon_id))).scalar_one()
        md = json.loads(w.item_metadata)
        md["hb_quality"] = "pessima"
        w.item_metadata = json.dumps(md)
        await s.commit()

    # ─── Act 1: nat-1 attack → first damage (integra → danneggiata)
    # wear_roll=4 → col [4,9] → "D" for quality=pessima; damage_state is "integra" → else branch → "danneggiata"
    patch_random_roll([1, 4])

    r1 = await client.post(f"/characters/{char_id}/items/{weapon_id}/attack")
    assert r1.status_code == 200
    body1 = r1.json()
    assert body1["is_fumble"] is True

    # Notifications: should include the "danneggiata" warning
    msgs1 = [n["message"].lower() for n in body1.get("homebrew_notifications", [])]
    assert any("danneggiata" in m for m in msgs1)

    # State after act 1
    async with test_session_factory() as s:
        w = (await s.execute(select(Item).where(Item.id == weapon_id))).scalar_one()
        md = json.loads(w.item_metadata)
    assert md["hb_damage_state"] == "danneggiata"
    assert w.is_equipped is True  # not destroyed yet

    # ─── Act 2: another nat-1 → second damage (danneggiata → distrutta + unequip)
    # wear_roll=5 → col [4,9] → "D" again. Since damage_state is "danneggiata", IF branch fires:
    #   distrutta + unequip + notify error.
    patch_random_roll([1, 5])

    r2 = await client.post(f"/characters/{char_id}/items/{weapon_id}/attack")
    assert r2.status_code == 200

    msgs2 = [n["message"].lower() for n in r2.json().get("homebrew_notifications", [])]
    assert any("distrutta" in m for m in msgs2)

    # State after act 2 — destroyed AND unequipped
    async with test_session_factory() as s:
        w = (await s.execute(select(Item).where(Item.id == weapon_id))).scalar_one()
        md = json.loads(w.item_metadata)
    assert md["hb_damage_state"] == "distrutta"
    assert w.is_equipped is False


async def _install_with_weapon(client, char_id, test_session_factory, *, quality: str):
    """Helper: create one equipped weapon, install quality_wear, set its quality."""
    from core.db.models import Item
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
    assert (
        await client.post(f"/characters/{char_id}/homebrew/templates/quality_wear/install")
    ).status_code == 201
    async with test_session_factory() as s:
        w = (await s.execute(select(Item).where(Item.id == weapon_id))).scalar_one()
        md = json.loads(w.item_metadata)
        md["hb_quality"] = quality
        w.item_metadata = json.dumps(md)
        await s.commit()
    return weapon_id


@pytest.mark.asyncio
async def test_quality_wear_x_outcome_destroys_immediately(
    client, char_id, test_session_factory, patch_random_roll,
):
    """#48: an 'X' table outcome destroys + unequips the item immediately, even from
    'integra' (pessima quality, wear_roll in the [1,1] bin)."""
    from core.db.models import Item
    weapon_id = await _install_with_weapon(
        client, char_id, test_session_factory, quality="pessima",
    )
    # Roll order: to-hit, damage, wear_roll. to-hit=1 (fumble), wear_roll=1 →
    # pessima col [1,1] = "X" → distrutta + unequip.
    patch_random_roll([1, 1, 1])
    r = await client.post(f"/characters/{char_id}/items/{weapon_id}/attack")
    assert r.status_code == 200
    msgs = [n["message"].lower() for n in r.json().get("homebrew_notifications", [])]
    assert any("distrutta" in m for m in msgs)
    async with test_session_factory() as s:
        w = (await s.execute(select(Item).where(Item.id == weapon_id))).scalar_one()
        md = json.loads(w.item_metadata)
    assert md["hb_damage_state"] == "distrutta"
    assert w.is_equipped is False


@pytest.mark.asyncio
async def test_quality_wear_s_outcome_is_noop(
    client, char_id, test_session_factory, patch_random_roll,
):
    """#48: an 'S' table outcome leaves the item untouched (pessima, wear_roll in the
    [16,20] bin)."""
    from core.db.models import Item
    weapon_id = await _install_with_weapon(
        client, char_id, test_session_factory, quality="pessima",
    )
    # Roll order: to-hit, damage, wear_roll. to-hit=1 (fumble), wear_roll=18 →
    # pessima col [16,20] = "S" → no-op.
    patch_random_roll([1, 1, 18])
    r = await client.post(f"/characters/{char_id}/items/{weapon_id}/attack")
    assert r.status_code == 200
    # No-op outcome → no homebrew notifications (the field comes back null, not absent).
    msgs = [n["message"].lower() for n in (r.json().get("homebrew_notifications") or [])]
    assert not any("distrutta" in m or "danneggiata" in m for m in msgs)
    async with test_session_factory() as s:
        w = (await s.execute(select(Item).where(Item.id == weapon_id))).scalar_one()
        md = json.loads(w.item_metadata)
    assert md["hb_damage_state"] == "integra"
    assert w.is_equipped is True


@pytest.mark.asyncio
async def test_quality_wear_fans_out_to_all_equipped_items_on_dropped_to_zero(
    client, char_id, test_session_factory, patch_random_roll,
):
    """#48: dropped_to_zero is a character-level event → the rule fans out to ALL
    equipped items carrying the quality property, not just one."""
    from core.db.models import Character, Item
    async with test_session_factory() as s:
        for name in ("Spada", "Ascia"):
            s.add(Item(
                character_id=char_id, name=name, item_type="weapon", quantity=1,
                item_metadata=json.dumps({"damage_dice": "1d8", "weapon_type": "melee"}),
                is_equipped=True,
            ))
        ch = (await s.execute(select(Character).where(Character.id == char_id))).scalar_one()
        ch.current_hit_points = 5
        ch.hit_points = 5
        await s.commit()
    assert (
        await client.post(f"/characters/{char_id}/homebrew/templates/quality_wear/install")
    ).status_code == 201
    # Constant wear_roll=4 → ordinaria col [4,9] = "D" → both go integra → danneggiata.
    patch_random_roll(4)
    r = await client.patch(
        f"/characters/{char_id}/hp",
        json={"op": "damage", "value": 5, "was_critical_hit": False},
    )
    assert r.status_code == 200
    async with test_session_factory() as s:
        items = (await s.execute(
            select(Item).where(Item.character_id == char_id)
        )).scalars().all()
    states = {i.name: json.loads(i.item_metadata)["hb_damage_state"] for i in items}
    assert states == {"Spada": "danneggiata", "Ascia": "danneggiata"}
