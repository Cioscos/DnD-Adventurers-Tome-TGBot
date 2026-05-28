"""Integration tests for damage_taken / dropped_to_zero / hp_healed events."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import select


def _patch_random(monkeypatch, value: int):
    import random as _random
    monkeypatch.setattr(_random, "randint", lambda lo, hi: value)


@pytest.mark.asyncio
async def test_critical_hit_with_quality_armor_marks_damaged(
    client, char_id, test_session_factory, monkeypatch,
):
    """Damage with was_critical_hit=True on equipped armor → Q&U marks it danneggiata."""
    from core.db.models import Item, Character
    # Bring HP above zero so DAMAGE doesn't make it drop to 0
    async with test_session_factory() as s:
        char = (await s.execute(select(Character).where(Character.id == char_id))).scalar_one()
        char.hit_points = 20
        char.current_hit_points = 20
        await s.commit()

    async with test_session_factory() as s:
        armor = Item(
            character_id=char_id, name="Cotta di maglia", item_type="armor",
            item_metadata=json.dumps({
                "hb_quality": "ordinaria", "hb_damage_state": "integra",
            }),
            is_equipped=True,
        )
        s.add(armor)
        await s.commit()
        await s.refresh(armor)
        armor_id = armor.id

    await client.post(f"/characters/{char_id}/homebrew/templates/quality_wear/install")

    # wear_roll = 2 → col [2,3] → D for quality=ordinaria; armor.damage_state goes integra → danneggiata.
    _patch_random(monkeypatch, 2)

    r = await client.patch(
        f"/characters/{char_id}/hp",
        json={"op": "damage", "value": 5, "was_critical_hit": True},
    )
    assert r.status_code == 200

    async with test_session_factory() as s:
        armor = (await s.execute(select(Item).where(Item.id == armor_id))).scalar_one()
        md = json.loads(armor.item_metadata)
    assert md["hb_damage_state"] == "danneggiata"


@pytest.mark.asyncio
async def test_non_critical_damage_does_not_trigger_quality_wear(
    client, char_id, test_session_factory, monkeypatch,
):
    """Damage with was_critical_hit=False on equipped armor → metadata untouched."""
    from core.db.models import Item, Character
    async with test_session_factory() as s:
        char = (await s.execute(select(Character).where(Character.id == char_id))).scalar_one()
        char.hit_points = 20
        char.current_hit_points = 20
        await s.commit()

    async with test_session_factory() as s:
        armor = Item(
            character_id=char_id, name="Cotta", item_type="armor",
            item_metadata=json.dumps({"hb_quality": "ordinaria", "hb_damage_state": "integra"}),
            is_equipped=True,
        )
        s.add(armor)
        await s.commit()
        await s.refresh(armor)
        armor_id = armor.id

    await client.post(f"/characters/{char_id}/homebrew/templates/quality_wear/install")

    _patch_random(monkeypatch, 2)

    r = await client.patch(
        f"/characters/{char_id}/hp",
        json={"op": "damage", "value": 5, "was_critical_hit": False},
    )
    assert r.status_code == 200

    async with test_session_factory() as s:
        armor = (await s.execute(select(Item).where(Item.id == armor_id))).scalar_one()
        md = json.loads(armor.item_metadata)
    assert md["hb_damage_state"] == "integra"


@pytest.mark.asyncio
async def test_dropped_to_zero_with_quality_armor_marks_damaged(
    client, char_id, test_session_factory, monkeypatch,
):
    """HP dropped from positive to 0 on equipped armor → dropped_to_zero event fires Q&U."""
    from core.db.models import Item, Character
    async with test_session_factory() as s:
        char = (await s.execute(select(Character).where(Character.id == char_id))).scalar_one()
        char.hit_points = 10
        char.current_hit_points = 10
        await s.commit()

    async with test_session_factory() as s:
        armor = Item(
            character_id=char_id, name="Cotta", item_type="armor",
            item_metadata=json.dumps({"hb_quality": "ordinaria", "hb_damage_state": "integra"}),
            is_equipped=True,
        )
        s.add(armor)
        await s.commit()
        await s.refresh(armor)
        armor_id = armor.id

    await client.post(f"/characters/{char_id}/homebrew/templates/quality_wear/install")

    _patch_random(monkeypatch, 2)

    # was_critical_hit=False but damage drops to 0 → dropped_to_zero trigger fires (Q&U)
    r = await client.patch(
        f"/characters/{char_id}/hp",
        json={"op": "damage", "value": 100, "was_critical_hit": False},
    )
    assert r.status_code == 200

    async with test_session_factory() as s:
        armor = (await s.execute(select(Item).where(Item.id == armor_id))).scalar_one()
        md = json.loads(armor.item_metadata)
    assert md["hb_damage_state"] == "danneggiata"


@pytest.mark.asyncio
async def test_heal_does_not_trigger_quality_wear(
    client, char_id, test_session_factory, monkeypatch,
):
    """Heal event fires hp_healed but Q&U doesn't subscribe to it → armor untouched."""
    from core.db.models import Item, Character
    async with test_session_factory() as s:
        char = (await s.execute(select(Character).where(Character.id == char_id))).scalar_one()
        char.hit_points = 20
        char.current_hit_points = 5
        await s.commit()

    async with test_session_factory() as s:
        armor = Item(
            character_id=char_id, name="Cotta", item_type="armor",
            item_metadata=json.dumps({"hb_quality": "ordinaria", "hb_damage_state": "integra"}),
            is_equipped=True,
        )
        s.add(armor)
        await s.commit()
        await s.refresh(armor)
        armor_id = armor.id

    await client.post(f"/characters/{char_id}/homebrew/templates/quality_wear/install")

    _patch_random(monkeypatch, 2)

    r = await client.patch(
        f"/characters/{char_id}/hp",
        json={"op": "heal", "value": 5},
    )
    assert r.status_code == 200

    async with test_session_factory() as s:
        armor = (await s.execute(select(Item).where(Item.id == armor_id))).scalar_one()
        md = json.loads(armor.item_metadata)
    assert md["hb_damage_state"] == "integra"


