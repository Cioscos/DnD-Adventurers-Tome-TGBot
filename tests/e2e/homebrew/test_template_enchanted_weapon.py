"""E2E lifecycle test for the Arma Incantata template via HTTP API.

Install enchanted_weapon → equip a weapon with hb_enchanted=true →
POST /items/{id}/attack → assert "+1d6 fuoco" notification is surfaced
in the weapon attack response's ``homebrew_notifications`` list.
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import select


@pytest.mark.asyncio
async def test_enchanted_weapon_template_fires_on_attack(
    client, char_id, test_session_factory, patch_random_roll,
):
    """End-to-end milestone: enchanted weapon → attack → +1d6 fire notify."""
    from core.db.models import Item

    # ─── Setup: create an equipped weapon WITH hb_enchanted=True up-front.
    # We seed via the DB rather than POST /items + PATCH because PATCH /items
    # overwrites the full ``item_metadata`` blob (no merge), and the install
    # step's ``_materialize_property_defaults`` only writes missing keys —
    # so it leaves our explicit ``hb_enchanted=True`` intact.
    async with test_session_factory() as s:
        weapon = Item(
            character_id=char_id, name="Spada Lunga", item_type="weapon", quantity=1,
            item_metadata=json.dumps({
                "damage_dice": "1d8", "weapon_type": "melee",
                "hb_enchanted": True,
            }),
            is_equipped=True,
        )
        s.add(weapon)
        await s.commit()
        await s.refresh(weapon)
        weapon_id = weapon.id

    # Install enchanted_weapon template (after the item exists so the rule's
    # property defaults pass through `_materialize_property_defaults` for the
    # already-existing weapon — leaving our True override untouched).
    inst = await client.post(
        f"/characters/{char_id}/homebrew/templates/enchanted_weapon/install",
    )
    assert inst.status_code == 201

    # Verify the override survived install (defensive — would mean a regression
    # in `_materialize_property_defaults` if False).
    async with test_session_factory() as s:
        w = (await s.execute(select(Item).where(Item.id == weapon_id))).scalar_one()
        md = json.loads(w.item_metadata)
    assert md["hb_enchanted"] is True

    # Patch random rolls: attack_with_weapon calls random.randint in order:
    #   1) to_hit_die (1d20) → 15 (hit, not crit, not fumble)
    #   2) weapon damage (1d8) → 5
    # Then the rule fires: roll_dice 1d6 → 4 (fire damage var)
    patch_random_roll([15, 5, 4])

    # ─── Act: attack
    r = await client.post(f"/characters/{char_id}/items/{weapon_id}/attack")
    assert r.status_code == 200
    body = r.json()
    assert body["is_critical"] is False
    assert body["is_fumble"] is False

    notifs = body.get("homebrew_notifications", [])
    fire_notifs = [n for n in notifs if "fuoco" in n["message"]]
    assert len(fire_notifs) == 1, notifs
    assert "4" in fire_notifs[0]["message"]  # $fire = 4


@pytest.mark.asyncio
async def test_enchanted_weapon_no_fire_when_not_enchanted(
    client, char_id, test_session_factory, patch_random_roll,
):
    """Default ``hb_enchanted=False`` (materialized at install) — no fire notify."""
    from core.db.models import Item

    async with test_session_factory() as s:
        weapon = Item(
            character_id=char_id, name="Spada Comune", item_type="weapon", quantity=1,
            item_metadata=json.dumps({
                "damage_dice": "1d8", "weapon_type": "melee",
            }),
            is_equipped=True,
        )
        s.add(weapon)
        await s.commit()
        await s.refresh(weapon)
        weapon_id = weapon.id

    inst = await client.post(
        f"/characters/{char_id}/homebrew/templates/enchanted_weapon/install",
    )
    assert inst.status_code == 201

    # Install materialized hb_enchanted=False (the property's declared default).
    async with test_session_factory() as s:
        w = (await s.execute(select(Item).where(Item.id == weapon_id))).scalar_one()
        md = json.loads(w.item_metadata)
    assert md["hb_enchanted"] is False

    # Same roll sequence as the happy-path test, but since the filter
    # `$subject.enchanted == True` fails, no `roll_dice` happens and the
    # third roll is never consumed.
    patch_random_roll([15, 5, 4])

    r = await client.post(f"/characters/{char_id}/items/{weapon_id}/attack")
    assert r.status_code == 200
    notifs = r.json().get("homebrew_notifications") or []
    assert not any("fuoco" in n.get("message", "") for n in notifs)
