"""Barbaro 2024 (Task 31): i quattro Cammini (Berserker, Cuore Selvaggio, Albero del Mondo, Zelota)."""
from __future__ import annotations

import pytest

from tests.integration.rules.test_2014_barbarian import _ability, _armor, _full, _hit, _hp, _keys, _states, _turn, _weapon
from tests.integration.rules.test_2024_barbarian import RAGE, _barbarian, _new_turn, _rage
from tests.integration.rules.test_2024_barbarian_strike import _damage, _deferred

BERSERKER, WILD, TREE, ZEALOT = ("Cammino del Berserker", "Cammino del Cuore Selvaggio",
                                 "Cammino dell'Albero del Mondo", "Cammino dello Zelota")
RECKLESS = "barbarian.reckless_attack"


async def _use(client, cid, key, **body):
    return await client.post(f"/characters/{cid}/features/barbarian.{key}/use", json=body)


async def _spent(client, cid, key="rage") -> int:
    return (await _ability(client, cid, f"barbarian.{key}"))["uses"]


async def _pick(client, cid, group, option) -> None:
    choice = next(c for c in (await _full(client, cid))["pending_choices"] if c.get("group") == group)
    r = await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve", json={"kind": "class_option", "options": [option]})
    assert r.status_code == 200, r.text


async def _keys_of(client, cid) -> set[str]:
    return {a["feature_key"] for a in (await _full(client, cid))["abilities"]}


# ---------------------------------------------------------------------------
# Berserker
# ---------------------------------------------------------------------------

async def test_frenzy_adds_rage_damage_in_d6_to_the_first_strength_hit_while_raging_with_reckless_attack(client):
    cid = await _barbarian(client, 3, BERSERKER, strength=16)
    sword = await _weapon(client, cid)
    await _rage(client, cid)
    await _new_turn(client, cid)
    assert "barbarian.frenzy" not in await _keys(client, cid, "attack", item_id=sword)  # niente Attacco Irruento
    hit = await _deferred(client, cid, sword, options=[RECKLESS])
    assert "barbarian.frenzy" in await _keys(client, cid, "attack", item_id=sword)
    r = await _damage(client, cid, hit, ["barbarian.frenzy"])
    assert r.status_code == 200, r.text
    rolls = r.json()["option_result"]["extra_rolls"]
    assert len(rolls) == 2 and all(1 <= v <= 6 for v in rolls)  # +2 al 3° livello
    again = await _deferred(client, cid, sword)
    assert "barbarian.frenzy" not in await _keys(client, cid, "attack", item_id=sword)  # una volta per turno
    assert again["attack_id"]


@pytest.mark.parametrize("level,dice", [(3, 2), (9, 3), (16, 4)])
async def test_frenzy_dice_follow_the_rage_damage(client, level, dice):
    cid = await _barbarian(client, level, BERSERKER, strength=16)
    sword = await _weapon(client, cid)
    await _rage(client, cid)
    await _new_turn(client, cid)
    hit = await _deferred(client, cid, sword, options=[RECKLESS])
    r = await _damage(client, cid, hit, ["barbarian.frenzy"])
    assert len(r.json()["option_result"]["extra_rolls"]) == dice


async def test_frenzy_needs_the_rage(client):
    cid = await _barbarian(client, 3, BERSERKER, strength=16)
    sword = await _weapon(client, cid)
    await _deferred(client, cid, sword, options=[RECKLESS])
    assert "barbarian.frenzy" not in await _keys(client, cid, "attack", item_id=sword)


async def test_mindless_rage_ends_charm_and_fear_on_entry_and_blocks_them_while_raging(client):
    cid = await _barbarian(client, 6, BERSERKER)
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"frightened": True, "charmed": True}})
    await _rage(client, cid)
    conditions = (await _full(client, cid))["conditions"]
    assert not conditions.get("frightened") and not conditions.get("charmed")  # la condizione termina, non è sospesa
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"charmed": True}})
    assert not r.json()["conditions"].get("charmed")
    await client.delete(f"/characters/{cid}/active-states/rage")
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"charmed": True}})
    assert r.json()["conditions"]["charmed"] is True


