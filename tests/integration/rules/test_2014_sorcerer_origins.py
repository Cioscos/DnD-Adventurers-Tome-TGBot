"""Stregone 2014 (Task 28): Discendenza Draconica e Magia Selvaggia."""
from __future__ import annotations

import pytest

from core.rules.catalog.y2014.sorcerer import DRAGONS
from core.rules.catalog.y2014.sorcerer_wild_magic import SURGES
from tests.integration.rules.test_2014_barbarian import _armor
from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _roll_keys, _use
from tests.integration.rules.test_2014_fighter_eldritch_knight import _spell
from tests.integration.rules.test_2014_paladin import _new_turn, _rest, _turn
from tests.integration.rules.test_2014_sorcerer import SP, _points, _set_points, _slots, _sorcerer
from tests.integration.rules.test_2014_sorcerer_metamagic import _damage, _use_spell

DRAGON_TYPES = {"silver": "cold", "white": "cold", "blue": "lightning", "bronze": "lightning", "black": "acid", "copper": "acid",
                "gold": "fire", "brass": "fire", "red": "fire", "green": "poison"}
AFFINITY, AFFINITY_USE = "sorcerer.elemental_affinity", "sorcerer.elemental_affinity_resistance"
WINGS, PRESENCE = "sorcerer.dragon_wings", "sorcerer.draconic_presence"
ANCESTOR_CHECK = "sorcerer.dragon_ancestor_check"
SURGE, TIDES, BEND, BOMBARD = "sorcerer.wild_magic_surge", "sorcerer.tides_of_chaos", "sorcerer.bend_luck", "sorcerer.spell_bombardment"
TIDES_OPTION = "sorcerer.tides_of_chaos_advantage"


def _pending(full: dict, group: str) -> dict | None:
    return next((c for c in full["pending_choices"] if c.get("group") == group), None)


async def _draconic(client, level=6, dragon="red", **scores) -> int:
    cid = await _sorcerer(client, level, "draconic", **{"charisma": 16, **scores})
    choice = _pending(await _full(client, cid), "dragon_ancestor")
    r = await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve", json={"kind": "class_option", "options": [dragon]})
    assert r.status_code == 200, r.text
    return cid


async def _wild(client, level=6, **scores) -> int:
    return await _sorcerer(client, level, "wild_magic", **{"charisma": 16, **scores})


def _states(full: dict) -> dict[str, dict]:
    return {s["key"]: s for s in full["active_states"] or []}


# ---------------------------------------------------------------------------
# Discendenza Draconica: Antenato, Resilienza
# ---------------------------------------------------------------------------

async def test_the_ancestor_is_one_of_ten_dragons_chosen_at_level_1_and_only_by_the_draconic_bloodline(client):
    choice = _pending(await _full(client, await _sorcerer(client, 1, "draconic")), "dragon_ancestor")
    assert choice["count"] == 1 and {o["key"] for o in choice["options"]} == set(DRAGON_TYPES) == set(DRAGONS)
    assert all(o["name"]["it"] and o["name"]["en"] for o in choice["options"])
    assert _pending(await _full(client, await _sorcerer(client, 1, "wild_magic")), "dragon_ancestor") is None
    assert _pending(await _full(client, await _sorcerer(client, 1)), "dragon_ancestor") is None


async def test_the_ancestor_adds_the_draconic_language_once(client):
    cid = await _draconic(client, 1, "gold")
    languages = (await _full(client, cid))["languages"]
    assert languages.count("Draconico") == 1


@pytest.mark.parametrize("level,extra", [(1, 1), (3, 3), (9, 9), (20, 20)])
async def test_draconic_resilience_adds_one_hit_point_per_sorcerer_level(client, level, extra):
    cid = await _draconic(client, level, constitution=10)
    base = (await _full(client, await _sorcerer(client, level, "wild_magic", constitution=10)))["computed"]["hp_max_effective"]
    assert (await _full(client, cid))["computed"]["hp_max_effective"] == base + extra


