"""Armi: bonus magico, versatili, da lancio e avviso di competenza."""
from __future__ import annotations


async def _char(client, strength=14, dexterity=10, level=1) -> int:
    r = await client.post("/characters", json={"name": "Armigero"})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    r = await client.post(
        f"/characters/{cid}/classes",
        json={"class_name": "fighter", "level": level, "hit_die": 10},
    )
    assert r.status_code == 201, r.text
    for ability, value in (("strength", strength), ("dexterity", dexterity)):
        r = await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})
        assert r.status_code == 200, r.text
    return cid


async def _weapon(client, cid, name="Spada", **meta) -> int:
    meta = {"damage_dice": "1d8", "weapon_type": "melee", "properties": [], **meta}
    r = await client.post(
        f"/characters/{cid}/items",
        json={"name": name, "item_type": "weapon", "item_metadata": meta},
    )
    assert r.status_code == 201, r.text
    return next(i["id"] for i in r.json()["items"] if i["name"] == name)


async def _attack(client, cid, wid, **body):
    return await client.post(
        f"/characters/{cid}/items/{wid}/attack", json={"die": 10, **body}
    )


async def test_magic_bonus_adds_to_hit_and_damage(client):
    cid = await _char(client)  # FOR 14 => +2, PB +2
    wid = await _weapon(client, cid, magic_bonus=2)
    r = await _attack(client, cid, wid)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["to_hit_bonus"] == 6  # 2 + 2 + 2
    assert body["damage_bonus"] == 4  # 2 + 2
    assert body["magic_bonus"] == 2


async def test_versatile_two_hands_uses_versatile_dice(client):
    cid = await _char(client)
    wid = await _weapon(client, cid, properties=["prop_versatile"], versatile_dice="1d10")
    r = await _attack(client, cid, wid, grip="two")
    assert r.status_code == 200, r.text
    assert r.json()["damage_dice"] == "1d10"
    r = await _attack(client, cid, wid, grip="one")
    assert r.json()["damage_dice"] == "1d8"


async def test_versatile_two_hands_blocked_by_off_hand(client):
    cid = await _char(client)
    wid = await _weapon(client, cid, properties=["prop_versatile"], versatile_dice="1d10")
    r = await client.post(
        f"/characters/{cid}/items",
        json={"name": "Scudo", "item_type": "shield", "item_metadata": {"ac_bonus": 2}},
    )
    sid = next(i["id"] for i in r.json()["items"] if i["name"] == "Scudo")
    r = await client.patch(
        f"/characters/{cid}/items/{sid}",
        json={"is_equipped": True, "equipment_slot": "off_hand"},
    )
    assert r.status_code == 200, r.text
    r = await _attack(client, cid, wid, grip="two")
    assert r.status_code == 422, r.text
    assert "off_hand_occupied" in r.text


async def test_thrown_requires_property(client):
    cid = await _char(client)
    wid = await _weapon(client, cid)
    r = await _attack(client, cid, wid, attack_mode="thrown")
    assert r.status_code == 422, r.text


async def test_thrown_finesse_uses_best(client):
    cid = await _char(client, strength=8, dexterity=16)  # FOR -1, DES +3
    fin = await _weapon(client, cid, "Pugnale", properties=["prop_thrown", "prop_finesse"])
    plain = await _weapon(client, cid, "Lancia", properties=["prop_thrown"])
    r = await _attack(client, cid, fin, attack_mode="thrown")
    assert r.json()["to_hit_bonus"] == 5  # +3 DES + PB 2
    r = await _attack(client, cid, plain, attack_mode="thrown")
    assert r.json()["to_hit_bonus"] == 1  # -1 FOR + PB 2


async def test_proficiency_warning_when_missing(client):
    cid = await _char(client)
    r = await client.patch(
        f"/characters/{cid}", json={"general_proficiencies": ["Armi semplici"]}
    )
    assert r.status_code == 200, r.text
    martial = await _weapon(client, cid, "Spadone", weapon_category="martial")
    simple = await _weapon(client, cid, "Randello", weapon_category="simple")
    assert (await _attack(client, cid, martial)).json()["proficiency_warning"] is True
    assert (await _attack(client, cid, simple)).json()["proficiency_warning"] is False


async def test_no_warning_when_list_empty(client):
    cid = await _char(client)
    wid = await _weapon(client, cid, weapon_category="martial")
    assert (await _attack(client, cid, wid)).json()["proficiency_warning"] is False


async def test_thrown_ranged_non_finesse_uses_strength(client):
    cid = await _char(client, strength=16, dexterity=8)  # FOR +3, DES -1
    wid = await _weapon(
        client, cid, "Giavellotto", weapon_type="ranged", properties=["prop_thrown"]
    )
    # Ranged attacks normally use DEX; thrown must switch to STR.
    assert (await _attack(client, cid, wid)).json()["to_hit_bonus"] == 1  # -1 DES + PB 2
    assert (await _attack(client, cid, wid, attack_mode="thrown")).json()["to_hit_bonus"] == 5