async def test_no_mindless_rage_before_level_6(client):
    cid = await _barbarian(client, 5, BERSERKER)
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"frightened": True}})
    await _rage(client, cid)
    assert (await _full(client, cid))["conditions"]["frightened"] is True


async def test_retaliation_is_a_reaction_attack_after_taking_damage_without_the_rage(client):
    cid = await _barbarian(client, 10, BERSERKER, strength=16)
    sword = await _weapon(client, cid)
    assert "barbarian.retaliation" not in await _keys(client, cid, "attack", item_id=sword)
    await _hit(client, cid, 3)
    assert "barbarian.retaliation" in await _keys(client, cid, "attack", item_id=sword)
    await client.post(f"/characters/{cid}/items/{sword}/attack", json={"die": 10, "options": ["barbarian.retaliation"]})
    assert (await _turn(client, cid))["reaction_used"] is True


async def test_intimidating_presence_is_a_bonus_action_with_a_dc_from_strength(client):
    cid = await _barbarian(client, 14, BERSERKER, strength=18)
    r = await _use(client, cid, "intimidating_presence")
    assert r.status_code == 200, r.text
    assert (await _turn(client, cid))["bonus_used"] is True and r.json()["targets"] == ["barbarian.intimidating_presence"]
    effect = (await client.get(f"/characters/{cid}/target-effects/barbarian.intimidating_presence")).json()["result"]
    assert (effect["condition"], effect["save_ability"], effect["save_dc"]) == ("frightened", "wisdom", 8 + 4 + 5)
    assert effect["rounds"] == 10 and effect["repeat_save"] == "end"
    assert (await _spent(client, cid, "intimidating_presence")) == 0


async def test_intimidating_presence_is_restored_by_spending_a_rage_use(client):
    cid = await _barbarian(client, 14, BERSERKER)
    await _use(client, cid, "intimidating_presence")
    await _new_turn(client, cid)
    assert (await _use(client, cid, "intimidating_presence")).status_code == 409  # finito
    before = await _spent(client, cid)
    again = await _use(client, cid, "intimidating_presence", params={"restore": True})
    assert again.status_code == 200, again.text
    assert await _spent(client, cid) == before - 1 and (await _turn(client, cid))["bonus_used"] is True
    assert (await _ability(client, cid, "barbarian.intimidating_presence"))["restoration_type"] == "long_rest"


# ---------------------------------------------------------------------------
# Cuore Selvaggio
# ---------------------------------------------------------------------------

async def test_wild_heart_asks_for_the_rage_animal_at_every_activation(client):
    cid = await _barbarian(client, 3, WILD)
    rage = await _ability(client, cid, RAGE)
    choice = next(c for c in rage["use_choices"] if c["key"] == "wild")
    assert [o["key"] for o in choice["options"]] == ["bear", "eagle", "wolf"]
    refused = await _rage(client, cid)
    assert refused.status_code == 422 and refused.json()["detail"]["code"] == "invalid_choice"
    assert (await _spent(client, cid)) == 3
    assert (await _rage(client, cid, wild="bear")).json()["state"]["data"]["wild"] == "bear"


async def test_other_paths_are_not_asked_for_the_animal(client):
    cid = await _barbarian(client, 14, BERSERKER)
    assert (await _ability(client, cid, RAGE))["use_choices"] == []
    assert (await _rage(client, cid)).status_code == 200


async def test_animal_speaker_and_nature_speaker_grant_ritual_only_spells(client):
    cid = await _barbarian(client, 3, WILD)
    spells = {s["name"]: s for s in (await client.get(f"/characters/{cid}/spells")).json()}
    assert {"Percezione delle bestie", "Parlare con gli animali"} <= set(spells) and "Comunione con la natura" not in spells
    speak = spells["Parlare con gli animali"]
    assert "ritual_only" in (await client.get(f"/characters/{cid}/spells/{speak['id']}/cast-check")).json()
    assert "ritual_only" not in (await client.get(f"/characters/{cid}/spells/{speak['id']}/cast-check", params={"ritual": True})).json()
    tenth = await _barbarian(client, 10, WILD)
    assert "Comunione con la natura" in {s["name"] for s in (await client.get(f"/characters/{tenth}/spells")).json()}


