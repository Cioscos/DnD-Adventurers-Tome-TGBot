"""Ranger 2014 (Task 26): progressione, PF, competenze, incantesimi, Nemico Prescelto, Esploratore Nato, Stile di
Combattimento, Consapevolezza Primordiale e i privilegi dal 5° livello (Attacco Extra, Andatura sul Territorio, Nascondersi in
Piena Vista, Svanire, Sensi Ferini, Sterminatore di Nemici)."""
from __future__ import annotations

import pytest

from core.rules.catalog import features_for
from core.rules.proficiencies import class_proficiencies
from core.rules.spellcasting import known_limits
from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _roll_keys, _skills, _use
from tests.integration.rules.test_2014_fighter_styles import _item
from tests.integration.rules.test_2014_paladin import _new_turn, _turn

ARCHETYPES = {"hunter": "Cacciatore", "beast_master": "Signore delle Bestie"}
ENEMIES = {"aberrations", "beasts", "celestials", "constructs", "dragons", "elementals", "fey", "giants", "fiends", "oozes",
           "monstrosities", "undead", "plants", "humanoids"}
TERRAINS = {"arctic", "coast", "desert", "forest", "mountain", "swamp", "grassland", "underdark"}
STYLES = {"archery", "defense", "dueling", "two_weapon"}
FE_ADV, NE_DOUBLE = "ranger.favored_enemy_advantage", "ranger.natural_explorer_double"
LANDS, HIDE_ADV, STEALTH_10 = "ranger.lands_stride", "ranger.hide_in_plain_sight", "ranger.hide_in_plain_sight_stealth"
FERAL, SLAYER_HIT, SLAYER_HIT_LATE, SLAYER_DMG = ("ranger.feral_senses", "ranger.foe_slayer_attack", "ranger.foe_slayer_attack_late",
                                                  "ranger.foe_slayer_damage")
AWARENESS, VANISH = "ranger.primeval_awareness", "ranger.vanish"


async def _ranger(client, level=5, archetype=None, **scores) -> int:
    body = {"name": "Ranger", "initial_class": {"class_name": "ranger", "level": level, "subclass": ARCHETYPES.get(archetype)}}
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for ability, value in scores.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})
        assert r.status_code == 200, r.text
    return cid


def _choice(full: dict, group: str) -> dict | None:
    return next((c for c in full["pending_choices"] if c.get("group") == group), None)


async def _resolve(client, cid, group, *options):
    choice = _choice(await _full(client, cid), group)
    return await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve",
                             json={"kind": "class_option", "options": list(options)})


async def _skill_roll(client, cid, skill, *options, die=10, **body):
    r = await client.post(f"/characters/{cid}/skills/{skill}/roll", json={"die": die, "options": list(options), **body})
    assert r.status_code == 200, r.text
    return r.json()


async def _styled(client, style, level=5, archetype=None, **scores) -> int:
    cid = await _ranger(client, level, archetype, **scores)
    r = await _resolve(client, cid, "fighting_style", style)
    assert r.status_code == 200, r.text
    return cid


# ---------------------------------------------------------------------------
# Progressione, PF, competenze, incantesimi
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,slots", [
    (2, {1: 2}), (3, {1: 3}), (5, {1: 4, 2: 2}), (9, {1: 4, 2: 3, 3: 2}), (13, {1: 4, 2: 3, 3: 3, 4: 1}),
    (17, {1: 4, 2: 3, 3: 3, 4: 3, 5: 1}), (19, {1: 4, 2: 3, 3: 3, 4: 3, 5: 2}), (20, {1: 4, 2: 3, 3: 3, 4: 3, 5: 2})])
async def test_slots_follow_the_half_caster_table(client, level, slots):
    cid = await _ranger(client, level)
    assert {s["level"]: s["total"] for s in (await _full(client, cid))["spell_slots"]} == slots


