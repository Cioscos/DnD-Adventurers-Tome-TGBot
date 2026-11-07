"""Stregone 2024, parte B: Stregoneria Aberrante, Meccanica, Draconica e Magia Selvaggia."""
from __future__ import annotations

import pytest

from core.rules.catalog import features_for
from core.rules.catalog.y2024.sorcerer_wild_magic import SURGES
from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _roll_keys, _states, _use
from tests.integration.rules.test_2014_paladin import _new_turn, _rest, _turn
from tests.integration.rules.test_2014_sorcerer import SP, _points, _set_points
from tests.integration.rules.test_2014_fighter_eldritch_knight import _spell

NAMES = {"aberrant": "Stregoneria Aberrante", "clockwork": "Stregoneria Meccanica", "draconic": "Stregoneria Draconica",
         "wild_magic": "Magia Selvaggia"}
P = "sorcerer."


async def _make(client, sub, level=10, **scores) -> int:
    body = {"name": "Stregone", "initial_class": {"class_name": "sorcerer", "level": level, "subclass": NAMES[sub]}}
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    for ability, value in {"charisma": 18, **scores}.items():
        assert (await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})).status_code == 200
    return cid


async def _spells(client, cid) -> dict[str, dict]:
    return {s["srd_index"]: s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["srd_index"]}


ROWS = {
    "aberrant": {3: ["psionic_spells", "telepathic_speech"], 6: ["psionic_sorcery", "psychic_defenses"],
                 14: ["revelation_in_flesh", "aquatic_adaptation", "glistening_flight", "see_the_invisible", "wormlike_movement"],
                 18: ["warping_implosion"]},
    "clockwork": {3: ["clockwork_spells", "restore_balance"], 6: ["bastion_of_law"], 14: ["trance_of_order"], 18: ["clockwork_cavalcade"]},
    "draconic": {3: ["draconic_resilience", "draconic_spells"], 6: ["elemental_affinity"], 14: ["dragon_wings"], 18: ["dragon_companion"]},
    "wild_magic": {3: ["wild_magic_surge", "tides_of_chaos"], 6: ["bend_luck"], 14: ["controlled_chaos"], 18: ["tamed_surge"]},
}
FLAT = [(sub, lv, key) for sub, levels in ROWS.items() for lv, keys in levels.items() for key in keys]


def test_every_subclass_mapping_title_has_its_row_with_both_languages():
    rows = features_for("2024", "sorcerer")
    titles = {f.source_title for f in rows}
    mapping = open("docs/superpowers/rules/mapping/2024/sorcerer.md", encoding="utf-8").read().splitlines()[4:]
    wanted = [l.split("|")[1].strip() for l in mapping if l.startswith("|") and ("(Stregoneria " in l.split("|")[1] or "(Magia Selvaggia " in l.split("|")[1])]
    assert len(wanted) == 25 and [t for t in wanted if t not in titles] == []
    assert all(f.summary["it"] and f.summary["en"] and len(f.summary["it"]) <= 200 and len(f.summary["en"]) <= 200 for f in rows)


@pytest.mark.parametrize("sub,level,key", FLAT)
def test_a_subclass_row_appears_at_its_level_and_only_for_its_subclass(sub, level, key):
    spec = {f.key: f for f in features_for("2024", "sorcerer")}[P + key]
    assert spec.level == level and spec.subclass == sub


def test_the_2024_surge_table_has_25_buckets_of_four():
    assert [(s.lo, s.hi) for s in SURGES] == [(lo, lo + 3) for lo in range(1, 100, 4)]
    assert all(s.name["it"] and s.name["en"] and 0 < len(s.text["it"]) <= 200 and 0 < len(s.text["en"]) <= 200 for s in SURGES)


@pytest.mark.parametrize("sub", list(ROWS))
async def test_rows_follow_the_subclass_and_the_level(client, sub):
    cid = await _make(client, sub, 5)
    keys = await _keys_of(client, cid)
    assert {P + k for k in ROWS[sub][3] if k not in ("draconic_spells", "clockwork_spells", "psionic_spells")} <= keys
    assert not keys & {P + k for lv in (6, 14, 18) for k in ROWS[sub][lv]}
    assert not keys & {P + k for other in ROWS if other != sub for k in ROWS[other][3]}


@pytest.mark.parametrize("sub,level,expect", [
    ("aberrant", 3, {"arms-of-hadar", "mind-sliver"}), ("aberrant", 9, {"telekinesis", "rarys-telepathic-bond"}),
    ("clockwork", 5, {"aid", "dispel-magic"}), ("clockwork", 9, {"wall-of-force", "greater-restoration"}),
    ("draconic", 3, {"chromatic-orb", "dragons-breath"}), ("draconic", 9, {"summon-dragon", "legend-lore"})])