async def test_bear_resists_every_damage_type_but_force_necrotic_psychic_and_radiant(client):
    cid = await _barbarian(client, 3, WILD)
    await _hp(client, cid, 80, 80)
    await _rage(client, cid, wild="bear")
    resisted = {"fire", "cold", "poison", "slashing", "thunder", "acid", "lightning"}
    full = await _full(client, cid)
    assert resisted <= set(full["computed"]["resistances"])
    assert not set(full["computed"]["resistances"]) & {"force", "necrotic", "psychic", "radiant"}
    assert (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10, "damage_type": "fire"})).json()["current_hit_points"] == 75
    assert (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10, "damage_type": "force"})).json()["current_hit_points"] == 65


async def test_eagle_adds_disengage_and_dash_on_entry_and_a_bonus_action_afterwards(client):
    cid = await _barbarian(client, 3, WILD)
    assert (await _use(client, cid, "wilds_eagle")).status_code == 409  # niente ira
    entry = await _rage(client, cid, wild="eagle")
    assert "Disimpegno" in entry.json()["message"]["it"] and "Dash" in entry.json()["message"]["en"]
    await _new_turn(client, cid)
    assert (await _use(client, cid, "wilds_eagle")).status_code == 200
    assert (await _turn(client, cid))["bonus_used"] is True
    other = await _barbarian(client, 3, WILD)
    await _rage(client, other, wild="bear")
    await _new_turn(client, other)
    assert (await _use(client, other, "wilds_eagle")).status_code == 409  # l'opzione scelta è un'altra


async def test_wolf_is_published_to_the_group_and_lion_too(client):
    cid = await _barbarian(client, 14, WILD)
    state = (await _rage(client, cid, wild="wolf", power="lion")).json()["state"]
    assert state["data"]["others"] == ["barbarian.wilds_wolf", "barbarian.power_lion"]
    plain = (await _rage(client, await _barbarian(client, 14, WILD), wild="bear", power="ram")).json()["state"]
    assert plain["data"]["others"] == []


async def test_power_of_the_wilds_is_asked_from_level_14_only(client):
    low = await _barbarian(client, 13, WILD)
    assert [c["key"] for c in (await _ability(client, low, RAGE))["use_choices"]] == ["wild"]
    high = await _barbarian(client, 14, WILD)
    choices = {c["key"]: [o["key"] for o in c["options"]] for c in (await _ability(client, high, RAGE))["use_choices"]}
    assert choices == {"wild": ["bear", "eagle", "wolf"], "power": ["falcon", "lion", "ram"]}


async def test_falcon_flies_at_the_walking_speed_only_without_armor(client):
    cid = await _barbarian(client, 14, WILD)
    await _rage(client, cid, wild="bear", power="falcon")
    full = await _full(client, cid)
    assert full["computed"]["fly_speed"] == full["computed"]["speed"]
    await _armor(client, cid, "light", 11)
    assert (await _full(client, cid))["computed"]["fly_speed"] is None
    ram = await _barbarian(client, 14, WILD)
    await _rage(client, ram, wild="bear", power="ram")
    assert (await _full(client, ram))["computed"]["fly_speed"] is None


