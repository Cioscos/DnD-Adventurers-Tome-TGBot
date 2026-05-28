"""End-to-end lifecycle test for the Qualità & Usura template via HTTP."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import select


def _patch_rolls(monkeypatch, rolls: list[int], fallback: int = 10):
    """Patch random.randint to return values from `rolls` in order, fallback after."""
    import random as _random
    it = iter(rolls)
    monkeypatch.setattr(_random, "randint", lambda lo, hi: next(it, fallback))


@pytest.mark.asyncio
async def test_quality_wear_complete_lifecycle(
    client, char_id, test_session_factory, monkeypatch,
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
    _patch_rolls(monkeypatch, [1, 4])

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
    _patch_rolls(monkeypatch, [1, 5])

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
