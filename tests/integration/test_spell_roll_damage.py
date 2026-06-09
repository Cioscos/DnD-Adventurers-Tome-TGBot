"""POST /characters/{id}/spells/{spell_id}/roll_damage — deterministic damage math.

Client-supplied ``main_rolls``/``extra_rolls`` make this fully deterministic (no
RNG): the server validates count + range and uses them verbatim. D&D 5e rules
encoded:
- A critical doubles the *dice count* (not the flat bonus): a base ``NdX`` then
  expects ``2N`` values when ``is_critical``.
- ``half_damage`` rounds up: ``(total + 1) // 2``.
- ``casting_level`` must be within ``[spell.level, 9]``.
- A flat bonus inside ``damage_dice`` (e.g. ``1d6+2``) is added once.

Contract: the response matches the FE ``RollDamageResult`` type
(rolls / total / half_damage / main_kind / main_rolls / extra_kind / extra_rolls)
consumed by api.spells.rollDamage in client.ts.
"""
from __future__ import annotations


async def _create_character(client) -> int:
    r = await client.post("/characters", json={"name": "Caster"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _add_spell(client, cid: int, *, name="Spell", level=3, damage_dice="2d6",
                     damage_type="fire") -> int:
    r = await client.post(
        f"/characters/{cid}/spells",
        json={"name": name, "level": level, "damage_dice": damage_dice,
              "damage_type": damage_type},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_main_rolls_used_verbatim_and_half_rounds_up(client):
    cid = await _create_character(client)
    sid = await _add_spell(client, cid, level=1, damage_dice="2d6", damage_type="fire")

    r = await client.post(
        f"/characters/{cid}/spells/{sid}/roll_damage",
        json={"casting_level": 1, "main_rolls": [3, 4]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rolls"] == [3, 4]
    assert body["main_rolls"] == [3, 4]
    assert body["total"] == 7
    assert body["half_damage"] == 4  # (7 + 1)//2, rounded up
    assert body["main_kind"] == "d6"
    assert body["damage_type"] == "fire"
    assert body["is_critical"] is False
    assert body["extra_rolls"] == []
    assert body["extra_kind"] is None
    assert body["casting_level"] == 1


async def test_critical_doubles_dice_count(client):
    cid = await _create_character(client)
    sid = await _add_spell(client, cid, level=1, damage_dice="2d6")

    # base 2d6 → crit expects 4 face values.
    r = await client.post(
        f"/characters/{cid}/spells/{sid}/roll_damage",
        json={"casting_level": 1, "is_critical": True, "main_rolls": [1, 2, 3, 4]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_critical"] is True
    assert body["main_rolls"] == [1, 2, 3, 4]
    assert body["total"] == 10
    assert body["half_damage"] == 5


async def test_extra_dice_added(client):
    cid = await _create_character(client)
    sid = await _add_spell(client, cid, level=1, damage_dice="1d8")

    r = await client.post(
        f"/characters/{cid}/spells/{sid}/roll_damage",
        json={"casting_level": 1, "main_rolls": [5], "extra_dice": "1d4", "extra_rolls": [3]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["main_rolls"] == [5]
    assert body["extra_rolls"] == [3]
    assert body["extra_kind"] == "d4"
    assert body["total"] == 8
    assert body["rolls"] == [5, 3]


async def test_flat_bonus_in_damage_dice_added_once(client):
    cid = await _create_character(client)
    sid = await _add_spell(client, cid, level=1, damage_dice="1d6+2")

    r = await client.post(
        f"/characters/{cid}/spells/{sid}/roll_damage",
        json={"casting_level": 1, "main_rolls": [4]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 6  # 4 + 2 flat bonus


async def test_main_rolls_wrong_length_is_400(client):
    cid = await _create_character(client)
    sid = await _add_spell(client, cid, level=1, damage_dice="2d6")
    r = await client.post(
        f"/characters/{cid}/spells/{sid}/roll_damage",
        json={"casting_level": 1, "main_rolls": [3]},  # expects 2
    )
    assert r.status_code == 400, r.text


async def test_main_rolls_out_of_range_is_400(client):
    cid = await _create_character(client)
    sid = await _add_spell(client, cid, level=1, damage_dice="2d6")
    r = await client.post(
        f"/characters/{cid}/spells/{sid}/roll_damage",
        json={"casting_level": 1, "main_rolls": [3, 7]},  # 7 > d6
    )
    assert r.status_code == 400, r.text


async def test_casting_level_below_spell_level_is_400(client):
    cid = await _create_character(client)
    sid = await _add_spell(client, cid, level=3, damage_dice="2d6")
    r = await client.post(
        f"/characters/{cid}/spells/{sid}/roll_damage",
        json={"casting_level": 2, "main_rolls": [3, 4]},
    )
    assert r.status_code == 400, r.text


async def test_casting_level_above_9_is_400(client):
    cid = await _create_character(client)
    sid = await _add_spell(client, cid, level=1, damage_dice="2d6")
    r = await client.post(
        f"/characters/{cid}/spells/{sid}/roll_damage",
        json={"casting_level": 10, "main_rolls": [3, 4]},
    )
    assert r.status_code == 400, r.text


async def test_spell_without_damage_dice_is_400(client):
    cid = await _create_character(client)
    sid = await _add_spell(client, cid, level=1, damage_dice=None)
    r = await client.post(
        f"/characters/{cid}/spells/{sid}/roll_damage",
        json={"casting_level": 1},
    )
    assert r.status_code == 400, r.text