async def test_a_level_1_ranger_has_no_slots_and_no_spells(client):
    full = await _full(client, await _ranger(client, 1))
    assert full["spell_slots"] == [] and full["spellcasting"]["limits"][0]["known_limit"] == 0


@pytest.mark.parametrize("level,known", [(1, 0), (2, 2), (3, 3), (4, 3), (5, 4), (6, 4), (7, 5), (9, 6), (11, 7), (13, 8),
                                         (15, 9), (17, 10), (19, 11), (20, 11)])
def test_known_spells_follow_the_ranger_table_with_no_cantrips(level, known):
    limits = known_limits("2014", "ranger", level)
    assert (limits.cantrips, limits.spells) == (0, known)


async def test_the_sheet_shows_the_known_limit_and_the_wisdom_spell_stats(client):
    cid = await _ranger(client, 5, wisdom=16)  # competenza +3, Saggezza +3
    spellcasting = (await _full(client, cid))["spellcasting"]
    assert spellcasting["limits"][0]["known_limit"] == 4 and not spellcasting["limits"][0]["cantrips_limit"]
    (stats,) = spellcasting["casters"]
    assert (stats["ability"], stats["save_dc"], stats["attack_bonus"]) == ("wisdom", 8 + 3 + 3, 3 + 3)


async def test_hit_points_use_the_d10_and_follow_constitution(client):
    full = await _full(client, await _ranger(client, 3))
    assert full["classes"][0]["hit_die"] == 10 and full["hit_points"] == 10 + 6 + 6


def test_class_proficiencies_first_class_and_multiclass():
    first = class_proficiencies("2014", "ranger", False)
    assert set(first.armor) == {"light", "medium", "shields"} and set(first.weapons) == {"simple", "martial"}
    assert set(first.saves) == {"strength", "dexterity"} and first.skills_count == 3
    assert set(first.skills_from) == {"animal_handling", "athletics", "insight", "investigation", "nature", "perception",
                                      "stealth", "survival"}
    multi = class_proficiencies("2014", "ranger", True)
    assert set(multi.armor) == {"light", "medium", "shields"} and set(multi.weapons) == {"simple", "martial"}
    assert not multi.saves and multi.skills_count == 1


async def test_a_ranger_added_as_a_second_class_adds_half_its_levels_to_the_slots(client):
    cid = await _ranger(client, 5)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "wizard", "level": 3, "hit_die": 6})
    assert r.status_code == 201, r.text
    # mago 3 (3) + ranger 5 diviso 2 per difetto (2) = livello da incantatore 5
    assert {s["level"]: s["total"] for s in (await _full(client, cid))["spell_slots"]} == {1: 4, 2: 3, 3: 2}


async def test_rules_only_rows_do_not_clutter_the_sheet(client):
    keys = await _keys_of(client, await _ranger(client, 20, "hunter"))
    assert not keys & {f"ranger.{k}" for k in (
        "hit_points", "proficiencies", "equipment", "fighting_style", "spellcasting", "ranger_archetype",
        "ability_score_improvement", "multiclassing", "hunters_prey", "defensive_tactics", "multiattack",
        "superior_hunters_defense")}


@pytest.mark.parametrize("level,pending", [(3, 0), (4, 1), (7, 1), (8, 2), (11, 2), (12, 3), (15, 3), (16, 4), (18, 4), (19, 5), (20, 5)])
async def test_asi_choices_are_pending_at_levels_4_8_12_16_and_19_only(client, level, pending):
    full = await _full(client, await _ranger(client, level))
    assert len([c for c in full["pending_choices"] if c.get("kind") == "asi"]) == pending


def test_extra_attack_is_two_attacks_from_level_5_and_does_not_grow():
    extra = [f for f in features_for("2014", "ranger") if f.attacks_per_action]
    assert [(f.level, f.attacks_per_action) for f in extra] == [(5, 2)]


