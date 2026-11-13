"""Talenti generali 2024 senza scelte, dal motore (PR 2 talenti, Task 2)."""
from __future__ import annotations

from tests.integration.rules.test_2014_bard import _full, _roll_keys, _spells
from tests.integration.rules.test_2014_barbarian import _armor, _weapon
from tests.integration.rules.test_feats_2024_selection import _char
from tests.integration.rules.test_feats_take_complete import _feat_rows, _take

STATS = {"dexterity": 14, "constitution": 14, "charisma": 13, "intelligence": 13, "wisdom": 13}


async def _with(client, key: str, ability: str | None = None, class_name: str = "fighter", level: int = 4) -> dict:
    ch = await _char(client, class_name, level, **STATS)
    r = await _take(client, ch["id"], f"2024_{key}", ability)
    assert r.status_code == 201, r.text
    return {"before": ch, "after": r.json(), "id": ch["id"]}


async def test_speedy_speed(client):
    c = await _with(client, "speedy", "dexterity")
    assert c["after"]["computed"]["speed"] == c["before"]["computed"]["speed"] + 10


async def test_athlete_climb_speed(client):
    c = await _with(client, "athlete", "strength")
    assert c["after"]["computed"]["climb_speed"] == c["after"]["computed"]["speed"]


async def test_skulker_blindsight(client):
    c = await _with(client, "skulker", "dexterity")
    assert any(s.get("range_ft") == 10 for s in c["after"]["computed"]["senses"]), c["after"]["computed"]["senses"]


async def test_durable_death_save_advantage(client):
    c = await _with(client, "durable", "constitution")
    await client.patch(f"/characters/{c['id']}/hp", json={"op": "set_current", "value": 0})
    r = await client.post(f"/characters/{c['id']}/death_saves/roll", json={"dice": [3, 15]})
    assert r.status_code == 200, r.text
    assert r.json()["mode_applied"] == "advantage"


async def test_war_caster_concentration(client):
    c = await _with(client, "war_caster", "intelligence", "wizard")
    r = await client.post(f"/characters/{c['id']}/concentration/save", json={"damage": 10, "dice": [3, 18]})
    assert r.status_code == 200, r.text
    assert r.json()["mode_applied"] == "advantage"


async def _damage(client, cid, value, damage_type, options=()):
    r = await client.patch(f"/characters/{cid}/hp",
                           json={"op": "damage", "value": value, "damage_type": damage_type, "options": list(options)})
    assert r.status_code == 200, r.text
    return r.json()


async def test_heavy_armor_master_reduces_physical_damage_in_heavy_armor(client):
    c = await _with(client, "heavy_armor_master", "strength")
    cid = c["id"]
    hp = c["after"]["current_hit_points"]
    assert (await _damage(client, cid, 10, "slashing"))["current_hit_points"] == hp - 10  # senza armatura pesante
    await _armor(client, cid, "heavy")
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": hp})
    assert (await _damage(client, cid, 10, "slashing", ["feat.2024_heavy_armor_master"]))["current_hit_points"] == hp - 8  # competenza 2
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": hp})
    assert (await _damage(client, cid, 10, "fire"))["current_hit_points"] == hp - 10


async def test_great_weapon_master_damage_with_heavy_weapon(client):
    c = await _with(client, "great_weapon_master", "strength")
    heavy = await _weapon(client, c["id"], "Spadone", properties=["heavy", "two_handed"])
    r = await client.post(f"/characters/{c['id']}/items/{heavy}/attack", json={"die": 15, "confirm_extra_attack": True})
    assert r.status_code == 200, r.text
    plain = await _char(client, "fighter", 4, **STATS)
    other = await _weapon(client, plain["id"], "Spadone", properties=["heavy", "two_handed"])
    base = await client.post(f"/characters/{plain['id']}/items/{other}/attack", json={"die": 15, "confirm_extra_attack": True})
    assert r.json()["damage_bonus"] == base.json()["damage_bonus"] + 2


