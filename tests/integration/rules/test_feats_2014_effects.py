"""Talenti 2014 senza scelte: effetti dal motore (PR 3 talenti, Task 2)."""
from __future__ import annotations

from tests.integration.rules.test_2014_bard import _full, _roll_keys
from tests.integration.rules.test_2014_barbarian import _armor, _weapon
from tests.integration.rules.test_feats_2014_selection import _char14
from tests.integration.rules.test_feats_take_complete import _feat_rows, _take


async def _with(client, key: str, ability: str | None = None, class_name: str = "fighter", **scores) -> dict:
    ch = await _char14(client, class_name, **scores)
    r = await _take(client, ch["id"], key, ability)
    assert r.status_code == 201, r.text
    return {"before": ch, "after": r.json(), "id": ch["id"]}


async def _damage(client, cid, value, damage_type="slashing", options=()):
    r = await client.patch(f"/characters/{cid}/hp",
                           json={"op": "damage", "value": value, "damage_type": damage_type, "options": list(options)})
    assert r.status_code == 200, r.text
    return r.json()["current_hit_points"]


async def _reset(client, cid, hp):
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": hp})


async def test_charger_adds_five_on_melee_hit(client):
    c = await _with(client, "charger")
    assert "feat.charger" in await _roll_keys(client, c["id"], "attack", attack_mode="melee")
    assert "feat.charger" not in await _roll_keys(client, c["id"], "attack", attack_mode="thrown")


async def test_dual_wielder_ac_and_non_light_offhand(client):
    c = await _with(client, "dual_wielder")
    cid = c["id"]
    await _weapon(client, cid, "Spada lunga", damage_dice="1d8")
    one = (await _full(client, cid))["ac"]
    off = await _weapon(client, cid, "Ascia da battaglia", equip="off_hand", damage_dice="1d8")
    assert (await _full(client, cid))["ac"] == one + 1
    r = await client.post(f"/characters/{cid}/items/{off}/attack", json={"die": 10, "attack_mode": "offhand"})
    assert r.status_code == 200, r.text


async def test_dungeon_delver_options_and_trap_damage(client):
    c = await _with(client, "dungeon_delver")
    cid = c["id"]
    assert "feat.dungeon_delver" in await _roll_keys(client, cid, "skill", skill="perception")
    assert "feat.dungeon_delver_traps" in await _roll_keys(client, cid, "save", ability="dexterity")
    hp = c["after"]["current_hit_points"]
    assert await _damage(client, cid, 10, "piercing", ["feat.dungeon_delver_trap_damage"]) == hp - 5


async def test_medium_armor_master_ac_and_stealth(client):
    plain = await _char14(client, "fighter", dexterity=16)
    feat = await _with(client, "medium_armor_master", dexterity=16)
    for cid in (plain["id"], feat["id"]):
        r = await client.post(f"/characters/{cid}/items", json={"name": "Corazza", "item_type": "armor", "item_metadata": {
            "ac_value": 14, "armor_type": "medium", "stealth_disadvantage": True}})
        iid = next(i["id"] for i in r.json()["items"] if i["name"] == "Corazza")
        await client.patch(f"/characters/{cid}/items/{iid}", json={"is_equipped": True, "equipment_slot": "body"})
    assert (await _full(client, feat["id"]))["ac"] == (await _full(client, plain["id"]))["ac"] + 1
    rolls = []
    for cid in (plain["id"], feat["id"]):
        r = await client.post(f"/characters/{cid}/skills/stealth/roll", json={})
        assert r.status_code == 200, r.text
        rolls.append(r.json().get("mode_applied"))
    assert rolls[0] == "disadvantage" and rolls[1] != "disadvantage"


async def test_heavy_armor_master_2014_offers_three(client):
    c = await _with(client, "heavy_armor_master", "strength")
    cid = c["id"]
    await _armor(client, cid, "heavy")
    hp = c["after"]["current_hit_points"]
    assert "feat.heavy_armor_master" in await _roll_keys(client, cid, "damage_taken", damage_type="slashing")
    assert await _damage(client, cid, 10, "slashing", ["feat.heavy_armor_master"]) == hp - 7
    await _reset(client, cid, hp)
    assert await _damage(client, cid, 10, "slashing") == hp - 10


