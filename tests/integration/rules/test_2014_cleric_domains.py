"""Chierico 2014 (Task 21), privilegi dei domini che passano da una conferma al tiro o da «Usa»."""
from __future__ import annotations

import pytest

from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _roll_keys, _use
from tests.integration.rules.test_2014_barbarian import _attack, _turn, _weapon
from tests.integration.rules.test_2014_cleric import POOL, _cleric


def _extra(attack: dict) -> dict:
    return attack["option_result"] or {}


async def _deferred(client, cid, sword, die, *after) -> dict:
    """Attacco col danno rimandato, poi le opzioni «dopo il colpo» (Colpo Divino)."""
    first = (await client.post(f"/characters/{cid}/items/{sword}/attack", json={"die": die, "defer_damage": True})).json()
    r = await client.post(f"/characters/{cid}/attack/{first['attack_id']}/damage", json={"options": list(after)})
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Colpo Divino
# ---------------------------------------------------------------------------

async def test_divine_strike_adds_the_dice_once_per_turn(client):
    cid = await _cleric(client, 8, "war", strength=14)
    sword = await _weapon(client, cid, "Mazza", damage_dice="1d6")
    first = await _deferred(client, cid, sword, 15, "cleric.divine_strike_war")
    assert len(_extra(first)["extra_rolls"]) == 1 and 1 <= _extra(first)["extra_total"] <= 8
    assert "cleric.divine_strike_war" not in await _roll_keys(client, cid, "attack", item_id=sword)  # una volta per turno
    await client.post(f"/characters/{cid}/turn/new")
    assert "cleric.divine_strike_war" in await _roll_keys(client, cid, "attack", item_id=sword)


async def test_divine_strike_is_2d8_from_level_14(client):
    cid = await _cleric(client, 14, "tempest", strength=14)
    sword = await _weapon(client, cid, "Mazza", damage_dice="1d6")
    hit = await _deferred(client, cid, sword, 15, "cleric.divine_strike_tempest")
    assert len(_extra(hit)["extra_rolls"]) == 2


async def test_divine_strike_nature_takes_a_single_type_per_turn(client):
    cid = await _cleric(client, 8, "nature", strength=14)
    sword = await _weapon(client, cid, "Mazza", damage_dice="1d6")
    first = (await client.post(f"/characters/{cid}/items/{sword}/attack", json={"die": 15, "defer_damage": True})).json()
    r = await client.post(f"/characters/{cid}/attack/{first['attack_id']}/damage", json={
        "options": ["cleric.divine_strike_nature_cold", "cleric.divine_strike_nature_fire"]})
    assert r.status_code == 409  # due tipi nello stesso colpo
    await client.post(f"/characters/{cid}/turn/new")
    hit = await _deferred(client, cid, sword, 15, "cleric.divine_strike_nature_fire")
    assert len(_extra(hit)["extra_rolls"]) == 1


async def test_divine_strike_is_not_offered_for_a_spell_attack(client):
    cid = await _cleric(client, 8, "life")
    spell = (await client.post(f"/characters/{cid}/spells", json={
        "name": "Raggio", "level": 0, "attack_save": "ATK", "damage_dice": "1d8"})).json()["id"]
    assert not any(k.startswith("cleric.divine_strike") for k in await _roll_keys(client, cid, "attack", spell_id=spell))


# ---------------------------------------------------------------------------
# Dominio della Guerra
# ---------------------------------------------------------------------------

async def test_war_priest_needs_an_attack_first_and_spends_a_use_and_the_bonus_action(client):
    cid = await _cleric(client, 3, "war", strength=14, wisdom=16)
    sword = await _weapon(client, cid, "Mazza", damage_dice="1d6")
    assert (await _ability(client, cid, "cleric.war_priest"))["max_uses"] == 3
    assert "cleric.war_priest" not in await _roll_keys(client, cid, "attack", item_id=sword)
    await _attack(client, cid, sword, die=12)
    assert "cleric.war_priest" in await _roll_keys(client, cid, "attack", item_id=sword)
    await _attack(client, cid, sword, die=12, options=["cleric.war_priest"])
    assert (await _turn(client, cid))["bonus_used"] is True
    assert (await _ability(client, cid, "cleric.war_priest"))["uses"] == 2
    assert "cleric.war_priest" not in await _roll_keys(client, cid, "attack", item_id=sword)