async def test_draconic_resilience_gives_13_plus_dexterity_without_armor_and_yields_to_armor(client):
    cid = await _draconic(client, 1, dexterity=14)
    assert (await _full(client, cid))["ac"] == 15
    await _armor(client, cid, "heavy", 16)
    assert (await _full(client, cid))["ac"] == 16


async def test_draconic_resilience_does_not_work_for_the_wild_magic_bloodline(client):
    assert (await _full(client, await _sorcerer(client, 1, "wild_magic", dexterity=14)))["ac"] == 12


# ---------------------------------------------------------------------------
# Antenato Draconico: prove di Carisma con i draghi
# ---------------------------------------------------------------------------

async def _check(client, cid, skill, *options):
    r = await client.post(f"/characters/{cid}/skills/{skill}/roll", json={"die": 10, "options": list(options)})
    assert r.status_code == 200, r.text
    return r.json()


async def test_the_proficiency_bonus_doubles_on_charisma_checks_to_deal_with_dragons_only_when_proficient(client):
    cid = await _draconic(client, 5)
    await client.patch(f"/characters/{cid}/skills", json={"skills": {"persuasion": True}})
    assert ANCESTOR_CHECK in await _roll_keys(client, cid, "skill", skill="persuasion")
    assert ANCESTOR_CHECK not in await _roll_keys(client, cid, "skill", skill="deception")  # non competente
    assert ANCESTOR_CHECK not in await _roll_keys(client, cid, "skill", skill="athletics")  # non è Carisma
    plain = (await _check(client, cid, "persuasion"))["total"]
    assert (await _check(client, cid, "persuasion", ANCESTOR_CHECK))["total"] == plain + 3


# ---------------------------------------------------------------------------
# Affinità Elementale
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("dragon,damage", [("red", "fire"), ("silver", "cold"), ("green", "poison"), ("bronze", "lightning"), ("copper", "acid")])
async def test_elemental_affinity_adds_the_charisma_modifier_to_one_damage_roll_of_the_ancestor_type(client, dragon, damage):
    cid = await _draconic(client, 6, dragon, charisma=18)
    spell = await _spell(client, cid, "Dardo", 1, attack_save="DEX", damage_dice="2d6", damage_type=damage)
    other = await _spell(client, cid, "Altro", 1, attack_save="DEX", damage_dice="2d6", damage_type="necrotic")
    assert AFFINITY in await _roll_keys(client, cid, "spell_damage", spell_id=spell)
    assert AFFINITY not in await _roll_keys(client, cid, "spell_damage", spell_id=other)
    plain = await _damage(client, cid, spell, casting_level=1, main_rolls=[3, 3])
    boosted = await _damage(client, cid, spell, casting_level=1, main_rolls=[3, 3], options=[AFFINITY])
    assert boosted["total"] == plain["total"] + 4


async def test_elemental_affinity_starts_at_level_6_and_needs_the_draconic_bloodline(client):
    cid = await _draconic(client, 5, "red")
    spell = await _spell(client, cid, "Dardo", 1, attack_save="DEX", damage_dice="2d6", damage_type="fire")
    assert AFFINITY not in await _roll_keys(client, cid, "spell_damage", spell_id=spell)
    cid = await _sorcerer(client, 6, "wild_magic")
    spell = await _spell(client, cid, "Dardo", 1, attack_save="DEX", damage_dice="2d6", damage_type="fire")
    assert AFFINITY not in await _roll_keys(client, cid, "spell_damage", spell_id=spell)


# ---------------------------------------------------------------------------
# Ali di Drago
# ---------------------------------------------------------------------------

async def test_dragon_wings_give_a_flying_speed_equal_to_the_walking_one_until_dismissed(client):
    cid = await _draconic(client, 14)
    assert (await _full(client, cid))["computed"]["fly_speed"] is None
    r = await _use(client, cid, WINGS)
    assert r.status_code == 200, r.text
    full = await _full(client, cid)
    assert full["computed"]["fly_speed"] == full["computed"]["speed"] and (await _turn(client, cid))["bonus_used"] is True
    await _rest(client, cid, "long")
    assert (await _full(client, cid))["computed"]["fly_speed"] == full["computed"]["speed"]  # restano finché non le congedi
    await _new_turn(client, cid)
    r = await client.delete(f"/characters/{cid}/active-states/dragon_wings")
    assert r.status_code == 200, r.text
    assert (await _full(client, cid))["computed"]["fly_speed"] is None