async def test_attacks_allowed_follow_extra_attack_and_never_add_up_with_another_class(client):
    assert (await client.get(f"/characters/{await _ranger(client, 4)}/turn-state")).json()["attacks_allowed"] == 1
    cid = await _ranger(client, 5)
    assert (await client.get(f"/characters/{cid}/turn-state")).json()["attacks_allowed"] == 2
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 5, "hit_die": 10})
    assert r.status_code == 201, r.text
    assert (await client.get(f"/characters/{cid}/turn-state")).json()["attacks_allowed"] == 2


async def test_the_hunter_and_beast_master_features_need_the_recognised_archetype(client):
    assert not {k for k in await _keys_of(client, await _ranger(client, 3)) if "colossus" in k or "companion" in k}
    assert "ranger.rangers_companion" in await _keys_of(client, await _ranger(client, 3, "beast_master"))
    assert "ranger.rangers_companion" not in await _keys_of(client, await _ranger(client, 3, "hunter"))


# ---------------------------------------------------------------------------
# Nemico Prescelto
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,count", [(1, 1), (5, 1), (6, 2), (13, 2), (14, 3), (20, 3)])
async def test_favored_enemies_are_chosen_at_levels_1_6_and_14(client, level, count):
    choice = _choice(await _full(client, await _ranger(client, level)), "favored_enemy")
    assert choice["count"] == count and {o["key"] for o in choice["options"]} == ENEMIES
    assert all(o["name"]["it"] and o["name"]["en"] for o in choice["options"])


async def test_each_enemy_comes_with_a_language_choice_that_can_be_skipped(client):
    cid = await _ranger(client, 1)
    language = _choice(await _full(client, cid), "favored_enemy_language")
    assert language["count"] == 1
    keys = {o["key"] for o in language["options"]}
    assert "giant" in keys and "none_1" in keys and "none_2" not in keys
    r = await _resolve(client, cid, "favored_enemy_language", "giant")
    assert r.status_code == 200, r.text
    assert (await _full(client, cid))["languages"] == ["Gigante"]


async def test_a_favored_enemy_that_speaks_no_language_adds_nothing_and_never_blocks_the_next(client):
    cid = await _ranger(client, 1)
    assert (await _resolve(client, cid, "favored_enemy_language", "none_1")).status_code == 200
    assert (await _full(client, cid))["languages"] in ([], None)
    assert _choice(await _full(client, cid), "favored_enemy_language") is None
    class_id = (await _full(client, cid))["classes"][0]["id"]
    await client.patch(f"/characters/{cid}/classes/{class_id}", json={"level": 6})
    second = _choice(await _full(client, cid), "favored_enemy_language")
    assert second["count"] == 1 and "none_2" in {o["key"] for o in second["options"]}


async def test_an_enemy_already_chosen_is_not_offered_again(client):
    cid = await _ranger(client, 1)
    assert (await _resolve(client, cid, "favored_enemy", "undead")).status_code == 200
    class_id = (await _full(client, cid))["classes"][0]["id"]
    await client.patch(f"/characters/{cid}/classes/{class_id}", json={"level": 6})
    assert "undead" not in {o["key"] for o in _choice(await _full(client, cid), "favored_enemy")["options"]}


@pytest.mark.parametrize("options", [[], ["undead", "giants"], ["goblins"]])
async def test_exactly_one_known_enemy_is_taken(client, options):
    cid = await _ranger(client, 1)
    assert (await _resolve(client, cid, "favored_enemy", *options)).status_code == 422


@pytest.mark.parametrize("skill", ["survival", "arcana", "history", "investigation", "nature", "religion"])
async def test_favored_enemy_advantage_is_asked_on_tracking_and_intelligence_checks(client, skill):
    cid = await _ranger(client, 1)
    assert FE_ADV in await _roll_keys(client, cid, "skill", skill=skill)
    body = await _skill_roll(client, cid, skill, FE_ADV, dice=[4, 17], mode="normal")
    assert body["mode"] == "advantage"


