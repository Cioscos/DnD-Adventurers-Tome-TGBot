"""Upcast automatico: higher_levels_dice x (livello slot - livello incantesimo)."""
from __future__ import annotations


async def _spell(client, **kw):
    cid = (await client.post("/characters", json={"name": "Mago"})).json()["id"]
    body = {"name": "Palla di fuoco", "level": 3, "damage_dice": "8d6", "damage_type": "fire", **kw}
    r = await client.post(f"/characters/{cid}/spells", json=body)
    assert r.status_code == 201, r.text
    return cid, r.json()["id"]


async def _roll(client, cid, sid, level, rolls=None):
    body = {"casting_level": level}
    if rolls is not None:
        body["main_rolls"] = rolls
    return await client.post(f"/characters/{cid}/spells/{sid}/roll_damage", json=body)


async def test_upcast_adds_higher_levels_dice(client):
    cid, sid = await _spell(client, higher_levels_dice="1d6", school="evocation", srd_index="fireball")
    r = await _roll(client, cid, sid, 5, [1] * 10)
    assert r.status_code == 200, r.text
    assert r.json()["scaled_dice"] == "10d6" and len(r.json()["main_rolls"]) == 10
    assert (await _roll(client, cid, sid, 5, [1] * 8)).status_code == 400
    sp = next(s for s in (await client.get(f"/characters/{cid}")).json()["spells"] if s["id"] == sid)
    assert (sp["school"], sp["srd_index"], sp["higher_levels_dice"]) == ("evocation", "fireball", "1d6")


async def test_upcast_without_field_unchanged(client):
    cid, sid = await _spell(client)
    r = await _roll(client, cid, sid, 5, [1] * 8)
    assert r.status_code == 200 and r.json()["scaled_dice"] == "8d6"


async def test_upcast_at_base_level_unchanged(client):
    cid, sid = await _spell(client, higher_levels_dice="1d6")
    assert (await _roll(client, cid, sid, 3, [1] * 8)).status_code == 200


async def test_sleep_pool_not_upcast(client):
    cid, sid = await _spell(client, name="Sonno", level=1, damage_dice="5d8", damage_type=None,
                            higher_levels_dice="2d8", srd_index="sleep")
    r = await _roll(client, cid, sid, 3, [1] * 5)
    assert r.status_code == 200 and r.json()["scaled_dice"] == "5d8"


async def test_higher_levels_dice_validated(client):
    cid = (await client.post("/characters", json={"name": "Mago"})).json()["id"]
    r = await client.post(f"/characters/{cid}/spells", json={"name": "X", "higher_levels_dice": "lots"})
    assert r.status_code == 422