async def test_dragon_wings_are_refused_while_wearing_armor_and_cost_nothing(client):
    cid = await _draconic(client, 14)
    await _armor(client, cid, "heavy", 16)
    r = await _use(client, cid, WINGS)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "feature_unavailable"
    assert (await _turn(client, cid))["bonus_used"] is False


async def test_dragon_wings_start_at_level_14(client):
    assert WINGS not in await _keys_of(client, await _draconic(client, 13))


# ---------------------------------------------------------------------------
# Presenza Draconica
# ---------------------------------------------------------------------------

async def test_draconic_presence_costs_5_points_and_an_action_and_starts_a_concentration(client):
    cid = await _draconic(client, 18, charisma=18)
    r = await _use(client, cid, PRESENCE, params={"mode": "awe"})
    assert r.status_code == 200, r.text
    full = await _full(client, cid)
    state = _states(full)["draconic_presence"]
    assert await _points(client, cid) == 13 and (await _turn(client, cid))["action_used"] is True
    assert state["rounds_left"] == 10 and state["data"]["dc"] == 8 + 6 + 4 and state["data"]["save"] == "wisdom"
    assert full["concentrating_spell_id"] is None and "concentration_rounds_left" in full["settings"]
    assert r.json()["targets"] == [PRESENCE]


@pytest.mark.parametrize("mode,condition", [("awe", "charmed"), ("fear", "frightened")])
async def test_draconic_presence_awe_charms_and_fear_frightens_those_who_fail_the_save(client, mode, condition):
    cid = await _draconic(client, 18)
    await _use(client, cid, PRESENCE, params={"mode": mode})
    effect = (await client.get(f"/characters/{cid}/target-effects/{PRESENCE}")).json()["result"]
    assert effect["condition"] == condition and effect["save_ability"] == "wisdom" and effect["immune_on_success"] is True


async def test_draconic_presence_ends_when_the_concentration_is_lost(client):
    cid = await _draconic(client, 18)
    await _use(client, cid, PRESENCE, params={"mode": "fear"})
    r = await client.patch(f"/characters/{cid}/concentration", json={"spell_id": None})
    assert r.status_code == 200, r.text
    assert "draconic_presence" not in _states(await _full(client, cid))


async def test_draconic_presence_needs_five_points_and_a_valid_mode(client):
    cid = await _draconic(client, 18)
    assert (await _use(client, cid, PRESENCE, params={"mode": "rage"})).status_code == 422
    await _set_points(client, cid, 4)
    r = await _use(client, cid, PRESENCE, params={"mode": "awe"})
    assert r.status_code == 409 and (await _turn(client, cid))["action_used"] is False


# ---------------------------------------------------------------------------
# Magia Selvaggia: la tabella
# ---------------------------------------------------------------------------

def test_the_surge_table_covers_the_hundred_results_in_fifty_pairs_with_both_languages():
    assert len(SURGES) == 50
    assert [(s.lo, s.hi) for s in SURGES] == [(i, i + 1) for i in range(1, 100, 2)]
    assert all(s.name["it"] and s.name["en"] and 0 < len(s.text["it"]) <= 200 and 0 < len(s.text["en"]) <= 200 for s in SURGES)


async def _surge(client, cid, *, die=1, percentile=(1,), tides=False, expect=200):
    r = await client.post(f"/characters/{cid}/wild-magic/surge", json={"die": die, "percentile": list(percentile), "tides": tides})
    assert r.status_code == expect, r.text
    return r.json()


async def test_the_surge_rolls_a_d20_and_only_a_one_opens_the_table(client):
    cid = await _wild(client, 1)
    body = await _surge(client, cid, die=7)
    assert body["die"] == 7 and body["triggered"] is False and body["options"] == [] and body["applied"] is None
    await _new_turn(client, cid)
    body = await _surge(client, cid, die=1, percentile=(39,))
    assert body["triggered"] is True and body["applied"]["lo"] == 39 and body["applied"]["name"]["it"]


