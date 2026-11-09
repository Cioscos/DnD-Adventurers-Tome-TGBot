"""Paladino 2014, giro di correzione 1 (I7): Arma Consacrata, testo al tiro per colpire, fine quando l'arma non è impugnata, colpo magico."""
from __future__ import annotations

from tests.integration.rules.test_2014_bard import _full, _use
from tests.integration.rules.test_2014_paladin import _paladin
from tests.integration.rules.test_2014_paladin_oaths import SW, _attack, _state, _sword


async def _bound(client, charisma=16):
    cid = await _paladin(client, 3, "devotion", charisma=charisma)
    sword = await _sword(client, cid, equip="main_hand")
    plain = (await _attack(client, cid, sword))["to_hit_bonus"]
    r = await _use(client, cid, SW, params={"weapon": str(sword)})
    assert r.status_code == 200, r.text
    return cid, sword, plain


async def test_the_state_says_the_bonus_is_on_the_attack_roll_not_on_the_damage(client):
    cid, sword, _ = await _bound(client)
    data = (await _state(client, cid, "sacred_weapon"))["data"]
    assert data["attack_bonus"] == 3 and "bonus" not in data  # la barra mostra «+3 al tiro per colpire», non «danni fissi»


async def test_unwielding_the_bound_weapon_ends_the_state_and_wielding_it_again_does_not_bring_it_back(client):
    cid, sword, plain = await _bound(client)
    await client.patch(f"/characters/{cid}/items/{sword}", json={"is_equipped": False})
    assert await _state(client, cid, "sacred_weapon") is None
    await client.patch(f"/characters/{cid}/items/{sword}", json={"is_equipped": True, "equipment_slot": "main_hand"})
    assert await _state(client, cid, "sacred_weapon") is None
    assert (await _attack(client, cid, sword))["to_hit_bonus"] == plain


async def test_swapping_the_bound_weapon_out_of_its_hand_ends_the_state(client):
    cid, sword, _ = await _bound(client)
    other = await _sword(client, cid, "Altra")
    await client.patch(f"/characters/{cid}/items/{other}", json={"is_equipped": True, "equipment_slot": "main_hand"})
    assert await _state(client, cid, "sacred_weapon") is None


async def test_deleting_or_stowing_the_bound_weapon_ends_the_state(client):
    cid, sword, _ = await _bound(client)
    assert (await client.delete(f"/characters/{cid}/items/{sword}")).status_code == 200
    assert await _state(client, cid, "sacred_weapon") is None
    cid, sword, _ = await _bound(client)
    bag = (await client.post(f"/characters/{cid}/items", json={
        "name": "Zaino", "item_type": "gear", "item_metadata": {"container": {"capacity_lb": 10, "counts_weight": True, "quick_access": False}}})).json()
    bag_id = max(i["id"] for i in bag["items"])
    r = await client.post(f"/characters/{cid}/items/move", json={"item_ids": [sword], "container_id": bag_id, "quantity": None})
    assert r.status_code == 200, r.text
    assert await _state(client, cid, "sacred_weapon") is None


async def test_another_weapon_leaving_the_hand_does_not_touch_the_state(client):
    cid, sword, _ = await _bound(client)
    dagger = await _sword(client, cid, "Pugnale", equip="off_hand")
    await client.patch(f"/characters/{cid}/items/{dagger}", json={"is_equipped": False})
    assert await _state(client, cid, "sacred_weapon") is not None


async def test_the_bound_weapon_strikes_as_a_magic_weapon_and_the_other_ones_do_not(client):
    cid, sword, _ = await _bound(client)
    dagger = await _item_off_hand(client, cid)
    assert (await _attack(client, cid, sword))["is_magic"] is True
    assert "is_magic" not in await _attack(client, cid, dagger)
    deferred = await _attack(client, cid, sword, defer_damage=True)
    assert deferred["is_magic"] is True


async def test_without_the_state_the_weapon_is_not_marked_magic(client):
    cid = await _paladin(client, 3, "devotion")
    sword = await _sword(client, cid, equip="main_hand")
    assert "is_magic" not in await _attack(client, cid, sword)


async def _item_off_hand(client, cid) -> int:
    return await _sword(client, cid, "Pugnale", equip="off_hand")