@pytest.mark.parametrize("wisdom,uses", [(8, 1), (10, 1), (14, 2), (20, 5)])
async def test_war_priest_uses_follow_wisdom_with_a_minimum_of_one(client, wisdom, uses):
    cid = await _cleric(client, 1, "war", wisdom=wisdom)
    assert (await _ability(client, cid, "cleric.war_priest"))["max_uses"] == uses


async def test_guided_strike_adds_ten_after_the_roll_and_spends_the_pool(client):
    cid = await _cleric(client, 2, "war", strength=14)
    sword = await _weapon(client, cid, "Mazza", damage_dice="1d6")
    first = (await client.post(f"/characters/{cid}/items/{sword}/attack", json={"die": 5, "defer_damage": True})).json()
    options = {o["key"]: o for o in (await client.get(
        f"/characters/{cid}/roll-options", params={"roll": "attack", "item_id": sword})).json()}
    assert options["cleric.guided_strike"]["phase"] == "after_roll"
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": ["cleric.guided_strike"]})
    assert r.status_code == 200, r.text
    assert r.json()["total"] == first["to_hit_total"] + 10 and r.json()["bonus"] == first["to_hit_bonus"] + 10
    assert (await _ability(client, cid, POOL))["uses"] == 0
    assert "cleric.guided_strike" not in await _roll_keys(client, cid, "attack", item_id=sword)  # niente usi


async def test_avatar_of_battle_is_offered_for_nonmagical_physical_damage_only(client):
    cid = await _cleric(client, 17, "war")
    assert "cleric.avatar_of_battle" in await _roll_keys(client, cid, "damage_taken", damage_type="slashing")
    assert "cleric.avatar_of_battle" not in await _roll_keys(client, cid, "damage_taken", damage_type="fire")
    low = await _cleric(client, 16, "war")
    assert "cleric.avatar_of_battle" not in await _roll_keys(client, low, "damage_taken", damage_type="slashing")


async def test_avatar_of_battle_halves_the_damage_taken(client):
    cid = await _cleric(client, 17, "war")
    hp = (await _full(client, cid))["current_hit_points"]
    r = await client.patch(f"/characters/{cid}/hp", json={
        "op": "damage", "value": 10, "damage_type": "slashing", "options": ["cleric.avatar_of_battle"]})
    assert r.status_code == 200, r.text
    assert (await _full(client, cid))["current_hit_points"] == hp - 5


# ---------------------------------------------------------------------------
# Dominio della Natura
# ---------------------------------------------------------------------------

async def test_dampen_elements_is_a_reaction_for_elemental_damage(client):
    cid = await _cleric(client, 6, "nature")
    assert "cleric.dampen_elements" in await _roll_keys(client, cid, "damage_taken", damage_type="lightning")
    assert "cleric.dampen_elements" not in await _roll_keys(client, cid, "damage_taken", damage_type="slashing")
    hp = (await _full(client, cid))["current_hit_points"]
    r = await client.patch(f"/characters/{cid}/hp", json={
        "op": "damage", "value": 9, "damage_type": "fire", "options": ["cleric.dampen_elements"]})
    assert r.status_code == 200, r.text
    assert (await _full(client, cid))["current_hit_points"] == hp - 4
    assert (await _turn(client, cid))["reaction_used"] is True
    assert "cleric.dampen_elements" not in await _roll_keys(client, cid, "damage_taken", damage_type="fire")


async def test_charm_animals_and_plants_unlocks_master_of_nature(client):
    cid = await _cleric(client, 17, "nature", wisdom=16)
    key = "cleric.master_of_nature"
    assert (await _use(client, cid, key)).status_code == 409  # senza l'effetto attivo
    r = await _use(client, cid, "cleric.charm_animals_and_plants")
    assert r.status_code == 200, r.text
    assert r.json()["targets"] == ["cleric.charm_animals_and_plants"] and r.json()["state"]["data"]["dc"] == 8 + 6 + 3
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _use(client, cid, key)).status_code == 200
    assert (await _turn(client, cid))["bonus_used"] is True