@pytest.mark.parametrize("skill", ["perception", "insight", "athletics", "stealth", "persuasion", "medicine"])
async def test_favored_enemy_advantage_is_not_asked_on_other_skills(client, skill):
    assert FE_ADV not in await _roll_keys(client, await _ranger(client, 1), "skill", skill=skill)


async def test_favored_enemy_advantage_also_covers_a_plain_intelligence_check(client):
    cid = await _ranger(client, 1)
    assert FE_ADV in await _roll_keys(client, cid, "ability", ability="intelligence")
    assert FE_ADV not in await _roll_keys(client, cid, "ability", ability="wisdom")


async def test_without_the_confirmation_there_is_no_advantage(client):
    cid = await _ranger(client, 1)
    assert (await _skill_roll(client, cid, "survival"))["mode"] == "normal"


# ---------------------------------------------------------------------------
# Esploratore Nato
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,count", [(1, 1), (5, 1), (6, 2), (9, 2), (10, 3), (20, 3)])
async def test_terrains_are_chosen_at_levels_1_6_and_10(client, level, count):
    choice = _choice(await _full(client, await _ranger(client, level)), "favored_terrain")
    assert choice["count"] == count and {o["key"] for o in choice["options"]} == TERRAINS


async def test_a_terrain_is_chosen_once(client):
    cid = await _ranger(client, 1)
    assert (await _resolve(client, cid, "favored_terrain", "forest", "desert")).status_code == 422
    assert (await _resolve(client, cid, "favored_terrain", "forest")).status_code == 200
    class_id = (await _full(client, cid))["classes"][0]["id"]
    await client.patch(f"/characters/{cid}/classes/{class_id}", json={"level": 6})
    assert "forest" not in {o["key"] for o in _choice(await _full(client, cid), "favored_terrain")["options"]}


@pytest.mark.parametrize("skill", ["survival", "nature", "perception", "investigation", "history"])
async def test_natural_explorer_doubles_the_proficiency_bonus_on_a_proficient_intelligence_or_wisdom_skill(client, skill):
    cid = await _ranger(client, 5)  # competenza +3
    await _skills(client, cid, **{skill: True})
    assert NE_DOUBLE in await _roll_keys(client, cid, "skill", skill=skill)
    plain = await _skill_roll(client, cid, skill)
    doubled = await _skill_roll(client, cid, skill, NE_DOUBLE)
    assert doubled["bonus"] == plain["bonus"] + 3 and doubled["total"] == plain["total"] + 3


async def test_natural_explorer_needs_the_proficiency_and_does_not_triple_an_expertise(client):
    cid = await _ranger(client, 5)
    assert NE_DOUBLE not in await _roll_keys(client, cid, "skill", skill="survival")
    await _skills(client, cid, survival="expert")
    assert NE_DOUBLE not in await _roll_keys(client, cid, "skill", skill="survival")


@pytest.mark.parametrize("skill", ["stealth", "athletics", "acrobatics", "persuasion"])
async def test_natural_explorer_is_only_for_intelligence_and_wisdom_checks(client, skill):
    cid = await _ranger(client, 5)
    await _skills(client, cid, **{skill: True})
    assert NE_DOUBLE not in await _roll_keys(client, cid, "skill", skill=skill)


async def test_natural_explorer_is_not_offered_to_other_classes(client):
    r = await client.post("/characters", json={"name": "Altro", "initial_class": {"class_name": "fighter", "level": 5}})
    cid = r.json()["id"]
    await _skills(client, cid, survival=True)
    assert NE_DOUBLE not in await _roll_keys(client, cid, "skill", skill="survival")


# ---------------------------------------------------------------------------
# Stile di Combattimento
# ---------------------------------------------------------------------------