async def test_the_surge_d20_is_rolled_once_per_turn(client):
    cid = await _wild(client, 1)
    await _surge(client, cid, die=7)
    r = await client.post(f"/characters/{cid}/wild-magic/surge", json={"die": 7})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "once_per_turn"
    await _new_turn(client, cid)
    await _surge(client, cid, die=7)


async def test_only_the_wild_magic_bloodline_has_the_surge(client):
    for cid in (await _draconic(client, 6), await _sorcerer(client, 6)):
        r = await client.post(f"/characters/{cid}/wild-magic/surge", json={"die": 1})
        assert r.status_code == 404


async def test_the_surge_is_a_feature_row_with_a_panel_not_a_plain_use(client):
    cid = await _wild(client, 1)
    row = await _ability(client, cid, SURGE)
    assert row["use_panel"] == "wild_magic"
    r = await _use(client, cid, SURGE)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "needs_panel"


async def test_a_surge_that_heals_applies_the_hit_points_and_reports_the_dice(client):
    cid = await _wild(client, 1)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 60})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 10})
    body = await _surge(client, cid, percentile=(40,))
    assert 2 <= body["applied"]["healed"] <= 20 and (await _full(client, cid))["current_hit_points"] == 10 + body["applied"]["healed"]


async def test_a_surge_that_returns_the_lowest_spent_slot_gives_back_that_slot(client):
    cid = await _wild(client, 6)
    for level in (2, 3):
        spell = await _spell(client, cid, f"Incantesimo {level}", level)
        assert (await client.post(f"/characters/{cid}/spells/{spell}/use", json={"slot_level": level})).status_code == 200
    body = await _surge(client, cid, percentile=(60,))
    assert body["applied"]["slot_level"] == 2
    assert (await _slots(client, cid))[2] == (3, 0) and (await _slots(client, cid))[3] == (3, 1)


async def test_a_surge_that_returns_all_the_sorcery_points_restores_them(client):
    cid = await _wild(client, 6)
    await _set_points(client, cid, 1)
    await _surge(client, cid, percentile=(99,))
    assert await _points(client, cid) == 6


async def test_a_surge_with_an_extra_action_grants_it(client):
    cid = await _wild(client, 6)
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "action", "used": True})
    await _surge(client, cid, percentile=(82,))
    assert (await _turn(client, cid))["extra_actions"] == 1


async def test_a_surge_that_heals_each_turn_heals_at_the_start_of_the_turn_for_a_minute(client):
    cid = await _wild(client, 6)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 60})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 10})
    body = await _surge(client, cid, percentile=(16,))
    assert body["applied"]["state"]["rounds_left"] == 10
    await _new_turn(client, cid)
    assert (await _full(client, cid))["current_hit_points"] == 15


async def test_a_surge_with_a_timer_shows_it_as_an_active_state_for_a_minute(client):
    cid = await _wild(client, 6)
    body = await _surge(client, cid, percentile=(26,))  # occhio sulla fronte: un minuto
    state = body["applied"]["state"]
    assert state["rounds_left"] == 10 and state["key"] in _states(await _full(client, cid))


async def test_a_surge_with_a_shield_adds_two_to_the_armor_class_and_resistance_to_all_damage(client):
    cid = await _wild(client, 6, dexterity=10)
    base = (await _full(client, cid))["ac"]
    await _surge(client, cid, percentile=(52,))
    assert (await _full(client, cid))["ac"] == base + 2
    await _new_turn(client, cid)
    await _surge(client, cid, percentile=(72,))
    assert "all" in (await _full(client, cid))["computed"]["resistances"]


async def test_a_surge_that_casts_a_spell_shows_the_save_dc(client):
    cid = await _wild(client, 6, charisma=18)
    body = await _surge(client, cid, percentile=(8,))  # palla di fuoco
    assert body["applied"]["dc"] == 8 + 3 + 4


async def test_a_surge_that_deals_damage_rolls_the_dice(client):
    cid = await _wild(client, 6)
    body = await _surge(client, cid, percentile=(66,))
    assert len(body["applied"]["damage"]["rolls"]) == 4 and body["applied"]["damage"]["type"] == "lightning"
    assert body["applied"]["damage"]["total"] == sum(body["applied"]["damage"]["rolls"])


