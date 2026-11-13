"""Copertura (mezza +2, tre quarti +5) dichiarata al TS su Destrezza, identica nelle due edizioni."""
from __future__ import annotations


async def _char(client) -> int:
    r = await client.post("/characters", json={"name": "Riparato"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _offered(client, cid, ability) -> set[str]:
    r = await client.get(f"/characters/{cid}/roll-options", params={"roll": "save", "ability": ability})
    assert r.status_code == 200, r.text
    return {o["key"] for o in r.json()}


async def _save(client, cid, ability, options):
    return await client.post(f"/characters/{cid}/saving_throws/{ability}/roll", json={"die": 10, "options": options})


async def test_cover_offered_only_on_dexterity_saves(client):
    cid = await _char(client)
    assert {"cover:half", "cover:three_quarters"} <= await _offered(client, cid, "dexterity")
    assert not {"cover:half", "cover:three_quarters"} & await _offered(client, cid, "wisdom")


async def test_cover_adds_to_the_total(client):
    cid = await _char(client)
    base = (await _save(client, cid, "dexterity", [])).json()["total"]
    assert (await _save(client, cid, "dexterity", ["cover:half"])).json()["total"] == base + 2
    assert (await _save(client, cid, "dexterity", ["cover:three_quarters"])).json()["total"] == base + 5


async def test_cover_options_are_exclusive(client):
    cid = await _char(client)
    r = await _save(client, cid, "dexterity", ["cover:half", "cover:three_quarters"])
    assert 400 <= r.status_code < 500, r.text


async def test_cover_refused_on_other_saves(client):
    cid = await _char(client)
    assert 400 <= (await _save(client, cid, "wisdom", ["cover:half"])).status_code < 500
