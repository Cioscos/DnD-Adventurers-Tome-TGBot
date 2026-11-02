"""Containers in the model, schemas and character response."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from core.db.models import Item

pytestmark = pytest.mark.asyncio


async def _char(client, **extra) -> int:
    r = await client.post("/characters", json={"name": "Tester", **extra})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


async def _add(client, cid, **body):
    return await client.post(f"/characters/{cid}/items", json=body)


def _item(r, name):
    return next(i for i in r.json()["items"] if i["name"] == name)


def _bag(**c):
    return {"container": c}


async def test_container_meta_validation(client):
    cid = await _char(client)
    r = await _add(client, cid, name="Zaino", item_metadata=_bag(capacity_lb=-1))
    assert r.status_code == 422
    r = await _add(client, cid, name="Zaino", item_metadata=_bag(bogus=1))
    assert r.status_code == 422
    r = await _add(client, cid, name="Zaino", item_metadata=_bag(coins={"gold": -1}))
    assert r.status_code == 422
    r = await _add(client, cid, name="Zaino", item_metadata=_bag(capacity_lb=30))
    assert r.status_code == 201
    assert _item(r, "Zaino")["container_stats"]["items_count"] == 0


async def test_create_inside_container_and_weight(client):
    cid = await _char(client)
    r = await _add(client, cid, name="Zaino", weight=5, item_metadata=_bag(capacity_lb=30))
    bag = _item(r, "Zaino")["id"]
    r = await _add(client, cid, name="Corda", weight=10, container_id=bag)
    assert r.status_code == 201
    assert r.json()["encumbrance"] == 15
    assert _item(r, "Corda")["container_id"] == bag
    s = _item(r, "Zaino")["container_stats"]
    assert s["contents_weight"] == 10 and s["items_count"] == 1


async def test_weightless_container_excluded(client):
    cid = await _char(client)
    r = await _add(client, cid, name="Borsa", weight=2, item_metadata=_bag(counts_weight=False))
    bag = _item(r, "Borsa")["id"]
    r = await _add(client, cid, name="Incudine", weight=100, container_id=bag)
    assert r.json()["encumbrance"] == 2


async def test_foreign_container_rejected(client):
    a, b = await _char(client), await _char(client)
    r = await _add(client, a, name="Zaino", item_metadata=_bag())
    bag_a = _item(r, "Zaino")["id"]
    r = await _add(client, b, name="Corda", container_id=bag_a)
    assert r.status_code == 404
    r = await _add(client, b, name="Sasso")
    rock = _item(r, "Sasso")["id"]
    r = await _add(client, b, name="Corda", container_id=rock)
    assert r.status_code == 422 and r.json()["detail"] == "not_a_container"


async def test_contained_wondrous_gives_no_bonus(client, test_session_factory):
    cid = await _char(client)
    meta = {"requires_attunement": True, "attuned": True, "bonuses": [{"target": "ac", "value": 1}]}
    r = await _add(client, cid, name="Amuleto", item_metadata=meta)
    assert r.json()["ac_breakdown"]["items"] == 1
    amu = _item(r, "Amuleto")["id"]
    r = await _add(client, cid, name="Zaino", item_metadata=_bag())
    bag = _item(r, "Zaino")["id"]
    async with test_session_factory() as s:
        (await s.get(Item, amu)).container_id = bag
        await s.commit()
    r = await client.get(f"/characters/{cid}")
    assert r.json()["ac_breakdown"]["items"] == 0
    assert _item(r, "Amuleto")["item_metadata"]["attuned"] is True


async def test_coin_totals_and_breakdown(client):
    cid = await _char(client)
    await client.patch(f"/characters/{cid}/currency", json={"gold": 2})
    r = await _add(client, cid, name="Forziere", item_metadata=_bag(coins={"gold": 300}))
    j = r.json()
    assert j["coin_totals"]["gold"] == 302
    assert [b["container_id"] for b in j["coin_breakdown"]] == [None, _item(r, "Forziere")["id"]]
    assert j["coin_breakdown"][1]["coins"]["gold"] == 300