async def test_the_style_is_chosen_at_level_2_among_four(client):
    assert _choice(await _full(client, await _ranger(client, 1)), "fighting_style") is None
    choice = _choice(await _full(client, await _ranger(client, 2)), "fighting_style")
    assert choice["count"] == 1 and {o["key"] for o in choice["options"]} == STYLES
    assert all(o["name"]["it"] and o["name"]["en"] and o["summary"]["it"] for o in choice["options"])


@pytest.mark.parametrize("options", [[], ["defense", "dueling"], ["protection"], ["great_weapon"]])
async def test_exactly_one_of_the_four_styles_is_taken(client, options):
    cid = await _ranger(client, 3)
    assert (await _resolve(client, cid, "fighting_style", *options)).status_code == 422


async def test_the_chosen_style_becomes_a_row_and_the_choice_closes(client):
    cid = await _styled(client, "dueling")
    assert "ranger.style_dueling" in await _keys_of(client, cid)
    assert _choice(await _full(client, cid), "fighting_style") is None
    assert not {f"ranger.style_{s}" for s in STYLES - {"dueling"}} & await _keys_of(client, cid)


async def test_a_style_a_fighter_class_already_has_is_not_offered(client):
    cid = await _styled(client, "defense")
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 1, "hit_die": 10})
    assert r.status_code == 201, r.text
    offered = {o["key"] for o in _choice(await _full(client, cid), "fighting_style")["options"]}
    assert "defense" not in offered and "archery" in offered
    assert (await _resolve(client, cid, "fighting_style", "defense")).status_code >= 400


async def _bow(client, cid) -> int:
    return await _item(client, cid, "Arco lungo", damage_dice="1d8", weapon_type="ranged", properties=["ammunition"],
                       equip="main_hand")


async def _sword(client, cid, **kw) -> int:
    return await _item(client, cid, "Spada", damage_dice="1d8", weapon_type="melee", properties=[], **kw)


async def _attack(client, cid, wid, die=10, **body):
    r = await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": die, "confirm_extra_attack": True, **body})
    assert r.status_code == 200, r.text
    return r.json()


async def test_archery_adds_two_to_ranged_attacks_only(client):
    cid = await _ranger(client, 2)
    bow, sword = await _bow(client, cid), await _sword(client, cid, equip="off_hand")
    plain = [(await _attack(client, cid, w))["to_hit_bonus"] for w in (bow, sword)]
    assert (await _resolve(client, cid, "fighting_style", "archery")).status_code == 200
    assert [(await _attack(client, cid, w))["to_hit_bonus"] for w in (bow, sword)] == [plain[0] + 2, plain[1]]


async def test_defense_adds_one_to_ac_only_while_wearing_armor(client):
    cid = await _ranger(client, 2)
    await _item(client, cid, "Cuoio", "armor", armor_type="light", ac_value=11)
    assert (await _resolve(client, cid, "fighting_style", "defense")).status_code == 200
    assert (await _full(client, cid))["ac_breakdown"]["rules"] == 0
    iid = next(i["id"] for i in (await _full(client, cid))["items"] if i["name"] == "Cuoio")
    await client.patch(f"/characters/{cid}/items/{iid}", json={"is_equipped": True, "equipment_slot": "body"})
    assert (await _full(client, cid))["ac_breakdown"]["rules"] == 1


async def test_dueling_adds_two_to_a_one_handed_melee_weapon_without_another_weapon(client):
    cid = await _ranger(client, 2)
    wid = await _sword(client, cid, equip="main_hand")
    plain = (await _attack(client, cid, wid))["damage_bonus"]
    assert (await _resolve(client, cid, "fighting_style", "dueling")).status_code == 200
    assert (await _attack(client, cid, wid))["damage_bonus"] == plain + 2
    await _item(client, cid, "Pugnale", damage_dice="1d4", weapon_type="melee", properties=["light"], equip="off_hand")
    assert (await _attack(client, cid, wid))["damage_bonus"] == plain