async def test_acolyte_of_nature_asks_for_a_skill_and_a_druid_cantrip(client):
    cid = await _cleric(client, 1, "nature")
    groups = {c.get("group"): c for c in (await _full(client, cid))["pending_choices"]}
    assert {o["key"] for o in groups["nature_skill"]["options"]} == {"animal_handling", "nature", "survival"}
    assert groups["nature_cantrip"]["count"] == 1


# ---------------------------------------------------------------------------
# Dominio della Luce
# ---------------------------------------------------------------------------

async def test_warding_flare_is_a_reaction_with_wisdom_uses(client):
    cid = await _cleric(client, 6, "light", wisdom=16)
    key = "cleric.warding_flare"
    assert (await _ability(client, cid, key))["max_uses"] == 3
    r = await _use(client, cid, key)
    assert r.status_code == 200 and r.json()["state"]["data"]["others"] == [key, "cleric.improved_flare"]
    assert (await _turn(client, cid))["reaction_used"] is True and (await _ability(client, cid, key))["uses"] == 2
    low = await _cleric(client, 5, "light", wisdom=16)
    assert (await _use(client, low, key)).json()["state"]["data"]["others"] == [key]


async def test_radiance_of_the_dawn_rolls_2d10_and_shows_dc_and_level_bonus(client):
    cid = await _cleric(client, 6, "light", wisdom=16)  # competenza +3, Saggezza +3
    r = await _use(client, cid, "cleric.radiance_of_the_dawn")
    assert r.status_code == 200, r.text
    rolls = r.json()["rolls"]
    assert len(rolls) == 2 and all(1 <= v <= 10 for v in rolls)
    data = r.json()["state"]["data"]
    assert (data["dc"], data["save"], data["bonus"]) == (14, "constitution", 6)
    assert (await _ability(client, cid, POOL))["uses"] == 1


async def test_corona_of_light_lasts_ten_rounds_and_ends_with_an_action(client):
    cid = await _cleric(client, 17, "light")
    r = await _use(client, cid, "cleric.corona_of_light")
    assert r.status_code == 200 and r.json()["state"]["rounds_left"] == 10 and r.json()["state"]["end_slot"] == "action"


async def test_light_domain_knows_the_light_cantrip_beyond_the_limit(client):
    cid = await _cleric(client, 1, "light")
    spells = {s["srd_index"]: s for s in (await client.get(f"/characters/{cid}/spells")).json()}
    assert spells["light"]["level"] == 0 and spells["light"]["is_prepared"]


# ---------------------------------------------------------------------------
# Dominio della Tempesta
# ---------------------------------------------------------------------------

async def test_wrath_of_the_storm_rolls_2d8_and_shows_the_dexterity_dc(client):
    cid = await _cleric(client, 1, "tempest", wisdom=14)
    key = "cleric.wrath_of_the_storm"
    assert (await _ability(client, cid, key))["max_uses"] == 2
    r = await client.post(f"/characters/{cid}/features/{key}/use", json={"params": {"damage_type": "thunder"}})
    assert r.status_code == 200, r.text
    assert len(r.json()["rolls"]) == 2 and all(1 <= v <= 8 for v in r.json()["rolls"])
    data = r.json()["state"]["data"]
    assert (data["dc"], data["save"], data["damage_type"]) == (8 + 2 + 2, "dexterity", "thunder")
    assert (await _turn(client, cid))["reaction_used"] is True and (await _ability(client, cid, key))["uses"] == 1


async def test_wrath_of_the_storm_asks_for_lightning_or_thunder_before_spending(client):
    cid = await _cleric(client, 1, "tempest", wisdom=14)
    key = "cleric.wrath_of_the_storm"
    [choice] = (await _ability(client, cid, key))["use_choices"]
    assert {o["key"] for o in choice["options"]} == {"lightning", "thunder"}
    for params in ({}, {"damage_type": "fire"}):
        r = await client.post(f"/characters/{cid}/features/{key}/use", json={"params": params})
        assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_choice"
    assert (await _ability(client, cid, key))["uses"] == 2 and (await _turn(client, cid))["reaction_used"] is False