async def test_a_surge_without_numbers_only_reports_the_result(client):
    cid = await _wild(client, 6)
    body = await _surge(client, cid, percentile=(18,))
    assert body["applied"]["state"] is None and body["applied"]["healed"] == 0


async def test_controlled_chaos_rolls_twice_and_the_player_chooses_before_anything_applies(client):
    cid = await _wild(client, 14)
    await _set_points(client, cid, 1)
    body = await _surge(client, cid, percentile=(99, 20))
    assert body["pending"] is True and [o["lo"] for o in body["options"]] == [99, 19] and body["applied"] is None
    assert await _points(client, cid) == 1
    r = await client.post(f"/characters/{cid}/wild-magic/surge/choose", json={"index": 1})
    assert r.status_code == 200, r.text
    assert r.json()["applied"]["lo"] == 19 and await _points(client, cid) == 1


async def test_controlled_chaos_is_not_offered_before_level_14(client):
    cid = await _wild(client, 13)
    body = await _surge(client, cid, percentile=(99, 20))
    assert body["pending"] is False and len(body["options"]) == 1 and body["applied"]["lo"] == 99


async def test_choosing_without_a_pending_surge_is_refused(client):
    cid = await _wild(client, 14)
    r = await client.post(f"/characters/{cid}/wild-magic/surge/choose", json={"index": 0})
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# Onde di Caos
# ---------------------------------------------------------------------------

async def test_tides_of_chaos_is_one_use_per_long_rest_and_gives_advantage_on_attack_checks_and_saves(client):
    cid = await _wild(client, 1)
    row = await _ability(client, cid, TIDES)
    assert (row["max_uses"], row["restoration_type"]) == (1, "long_rest")
    for roll, query in (("attack", {}), ("skill", {"skill": "stealth"}), ("save", {"ability": "wisdom"})):
        assert TIDES_OPTION in await _roll_keys(client, cid, roll, **query)
    r = await client.post(f"/characters/{cid}/skills/stealth/roll", json={"dice": [3, 15], "options": [TIDES_OPTION]})
    assert r.status_code == 200, r.text
    assert r.json()["mode"] == "advantage" and (await _ability(client, cid, TIDES))["uses"] == 0
    assert TIDES_OPTION not in await _roll_keys(client, cid, "skill", skill="stealth")
    await _rest(client, cid, "long")
    assert (await _ability(client, cid, TIDES))["uses"] == 1


async def test_a_surge_requested_after_using_tides_returns_the_use(client):
    cid = await _wild(client, 6)
    await client.post(f"/characters/{cid}/skills/stealth/roll", json={"dice": [3, 15], "options": [TIDES_OPTION]})
    body = await _surge(client, cid, percentile=(18,), tides=True)
    assert body["tides_restored"] is True and (await _ability(client, cid, TIDES))["uses"] == 1


async def test_the_tides_surge_needs_the_use_to_be_spent(client):
    cid = await _wild(client, 6)
    body = await _surge(client, cid, percentile=(18,), tides=True, expect=409)
    assert body["detail"]["code"] == "tides_not_spent"


# ---------------------------------------------------------------------------
# Piegare la Fortuna
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("sign", ["plus", "minus"])
async def test_bend_luck_spends_two_points_and_a_reaction_and_rolls_a_d4(client, sign):
    cid = await _wild(client, 6)
    r = await _use(client, cid, BEND, params={"sign": sign})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["rolls"]) == 1 and 1 <= body["rolls"][0] <= 4 and f"bend_luck_{sign}" in body["notes"]
    assert await _points(client, cid) == 4 and (await _turn(client, cid))["reaction_used"] is True


async def test_bend_luck_needs_a_valid_sign_two_points_and_the_reaction(client):
    cid = await _wild(client, 6)
    assert (await _use(client, cid, BEND, params={"sign": "zero"})).status_code == 422
    await _set_points(client, cid, 1)
    assert (await _use(client, cid, BEND, params={"sign": "plus"})).status_code == 409
    await _set_points(client, cid, 6)
    assert (await _use(client, cid, BEND, params={"sign": "plus"})).status_code == 200
    r = await _use(client, cid, BEND, params={"sign": "plus"})
    assert r.status_code == 409 and await _points(client, cid) == 4