async def test_subclass_spells_are_always_prepared_from_their_level(client, sub, level, expect):
    cid = await _make(client, sub, level)
    spells = await _spells(client, cid)
    assert expect <= set(spells) and all(spells[k]["always_prepared"] for k in expect)
    if level < 9:
        assert "summon-dragon" not in spells and "telekinesis" not in spells


async def test_psionic_sorcery_casts_with_points_equal_to_the_spell_level_and_no_slot(client):
    cid = await _make(client, "aberrant", 7)
    spell = (await _spells(client, cid))["hunger-of-hadar"]["id"]
    total = sum(s["available"] for s in (await _full(client, cid))["spell_slots"])
    r = await client.post(f"/characters/{cid}/spells/{spell}/use", json={"ki": True})
    assert r.status_code == 200, r.text
    assert await _points(client, cid) == 7 - 3 and sum(s["available"] for s in (await _full(client, cid))["spell_slots"]) == total


async def test_psionic_sorcery_needs_level_6_and_a_psionic_spell(client):
    cid = await _make(client, "aberrant", 5)
    spell = (await _spells(client, cid))["arms-of-hadar"]["id"]
    assert (await client.post(f"/characters/{cid}/spells/{spell}/use", json={"ki": True})).status_code == 409
    other = await _make(client, "draconic", 7)
    fly = (await _spells(client, other))["fly"]["id"]
    assert (await client.post(f"/characters/{other}/spells/{fly}/use", json={"ki": True})).status_code == 409


async def test_telepathic_speech_lasts_the_sorcerer_level_in_minutes(client):
    cid = await _make(client, "aberrant", 5)
    r = await _use(client, cid, P + "telepathic_speech")
    assert r.status_code == 200, r.text
    state = next(s for s in await _states(client, cid) if s["key"] == "telepathic_speech")
    assert state["rounds_left"] == 5 * 10 and (await _turn(client, cid))["bonus_used"] is True


async def test_psychic_defenses_resist_psychic_damage_and_offer_advantage_against_charm_and_fear(client):
    cid = await _make(client, "aberrant", 6)
    assert P + "psychic_defenses" in await _roll_keys(client, cid, "save", ability="wisdom")
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 40}); assert r.status_code in (200, 422)
    full = await _full(client, cid)
    start = full["current_hit_points"]
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10, "damage_type": "psychic"})
    assert r.json()["current_hit_points"] == start - 5
    low = await _make(client, "aberrant", 5)
    assert P + "psychic_defenses" not in await _roll_keys(client, low, "save", ability="wisdom")


async def test_revelation_in_flesh_costs_a_point_per_benefit_and_lasts_ten_minutes(client):
    cid = await _make(client, "aberrant", 14)
    r = await _use(client, cid, P + "revelation_in_flesh", params={"swim": True, "fly": True})
    assert r.status_code == 200, r.text
    assert await _points(client, cid) == 14 - 2 and (await _turn(client, cid))["bonus_used"] is True
    state = next(s for s in await _states(client, cid) if s["key"] == "revelation_in_flesh")
    assert state["rounds_left"] == 100 and set(state["data"]["benefits"]) == {"swim", "fly"}
    full = await _full(client, cid)
    assert full["computed"]["fly_speed"] == full["computed"]["speed"] and full["computed"]["swim_speed"] == full["computed"]["speed"]


async def test_revelation_in_flesh_without_a_benefit_is_refused_and_costs_nothing(client):
    cid = await _make(client, "aberrant", 14)
    assert (await _use(client, cid, P + "revelation_in_flesh")).status_code == 422
    assert await _points(client, cid) == 14 and (await _turn(client, cid))["bonus_used"] is False


async def test_warping_implosion_is_one_use_restorable_with_five_points(client):
    cid = await _make(client, "aberrant", 18)
    r = await _use(client, cid, P + "warping_implosion")
    assert r.status_code == 200 and r.json()["rolls"] and len(r.json()["rolls"]) == 3, r.text
    await _new_turn(client, cid)
    assert (await _use(client, cid, P + "warping_implosion")).status_code in (409, 422)
    r = await _use(client, cid, P + "warping_implosion", params={"restore": True})
    assert r.status_code == 200, r.text
    assert await _points(client, cid) == 18 - 5


async def test_restore_balance_uses_follow_charisma_with_a_minimum_of_one(client):
    assert (await _ability(client, await _make(client, "clockwork", 5, charisma=18), P + "restore_balance"))["max_uses"] == 4
    assert (await _ability(client, await _make(client, "clockwork", 5, charisma=6), P + "restore_balance"))["max_uses"] == 1