async def test_destructive_wrath_maximises_the_wrath_of_the_storm_dice_and_spends_the_pool(client):
    cid = await _cleric(client, 2, "tempest", wisdom=14)
    key = "cleric.wrath_of_the_storm"
    assert [t["key"] for t in (await _ability(client, cid, key))["use_toggles"]] == ["destructive"]
    r = await client.post(f"/characters/{cid}/features/{key}/use", json={"params": {"damage_type": "lightning", "destructive": True}})
    assert r.status_code == 200, r.text
    assert r.json()["rolls"] == [8, 8] and r.json()["state"]["data"]["maximized"] is True
    assert (await _ability(client, cid, POOL))["uses"] == 0 and (await _ability(client, cid, key))["uses"] == 1


async def test_destructive_wrath_without_a_channel_divinity_use_is_refused_and_changes_nothing(client):
    cid = await _cleric(client, 2, "tempest", wisdom=14)  # una sola Incanalare Divinità, due Collere
    key = "cleric.wrath_of_the_storm"
    params = {"damage_type": "thunder", "destructive": True}
    assert (await client.post(f"/characters/{cid}/features/{key}/use", json={"params": params})).status_code == 200
    await client.post(f"/characters/{cid}/turn/new")
    r = await client.post(f"/characters/{cid}/features/{key}/use", json={"params": params})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses"
    assert (await _ability(client, cid, key))["uses"] == 1 and (await _turn(client, cid))["reaction_used"] is False
    plain = await client.post(f"/characters/{cid}/features/{key}/use", json={"params": {"damage_type": "thunder"}})
    assert plain.status_code == 200  # senza Collera Distruttiva si tira normalmente


async def test_destructive_wrath_is_not_offered_at_level_1(client):
    cid = await _cleric(client, 1, "tempest")
    assert (await _ability(client, cid, "cleric.wrath_of_the_storm"))["use_toggles"] == []


# ---------------------------------------------------------------------------
# Dominio della Conoscenza
# ---------------------------------------------------------------------------

async def test_blessings_of_knowledge_sets_two_skills_to_expert(client):
    cid = await _cleric(client, 1, "knowledge")
    choice = next(c for c in (await _full(client, cid))["pending_choices"] if c.get("group") == "knowledge_skills")
    assert {o["key"] for o in choice["options"]} == {"arcana", "nature", "religion", "history"} and choice["count"] == 2
    r = await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve",
                          json={"kind": "class_option", "options": ["arcana", "history"]})
    assert r.status_code == 200, r.text
    skills = (await _full(client, cid))["skills"]
    assert skills["arcana"] == "expert" and skills["history"] == "expert"


async def _own_spell(client, cid, level, dice="1d8") -> int:
    row = (await _full(client, cid))["classes"][0]["id"]
    r = await client.post(f"/characters/{cid}/spells", json={
        "name": f"Incantesimo {level}", "level": level, "damage_dice": dice, "damage_type": "radiant", "class_id": row})
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.mark.parametrize("domain", ["knowledge", "light"])
async def test_potent_spellcasting_adds_wisdom_to_a_cleric_cantrip_only(client, domain):
    cid = await _cleric(client, 8, domain, wisdom=16)  # Saggezza +3; a livello 8 il trucchetto tira 2 dadi
    cantrip = await _own_spell(client, cid, 0)
    r = await client.post(f"/characters/{cid}/spells/{cantrip}/roll_damage", json={"main_rolls": [4, 3]})
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 4 + 3 + 3
    leveled = await _own_spell(client, cid, 1)
    assert (await client.post(f"/characters/{cid}/spells/{leveled}/roll_damage", json={"main_rolls": [4]})).json()["total"] == 4


async def test_potent_spellcasting_is_absent_without_the_right_domain(client):
    cid = await _cleric(client, 8, "life", wisdom=16)
    assert not {k for k in await _keys_of(client, cid) if "potent" in k}
    cantrip = await _own_spell(client, cid, 0)
    r = await client.post(f"/characters/{cid}/spells/{cantrip}/roll_damage", json={"main_rolls": [4, 3]})
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 7