async def test_two_weapon_fighting_adds_the_modifier_to_the_offhand_damage_only(client):
    cid = await _ranger(client, 2, dexterity=16)
    main = await _item(client, cid, "Spada corta", damage_dice="1d6", weapon_type="melee", properties=["finesse", "light"],
                       equip="main_hand")
    off = await _item(client, cid, "Pugnale", damage_dice="1d4", weapon_type="melee", properties=["finesse", "light"],
                      equip="off_hand")
    plain = (await _attack(client, cid, off, attack_mode="offhand"))["damage_bonus"]
    assert (await _resolve(client, cid, "fighting_style", "two_weapon")).status_code == 200
    await _new_turn(client, cid)  # l'attacco con la seconda arma costa l'azione bonus
    assert (await _attack(client, cid, off, attack_mode="offhand"))["damage_bonus"] == plain + 3
    assert (await _attack(client, cid, main))["damage_bonus"] == 3  # il primo attacco ha già il modificatore


# ---------------------------------------------------------------------------
# Consapevolezza Primordiale
# ---------------------------------------------------------------------------

async def test_primeval_awareness_comes_with_the_archetype_level(client):
    assert AWARENESS not in await _keys_of(client, await _ranger(client, 2))
    row = await _ability(client, await _ranger(client, 3), AWARENESS)
    assert row["action_type"] == "action" and [o["key"] for o in row["use_choices"][0]["options"]] == ["1"]


async def test_primeval_awareness_spends_a_slot_of_the_chosen_level_and_lasts_a_minute_per_level(client):
    cid = await _ranger(client, 5)  # slot 1° x4, 2° x2
    row = await _ability(client, cid, AWARENESS)
    assert [o["key"] for o in row["use_choices"][0]["options"]] == ["1", "2"]
    r = await _use(client, cid, AWARENESS, params={"slot_level": "2"})
    assert r.status_code == 200, r.text
    state = next(s for s in await _states(client, cid) if s["key"] == "primeval_awareness")
    assert state["rounds_left"] == 20 and state["data"]["radius_km"] == 1.5
    slots = {s["level"]: s["used"] for s in (await _full(client, cid))["spell_slots"]}
    assert slots == {1: 0, 2: 1} and (await _turn(client, cid))["action_used"] is True


async def test_primeval_awareness_reaches_nine_kilometres_in_the_favored_terrain(client):
    cid = await _ranger(client, 3)
    r = await _use(client, cid, AWARENESS, params={"slot_level": "1", "terrain": True})
    assert r.status_code == 200, r.text
    state = next(s for s in await _states(client, cid) if s["key"] == "primeval_awareness")
    assert state["rounds_left"] == 10 and state["data"]["radius_km"] == 9


