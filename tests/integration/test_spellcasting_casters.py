"""CD incantesimi e bonus d'attacco per classe in ``spellcasting.casters``."""
from __future__ import annotations


async def _create(client, class_name: str, level: int, ability: str | None) -> tuple[int, int]:
    body = {"class_name": class_name, "level": level, "hit_die": 8}
    if ability:
        body["spellcasting_ability"] = ability
    r = await client.post("/characters", json={"name": "Caster", "initial_class": body})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    full = (await client.get(f"/characters/{cid}")).json()
    return cid, full["classes"][0]["id"]


async def test_casters_include_dc_and_attack(client):
    cid, wid = await _create(client, "wizard", 5, "intelligence")
    r = await client.patch(f"/characters/{cid}/ability_scores/intelligence", json={"value": 16})
    assert r.status_code == 200, r.text
    meta = {"ability_modifiers": [{"ability": "intelligence", "kind": "relative", "value": 2}]}
    r = await client.post(
        f"/characters/{cid}/items",
        json={"name": "Fascia", "item_type": "accessory", "item_metadata": meta},
    )
    assert r.status_code == 201, r.text
    iid = (await client.get(f"/characters/{cid}/items")).json()[0]["id"]
    r = await client.patch(f"/characters/{cid}/items/{iid}", json={"is_equipped": True})
    assert r.status_code == 200, r.text

    sc = (await client.get(f"/characters/{cid}")).json()["spellcasting"]
    assert sc["casters"] == [{"class_id": wid, "class_name": "wizard", "ability": "intelligence",
                              "save_dc": 15, "attack_bonus": 7}]   # INT 18 -> +4


async def test_non_caster_has_no_casters(client):
    cid, _ = await _create(client, "fighter", 3, None)
    sc = (await client.get(f"/characters/{cid}")).json()["spellcasting"]
    assert sc["casters"] == []


async def test_multiclass_lists_each_caster(client):
    cid, first = await _create(client, "cleric", 3, "wisdom")
    r = await client.post(
        f"/characters/{cid}/classes",
        json={"class_name": "wizard", "level": 2, "hit_die": 6, "spellcasting_ability": "intelligence"},
    )
    assert r.status_code == 201, r.text
    sc = (await client.get(f"/characters/{cid}")).json()["spellcasting"]
    assert [c["class_name"] for c in sc["casters"]] == ["cleric", "wizard"]
    assert [c["ability"] for c in sc["casters"]] == ["wisdom", "intelligence"]
    assert sc["casters"][0]["class_id"] == first
