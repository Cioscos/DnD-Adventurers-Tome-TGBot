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


async def _move(client, cid, ids, container_id=None, quantity=None):
    return await client.post(
        f"/characters/{cid}/items/move",
        json={"item_ids": ids, "container_id": container_id, "quantity": quantity},
    )


async def test_uncontainer_reparents(client):
    cid = await _char(client)
    r = await _add(client, cid, name="Zaino", item_metadata=_bag(coins={"gold": 5}))
    bag = _item(r, "Zaino")["id"]
    await _add(client, cid, name="Corda", container_id=bag)
    r = await _add(client, cid, name="Torcia", container_id=bag)
    r = await client.patch(f"/characters/{cid}/items/{bag}", json={"item_metadata": {"x": 1}})
    assert r.status_code == 200, r.text
    assert _item(r, "Corda")["container_id"] is None and _item(r, "Torcia")["container_id"] is None
    assert r.json()["coin_totals"]["gold"] == 5
    assert r.json()["currency"]["gold"] == 5


async def test_move_multi_and_back(client):
    cid = await _char(client)
    r = await _add(client, cid, name="Zaino", item_metadata=_bag())
    bag = _item(r, "Zaino")["id"]
    for n in "ABC":
        r = await _add(client, cid, name=n, item_type="weapon")
    ids = [_item(r, n)["id"] for n in "ABC"]
    r = await _move(client, cid, ids, bag)
    assert r.status_code == 200, r.text
    assert all(_item(r, n)["container_id"] == bag for n in "ABC")
    r = await _move(client, cid, ids, None)
    assert all(_item(r, n)["container_id"] is None for n in "ABC")


async def test_move_cycle_rejected(client):
    cid = await _char(client)
    r = await _add(client, cid, name="Zaino", item_metadata=_bag())
    bag = _item(r, "Zaino")["id"]
    r = await _add(client, cid, name="Borsa", item_metadata=_bag(), container_id=bag)
    pouch = _item(r, "Borsa")["id"]
    for ids in ([bag], [bag, pouch]):
        r = await _move(client, cid, ids, pouch)
        assert r.status_code == 422 and r.json()["detail"] == "container_cycle"
    r = await client.get(f"/characters/{cid}")
    assert _item(r, "Zaino")["container_id"] is None and _item(r, "Borsa")["container_id"] == bag
    r = await _move(client, cid, [bag], bag)
    assert r.status_code == 422


async def test_move_errors(client):
    cid, other = await _char(client), await _char(client)
    r = await _add(client, cid, name="Sasso")
    rock = _item(r, "Sasso")["id"]
    r = await _add(client, other, name="Zaino", item_metadata=_bag())
    foreign = _item(r, "Zaino")["id"]
    assert (await _move(client, cid, [rock], rock)).json()["detail"] == "not_a_container"
    assert (await _move(client, cid, [rock], foreign)).status_code == 404
    assert (await _move(client, cid, [foreign], None)).status_code == 404


async def test_move_unequips(client):
    cid = await _char(client)
    r = await _add(client, cid, name="Zaino", item_metadata=_bag())
    bag = _item(r, "Zaino")["id"]
    r = await _add(client, cid, name="Scudo", item_type="shield", item_metadata={"ac_bonus": 2})
    shield = _item(r, "Scudo")["id"]
    base = r.json()["shield_armor_class"]
    r = await client.patch(
        f"/characters/{cid}/items/{shield}", json={"is_equipped": True, "equipment_slot": "off_hand"}
    )
    assert r.json()["shield_armor_class"] == base + 2
    r = await _move(client, cid, [shield], bag)
    j = r.json()
    assert j["unequipped_item_names"] == ["Scudo"]
    assert _item(r, "Scudo")["is_equipped"] is False and _item(r, "Scudo")["equipment_slot"] is None
    assert j["shield_armor_class"] == base