async def test_ram_offers_a_prone_effect_after_a_melee_hit_in_rage(client):
    cid = await _barbarian(client, 14, WILD, strength=16)
    sword = await _weapon(client, cid)
    await _rage(client, cid, wild="bear", power="ram")
    await _new_turn(client, cid)
    hit = await _deferred(client, cid, sword)
    assert "barbarian.power_ram" in await _keys(client, cid, "attack", item_id=sword)
    r = await _damage(client, cid, hit, ["barbarian.power_ram"])
    assert r.json()["option_result"]["targets"] == ["barbarian.power_ram"]
    assert (await client.get(f"/characters/{cid}/target-effects/barbarian.power_ram")).json()["result"]["condition"] == "prone"
    falcon = await _barbarian(client, 14, WILD, strength=16)
    await _rage(client, falcon, wild="bear", power="falcon")
    assert "barbarian.power_ram" not in await _keys(client, falcon, "attack", item_id=await _weapon(client, falcon))


async def test_aspect_of_the_wilds_is_chosen_at_6_and_each_option_gives_its_benefit(client):
    cid = await _barbarian(client, 6, WILD)
    choice = next(c for c in (await _full(client, cid))["pending_choices"] if c.get("group") == "aspect_of_the_wilds")
    assert {o["key"] for o in choice["options"]} == {"owl", "panther", "salmon"}
    base = (await _full(client, cid))["computed"]
    assert base["climb_speed"] is None and base["swim_speed"] is None and base["senses"] == []
    await _pick(client, cid, "aspect_of_the_wilds", "panther")
    full = await _full(client, cid)
    assert full["computed"]["climb_speed"] == full["computed"]["speed"] and full["computed"]["swim_speed"] is None
    swimmer = await _barbarian(client, 6, WILD)
    await _pick(client, swimmer, "aspect_of_the_wilds", "salmon")
    computed = (await _full(client, swimmer))["computed"]
    assert computed["swim_speed"] == computed["speed"] and computed["climb_speed"] is None


async def test_owl_gives_darkvision_60_and_adds_60_to_the_one_already_owned(client):
    cid = await _barbarian(client, 6, WILD)
    await _pick(client, cid, "aspect_of_the_wilds", "owl")
    assert (await _full(client, cid))["computed"]["senses"] == [{"type": "darkvision", "range_ft": 60}]
    elf = await _barbarian(client, 6, WILD)
    await client.patch(f"/characters/{elf}", json={"settings": {"senses": [{"type": "darkvision", "range_ft": 60}]}})
    await _pick(client, elf, "aspect_of_the_wilds", "owl")
    assert (await _full(client, elf))["computed"]["senses"] == [{"type": "darkvision", "range_ft": 120}]


async def test_aspect_rows_exist_only_for_the_chosen_option(client):
    cid = await _barbarian(client, 6, WILD)
    await _pick(client, cid, "aspect_of_the_wilds", "salmon")
    keys = await _keys_of(client, cid)
    assert "barbarian.aspect_salmon" in keys and not keys & {"barbarian.aspect_owl", "barbarian.aspect_panther"}


# ---------------------------------------------------------------------------
# Albero del Mondo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level", [3, 9, 20])
async def test_vitality_surge_gives_temporary_hit_points_equal_to_the_level_with_the_greater_rule(client, level):
    cid = await _barbarian(client, level, TREE)
    assert (await _rage(client, cid)).json()["temp_hp"] == level
    assert (await _full(client, cid))["temp_hp"] == level
    second = await _barbarian(client, level, TREE)
    await client.patch(f"/characters/{second}/hp", json={"op": "set_temp", "value": level + 5})
    await _rage(client, second)
    assert (await _full(client, second))["temp_hp"] == level + 5


async def test_other_paths_get_no_temporary_hit_points_from_the_rage(client):
    cid = await _barbarian(client, 5, BERSERKER)
    assert (await _rage(client, cid)).json()["temp_hp"] is None  # niente toast «PF temporanei: 0» (I5)
    assert (await _full(client, cid))["temp_hp"] == 0


@pytest.mark.parametrize("level,dice", [(3, 2), (9, 3), (16, 4)])
async def test_life_giving_force_rolls_the_rage_damage_in_d6_for_another_creature(client, level, dice):
    cid = await _barbarian(client, level, TREE)
    assert (await _use(client, cid, "life_giving_force")).status_code == 409  # niente ira
    await _rage(client, cid)
    await _new_turn(client, cid)
    r = await _use(client, cid, "life_giving_force")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["rolls"]) == dice and body["given"] == sum(body["rolls"])
    assert (await _use(client, cid, "life_giving_force")).status_code == 409  # una volta per turno
    assert (await _full(client, cid))["temp_hp"] == level  # i suoi PF temporanei non cambiano