async def test_bastion_of_law_spends_points_for_that_many_d8_and_damage_spends_them(client):
    cid = await _make(client, "clockwork", 8)
    assert (await _use(client, cid, P + "bastion_of_law", params={"points": "6"})).status_code == 422
    r = await _use(client, cid, P + "bastion_of_law", params={"points": "3"})
    assert r.status_code == 200, r.text
    assert await _points(client, cid) == 8 - 3
    state = next(s for s in await _states(client, cid) if s["key"] == "bastion_of_law")
    assert state["data"]["dice"] == 3
    keys = await _roll_keys(client, cid, "damage_taken")
    assert P + "bastion_of_law_3" in keys and P + "bastion_of_law_4" not in keys


async def test_trance_of_order_turns_a_low_d20_on_a_check_into_ten(client):
    cid = await _make(client, "clockwork", 14)
    skill = lambda die: client.post(f"/characters/{cid}/skills/athletics/roll", json={"die": die})  # noqa: E731
    assert (await skill(5)).json()["die"] == 5
    r = await _use(client, cid, P + "trance_of_order")
    assert r.status_code == 200, r.text
    assert (await skill(5)).json()["die"] == 10 and (await skill(14)).json()["die"] == 14


@pytest.mark.parametrize("key,points,level", [("trance_of_order", 5, 14), ("clockwork_cavalcade", 7, 18)])
async def test_clockwork_once_per_rest_features_can_be_restored_with_points(client, key, points, level):
    cid = await _make(client, "clockwork", level)
    assert (await _use(client, cid, P + key)).status_code == 200
    await _new_turn(client, cid)
    assert (await _use(client, cid, P + key)).status_code in (409, 422)
    assert (await _use(client, cid, P + key, params={"restore": True})).status_code == 200
    assert await _points(client, cid) == level - points


async def test_draconic_resilience_adds_one_hp_per_level_and_sets_the_unarmored_ac(client):
    cid = await _make(client, "draconic", 3, constitution=10, dexterity=14)
    plain = await _make(client, "clockwork", 3, constitution=10, dexterity=14)
    assert (await _full(client, cid))["computed"]["hp_max_effective"] == (await _full(client, plain))["computed"]["hp_max_effective"] + 3
    full = await _full(client, cid)
    assert full["ac_breakdown"]["base"] == 10 + 2 + 4 and full["unarmored_formula"] == ["dexterity", "charisma"]
    up = await _make(client, "draconic", 7, constitution=10)
    assert (await _full(client, up))["computed"]["hp_max_effective"] == (await _full(client, await _make(client, "clockwork", 7, constitution=10)))["computed"]["hp_max_effective"] + 7


async def _affinity(client, cid, kind) -> None:
    choice = next(c for c in (await _full(client, cid))["pending_choices"] if c.get("group") == "elemental_affinity")
    r = await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve", json={"kind": "class_option", "options": [kind]})
    assert r.status_code == 200, r.text


async def test_elemental_affinity_is_a_chosen_type_with_resistance_and_a_charisma_bonus(client):
    cid = await _make(client, "draconic", 6)
    choice = next(c for c in (await _full(client, cid))["pending_choices"] if c.get("group") == "elemental_affinity")
    assert {o["key"] for o in choice["options"]} == {"acid", "cold", "fire", "lightning", "poison"}
    await _affinity(client, cid, "fire")
    fire = await _spell(client, cid, "Dardo", 1, attack_save="DEX", damage_dice="2d6", damage_type="fire")
    cold = await _spell(client, cid, "Gelo", 1, attack_save="DEX", damage_dice="2d6", damage_type="cold")
    assert P + "elemental_affinity" in await _roll_keys(client, cid, "spell_damage", spell_id=fire)
    assert P + "elemental_affinity" not in await _roll_keys(client, cid, "spell_damage", spell_id=cold)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 40})
    start = (await _full(client, cid))["current_hit_points"]
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10, "damage_type": "fire"})
    assert r.json()["current_hit_points"] == start - 5


async def test_dragon_wings_fly_for_an_hour_and_restore_for_three_points(client):
    cid = await _make(client, "draconic", 14)
    assert (await _use(client, cid, P + "dragon_wings")).status_code == 200
    state = next(s for s in await _states(client, cid) if s["key"] == "dragon_wings")
    assert state["rounds_left"] == 600 and (await _full(client, cid))["computed"]["fly_speed"] is not None
    await _new_turn(client, cid)
    assert (await _use(client, cid, P + "dragon_wings", params={"restore": True})).status_code == 200
    assert await _points(client, cid) == 14 - 3


