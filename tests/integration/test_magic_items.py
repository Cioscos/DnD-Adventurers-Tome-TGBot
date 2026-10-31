"""Oggetti magici: sintonia (max 3), bonus condizionati, campi tipizzati."""
from __future__ import annotations

import pytest


async def _char(client, **initial) -> int:
    r = await client.post("/characters", json={"name": "Magico", "initial_class": {
        "class_name": "wizard", "level": 5, "hit_die": 6,
        "spellcasting_ability": "intelligence", **initial}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    await client.patch(f"/characters/{cid}/ability_scores/intelligence", json={"value": 18})
    return cid


async def _item(client, cid, name="Mantello", item_type="accessory", slot=None, **meta):
    body = {"name": name, "item_type": item_type, "item_metadata": meta}
    r = await client.post(f"/characters/{cid}/items", json=body)
    assert r.status_code == 201, r.text
    items = (await client.get(f"/characters/{cid}/items")).json()
    iid = next(i["id"] for i in items if i["name"] == name)
    if slot:
        r = await client.patch(f"/characters/{cid}/items/{iid}", json={"is_equipped": True, "equipment_slot": slot})
        assert r.status_code == 200, r.text
    return iid


COP = {"requires_attunement": True, "is_magic": True, "bonuses": [
    {"target": "ac", "value": 1}, {"target": "saves", "value": 1}]}


async def test_cloak_of_protection_requires_attunement_for_bonus(client):
    cid = await _char(client)
    base = (await client.get(f"/characters/{cid}")).json()
    iid = await _item(client, cid, slot="cloak", **COP)
    r = (await client.get(f"/characters/{cid}")).json()
    assert r["ac_breakdown"]["items"] == 0
    assert r["saves_homebrew_modifiers"] == base["saves_homebrew_modifiers"]
    roll0 = (await client.post(f"/characters/{cid}/saving_throws/dexterity/roll", json={"die": 10})).json()

    r = await client.patch(f"/characters/{cid}/items/{iid}", json={"item_metadata": {**COP, "attuned": True}})
    assert r.status_code == 200, r.text
    assert r.json()["ac_breakdown"]["items"] == 1
    roll1 = (await client.post(f"/characters/{cid}/saving_throws/dexterity/roll", json={"die": 10})).json()
    assert roll1["bonus"] == roll0["bonus"] + 1


async def test_fourth_attunement_rejected_409(client):
    cid = await _char(client)
    meta = {"requires_attunement": True, "attuned": True}
    for n in range(3):
        await _item(client, cid, name=f"A{n}", **meta)
    r = await client.post(f"/characters/{cid}/items", json={
        "name": "A3", "item_type": "accessory", "item_metadata": meta})
    assert r.status_code == 409
    iid = await _item(client, cid, name="B", requires_attunement=True)
    r = await client.patch(f"/characters/{cid}/items/{iid}", json={"item_metadata": meta})
    assert r.status_code == 409


async def test_attuned_without_requirement_422(client):
    cid = await _char(client)
    r = await client.post(f"/characters/{cid}/items", json={
        "name": "X", "item_type": "accessory", "item_metadata": {"attuned": True}})
    assert r.status_code == 422


async def test_ring_unequipped_no_bonus(client):
    cid = await _char(client)
    await _item(client, cid, name="Anello", bonuses=[{"target": "ac", "value": 1}])
    assert (await client.get(f"/characters/{cid}")).json()["ac_breakdown"]["items"] == 0


async def test_weapon_attack_bonus_from_item(client):
    cid = await _char(client)
    wid = await _item(client, cid, name="Spada", item_type="weapon", damage_dice="1d8",
                      weapon_type="melee", bonuses=[{"target": "attack", "value": 2},
                                                    {"target": "damage", "value": 1}])
    r0 = (await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 10})).json()
    # unequipped weapon: not active
    await client.patch(f"/characters/{cid}/items/{wid}", json={"is_equipped": True, "equipment_slot": "main_hand"})
    r1 = (await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 10})).json()
    assert r1["to_hit_bonus"] == r0["to_hit_bonus"] + 2
    assert r1["damage_bonus"] == r0["damage_bonus"] + 1


async def test_spell_dc_bonus_from_item(client):
    cid = await _char(client)
    before = (await client.get(f"/characters/{cid}")).json()["spellcasting"]
    base = (await client.get(f"/characters/{cid}")).json()
    await _item(client, cid, slot="neck", bonuses=[{"target": "spell_dc", "value": 1},
                                                   {"target": "spell_attack", "value": 2}])
    after = (await client.get(f"/characters/{cid}")).json()
    c0 = base["spellcasting"]["casters"][0] if "casters" in base["spellcasting"] else None
    c1 = after["spellcasting"]["casters"][0] if c0 else None
    assert c0 is not None, before
    assert c1["save_dc"] == c0["save_dc"] + 1
    assert c1["attack_bonus"] == c0["attack_bonus"] + 2


async def test_item_without_magic_fields_unchanged(client):
    cid = await _char(client)
    base = (await client.get(f"/characters/{cid}")).json()
    await _item(client, cid, name="Corda", item_type="generic")
    await _item(client, cid, name="Anello", slot="ring1", foo="bar")
    after = (await client.get(f"/characters/{cid}")).json()
    assert after["ac"] == base["ac"]
    assert after["ac_breakdown"]["items"] == 0
    assert after["speed_items_modifier"] == 0
    assert after["initiative_bonus"] == base["initiative_bonus"]


async def test_metadata_unknown_keys_preserved(client):
    cid = await _char(client)
    iid = await _item(client, cid, rarity="rare", mystery={"a": 1})
    items = (await client.get(f"/characters/{cid}/items")).json()
    meta = next(i for i in items if i["id"] == iid)["item_metadata"]
    assert meta["mystery"] == {"a": 1} and meta["rarity"] == "rare"


@pytest.mark.parametrize("meta", [
    {"rarity": "mythic"}, {"bonuses": [{"target": "ac", "value": 11}]},
    {"bonuses": [{"target": "luck", "value": 1}]},
])
async def test_invalid_magic_fields_422(client, meta):
    cid = await _char(client)
    r = await client.post(f"/characters/{cid}/items", json={
        "name": "X", "item_type": "accessory", "item_metadata": meta})
    assert r.status_code == 422


async def test_speed_and_initiative_items(client):
    cid = await _char(client)
    await _item(client, cid, slot="neck", bonuses=[{"target": "speed", "value": 10},
                                                   {"target": "initiative", "value": 2}])
    b = (await client.get(f"/characters/{cid}")).json()
    dex = next(a["modifier"] for a in b["ability_scores"] if a["name"] == "dexterity")
    assert b["speed_items_modifier"] == 10
    assert b["initiative_bonus"] == dex + 2
