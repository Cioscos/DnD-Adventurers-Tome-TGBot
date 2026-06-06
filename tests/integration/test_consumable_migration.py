"""The startup backfill converts legacy potion/scroll items to consumable+subtype."""
from __future__ import annotations

from core.db.migrations_data import backfill_consumable_types


async def test_backfill_converts_potion_and_scroll(client, test_session_factory):
    r = await client.post("/characters", json={"name": "Mig"})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    # Seed legacy-typed items (item_type is a free string on the API; a plain
    # potion/scroll with no structured effects passes validation).
    await client.post(f"/characters/{cid}/items", json={
        "name": "Pozione", "item_type": "potion", "quantity": 1,
        "item_metadata": {"effect": "cura"},
    })
    await client.post(f"/characters/{cid}/items", json={
        "name": "Pergamena", "item_type": "scroll", "quantity": 1,
    })

    async with test_session_factory() as s:
        converted = await backfill_consumable_types(s)
    assert converted == 2

    r = await client.get(f"/characters/{cid}/items")
    assert r.status_code == 200, r.text
    by_name = {i["name"]: i for i in r.json()}
    assert by_name["Pozione"]["item_type"] == "consumable"
    assert by_name["Pozione"]["item_metadata"]["subtype"] == "potion"
    assert by_name["Pozione"]["item_metadata"]["effect"] == "cura"
    assert by_name["Pergamena"]["item_type"] == "consumable"
    assert by_name["Pergamena"]["item_metadata"]["subtype"] == "scroll"


async def test_backfill_is_idempotent(client, test_session_factory):
    r = await client.post("/characters", json={"name": "Mig2"})
    cid = r.json()["id"]
    await client.post(f"/characters/{cid}/items", json={
        "name": "Pozione", "item_type": "potion", "quantity": 1,
    })

    async with test_session_factory() as s:
        assert await backfill_consumable_types(s) == 1
    async with test_session_factory() as s:
        assert await backfill_consumable_types(s) == 0


async def test_backfill_preserves_existing_subtype(client, test_session_factory):
    r = await client.post("/characters", json={"name": "Mig3"})
    cid = r.json()["id"]
    await client.post(f"/characters/{cid}/items", json={
        "name": "Pozione Speciale", "item_type": "potion", "quantity": 1,
        "item_metadata": {"subtype": "other", "notes": "custom"},
    })
    async with test_session_factory() as s:
        await backfill_consumable_types(s)
    r = await client.get(f"/characters/{cid}/items")
    item = next(i for i in r.json() if i["name"] == "Pozione Speciale")
    assert item["item_metadata"]["subtype"] == "other"
    assert item["item_metadata"]["notes"] == "custom"
    assert item["item_type"] == "consumable"
