"""Coins living in containers: automatic withdrawal, exact undo, moves, convert."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def _setup(client, purse_gold=2, bag_gold=300):
    cid = (await client.post("/characters", json={"name": "T"})).json()["id"]
    await client.patch(f"/characters/{cid}/currency", json={"gold": purse_gold})
    r = await client.post(f"/characters/{cid}/items", json={
        "name": "Zaino", "item_metadata": {"container": {"coins": {"gold": bag_gold}}}})
    bag = next(i for i in r.json()["items"] if i["name"] == "Zaino")["id"]
    return cid, bag


def _adj(client, cid, delta, placements=None, coin="gold"):
    body = {"coin": coin, "delta": delta}
    if placements is not None:
        body["placements"] = placements
    return client.post(f"/characters/{cid}/currency/adjust", json=body)


def _pl(r):
    return [(p["container_id"], p["amount"]) for p in r.json()["placements"]]


async def test_adjust_spend_split(client):
    cid, bag = await _setup(client)
    r = await _adj(client, cid, -5)
    assert r.status_code == 200, r.text
    assert _pl(r) == [(None, -2), (bag, -3)]
    assert r.json()["coin_totals"]["gold"] == 297
    assert r.json()["purse"]["gold"] == 0


async def test_adjust_receive_to_purse(client):
    cid, _ = await _setup(client)
    r = await _adj(client, cid, 10)
    assert _pl(r) == [(None, 10)] and r.json()["purse"]["gold"] == 12


async def test_adjust_insufficient(client):
    cid, _ = await _setup(client)
    assert (await _adj(client, cid, -1000)).status_code == 409
    c = (await client.get(f"/characters/{cid}")).json()
    assert c["coin_totals"]["gold"] == 302 and c["currency"]["gold"] == 2


async def test_adjust_validation(client):
    cid, bag = await _setup(client)
    assert (await _adj(client, cid, 0)).status_code == 422
    assert (await _adj(client, cid, 5, [{"container_id": None, "amount": 4}])).status_code == 422
    # Over-withdrawal at one location is atomic: the valid half is not applied.
    r = await _adj(client, cid, -5, [{"container_id": None, "amount": -1}, {"container_id": bag, "amount": -4}])
    assert r.status_code == 200
    r = await _adj(client, cid, -3, [{"container_id": None, "amount": -2}, {"container_id": bag, "amount": -1}])
    assert r.status_code == 409
    assert (await client.get(f"/characters/{cid}")).json()["coin_totals"]["gold"] == 297


async def test_undo_exact(client):
    cid, bag = await _setup(client)
    r = await _adj(client, cid, -5)
    undo = [{"container_id": loc, "amount": -a} for loc, a in _pl(r)]
    r = await _adj(client, cid, 5, undo)
    assert r.status_code == 200
    b = {x["container_id"]: x["coins"]["gold"] for x in (await client.get(f"/characters/{cid}")).json()["coin_breakdown"]}
    assert b == {None: 2, bag: 300}


async def test_undo_after_container_deleted(client):
    cid, bag = await _setup(client)
    r = await _adj(client, cid, -5)
    undo = [{"container_id": loc, "amount": -a} for loc, a in _pl(r)]
    await client.delete(f"/characters/{cid}/items/{bag}")
    r = await _adj(client, cid, 5, undo)
    assert r.status_code == 200
    assert _pl(r) == [(None, 5)]
    assert r.json()["coin_totals"]["gold"] == 302
    # A withdrawal from the vanished container is not silently redirected.
    assert (await _adj(client, cid, -1, [{"container_id": bag, "amount": -1}])).status_code == 409


async def test_move_coins(client):
    cid, bag = await _setup(client)
    url = f"/characters/{cid}/currency/move"
    r = await client.post(url, json={"coin": "gold", "amount": 50, "from_container_id": bag, "to_container_id": None})
    assert r.status_code == 200 and r.json()["purse"]["gold"] == 52
    r = await client.post(url, json={"coin": "gold", "amount": 52, "from_container_id": None, "to_container_id": bag})
    assert r.status_code == 200 and r.json()["purse"]["gold"] == 0
    assert r.json()["coin_totals"]["gold"] == 302
    r = await client.post(url, json={"coin": "gold", "amount": 1, "from_container_id": None, "to_container_id": bag})
    assert r.status_code == 409
    r = await client.post(url, json={"coin": "gold", "amount": 1, "from_container_id": bag, "to_container_id": bag})
    assert r.status_code == 422


async def test_convert_draws_from_containers(client):
    cid, bag = await _setup(client, purse_gold=0, bag_gold=10)
    r = await client.post(f"/characters/{cid}/currency/convert", json={"source": "gold", "target": "silver", "amount": 5})
    assert r.status_code == 200, r.text
    assert r.json()["silver"] == 50 and r.json()["gold"] == 0
    b = {x["container_id"]: x["coins"]["gold"] for x in (await client.get(f"/characters/{cid}")).json()["coin_breakdown"]}
    assert b == {None: 0, bag: 5}
    r = await client.post(f"/characters/{cid}/currency/convert", json={"source": "gold", "target": "silver", "amount": 6})
    assert r.status_code == 400


async def test_generic_does_not_merge_into_same_name_container(client):
    cid, bag = await _setup(client)
    r = await client.post(f"/characters/{cid}/items", json={"name": "Zaino"})
    zs = [i for i in r.json()["items"] if i["name"] == "Zaino"]
    assert len(zs) == 2 and next(z for z in zs if z["id"] == bag)["quantity"] == 1