@pytest.mark.asyncio
async def test_hp_endpoint_backwards_compatible_without_was_critical_hit_field(
    client, char_id, test_session_factory,
):
    """Body without was_critical_hit must still work (default False)."""
    from core.db.models import Character
    async with test_session_factory() as s:
        char = (await s.execute(select(Character).where(Character.id == char_id))).scalar_one()
        char.hit_points = 20
        char.current_hit_points = 20
        await s.commit()

    r = await client.patch(
        f"/characters/{char_id}/hp",
        json={"op": "damage", "value": 3},
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_critical_hit_returns_homebrew_notifications(
    client, char_id, test_session_factory, monkeypatch,
):
    """Critical hit on Q&U armor → HP response includes homebrew_notifications."""
    from core.db.models import Item, Character

    async with test_session_factory() as s:
        char = (await s.execute(select(Character).where(Character.id == char_id))).scalar_one()
        char.hit_points = 20
        char.current_hit_points = 20
        await s.commit()

    async with test_session_factory() as s:
        armor = Item(
            character_id=char_id, name="Cotta", item_type="armor",
            item_metadata=json.dumps({"hb_quality": "ordinaria", "hb_damage_state": "integra"}),
            is_equipped=True,
        )
        s.add(armor)
        await s.commit()
        await s.refresh(armor)
        armor_id = armor.id

    inst = await client.post(f"/characters/{char_id}/homebrew/templates/quality_wear/install")
    assert inst.status_code == 201

    _patch_random(monkeypatch, 2)

    r = await client.patch(
        f"/characters/{char_id}/hp",
        json={"op": "damage", "value": 5, "was_critical_hit": True},
    )
    assert r.status_code == 200
    body = r.json()
    notifs = body.get("homebrew_notifications")
    assert notifs is not None
    assert len(notifs) >= 1
    assert any("danneggiata" in n["message"].lower() for n in notifs)
    n = notifs[0]
    assert n["severity"] in {"info", "warning", "error", "success"}
    assert n["rule_id"] is not None
    assert n["rule_name"] == "Qualità & Usura"


@pytest.mark.asyncio
async def test_hp_no_rule_returns_no_notifications_field(
    client, char_id, test_session_factory,
):
    """Endpoint should NOT set homebrew_notifications when no rule fires."""
    from core.db.models import Character
    async with test_session_factory() as s:
        char = (await s.execute(select(Character).where(Character.id == char_id))).scalar_one()
        char.hit_points = 20
        char.current_hit_points = 20
        await s.commit()

    r = await client.patch(
        f"/characters/{char_id}/hp",
        json={"op": "damage", "value": 3},
    )
    assert r.status_code == 200
    body = r.json()
    # The field is Optional[list]; either omitted or null.
    assert body.get("homebrew_notifications") is None