async def test_actor_offers_advantage_on_deception(client):
    c = await _with(client, "actor", "charisma")
    assert "feat.2024_actor" in await _roll_keys(client, c["id"], "skill", skill="deception")
    assert "feat.2024_actor" not in await _roll_keys(client, c["id"], "skill", skill="athletics")


async def test_mage_slayer_guarded_mind(client):
    c = await _with(client, "mage_slayer", "strength")
    assert "feat.2024_mage_slayer" in await _roll_keys(client, c["id"], "save", ability="wisdom")
    assert "feat.2024_mage_slayer" not in await _roll_keys(client, c["id"], "save", ability="dexterity")
    row = _feat_rows(c["after"], "2024_mage_slayer")[0]
    assert (row["max_uses"], row["restoration_type"]) == (1, "short_rest")


async def test_telepathic_detect_thoughts_free_once(client):
    c = await _with(client, "telepathic", "intelligence")
    spell = (await _spells(client, c["id"]))["Individuazione dei pensieri"]
    assert spell["always_prepared"] and spell["pact_cast"]["uses_left"] == 1


async def test_telekinetic_mage_hand(client):
    c = await _with(client, "telekinetic", "intelligence")
    assert (await _spells(client, c["id"]))["Mano magica"]["always_prepared"]


async def test_chef_treats_and_cook_utensils(client):
    c = await _with(client, "chef", "constitution")
    row = _feat_rows(c["after"], "2024_chef")[0]
    assert (row["max_uses"], row["restoration_type"]) == (2, "long_rest")
    assert any("cuoco" in t.lower() or "cook" in t.lower() for t in c["after"]["general_proficiencies"]["tools"])


async def test_lightly_armored_grant_follows_the_feat(client):
    c = await _with(client, "lightly_armored", "strength", "wizard")
    armor = c["after"]["general_proficiencies"]["armor"]
    assert any("legger" in a.lower() for a in armor)
    row = _feat_rows(c["after"], "2024_lightly_armored")[0]
    r = await client.delete(f"/characters/{c['id']}/feats/{row['id']}")
    assert r.status_code == 200, r.text
    assert not any("legger" in a.lower() for a in r.json()["general_proficiencies"]["armor"])


async def test_medium_armor_master_ac(client):
    c = await _with(client, "medium_armor_master", "dexterity")
    plain = await _char(client, "fighter", 4, **{**STATS, "dexterity": 16})
    feat = await _char(client, "fighter", 4, **{**STATS, "dexterity": 16})
    assert (await _take(client, feat["id"], "2024_medium_armor_master", "strength")).status_code == 201
    for cid in (plain["id"], feat["id"]):
        await _armor(client, cid, "medium", 14)
    assert (await _full(client, feat["id"]))["ac"] == (await _full(client, plain["id"]))["ac"] + 1
    assert c["after"]["ac"] == c["before"]["ac"]


async def test_inspiring_leader_rest_temp_hp(client):
    c = await _with(client, "inspiring_leader", "charisma")
    r = await client.post(f"/characters/{c['id']}/rest", json={"rest_type": "short"})
    assert r.status_code == 200, r.text
    assert (await _full(client, c["id"]))["temp_hp"] == 4 + 2  # livello 4 + Carisma 14


async def test_defensive_duelist_reaction(client):
    c = await _with(client, "defensive_duelist", "dexterity")
    cid = c["id"]
    await _weapon(client, cid, "Stocco", properties=["finesse"])
    full = await _full(client, cid)
    r = await client.post(f"/characters/{cid}/features/feat.2024_defensive_duelist/use", json={})
    assert r.status_code == 200, r.text
    assert (await _full(client, cid))["ac"] == full["ac"] + 2


async def test_text_only_feats_have_a_row(client):
    c = await _with(client, "sentinel", "strength")
    row = _feat_rows(c["after"], "2024_sentinel")[0]
    assert row["feat_status"] == "active" and row["is_passive"]


def test_catalog_version_bumped():
    from core.rules.catalog import CATALOG_VERSION
    assert CATALOG_VERSION >= 71  # i personaggi esistenti ripassano dal sync con i talenti 2024 (70) e 2014 (71)