async def test_branches_of_the_tree_is_a_reaction_with_a_strength_save_dc(client):
    cid = await _barbarian(client, 6, TREE, strength=18)
    assert (await _use(client, cid, "branches_of_the_tree")).status_code == 409  # niente ira
    await _rage(client, cid)
    await _new_turn(client, cid)
    r = await _use(client, cid, "branches_of_the_tree")
    assert r.status_code == 200, r.text
    assert (await _turn(client, cid))["reaction_used"] is True and r.json()["targets"] == ["barbarian.branches_of_the_tree"]
    effect = (await client.get(f"/characters/{cid}/target-effects/barbarian.branches_of_the_tree")).json()["result"]
    assert (effect["save_ability"], effect["save_dc"]) == ("strength", 8 + 4 + 3)
    assert effect["note"] == "branches_of_the_tree"


async def test_battering_roots_adds_ten_feet_of_reach_to_heavy_and_versatile_melee_weapons(client):
    cid = await _barbarian(client, 10, TREE, strength=16)
    heavy = await _weapon(client, cid, "Ascia bipenne", None, properties=["heavy", "two_handed"], damage_dice="1d12")
    versatile = await _weapon(client, cid, "Spada lunga", None, properties=["versatile"], damage_dice="1d8")
    light = await _weapon(client, cid, "Pugnale", None, properties=["light", "finesse"], damage_dice="1d4")
    bow = await _weapon(client, cid, "Arco", None, weapon_type="ranged", properties=["heavy"], damage_dice="1d8")
    reach = {i["id"]: i.get("reach_bonus_ft") for i in (await _full(client, cid))["items"]}
    assert reach[heavy] == 10 and reach[versatile] == 10 and reach[light] is None and reach[bow] is None
    early = await _barbarian(client, 9, TREE)
    ids = [await _weapon(client, early, "Ascia bipenne", None, properties=["heavy"], damage_dice="1d12")]
    assert all(i.get("reach_bonus_ft") is None for i in (await _full(client, early))["items"] if i["id"] in ids)


async def test_battering_roots_adds_push_or_topple_to_a_different_mastery_of_the_weapon(client):
    cid = await _barbarian(client, 10, TREE, strength=16)
    choice = next(c for c in (await _full(client, cid))["pending_choices"] if c.get("group") == "weapon_mastery")
    await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve",
                      json={"kind": "class_option", "options": ["greataxe", "greatsword", "handaxe", "quarterstaff"]})
    axe = await _weapon(client, cid, "Ascia bipenne", damage_dice="1d12", properties=["heavy", "two_handed"])  # Cleave
    keys = await _keys(client, cid, "attack", item_id=axe)
    assert {"barbarian.battering_roots_push", "barbarian.battering_roots_topple"} <= set(keys)
    hit = await _deferred(client, cid, axe)
    r = await _damage(client, cid, hit, ["mastery_cleave", "barbarian.battering_roots_topple"])
    assert r.status_code == 200, r.text
    assert (await _damage(client, cid, await _deferred(client, cid, axe), [
        "barbarian.battering_roots_push", "barbarian.battering_roots_topple"])).status_code == 409  # una sola
    # con Topple già come padronanza dell'arma: resta solo Push
    staff = await _weapon(client, cid, "Bastone", None, properties=["versatile"], damage_dice="1d6")
    plain = await _weapon(client, cid, "Mazza", None, damage_dice="1d6")  # né pesante né versatile
    assert "barbarian.battering_roots_push" not in await _keys(client, cid, "attack", item_id=plain)
    assert staff


