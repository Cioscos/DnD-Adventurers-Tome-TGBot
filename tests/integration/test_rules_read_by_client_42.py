"""Punto 42: le regole che il client mostrava calcolandole da solo ora arrivano dal server."""
from __future__ import annotations

from core.game.actions import HIDE_MIN_TOTAL


async def _monk(client, level=5) -> int:
    r = await client.post("/characters", json={"name": "Monaco", "initial_class": {"class_name": "monk", "level": level}})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _full(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}")).json()


async def _weapon(client, cid, name, equip=None, **meta) -> int:
    r = await client.post(f"/characters/{cid}/items", json={"name": name, "item_type": "weapon", "item_metadata": meta})
    assert r.status_code == 201, r.text
    iid = max(i["id"] for i in r.json()["items"])
    if equip:
        assert (await client.patch(f"/characters/{cid}/items/{iid}", json={"is_equipped": True, "equipment_slot": equip})).status_code == 200
    return iid


async def test_42_unarmed_dice_follow_martial_arts_and_the_armor(client):
    cid = await _monk(client, 5)
    assert (await _full(client, cid))["unarmed_damage_dice"] == "1d6"
    r = await client.post(f"/characters/{cid}/items", json={"name": "Cotta", "item_type": "armor", "item_metadata": {"ac_value": 14, "armor_type": "heavy"}})
    iid = max(i["id"] for i in r.json()["items"])
    assert (await client.patch(f"/characters/{cid}/items/{iid}", json={"is_equipped": True, "equipment_slot": "body"})).status_code == 200
    assert (await _full(client, cid))["unarmed_damage_dice"] == "1"


async def test_42_weapons_say_whether_martial_arts_applies(client):
    cid = await _monk(client)
    staff = await _weapon(client, cid, "Bastone", damage_dice="1d6", weapon_type="melee", weapon_category="simple", properties=[])
    maul = await _weapon(client, cid, "Maglio", damage_dice="2d6", weapon_type="melee", weapon_category="martial", properties=["heavy", "two_handed"])
    items = {i["id"]: i for i in (await _full(client, cid))["items"]}
    assert items[staff]["martial_arts"] is True and items[maul]["martial_arts"] is False


async def test_42_unarmored_previews_are_never_worse_than_ten_plus_dex(client):
    cid = await _monk(client)
    for ability, value in (("dexterity", 16), ("wisdom", 14), ("constitution", 6)):
        assert (await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})).status_code == 200
    assert (await _full(client, cid))["unarmored_previews"] == {"wisdom": 10 + 3 + 2, "constitution": 10 + 3}


async def test_42_turn_state_carries_the_hide_threshold(client):
    cid = await _monk(client)
    assert (await client.get(f"/characters/{cid}/turn-state")).json()["hide_min_total"] == HIDE_MIN_TOTAL == 15
