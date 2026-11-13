"""Recupero delle munizioni: metà delle spese, per difetto, col pulsante o a fine scontro."""
from __future__ import annotations

from tests.integration.test_attack_ammunition import _arrows, _bow, _char, _qty


async def _spent(client, cid, item_id) -> int:
    items = (await client.get(f"/characters/{cid}/items")).json()
    return next(i["ammo_spent"] for i in items if i["id"] == item_id)


async def _shoot(client, cid, wid, times: int) -> None:
    for _ in range(times):
        r = await client.post(f"/characters/{cid}/items/{wid}/attack",
                              json={"die": 10, "confirm_extra_attack": True})  # oltre il limite di attacchi del turno
        assert r.status_code == 200, r.text


async def test_attack_counts_spent_ammo(client):
    cid = await _char(client)
    wid = await _bow(client, cid)
    aid = await _arrows(client, cid)
    await _shoot(client, cid, wid, 3)
    assert await _qty(client, cid, aid) == 17
    assert await _spent(client, cid, aid) == 3


async def test_inspiration_reroll_does_not_count(client):
    cid = await _char(client)
    await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})
    wid = await _bow(client, cid)
    aid = await _arrows(client, cid)
    await client.patch(f"/characters/{cid}/inspiration", json={"heroic_inspiration": True})
    await _shoot(client, cid, wid, 1)
    r = await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 5, "with_inspiration": True})
    assert r.status_code == 200, r.text
    assert await _spent(client, cid, aid) == 1


async def test_missing_ammo_does_not_count(client):
    cid = await _char(client)
    wid = await _bow(client, cid)
    aid = await _arrows(client, cid, quantity=0)
    r = await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 10})
    assert r.json()["ammo_missing"] is True
    assert await _spent(client, cid, aid) == 0


async def test_recover_returns_half_rounded_down(client):
    cid = await _char(client)
    wid = await _bow(client, cid)
    aid = await _arrows(client, cid)
    await _shoot(client, cid, wid, 5)
    r = await client.post(f"/characters/{cid}/items/{aid}/recover-ammo")
    assert r.status_code == 200, r.text
    item = next(i for i in r.json()["items"] if i["id"] == aid)
    assert (item["quantity"], item["ammo_spent"]) == (17, 0)
    history = (await client.get(f"/characters/{cid}/history")).json()
    assert any(h["description"] == "Munizioni recuperate: 2 Frecce" for h in history)


async def test_recover_twice_returns_nothing(client):
    cid = await _char(client)
    wid = await _bow(client, cid)
    aid = await _arrows(client, cid)
    await _shoot(client, cid, wid, 4)
    await client.post(f"/characters/{cid}/items/{aid}/recover-ammo")
    r = await client.post(f"/characters/{cid}/items/{aid}/recover-ammo")
    assert r.status_code == 200, r.text
    assert await _qty(client, cid, aid) == 18


async def test_recover_rejects_non_ammunition(client):
    cid = await _char(client)
    wid = await _bow(client, cid)
    r = await client.post(f"/characters/{cid}/items/{wid}/recover-ammo")
    assert r.status_code == 422 and "not_ammunition" in r.text