async def test_travel_along_the_tree_is_a_bonus_action_teleport_with_a_150_foot_use_once_per_rage(client):
    cid = await _barbarian(client, 15, TREE)  # dal 15° l'Ira non va prolungata: i turni passano senza attacchi
    assert (await _use(client, cid, "travel_along_the_tree")).status_code == 409  # niente ira
    entry = (await _rage(client, cid)).json()["message"]
    assert "18 m" in entry["it"] and "60 ft" in entry["en"]  # all'attivazione dell'Ira
    await _new_turn(client, cid)
    near = await _use(client, cid, "travel_along_the_tree")
    assert near.status_code == 200 and "18 m" in near.json()["message"]["it"] and "45 m" in near.json()["message"]["it"]
    await _new_turn(client, cid)
    far = await _use(client, cid, "travel_along_the_tree", params={"far": True})
    assert far.status_code == 200 and "45 m" in far.json()["message"]["it"] and "150 ft" in far.json()["message"]["en"]
    await _new_turn(client, cid)
    assert (await _use(client, cid, "travel_along_the_tree", params={"far": True})).status_code == 409  # una volta per Ira
    left = await _use(client, cid, "travel_along_the_tree")  # senza «far» il teletrasporto da 18 m resta
    assert left.status_code == 200 and "45 m" not in left.json()["message"]["it"]
    await client.delete(f"/characters/{cid}/active-states/rage")
    await _new_turn(client, cid)
    await _rage(client, cid)
    await _new_turn(client, cid)
    assert (await _use(client, cid, "travel_along_the_tree", params={"far": True})).status_code == 200  # un'altra Ira


# ---------------------------------------------------------------------------
# Zelota
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,flat", [(3, 1), (6, 3), (10, 5), (20, 10)])
async def test_divine_fury_adds_d6_plus_half_the_level_of_a_chosen_type_once_per_turn(client, level, flat):
    cid = await _barbarian(client, level, ZEALOT, strength=16)
    sword = await _weapon(client, cid)
    assert "barbarian.divine_fury_radiant" not in await _keys(client, cid, "attack", item_id=sword)  # niente ira
    await _rage(client, cid)
    await _new_turn(client, cid)
    keys = await _keys(client, cid, "attack", item_id=sword)
    assert {"barbarian.divine_fury_necrotic", "barbarian.divine_fury_radiant"} <= set(keys)
    hit = await _deferred(client, cid, sword)
    assert (await _damage(client, cid, hit, ["barbarian.divine_fury_necrotic", "barbarian.divine_fury_radiant"])).status_code == 409
    r = await _damage(client, cid, hit, ["barbarian.divine_fury_radiant"])
    assert r.status_code == 200, r.text
    result = r.json()["option_result"]
    assert len(result["extra_rolls"]) == 1 and result["extra_total"] == result["extra_rolls"][0] + flat
    keys = await _keys(client, cid, "attack", item_id=sword)
    assert not [k for k in keys if k.startswith("barbarian.divine_fury")]


@pytest.mark.parametrize("level,dice", [(3, 4), (5, 4), (6, 5), (12, 6), (17, 7)])
async def test_warrior_of_the_gods_pool_by_level(client, level, dice):
    row = await _ability(client, await _barbarian(client, level, ZEALOT), "barbarian.warrior_of_the_gods")
    assert (row["max_uses"], row["restoration_type"]) == (dice, "long_rest")


async def test_warrior_of_the_gods_spends_dice_for_hit_points_as_a_bonus_action_without_rage(client):
    cid = await _barbarian(client, 6, ZEALOT)
    await _hp(client, cid, 5, 60)
    r = await _use(client, cid, "warrior_of_the_gods", amount=3)
    assert r.status_code == 200, r.text
    rolls = r.json()["rolls"]
    assert len(rolls) == 3 and all(1 <= v <= 12 for v in rolls)
    assert r.json()["healed"] == sum(rolls) and (await _full(client, cid))["current_hit_points"] == 5 + sum(rolls)
    assert await _spent(client, cid, "warrior_of_the_gods") == 2 and (await _turn(client, cid))["bonus_used"] is True
    await _new_turn(client, cid)
    assert (await _use(client, cid, "warrior_of_the_gods", amount=3)).status_code == 409  # ne restano 2
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "short", "confirm_early": True})
    assert await _spent(client, cid, "warrior_of_the_gods") == 2
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})
    assert await _spent(client, cid, "warrior_of_the_gods") == 5