async def test_dragon_companion_casts_summon_dragon_once_without_a_slot(client):
    cid = await _make(client, "draconic", 18)
    spell = (await _spells(client, cid))["summon-dragon"]["id"]
    before = sum(s["available"] for s in (await _full(client, cid))["spell_slots"])
    r = await client.post(f"/characters/{cid}/spells/{spell}/use", json={"free_cast": True})
    assert r.status_code == 200, r.text
    assert sum(s["available"] for s in (await _full(client, cid))["spell_slots"]) == before
    assert (await _ability(client, cid, P + "dragon_companion"))["uses"] == 0
    assert P + "dragon_companion_no_concentration" in await _roll_keys(client, cid, "cast", spell_id=spell)


# ---------------------------------------------------------------------------
# Magia Selvaggia
# ---------------------------------------------------------------------------

async def _surge(client, cid, expect=200, **body):
    r = await client.post(f"/characters/{cid}/wild-magic/surge", json=body)
    assert r.status_code == expect, r.text
    return r.json()


async def test_the_surge_triggers_on_a_twenty_not_on_a_one(client):
    cid = await _make(client, "wild_magic", 3)
    assert (await _surge(client, cid, die=1))["triggered"] is False
    await _new_turn(client, cid)
    body = await _surge(client, cid, die=20, percentile=[37])
    assert body["triggered"] is True and body["applied"]["lo"] == 37 and body["applied"]["label"] == "37-40"
    assert body["applied"]["state"]["key"] == "wild_vulnerable_all"
    await _surge(client, cid, die=20, expect=409)


async def test_a_surge_result_applies_its_numbers(client):
    cid = await _make(client, "wild_magic", 3)
    body = await _surge(client, cid, die=20, percentile=[85])
    assert body["applied"]["damage"]["dice"] == "1d10" and body["applied"]["label"] == "85-88"
    await _new_turn(client, cid)
    body = await _surge(client, cid, die=20, percentile=[100])
    assert body["applied"]["label"] == "97-00" and body["applied"]["extra_roll"]["dice"] == "1d6"


async def test_controlled_chaos_rolls_twice_and_the_player_picks_one(client):
    cid = await _make(client, "wild_magic", 14)
    body = await _surge(client, cid, die=20, percentile=[10, 50])
    assert body["pending"] is True and len(body["options"]) == 2
    r = await client.post(f"/characters/{cid}/wild-magic/surge/choose", json={"index": 1})
    assert r.status_code == 200 and r.json()["applied"]["label"] == "49-52"


async def test_tides_of_chaos_gives_advantage_to_a_check_and_returns_after_a_surge(client):
    cid = await _make(client, "wild_magic", 3)
    assert P + "tides_of_chaos_advantage" in await _roll_keys(client, cid, "skill")
    assert P + "tides_of_chaos_advantage" not in await _roll_keys(client, cid, "attack")
    r = await client.post(f"/characters/{cid}/skills/arcana/roll", json={"die": 8, "options": [P + "tides_of_chaos_advantage"]})
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, P + "tides_of_chaos"))["uses"] == 0
    body = await _surge(client, cid, tides=True, percentile=[5])
    assert body["tides_restored"] is True and (await _ability(client, cid, P + "tides_of_chaos"))["uses"] == 1


async def test_bend_luck_costs_one_point(client):
    cid = await _make(client, "wild_magic", 6)
    r = await _use(client, cid, P + "bend_luck", params={"sign": "plus"})
    assert r.status_code == 200, r.text
    assert await _points(client, cid) == 6 - 1 and (await _turn(client, cid))["reaction_used"] is True


async def test_tamed_surge_picks_the_result_once_and_never_the_last_row(client):
    cid = await _make(client, "wild_magic", 18)
    await _surge(client, cid, tamed=True, percentile=[98], expect=422)
    assert (await _ability(client, cid, P + "tamed_surge"))["uses"] == 1
    body = await _surge(client, cid, tamed=True, percentile=[53])
    assert body["applied"]["label"] == "53-56" and body["applied"]["extra_action"] is True
    assert (await _ability(client, cid, P + "tamed_surge"))["uses"] == 0
    await _surge(client, cid, tamed=True, percentile=[53], expect=409)
    await _rest(client, cid, "long")
    assert (await _ability(client, cid, P + "tamed_surge"))["uses"] == 1


async def test_the_2014_surge_is_unchanged_for_a_2014_character(client):
    body = {"name": "Vecchio", "initial_class": {"class_name": "sorcerer", "level": 3, "subclass": "Magia Selvaggia"}}
    cid = (await client.post("/characters", json=body)).json()["id"]
    assert (await _surge(client, cid, die=1, percentile=[1]))["triggered"] is True