async def test_bend_luck_starts_at_level_6(client):
    assert BEND not in await _keys_of(client, await _wild(client, 5))


# ---------------------------------------------------------------------------
# Bombardamento Magico
# ---------------------------------------------------------------------------

async def test_spell_bombardment_rerolls_one_die_showing_its_maximum_and_adds_the_new_result(client):
    cid = await _wild(client, 18)
    spell = await _spell(client, cid, "Dardo", 1, attack_save="DEX", damage_dice="3d6", damage_type="fire")
    first = await _damage(client, cid, spell, casting_level=1, main_rolls=[6, 2, 3])
    assert BOMBARD in await _roll_keys(client, cid, "spell_damage", spell_id=spell)
    r = await client.post(f"/characters/{cid}/last-damage/options", json={"options": [BOMBARD], "option_inputs": {}, "reroll": [0]})
    assert r.status_code == 200, r.text
    assert r.json()["total"] > first["total"] and len(r.json()["rolls"]) == 4


async def test_spell_bombardment_refuses_a_die_that_is_not_at_its_maximum_and_does_not_use_up_the_turn(client):
    cid = await _wild(client, 18)
    spell = await _spell(client, cid, "Dardo", 1, attack_save="DEX", damage_dice="3d6", damage_type="fire")
    await _damage(client, cid, spell, casting_level=1, main_rolls=[6, 2, 3])
    r = await client.post(f"/characters/{cid}/last-damage/options", json={"options": [BOMBARD], "option_inputs": {}, "reroll": [1]})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "bad_reroll"
    assert BOMBARD in await _roll_keys(client, cid, "spell_damage", spell_id=spell)


async def test_spell_bombardment_is_once_per_turn_and_starts_at_level_18(client):
    cid = await _wild(client, 18)
    spell = await _spell(client, cid, "Dardo", 1, attack_save="DEX", damage_dice="3d6", damage_type="fire")
    await _damage(client, cid, spell, casting_level=1, main_rolls=[6, 6, 3])
    assert (await client.post(f"/characters/{cid}/last-damage/options",
                              json={"options": [BOMBARD], "option_inputs": {}, "reroll": [0]})).status_code == 200
    assert BOMBARD not in await _roll_keys(client, cid, "spell_damage", spell_id=spell)
    await _new_turn(client, cid)
    assert BOMBARD in await _roll_keys(client, cid, "spell_damage", spell_id=spell)


async def test_spell_bombardment_starts_at_level_18(client):
    cid = await _wild(client, 17)
    spell = await _spell(client, cid, "Dardo", 1, attack_save="DEX", damage_dice="3d6", damage_type="fire")
    assert BOMBARD not in await _roll_keys(client, cid, "spell_damage", spell_id=spell)


# ---------------------------------------------------------------------------
# Giro di correzione 1: Affinità Elementale al lancio (I3), condizioni degli impulsi (I4)
# ---------------------------------------------------------------------------

AFFINITY_CAST = "sorcerer.elemental_affinity_resistance"


async def _cast_keys(client, cid, spell) -> list[str]:
    return await _roll_keys(client, cid, "cast", spell_id=spell)


async def test_the_resistance_is_a_cast_option_offered_only_for_a_spell_of_the_ancestor_type(client):  # I3
    cid = await _draconic(client, 6, "blue")
    lightning = await _spell(client, cid, "Fulmine", 3, attack_save="DEX", damage_dice="8d6", damage_type="lightning")
    fire = await _spell(client, cid, "Dardo", 1, attack_save="DEX", damage_dice="2d6", damage_type="fire")
    assert AFFINITY_CAST in await _cast_keys(client, cid, lightning) and AFFINITY_CAST not in await _cast_keys(client, cid, fire)
    assert AFFINITY_USE not in await _keys_of(client, cid)  # non c'è più un «Usa» slegato dal lancio