async def test_equip_pulls_out(client):
    cid = await _char(client)
    r = await _add(client, cid, name="Zaino", item_metadata=_bag())
    bag = _item(r, "Zaino")["id"]
    r = await _add(client, cid, name="Spada", item_type="weapon", container_id=bag)
    sw = _item(r, "Spada")["id"]
    r = await client.patch(
        f"/characters/{cid}/items/{sw}", json={"is_equipped": True, "equipment_slot": "main_hand"}
    )
    assert r.status_code == 200, r.text
    assert _item(r, "Spada")["container_id"] is None


async def test_add_in_container_forces_unequipped(client):
    cid = await _char(client)
    r = await _add(client, cid, name="Zaino", item_metadata=_bag())
    bag = _item(r, "Zaino")["id"]
    r = await _add(client, cid, name="Spada", item_type="weapon", container_id=bag,
                   is_equipped=True, equipment_slot="main_hand")
    assert r.status_code == 201, r.text
    s = _item(r, "Spada")
    assert s["is_equipped"] is False and s["equipment_slot"] is None


async def test_move_split_and_merge(client):
    cid = await _char(client)
    r = await _add(client, cid, name="Zaino", item_metadata=_bag())
    bag = _item(r, "Zaino")["id"]
    r = await _add(client, cid, name="Razioni", quantity=10)
    rid = _item(r, "Razioni")["id"]
    r = await _move(client, cid, [rid], bag, quantity=4)
    rows = {i["container_id"]: i["quantity"] for i in r.json()["items"] if i["name"] == "Razioni"}
    assert rows == {None: 6, bag: 4}
    r = await _move(client, cid, [rid], bag, quantity=7)
    assert r.status_code == 422
    r = await _move(client, cid, [rid], bag)
    rows = [i for i in r.json()["items"] if i["name"] == "Razioni"]
    assert len(rows) == 1 and rows[0]["quantity"] == 10 and rows[0]["container_id"] == bag


async def test_add_dedup_per_container(client):
    cid = await _char(client)
    r = await _add(client, cid, name="Zaino", item_metadata=_bag())
    bag = _item(r, "Zaino")["id"]
    await _add(client, cid, name="Corda")
    await _add(client, cid, name="Corda", container_id=bag)
    r = await _add(client, cid, name="Corda", container_id=bag)
    rows = [i for i in r.json()["items"] if i["name"] == "Corda"]
    assert sorted(i["quantity"] for i in rows) == [1, 2]


async def test_delete_container_reparents(client):
    cid = await _char(client)
    r = await _add(client, cid, name="A", item_metadata=_bag())
    a = _item(r, "A")["id"]
    r = await _add(client, cid, name="B", item_metadata=_bag(coins={"gold": 7}), container_id=a)
    b = _item(r, "B")["id"]
    await _add(client, cid, name="C", item_metadata=_bag(), container_id=b)
    await _add(client, cid, name="X", item_type="weapon", container_id=b)
    r = await _add(client, cid, name="Y", item_type="weapon", container_id=b)
    before = r.json()["coin_totals"]
    r = await client.delete(f"/characters/{cid}/items/{b}")
    assert r.status_code == 200, r.text
    assert all(_item(r, n)["container_id"] == a for n in ("C", "X", "Y"))
    assert _item(r, "A")["item_metadata"]["container"]["coins"]["gold"] == 7
    assert r.json()["coin_totals"] == before
    r = await client.delete(f"/characters/{cid}/items/{a}")
    assert all(_item(r, n)["container_id"] is None for n in ("C", "X", "Y"))
    assert r.json()["currency"]["gold"] == 7 and r.json()["coin_totals"] == before


async def test_container_quantity_must_be_one(client):
    cid = await _char(client)
    r = await _add(client, cid, name="Zaino", quantity=3, item_metadata=_bag())
    assert r.status_code == 422 and r.json()["detail"] == "container_quantity"
    r = await _add(client, cid, name="Zaino", item_metadata=_bag())
    bag = _item(r, "Zaino")["id"]
    r = await client.patch(f"/characters/{cid}/items/{bag}", json={"quantity": 2})
    assert r.status_code == 422