async def test_shield_master_save_bonus_and_no_damage(client):
    c = await _with(client, "shield_master")
    cid = c["id"]
    assert "feat.shield_master" not in await _roll_keys(client, cid, "save", ability="dexterity")
    r = await client.post(f"/characters/{cid}/items", json={"name": "Scudo", "item_type": "shield", "item_metadata": {"ac_value": 2}})
    iid = next(i["id"] for i in r.json()["items"] if i["name"] == "Scudo")
    await client.patch(f"/characters/{cid}/items/{iid}", json={"is_equipped": True, "equipment_slot": "off_hand"})
    assert "feat.shield_master" in await _roll_keys(client, cid, "save", ability="dexterity")
    hp = c["after"]["current_hit_points"]
    assert await _damage(client, cid, 10, "fire", ["feat.shield_master_evasion"]) == hp


async def test_durable_hit_die_minimum(client):
    c = await _with(client, "durable", "constitution", constitution=13)  # 13 -> 14: modificatore +2
    cid = c["id"]
    await _reset(client, cid, 1)
    r = await client.post(f"/characters/{cid}/hit_dice/spend", json={"count": 1, "rolls": [1], "class_id": c["after"]["classes"][0]["id"]})
    assert r.status_code == 200, r.text
    assert (await _full(client, cid))["current_hit_points"] == 1 + 4


async def test_savage_attacker_is_melee_only(client):
    from core.rules.catalog import active_features
    from core.rules.catalog.feats import FEAT_FEATURES
    assert FEAT_FEATURES["feat.savage_attacker"].weapon_damage_twice == "melee"
    assert FEAT_FEATURES["feat.2024_savage_attacker"].weapon_damage_twice is True
    assert active_features is not None


async def test_armor_feats_grant_training(client):
    c = await _with(client, "lightly_armored", "strength", "wizard")
    assert any("legger" in a.lower() for a in c["after"]["general_proficiencies"]["armor"])
    f = await _with(client, "heavily_armored", "strength")
    assert any("pesant" in a.lower() for a in f["after"]["general_proficiencies"]["armor"])


async def test_tavern_brawler_unarmed_d4_and_improvised(client):
    c = await _with(client, "tavern_brawler", "strength")
    assert any("improvvisat" in w.lower() for w in c["after"]["general_proficiencies"]["weapons"])
    r = await client.post(f"/characters/{c['id']}/attack/unarmed", json={"die": 10, "confirm_extra_attack": True})
    assert r.status_code == 200, r.text
    assert r.json()["damage_dice"].startswith("1d4")


async def test_inspiring_leader_rest_temp_hp(client):
    c = await _with(client, "inspiring_leader", charisma=14)
    r = await client.post(f"/characters/{c['id']}/rest", json={"rest_type": "short"})
    assert r.status_code == 200, r.text
    assert (await _full(client, c["id"]))["temp_hp"] == 4 + 2  # livello 4 + Carisma 14


async def test_defensive_duelist_reaction(client):
    c = await _with(client, "defensive_duelist")
    cid = c["id"]
    await _weapon(client, cid, "Stocco", properties=["finesse"])
    ac = (await _full(client, cid))["ac"]
    r = await client.post(f"/characters/{cid}/features/feat.defensive_duelist/use", json={})
    assert r.status_code == 200, r.text
    assert (await _full(client, cid))["ac"] == ac + 2


async def test_grappler_actor_mage_slayer_options(client):
    g = await _with(client, "grappler", strength=13)
    assert "feat.grappler" in await _roll_keys(client, g["id"], "attack")
    a = await _with(client, "actor", "charisma")
    assert "feat.actor" in await _roll_keys(client, a["id"], "skill", skill="deception")
    assert "feat.actor" not in await _roll_keys(client, a["id"], "skill", skill="athletics")
    m = await _with(client, "mage_slayer")
    assert "feat.mage_slayer" in await _roll_keys(client, m["id"], "save", ability="wisdom")


async def test_athlete_climb_speed(client):
    c = await _with(client, "athlete", "strength")
    assert c["after"]["computed"]["climb_speed"] == c["after"]["computed"]["speed"]


async def test_text_only_feats_have_a_row(client):
    c = await _with(client, "sentinel")
    assert _feat_rows(c["after"], "sentinel")[0]["feat_status"] == "active"
