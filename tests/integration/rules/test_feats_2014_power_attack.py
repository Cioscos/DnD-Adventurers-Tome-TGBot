"""-5/+10 di Maestro d'Armi Possenti e Tiratore Scelto 2014 (PR 3 talenti, Task 3)."""
from __future__ import annotations

from tests.integration.rules.test_2014_bard import _roll_keys
from tests.integration.rules.test_2014_barbarian import _weapon
from tests.integration.rules.test_feats_2014_selection import _char14
from tests.integration.rules.test_feats_take_complete import _take

GWM, SS = "feat.great_weapon_master", "feat.sharpshooter"


async def _fighter_with(client, key: str) -> int:
    ch = await _char14(client, "fighter", strength=16)
    assert (await _take(client, ch["id"], key)).status_code == 201
    return ch["id"]


async def _attack(client, cid, wid, die, options=()) -> dict:
    r = await client.post(f"/characters/{cid}/items/{wid}/attack",
                          json={"die": die, "confirm_extra_attack": True, "options": list(options)})
    assert r.status_code == 200, r.text
    return r.json()


async def test_great_weapon_master_minus_five_plus_ten(client):
    cid = await _fighter_with(client, "great_weapon_master")
    wid = await _weapon(client, cid, "Spadone", damage_dice="0d6+3", properties=["heavy", "two_handed"])
    plain = await _attack(client, cid, wid, 15)
    power = await _attack(client, cid, wid, 15, [GWM])
    assert power["to_hit_total"] == plain["to_hit_total"] - 5
    assert power["damage_total"] == plain["damage_total"] + 10


async def test_power_attack_not_doubled_on_crit(client):
    cid = await _fighter_with(client, "great_weapon_master")
    wid = await _weapon(client, cid, "Spadone", damage_dice="0d6+3", properties=["heavy", "two_handed"])
    plain = await _attack(client, cid, wid, 20)
    power = await _attack(client, cid, wid, 20, [GWM])
    assert power["damage_total"] == plain["damage_total"] + 10


async def test_power_attack_needs_the_right_weapon(client):
    cid = await _fighter_with(client, "great_weapon_master")
    light = await _weapon(client, cid, "Spada corta", damage_dice="1d6", properties=["light"])
    assert GWM not in await _roll_keys(client, cid, "attack", item_id=light)
    heavy = await _weapon(client, cid, "Spadone", damage_dice="2d6", properties=["heavy", "two_handed"])
    assert GWM in await _roll_keys(client, cid, "attack", item_id=heavy)
    sid = await _fighter_with(client, "sharpshooter")
    sword = await _weapon(client, sid, "Spada lunga", damage_dice="1d8")
    assert SS not in await _roll_keys(client, sid, "attack", item_id=sword)


async def test_sharpshooter_minus_five_plus_ten(client):
    cid = await _fighter_with(client, "sharpshooter")
    wid = await _weapon(client, cid, "Arco lungo", damage_dice="0d8+3", weapon_type="ranged", properties=["heavy", "two_handed"])
    plain = await _attack(client, cid, wid, 15)
    power = await _attack(client, cid, wid, 15, [SS])
    assert power["to_hit_total"] == plain["to_hit_total"] - 5
    assert power["damage_total"] == plain["damage_total"] + 10
