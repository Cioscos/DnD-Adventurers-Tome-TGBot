"""Tipo di azione sulle abilità, feature di classe e attacks_per_action nella scheda."""
from __future__ import annotations


async def _new_char(client, name: str = "Azione") -> int:
    r = await client.post("/characters", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _add_class(client, cid: int, class_name: str, level: int):
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": class_name, "level": level})
    assert r.status_code == 201, r.text


async def test_class_feature_gets_action_type(client):
    cid = await _new_char(client)
    await _add_class(client, cid, "barbarian", 1)
    abilities = (await client.get(f"/characters/{cid}/abilities")).json()
    rage = next(a for a in abilities if a["feature_key"] == "barbarian.rage")
    assert rage["action_type"] == "bonus_action"


async def test_ability_create_with_action_type(client):
    cid = await _new_char(client)
    r = await client.post(
        f"/characters/{cid}/abilities", json={"name": "Scatto", "action_type": "reaction"}
    )
    assert r.status_code == 201, r.text
    assert r.json()["action_type"] == "reaction"
    r = await client.patch(
        f"/characters/{cid}/abilities/{r.json()['id']}", json={"action_type": "free"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["action_type"] == "free"


async def test_ability_without_action_type_is_null(client):
    cid = await _new_char(client)
    r = await client.post(f"/characters/{cid}/abilities", json={"name": "Vecchia"})
    assert r.status_code == 201, r.text
    assert r.json()["action_type"] is None


async def test_invalid_action_type_422(client):
    cid = await _new_char(client)
    r = await client.post(
        f"/characters/{cid}/abilities", json={"name": "X", "action_type": "swift"}
    )
    assert r.status_code == 422
    ok = await client.post(f"/characters/{cid}/abilities", json={"name": "Y"})
    r = await client.patch(
        f"/characters/{cid}/abilities/{ok.json()['id']}", json={"action_type": "swift"}
    )
    assert r.status_code == 422


async def test_character_full_attacks_per_action(client):
    cid = await _new_char(client)
    assert (await client.get(f"/characters/{cid}")).json()["attacks_per_action"] == 1
    await _add_class(client, cid, "fighter", 11)
    assert (await client.get(f"/characters/{cid}")).json()["attacks_per_action"] == 3