async def test_casting_with_the_option_pays_a_point_and_gives_resistance_for_an_hour_without_ending_on_rests(client):  # I3
    cid = await _draconic(client, 6, "blue")
    spell = await _spell(client, cid, "Fulmine", 3, attack_save="DEX", damage_dice="8d6", damage_type="lightning")
    r = await _use_spell(client, cid, spell, AFFINITY_CAST, slot_level=3)
    assert r.status_code == 200, r.text
    full = await _full(client, cid)
    state = _states(full)["elemental_resistance"]
    assert state["rounds_left"] == 600 and "rest_short" not in state["ends_on"] and "rest_long" not in state["ends_on"]
    assert "lightning" in full["computed"]["resistances"] and await _points(client, cid) == 5


async def test_the_resistance_option_is_refused_for_another_damage_type_and_costs_nothing(client):  # I3
    cid = await _draconic(client, 6, "blue")
    fire = await _spell(client, cid, "Dardo", 1, attack_save="DEX", damage_dice="2d6", damage_type="fire")
    r = await _use_spell(client, cid, fire, AFFINITY_CAST, slot_level=1)
    assert r.status_code == 409 and await _points(client, cid) == 6 and "elemental_resistance" not in _states(await _full(client, cid))


async def _surge_state(client, cid, percentile):
    await _new_turn(client, cid)
    body = await _surge(client, cid, percentile=(percentile,))
    return body, await _full(client, cid)


async def test_the_plant_surge_makes_you_incapacitated_and_vulnerable_to_everything_until_the_next_turn(client):  # I4
    cid = await _wild(client, 6)
    _, full = await _surge_state(client, cid, 41)
    assert full["conditions"]["incapacitated"] is True and "all" in full["computed"]["vulnerabilities"]
    await _new_turn(client, cid)
    full = await _full(client, cid)
    assert not full["conditions"].get("incapacitated") and "all" not in full["computed"]["vulnerabilities"]


async def test_the_fear_surge_frightens_you_until_the_next_turn(client):  # I4
    cid = await _wild(client, 6)
    _, full = await _surge_state(client, cid, 67)
    assert full["conditions"]["frightened"] is True
    await _new_turn(client, cid)
    assert not (await _full(client, cid))["conditions"].get("frightened")


async def test_the_silent_invisibility_surge_makes_you_invisible_for_a_minute(client):  # I4
    cid = await _wild(client, 6)
    _, full = await _surge_state(client, cid, 89)
    assert full["conditions"]["invisible"] is True and _states(full)["wild_invisible"]["rounds_left"] == 10


async def test_the_vulnerability_surge_makes_you_vulnerable_to_piercing_damage_only(client):  # I4
    cid = await _wild(client, 6)
    _, full = await _surge_state(client, cid, 95)
    assert full["computed"]["vulnerabilities"] == ["piercing"]


async def test_the_repeat_surge_lets_you_roll_the_table_at_each_turn_for_a_minute_once_per_turn(client):  # I4
    cid = await _wild(client, 6)
    await _surge(client, cid, percentile=(1,))
    assert _states(await _full(client, cid))["wild_repeat"]["rounds_left"] == 10
    await _new_turn(client, cid)
    again = await client.post(f"/characters/{cid}/wild-magic/surge", json={"repeat": True, "percentile": [39]})
    assert again.status_code == 200 and again.json()["die"] is None and again.json()["applied"]["lo"] == 39
    twice = await client.post(f"/characters/{cid}/wild-magic/surge", json={"repeat": True, "percentile": [39]})
    assert twice.status_code == 409 and twice.json()["detail"]["code"] == "once_per_turn"
    await _new_turn(client, cid)
    ignored = await client.post(f"/characters/{cid}/wild-magic/surge", json={"repeat": True, "percentile": [2]})
    assert ignored.status_code == 200 and ignored.json()["applied"]["ignored"] is True


async def test_the_repeat_roll_needs_the_repeat_state(client):  # I4
    cid = await _wild(client, 6)
    r = await client.post(f"/characters/{cid}/wild-magic/surge", json={"repeat": True, "percentile": [39]})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_repeat"