async def test_fanatical_focus_rerolls_a_save_with_the_rage_bonus_once_per_rage(client):
    cid = await _barbarian(client, 6, ZEALOT)
    key = "barbarian.fanatical_focus"
    await client.post(f"/characters/{cid}/saving_throws/wisdom/roll", json={"die": 2})
    assert (await client.post(f"/characters/{cid}/last-roll/options", json={"options": [key], "dice": [4]})).status_code == 409  # niente ira
    await _rage(client, cid)
    first = (await client.post(f"/characters/{cid}/saving_throws/wisdom/roll", json={"die": 2})).json()
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [key], "dice": [4]})
    assert r.status_code == 200, r.text
    assert r.json()["die"] == 4 and r.json()["total"] == first["total"] + 2 + 2  # nuovo d20 e +2 di Ira
    await client.post(f"/characters/{cid}/saving_throws/wisdom/roll", json={"die": 2})
    assert (await client.post(f"/characters/{cid}/last-roll/options", json={"options": [key], "dice": [4]})).status_code == 409
    await client.delete(f"/characters/{cid}/active-states/rage")
    await _new_turn(client, cid)
    await _rage(client, cid)
    await client.post(f"/characters/{cid}/saving_throws/wisdom/roll", json={"die": 2})
    assert (await client.post(f"/characters/{cid}/last-roll/options", json={"options": [key], "dice": [4]})).status_code == 200


async def test_zealous_presence_is_published_to_the_group_until_the_next_turn(client):
    cid = await _barbarian(client, 10, ZEALOT)
    r = await _use(client, cid, "zealous_presence")
    assert r.status_code == 200, r.text
    state = next(s for s in await _states(client, cid) if s["key"] == "zealous_presence")
    assert state["data"]["others"] == ["barbarian.zealous_presence"] and state["rounds_left"] == 1
    assert (await _turn(client, cid))["bonus_used"] is True


async def test_zealous_presence_is_restored_by_a_rage_use(client):
    cid = await _barbarian(client, 10, ZEALOT)
    await _use(client, cid, "zealous_presence")
    await _new_turn(client, cid)
    assert (await _use(client, cid, "zealous_presence")).status_code == 409
    before = await _spent(client, cid)
    assert (await _use(client, cid, "zealous_presence", params={"restore": True})).status_code == 200
    assert await _spent(client, cid) == before - 1


async def test_rage_of_the_gods_is_chosen_on_entry_once_per_long_rest(client):
    cid = await _barbarian(client, 14, ZEALOT)
    rage = await _ability(client, cid, RAGE)
    assert [t["key"] for t in rage["use_toggles"]] == ["divine_form"]
    assert (await _rage(client, cid, divine_form=True)).status_code == 200
    form = next(s for s in await _states(client, cid) if s["key"] == "divine_form")
    assert form["rounds_left"] == 10 and "unconscious" in form["ends_on"]
    assert await _spent(client, cid, "rage_of_the_gods") == 0
    await client.delete(f"/characters/{cid}/active-states/rage")
    await _new_turn(client, cid)
    await client.delete(f"/characters/{cid}/active-states/divine_form")
    assert [t["key"] for t in (await _ability(client, cid, RAGE))["use_toggles"]] == []  # l'uso è speso
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})
    assert [t["key"] for t in (await _ability(client, cid, RAGE))["use_toggles"]] == ["divine_form"]