async def test_primeval_awareness_refuses_a_missing_slot_and_costs_nothing(client):
    cid = await _ranger(client, 5)
    r = await _use(client, cid, AWARENESS, params={"slot_level": "3"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_choice"
    assert (await _turn(client, cid))["action_used"] is False
    for _ in range(4):
        await _new_turn(client, cid)
        assert (await _use(client, cid, AWARENESS, params={"slot_level": "1"})).status_code == 200
    await _new_turn(client, cid)
    again = await _use(client, cid, AWARENESS, params={"slot_level": "1"})
    assert again.status_code == 422  # gli slot di 1° livello sono finiti: il livello non è più fra le scelte
    assert (await _turn(client, cid))["action_used"] is False


async def test_primeval_awareness_needs_the_action_of_the_turn(client):
    cid = await _ranger(client, 3)
    assert (await _use(client, cid, AWARENESS, params={"slot_level": "1"})).status_code == 200
    again = await _use(client, cid, AWARENESS, params={"slot_level": "1"})
    assert again.status_code == 409 and again.json()["detail"]["code"] == "turn_slot_used"
    assert {s["level"]: s["used"] for s in (await _full(client, cid))["spell_slots"]} == {1: 1}


async def test_primeval_awareness_can_use_a_pact_slot(client, test_session_factory):
    from sqlalchemy import select
    from core.db.models import SpellSlot
    cid = await _ranger(client, 3)
    async with test_session_factory() as s:
        for slot in (await s.execute(select(SpellSlot).where(SpellSlot.character_id == cid))).scalars():
            slot.used = slot.total
        s.add(SpellSlot(character_id=cid, level=2, total=1, used=0, is_pact=True))
        await s.commit()
    r = await _use(client, cid, AWARENESS, params={"slot_level": "2"})
    assert r.status_code == 200, r.text
    assert next(s for s in await _states(client, cid) if s["key"] == "primeval_awareness")["rounds_left"] == 20


async def _states(client, cid) -> list[dict]:
    return (await _full(client, cid))["active_states"] or []


# ---------------------------------------------------------------------------
# Andatura sul Territorio
# ---------------------------------------------------------------------------

async def test_lands_stride_asks_about_magical_plants_on_saves_from_level_8(client):
    assert LANDS not in await _roll_keys(client, await _ranger(client, 7), "save", ability="strength")
    cid = await _ranger(client, 8)
    for ability in ("strength", "dexterity"):
        assert LANDS in await _roll_keys(client, cid, "save", ability=ability)
    r = await client.post(f"/characters/{cid}/saving_throws/strength/roll", json={"dice": [3, 17], "options": [LANDS]})
    assert r.status_code == 200, r.text
    assert r.json()["mode"] == "advantage" and r.json()["die"] == 17


async def test_lands_stride_has_a_row_that_states_the_difficult_terrain_exemption(client):
    row = await _ability(client, await _ranger(client, 8), LANDS)
    assert "terreno difficile" in row["description"].lower()


# ---------------------------------------------------------------------------
# Nascondersi in Piena Vista
# ---------------------------------------------------------------------------

async def test_hide_in_plain_sight_is_a_camouflage_state_that_gives_plus_ten_to_stealth(client):
    cid = await _ranger(client, 10)
    assert STEALTH_10 not in await _roll_keys(client, cid, "skill", skill="stealth")
    r = await _use(client, cid, HIDE_ADV)
    assert r.status_code == 200, r.text
    assert any(s["key"] == "camouflaged" for s in await _states(client, cid))
    assert STEALTH_10 in await _roll_keys(client, cid, "skill", skill="stealth")
    assert STEALTH_10 not in await _roll_keys(client, cid, "skill", skill="perception")
    plain = (await _skill_roll(client, cid, "stealth"))["bonus"]
    assert (await _skill_roll(client, cid, "stealth", STEALTH_10))["bonus"] == plain + 10


async def test_hide_in_plain_sight_is_not_there_before_level_10(client):
    assert HIDE_ADV not in await _keys_of(client, await _ranger(client, 9))


async def test_camouflage_ends_when_the_ranger_attacks(client):
    cid = await _ranger(client, 10)
    wid = await _bow(client, cid)
    assert (await _use(client, cid, HIDE_ADV)).status_code == 200
    await _attack(client, cid, wid)
    assert not any(s["key"] == "camouflaged" for s in await _states(client, cid))
    assert STEALTH_10 not in await _roll_keys(client, cid, "skill", skill="stealth")


async def test_camouflage_can_be_dropped_by_hand_and_does_not_outlast_a_rest(client):
    cid = await _ranger(client, 10)
    assert (await _use(client, cid, HIDE_ADV)).status_code == 200
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "short", "confirm_early": True})
    assert not any(s["key"] == "camouflaged" for s in await _states(client, cid))


# ---------------------------------------------------------------------------
# Svanire
# ---------------------------------------------------------------------------

