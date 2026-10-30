"""Le armi con la proprietà munizioni scalano la munizione equipaggiata."""
from __future__ import annotations


async def _char(client) -> int:
    r = await client.post("/characters", json={"name": "Arciere"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _add(client, cid, name, item_type, quantity=1, meta=None) -> int:
    r = await client.post(
        f"/characters/{cid}/items",
        json={"name": name, "item_type": item_type, "quantity": quantity, "item_metadata": meta or {}},
    )
    assert r.status_code == 201, r.text
    return next(i["id"] for i in r.json()["items"] if i["name"] == name)


async def _bow(client, cid) -> int:
    meta = {"damage_dice": "1d8", "weapon_type": "ranged", "properties": ["prop_ammunition"]}
    return await _add(client, cid, "Arco", "weapon", meta=meta)


async def _arrows(client, cid, quantity=20, equip=True) -> int:
    aid = await _add(client, cid, "Frecce", "ammunition", quantity=quantity)
    if equip:
        r = await client.patch(
            f"/characters/{cid}/items/{aid}",
            json={"is_equipped": True, "equipment_slot": "ammunition"},
        )
        assert r.status_code == 200, r.text
    return aid


async def _qty(client, cid, item_id) -> int:
    items = (await client.get(f"/characters/{cid}/items")).json()
    return next(i["quantity"] for i in items if i["id"] == item_id)


async def test_ammo_weapon_consumes_slot_item(client):
    cid = await _char(client)
    wid = await _bow(client, cid)
    aid = await _arrows(client, cid)
    r = await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 10})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ammo"] == {"item_id": aid, "name": "Frecce", "remaining": 19}
    assert body["ammo_missing"] is False
    assert await _qty(client, cid, aid) == 19


async def test_ammo_consumed_on_fumble(client):
    cid = await _char(client)
    wid = await _bow(client, cid)
    aid = await _arrows(client, cid)
    r = await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 1})
    assert r.status_code == 200, r.text
    assert r.json()["ammo"]["remaining"] == 19
    assert await _qty(client, cid, aid) == 19


async def test_inspiration_reroll_does_not_consume(client):
    cid = await _char(client)
    wid = await _bow(client, cid)
    aid = await _arrows(client, cid)
    r = await client.patch(f"/characters/{cid}/inspiration", json={"heroic_inspiration": True})
    assert r.status_code == 200, r.text
    r = await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 10})
    assert r.json()["ammo"]["remaining"] == 19
    r = await client.post(
        f"/characters/{cid}/items/{wid}/attack", json={"die": 12, "with_inspiration": True}
    )
    assert r.status_code == 200, r.text
    assert await _qty(client, cid, aid) == 19


async def test_empty_slot_single_ammo_item_fallback(client):
    cid = await _char(client)
    wid = await _bow(client, cid)
    aid = await _arrows(client, cid, equip=False)
    r = await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 10})
    assert r.status_code == 200, r.text
    assert r.json()["ammo"]["item_id"] == aid
    assert await _qty(client, cid, aid) == 19


async def test_ammo_missing_still_attacks(client):
    cid = await _char(client)
    wid = await _bow(client, cid)
    r = await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 10})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ammo_missing"] is True
    assert body["ammo"] is None


async def test_ammo_never_negative(client):
    cid = await _char(client)
    wid = await _bow(client, cid)
    aid = await _arrows(client, cid, quantity=0)
    r = await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 10})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ammo_missing"] is True
    assert await _qty(client, cid, aid) == 0


async def test_melee_weapon_untouched(client):
    cid = await _char(client)
    meta = {"damage_dice": "1d8", "weapon_type": "melee", "properties": []}
    wid = await _add(client, cid, "Spada", "weapon", meta=meta)
    aid = await _arrows(client, cid)
    r = await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 10})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ammo"] is None
    assert body["ammo_missing"] is False
    assert await _qty(client, cid, aid) == 20


async def test_ammunition_type_fits_ammunition_slot(client):
    cid = await _char(client)
    aid = await _add(client, cid, "Frecce", "ammunition", quantity=5)
    r = await client.patch(
        f"/characters/{cid}/items/{aid}",
        json={"is_equipped": True, "equipment_slot": "ammunition"},
    )
    assert r.status_code == 200, r.text