async def test_the_divine_form_gives_flight_and_resistance_and_ends_at_zero_hit_points(client, monkeypatch):
    monkeypatch.setattr("api.services.d20.random.randint", lambda a, b: 1)  # Ira Implacabile fallisce: si cade a 0 PF
    cid = await _barbarian(client, 14, ZEALOT)
    await _hp(client, cid, 100, 100)
    plain = await _full(client, cid)
    assert plain["computed"]["fly_speed"] is None and "radiant" not in plain["computed"]["resistances"]
    await _rage(client, cid, divine_form=True)
    full = await _full(client, cid)
    assert full["computed"]["fly_speed"] == full["computed"]["speed"]
    assert {"necrotic", "psychic", "radiant", "slashing"} <= set(full["computed"]["resistances"])
    await _hit(client, cid, 100)
    assert not [s for s in await _states(client, cid) if s["key"] == "divine_form"]
    ordinary = await _barbarian(client, 14, ZEALOT)
    await _rage(client, ordinary)
    assert (await _full(client, ordinary))["computed"]["fly_speed"] is None


async def test_revivification_spends_a_rage_use_in_the_divine_form_only(client):
    cid = await _barbarian(client, 14, ZEALOT)
    assert (await _use(client, cid, "revivification", params={"mode": "other"})).status_code == 409  # niente forma
    await _rage(client, cid, divine_form=True)
    before = await _spent(client, cid)
    other = {"params": {"mode": "other"}}
    r = await _use(client, cid, "revivification", **other)
    assert r.status_code == 200, r.text
    assert r.json()["given"] == 14 and await _spent(client, cid) == before - 1
    assert (await _turn(client, cid))["reaction_used"] is True
    assert (await _use(client, cid, "revivification", **other)).status_code == 409  # la reazione è già spesa


async def test_intimidating_presence_while_raging_extends_the_rage_as_a_forced_save_would(client):
    """Il TS imposto è un prolungamento dell'Ira anche quando lo impone Presenza Intimidatoria (I3)."""
    cid = await _barbarian(client, 14, BERSERKER)
    assert (await _rage(client, cid)).status_code == 200
    await _new_turn(client, cid)  # l'Ira appena nata perde il segno `fresh`
    assert (await _use(client, cid, "intimidating_presence")).status_code == 200
    await _new_turn(client, cid)  # nessun attacco, ma c'è stato un TS imposto
    assert any(s["key"] == "rage" for s in await _states(client, cid))
    await _new_turn(client, cid)  # il turno dopo, senza nulla: finisce
    assert not any(s["key"] == "rage" for s in await _states(client, cid))


async def test_intimidating_presence_without_the_rage_does_not_mark_an_extension(client):
    cid = await _barbarian(client, 14, BERSERKER)
    assert (await _use(client, cid, "intimidating_presence")).status_code == 200
    await _new_turn(client, cid)  # l'azione bonus è di nuovo libera
    assert (await _rage(client, cid)).status_code == 200
    await _new_turn(client, cid)
    await _new_turn(client, cid)
    assert not any(s["key"] == "rage" for s in await _states(client, cid))


async def test_zealot_features_need_the_recognised_subclass(client):
    keys = await _keys_of(client, await _barbarian(client, 14, "Cammino dello Zelota Falso"))
    assert not {k for k in keys if k.split(".")[1] in {"divine_fury", "warrior_of_the_gods", "fanatical_focus", "zealous_presence"}}
    assert {"barbarian.divine_fury", "barbarian.rage_of_the_gods"} <= await _keys_of(client, await _barbarian(client, 14, ZEALOT))


def test_every_note_a_catalog_target_effect_names_has_a_text_in_both_languages():
    import json
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    wanted = {m for path in (root / "core" / "rules" / "catalog").rglob("*.py")
              for m in re.findall(r'note="(\w+)"', path.read_text(encoding="utf-8"))}
    assert "branches_of_the_tree" in wanted
    for lang in ("it", "en"):
        notes = json.loads((root / "webapp" / "src" / "locales" / f"{lang}.json").read_text(encoding="utf-8"))["character"]["target_effect"]["notes"]
        assert not wanted - set(notes), (lang, wanted - set(notes))
