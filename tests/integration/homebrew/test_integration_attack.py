"""Integration test: attack_rolled event fires homebrew rules."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import select


@pytest.mark.asyncio
async def test_attack_fumble_with_quality_wear_marks_weapon_damaged(
    client, char_id, test_session_factory, monkeypatch,
):
    """Nat-1 attack on a quality=pessima weapon → hb_damage_state becomes 'danneggiata'.

    Forces:
      - to_hit_die = 1 (nat-1 fumble)
      - wear_roll = 7 (col [4,9] → D for quality=pessima)
    """
    from core.db.models import Item

    # Pre-create the weapon equipped + quality=pessima
    async with test_session_factory() as s:
        weapon = Item(
            character_id=char_id, name="Spada lunga", item_type="weapon", quantity=1,
            item_metadata=json.dumps({
                "damage_dice": "1d8", "weapon_type": "melee",
                "hb_quality": "pessima", "hb_damage_state": "integra",
            }),
            is_equipped=True,
        )
        s.add(weapon)
        await s.commit()
        await s.refresh(weapon)
        weapon_id = weapon.id

    # Install template
    r = await client.post(f"/characters/{char_id}/homebrew/templates/quality_wear/install")
    assert r.status_code == 201

    # Force deterministic rolls via a shared iterator on the global random module.
    # Both items.py and actions.py do `import random` so they share the same module
    # object; patching either module's .randint attribute patches the same function.
    # Call order: [1] to-hit die (nat-1 → fumble), [7] wear_roll ([4,9] bin → "D").
    # "D" + damage_state=integra (not already "danneggiata") → else branch → "danneggiata".
    import random as _random
    rolls = iter([1, 7])
    monkeypatch.setattr(_random, "randint", lambda lo, hi: next(rolls, 10))

    # Trigger attack
    r = await client.post(f"/characters/{char_id}/items/{weapon_id}/attack")
    assert r.status_code == 200
    body = r.json()
    assert body["is_fumble"] is True

    # Verify weapon metadata changed
    async with test_session_factory() as s:
        weapon = (await s.execute(select(Item).where(Item.id == weapon_id))).scalar_one()
        md = json.loads(weapon.item_metadata)
    assert md["hb_damage_state"] == "danneggiata"
    assert md["hb_quality"] == "pessima"  # untouched


@pytest.mark.asyncio
async def test_attack_normal_roll_does_not_mark_weapon(
    client, char_id, test_session_factory, monkeypatch,
):
    """Normal hit (no fumble) → no wear applied."""
    from core.db.models import Item

    async with test_session_factory() as s:
        weapon = Item(
            character_id=char_id, name="Spada", item_type="weapon", quantity=1,
            item_metadata=json.dumps({
                "damage_dice": "1d8", "weapon_type": "melee",
                "hb_quality": "pessima", "hb_damage_state": "integra",
            }),
            is_equipped=True,
        )
        s.add(weapon)
        await s.commit()
        await s.refresh(weapon)
        weapon_id = weapon.id

    await client.post(f"/characters/{char_id}/homebrew/templates/quality_wear/install")

    # to-hit_die=15 (no fumble), other rolls don't matter
    monkeypatch.setattr("api.routers.items.random.randint", lambda lo, hi: 15)

    r = await client.post(f"/characters/{char_id}/items/{weapon_id}/attack")
    assert r.status_code == 200
    assert r.json()["is_fumble"] is False

    async with test_session_factory() as s:
        weapon = (await s.execute(select(Item).where(Item.id == weapon_id))).scalar_one()
        md = json.loads(weapon.item_metadata)
    assert md["hb_damage_state"] == "integra"  # untouched


@pytest.mark.asyncio
async def test_attack_with_no_rule_installed_still_works(
    client, char_id, test_session_factory, monkeypatch,
):
    """Sanity: dispatcher should be a no-op when no rules are installed."""
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

    monkeypatch.setattr("api.routers.items.random.randint", lambda lo, hi: 1)

    r = await client.post(f"/characters/{char_id}/items/{weapon_id}/attack")
    assert r.status_code == 200
    # Item metadata stays as it was — no homebrew rule to react.
    async with test_session_factory() as s:
        weapon = (await s.execute(select(Item).where(Item.id == weapon_id))).scalar_one()
        md = json.loads(weapon.item_metadata)
    assert "hb_damage_state" not in md