async def test_vanish_is_a_bonus_action_that_hides_from_level_14(client):
    assert VANISH not in await _keys_of(client, await _ranger(client, 13))
    cid = await _ranger(client, 14)
    row = await _ability(client, cid, VANISH)
    assert row["action_type"] == "bonus_action"
    r = await _use(client, cid, VANISH)
    assert r.status_code == 200, r.text
    assert "vanish_hide" in r.json()["notes"] and (await _turn(client, cid))["bonus_used"] is True
    assert (await _turn(client, cid))["action_used"] is False
    again = await _use(client, cid, VANISH)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "turn_slot_used"


# ---------------------------------------------------------------------------
# Sensi Ferini
# ---------------------------------------------------------------------------

async def test_feral_senses_is_asked_on_attacks_from_level_18(client):
    assert FERAL not in await _roll_keys(client, await _ranger(client, 17), "attack")
    cid = await _ranger(client, 18)
    assert FERAL in await _roll_keys(client, cid, "attack")
    wid = await _sword(client, cid, equip="main_hand")
    body = await _attack(client, cid, wid, options=[FERAL])
    assert "Sensi Ferini" in body["option_result"]["effects"][0]["it"]
    assert "Feral Senses" in body["option_result"]["effects"][0]["en"]


# ---------------------------------------------------------------------------
# Sterminatore di Nemici
# ---------------------------------------------------------------------------

async def _slayer(client, **scores) -> tuple[int, int]:
    cid = await _ranger(client, 20, wisdom=16, **scores)  # Saggezza +3
    return cid, await _sword(client, cid, equip="main_hand")


async def test_foe_slayer_is_offered_from_level_20_on_attacks_only(client):
    assert SLAYER_HIT not in await _roll_keys(client, await _ranger(client, 19, wisdom=16), "attack")
    cid, _ = await _slayer(client)
    assert {SLAYER_HIT, SLAYER_HIT_LATE, SLAYER_DMG} <= set(await _roll_keys(client, cid, "attack"))
    assert SLAYER_HIT not in await _roll_keys(client, cid, "skill", skill="survival")


async def test_foe_slayer_adds_the_wisdom_modifier_to_the_attack_roll(client):
    cid, wid = await _slayer(client)
    plain = (await _attack(client, cid, wid))["to_hit_bonus"]
    await _new_turn(client, cid)
    assert (await _attack(client, cid, wid, options=[SLAYER_HIT]))["to_hit_bonus"] == plain + 3


async def test_foe_slayer_adds_the_wisdom_modifier_to_the_damage_roll_after_the_hit(client):
    cid, wid = await _slayer(client)
    hit = await _attack(client, cid, wid, defer_damage=True)
    plain = hit["damage_total"]
    r = await client.post(f"/characters/{cid}/attack/{hit['attack_id']}/damage", json={"options": [SLAYER_DMG]})
    assert r.status_code == 200, r.text
    assert r.json()["damage_total"] == plain + 3


async def test_foe_slayer_can_be_decided_after_seeing_the_d20(client):
    cid, wid = await _slayer(client)
    hit = await _attack(client, cid, wid, defer_damage=True)
    assert hit["attack_id"]
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [SLAYER_HIT_LATE]})
    assert r.status_code == 200, r.text
    assert r.json()["total"] == hit["to_hit_total"] + 3


async def test_foe_slayer_is_once_per_turn_across_the_three_moments(client):
    cid, wid = await _slayer(client)
    await _attack(client, cid, wid, options=[SLAYER_HIT])
    assert not {SLAYER_HIT, SLAYER_HIT_LATE, SLAYER_DMG} & set(await _roll_keys(client, cid, "attack"))
    r = await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 10, "confirm_extra_attack": True, "options": [SLAYER_HIT]})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "option_unavailable"
    await _new_turn(client, cid)
    assert (await _attack(client, cid, wid, options=[SLAYER_HIT]))["to_hit_bonus"]


async def test_foe_slayer_is_not_offered_with_a_non_positive_wisdom_modifier(client):
    cid = await _ranger(client, 20, wisdom=8)
    assert SLAYER_HIT not in await _roll_keys(client, cid, "attack")
