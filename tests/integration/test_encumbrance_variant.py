"""Ingombro dettagliato: peso delle monete e variante a soglie FOR x5 / FOR x10."""
from __future__ import annotations


async def _setup(client, strength: int = 10) -> int:
    r = await client.post("/characters", json={"name": "Portatore"})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    r = await client.patch(f"/characters/{cid}/ability_scores/strength", json={"value": strength})
    assert r.status_code == 200, r.text
    return cid


async def _add_weight(client, cid: int, weight: float) -> None:
    r = await client.post(
        f"/characters/{cid}/items",
        json={"name": "Zavorra", "item_type": "generic", "weight": weight},
    )
    assert r.status_code == 201, r.text


async def _settings(client, cid: int, **kw) -> None:
    r = await client.patch(f"/characters/{cid}", json={"settings": kw})
    assert r.status_code == 200, r.text


async def _get(client, cid: int) -> dict:
    return (await client.get(f"/characters/{cid}")).json()


async def test_coin_weight_counts_when_enabled(client):
    cid = await _setup(client)
    await _add_weight(client, cid, 10)
    r = await client.patch(f"/characters/{cid}/currency", json={"gold": 60, "copper": 40})
    assert r.status_code == 200, r.text
    assert (await _get(client, cid))["encumbrance_total"] == 10
    await _settings(client, cid, coin_weight=True)
    body = await _get(client, cid)
    assert body["encumbrance_total"] == 12  # 10 + 100 monete / 50
    assert body["encumbrance"] == 10  # resta solo oggetti


async def test_variant_thresholds_and_speed_penalty(client):
    cid = await _setup(client, strength=10)  # soglie 50 / 100
    await _settings(client, cid, encumbrance_variant=True)
    body = await _get(client, cid)
    assert (body["encumbrance_level"], body["speed_encumbrance_penalty_ft"]) == ("none", 0)
    await _add_weight(client, cid, 51)
    body = await _get(client, cid)
    assert (body["encumbrance_level"], body["speed_encumbrance_penalty_ft"]) == ("encumbered", 10)
    await _add_weight(client, cid, 50)
    body = await _get(client, cid)
    assert (body["encumbrance_level"], body["speed_encumbrance_penalty_ft"]) == ("heavily", 20)


async def test_defaults_unchanged(client):
    cid = await _setup(client, strength=10)
    await _add_weight(client, cid, 120)
    await client.patch(f"/characters/{cid}/currency", json={"gold": 500})
    body = await _get(client, cid)
    assert body["encumbrance_total"] == body["encumbrance"] == 120
    assert body["encumbrance_level"] == "none"
    assert body["speed_encumbrance_penalty_ft"] == 0
