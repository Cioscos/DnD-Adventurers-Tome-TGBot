"""Ladro 2014 (Task 27): progressione, PF, competenze, Maestria, Attacco Furtivo, Azione Scaltra, Schivata Prodigiosa,
Elusione, Dote Affidabile, Percezione Cieca, Mente Sfuggente, Inafferrabile e Colpo di Fortuna."""
from __future__ import annotations

import pytest

from core.rules.catalog import features_for
from core.rules.proficiencies import class_proficiencies
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user
from tests.integration.rules.test_2014_barbarian_round1 import _combatant_states, _in_encounter
from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _roll_keys, _skills, _use
from tests.integration.rules.test_2014_fighter_styles import _item
from tests.integration.rules.test_2014_paladin import _new_turn, _turn

ARCHETYPES = {"thief": "Furfante", "assassin": "Assassino", "arcane_trickster": "Mistificatore Arcano"}
SNEAK, CUNNING, UNCANNY, EVASION = "rogue.sneak_attack", "rogue.cunning_action", "rogue.uncanny_dodge", "rogue.evasion"
EVASION_OK, EVASION_KO = "rogue.evasion_success", "rogue.evasion_failed"
RELIABLE, BLINDSENSE, SLIPPERY, ELUSIVE = "rogue.reliable_talent", "rogue.blindsense", "rogue.slippery_mind", "rogue.elusive"
LUCK = "rogue.stroke_of_luck"
SKILL_LIST = {"acrobatics", "athletics", "deception", "insight", "intimidation", "investigation", "perception", "performance",
              "persuasion", "sleight_of_hand", "stealth"}


async def _rogue(client, level=5, archetype=None, **scores) -> int:
    body = {"name": "Ladro", "initial_class": {"class_name": "rogue", "level": level, "subclass": ARCHETYPES.get(archetype)}}
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


async def _skill_roll(client, cid, skill, *options, **body):
    r = await client.post(f"/characters/{cid}/skills/{skill}/roll", json={"die": 10, "options": list(options), **body})
    assert r.status_code == 200, r.text
    return r.json()


async def _rapier(client, cid, equip="main_hand", **kw) -> int:
    return await _item(client, cid, "Stocco", damage_dice="1d8", weapon_type="melee", properties=["finesse"], equip=equip, **kw)


async def _hit(client, cid, wid, die=10, **body) -> dict:
    r = await client.post(f"/characters/{cid}/items/{wid}/attack",
                          json={"die": die, "defer_damage": True, "confirm_extra_attack": True, **body})
    assert r.status_code == 200, r.text
    return r.json()


async def _damage(client, cid, hit, *options):
    return await client.post(f"/characters/{cid}/attack/{hit['attack_id']}/damage", json={"options": list(options)})


async def _hurt(client, cid, value, *options):
    return await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": value, "options": list(options)})


async def _full_hp(client, cid, hp=60):
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": hp})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": hp})


async def _save(client, cid, ability, *options, die=10):
    r = await client.post(f"/characters/{cid}/saving_throws/{ability}/roll", json={"die": die, "options": list(options)})
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Progressione, PF, competenze
# ---------------------------------------------------------------------------

async def test_hit_points_use_the_d8_and_follow_constitution(client):
    full = await _full(client, await _rogue(client, 3))
    assert full["classes"][0]["hit_die"] == 8 and full["hit_points"] == 8 + 5 + 5


def test_class_proficiencies_first_class_and_multiclass():
    first = class_proficiencies("2014", "rogue", False)
    assert set(first.armor) == {"light"} and set(first.weapons) == {"simple", "hand_crossbow", "longsword", "rapier", "shortsword"}
    assert set(first.tools) == {"thieves_tools"} and set(first.saves) == {"dexterity", "intelligence"}
    assert first.skills_count == 4 and set(first.skills_from) == SKILL_LIST and first.languages == ("thieves_cant",)
    multi = class_proficiencies("2014", "rogue", True)
    assert set(multi.armor) == {"light"} and not multi.weapons and set(multi.tools) == {"thieves_tools"}
    assert not multi.saves and multi.skills_count == 1


async def test_thieves_cant_is_among_the_languages(client):
    full = await _full(client, await _rogue(client, 1))
    assert "Gergo Ladresco" in full["languages"]


async def test_rules_only_rows_do_not_clutter_the_sheet(client):
    keys = await _keys_of(client, await _rogue(client, 20, "thief"))
    assert not keys & {f"rogue.{k}" for k in (
        "hit_points", "proficiencies", "equipment", "thieves_cant", "roguish_archetype", "ability_score_improvement", "multiclassing")}


@pytest.mark.parametrize("level,pending", [(3, 0), (4, 1), (7, 1), (8, 2), (9, 2), (10, 3), (12, 4), (15, 4), (16, 5), (18, 5), (19, 6), (20, 6)])
async def test_asi_choices_are_pending_at_levels_4_8_10_12_16_and_19(client, level, pending):
    full = await _full(client, await _rogue(client, level))
    assert len([c for c in full["pending_choices"] if c.get("kind") == "asi"]) == pending


# ---------------------------------------------------------------------------
# Maestria
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,count", [(1, 2), (5, 2), (6, 4), (20, 4)])
async def test_expertise_comes_at_levels_1_and_6(client, level, count):
    assert _choice(await _full(client, await _rogue(client, level)), "expertise")["count"] == count


async def test_expertise_offers_the_proficient_skills_and_doubles_the_bonus(client):
    cid = await _rogue(client, 1, dexterity=16)
    await _skills(client, cid, stealth=True, acrobatics=True, perception=True)
    choice = _choice(await _full(client, cid), "expertise")
    assert {o["key"] for o in choice["options"]} == {"stealth", "acrobatics", "perception"}
    r = await _resolve(client, cid, "expertise", "stealth", "acrobatics")
    assert r.status_code == 200, r.text
    skills = r.json()["skills"]
    assert skills["stealth"] == "expert" and skills["acrobatics"] == "expert" and skills["perception"] is True
    assert (await _skill_roll(client, cid, "stealth"))["bonus"] == 3 + 2 * 2  # Destrezza +3, competenza +2 doppia


async def test_expertise_refuses_a_skill_without_proficiency(client):
    cid = await _rogue(client, 1)
    await _skills(client, cid, stealth=True, acrobatics=True)
    assert (await _resolve(client, cid, "expertise", "stealth", "insight")).status_code == 422
    assert (await _resolve(client, cid, "expertise", "stealth", "acrobatics")).status_code == 200


async def test_the_second_expertise_excludes_the_skills_already_expert(client):
    cid = await _rogue(client, 1)
    await _skills(client, cid, **{s: True for s in ("stealth", "acrobatics", "perception", "insight", "athletics")})
    await _resolve(client, cid, "expertise", "stealth", "acrobatics")
    row = (await _full(client, cid))["classes"][0]["id"]
    await client.patch(f"/characters/{cid}/classes/{row}", json={"level": 6})
    choice = _choice(await _full(client, cid), "expertise")
    assert choice["count"] == 2 and {o["key"] for o in choice["options"]} == {"perception", "insight", "athletics"}


# ---------------------------------------------------------------------------
# Attacco Furtivo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,dice", [(1, 1), (2, 1), (3, 2), (5, 3), (7, 4), (9, 5), (11, 6), (13, 7), (15, 8), (17, 9), (19, 10), (20, 10)])
async def test_sneak_attack_dice_follow_the_table(client, level, dice):
    cid = await _rogue(client, level)
    wid = await _rapier(client, cid)
    hit = await _hit(client, cid, wid, mode="advantage", dice=[10, 12])
    r = await _damage(client, cid, hit, SNEAK)
    assert r.status_code == 200, r.text
    block = r.json()["option_result"]
    assert len(block["extra_rolls"]) == dice and all(1 <= v <= 6 for v in block["extra_rolls"])
    assert r.json()["damage_total"] == hit["damage_total"] + block["extra_total"]


async def test_sneak_attack_dice_double_on_a_critical_hit(client):
    cid = await _rogue(client, 5)
    wid = await _rapier(client, cid)
    hit = await _hit(client, cid, wid, die=20, mode="advantage", dice=[20, 12])
    assert hit["is_critical"] is True
    block = (await _damage(client, cid, hit, SNEAK)).json()["option_result"]
    assert len(block["extra_rolls"]) == 6


async def test_sneak_attack_needs_a_finesse_or_ranged_weapon(client):
    cid = await _rogue(client, 5)
    sword = await _item(client, cid, "Spada", damage_dice="1d8", weapon_type="melee", properties=[], equip="main_hand")
    assert SNEAK not in await _roll_keys(client, cid, "attack", item_id=sword)
    hit = await _hit(client, cid, sword, mode="advantage", dice=[10, 12])
    refused = await _damage(client, cid, hit, SNEAK)
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "option_unavailable"
    bow = await _item(client, cid, "Arco corto", damage_dice="1d6", weapon_type="ranged", properties=["ammunition"], equip="off_hand")
    assert SNEAK in await _roll_keys(client, cid, "attack", item_id=bow)


async def test_sneak_attack_is_not_offered_to_a_thrown_axe_that_is_neither_finesse_nor_ranged(client):
    cid = await _rogue(client, 5)
    axe = await _item(client, cid, "Ascia", damage_dice="1d6", weapon_type="melee", properties=["light", "thrown"], equip="main_hand")
    assert SNEAK not in await _roll_keys(client, cid, "attack", item_id=axe, attack_mode="thrown")
    dagger = await _item(client, cid, "Pugnale", damage_dice="1d4", weapon_type="melee", properties=["finesse", "thrown"], equip="off_hand")
    assert SNEAK in await _roll_keys(client, cid, "attack", item_id=dagger, attack_mode="thrown")


async def test_sneak_attack_is_not_offered_with_disadvantage_but_is_with_an_ally_next_to_the_target(client):
    cid = await _rogue(client, 5)
    wid = await _rapier(client, cid)
    plain = await _hit(client, cid, wid)  # nessun vantaggio: vale l'alleato accanto al bersaglio, lo dichiara il giocatore
    assert (await _damage(client, cid, plain, SNEAK)).status_code == 200
    await _new_turn(client, cid)
    worse = await _hit(client, cid, wid, mode="disadvantage", dice=[10, 12])
    refused = await _damage(client, cid, worse, SNEAK)
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "option_unavailable"


async def test_sneak_attack_is_once_per_turn_and_comes_back_next_turn(client):
    cid = await _rogue(client, 5)
    wid = await _rapier(client, cid)
    hit = await _hit(client, cid, wid, mode="advantage", dice=[10, 12])
    assert (await _damage(client, cid, hit, SNEAK)).status_code == 200
    assert SNEAK not in await _roll_keys(client, cid, "attack", item_id=wid)
    again = await _hit(client, cid, wid, mode="advantage", dice=[10, 12])
    refused = await _damage(client, cid, again, SNEAK)
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "option_unavailable"
    await _new_turn(client, cid)
    assert SNEAK in await _roll_keys(client, cid, "attack", item_id=wid)


async def test_sneak_attack_is_not_offered_to_an_unarmed_strike(client):
    cid = await _rogue(client, 5)
    assert SNEAK not in await _roll_keys(client, cid, "attack")


async def test_sneak_attack_counts_only_the_rogue_levels_when_multiclassed(client):
    cid = await _rogue(client, 5)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 5, "hit_die": 10})
    assert r.status_code == 201, r.text
    wid = await _rapier(client, cid)
    hit = await _hit(client, cid, wid, mode="advantage", dice=[10, 12])
    assert len((await _damage(client, cid, hit, SNEAK)).json()["option_result"]["extra_rolls"]) == 3


# ---------------------------------------------------------------------------
# Azione Scaltra
# ---------------------------------------------------------------------------

async def test_cunning_action_starts_at_level_2_as_a_bonus_action(client):
    assert CUNNING not in await _keys_of(client, await _rogue(client, 1))
    cid = await _rogue(client, 2)
    assert (await _ability(client, cid, CUNNING))["action_type"] == "bonus_action"


@pytest.mark.parametrize("action", ["dash", "disengage", "hide"])
async def test_cunning_action_spends_the_bonus_action_for_one_of_three_actions(client, action):
    cid = await _rogue(client, 2)
    row = await _ability(client, cid, CUNNING)
    assert [o["key"] for o in row["use_choices"][0]["options"]] == ["dash", "disengage", "hide"]
    r = await _use(client, cid, CUNNING, params={"action": action})
    assert r.status_code == 200, r.text
    assert f"cunning_{action}" in r.json()["notes"] and (await _turn(client, cid))["bonus_used"] is True
    again = await _use(client, cid, CUNNING, params={"action": action})
    assert again.status_code == 409 and again.json()["detail"]["code"] == "turn_slot_used"
    await _new_turn(client, cid)
    assert (await _use(client, cid, CUNNING, params={"action": action})).status_code == 200


async def test_cunning_action_refuses_an_action_outside_the_three_and_costs_nothing(client):
    cid = await _rogue(client, 2)
    r = await _use(client, cid, CUNNING, params={"action": "sleight_of_hand"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_choice"
    assert (await _turn(client, cid))["bonus_used"] is False


# ---------------------------------------------------------------------------
# Schivata Prodigiosa, Elusione
# ---------------------------------------------------------------------------

async def test_uncanny_dodge_halves_the_damage_and_spends_the_reaction(client):
    cid = await _rogue(client, 5)
    await _full_hp(client, cid)
    assert UNCANNY in await _roll_keys(client, cid, "damage_taken")
    assert (await _hurt(client, cid, 21, UNCANNY)).json()["current_hit_points"] == 60 - 10  # per difetto
    assert (await _turn(client, cid))["reaction_used"] is True
    assert UNCANNY not in await _roll_keys(client, cid, "damage_taken")
    refused = await _hurt(client, cid, 20, UNCANNY)
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "option_unavailable"
    await _new_turn(client, cid)
    assert UNCANNY in await _roll_keys(client, cid, "damage_taken")


async def test_uncanny_dodge_needs_level_5(client):
    cid = await _rogue(client, 4)
    assert UNCANNY not in await _roll_keys(client, cid, "damage_taken")


async def test_evasion_takes_no_damage_on_a_success_and_half_on_a_failure(client):
    cid = await _rogue(client, 7)
    await _full_hp(client, cid)
    assert EVASION in await _roll_keys(client, cid, "save", ability="dexterity")
    assert EVASION not in await _roll_keys(client, cid, "save", ability="wisdom")
    body = await _save(client, cid, "dexterity", EVASION)
    assert "Elusione" in body["option_result"]["effects"][0]["it"]
    keys = await _roll_keys(client, cid, "damage_taken")
    assert EVASION_OK in keys and EVASION_KO in keys
    assert (await _hurt(client, cid, 20, EVASION_OK)).json()["current_hit_points"] == 60
    assert EVASION_OK not in await _roll_keys(client, cid, "damage_taken")
    await _save(client, cid, "dexterity", EVASION)
    assert (await _hurt(client, cid, 20, EVASION_KO)).json()["current_hit_points"] == 50


async def test_evasion_damage_options_need_the_confirmed_save_and_level_7(client):
    cid = await _rogue(client, 7)
    await _full_hp(client, cid)
    r = await _hurt(client, cid, 20, EVASION_OK)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "option_unavailable"
    assert EVASION not in await _roll_keys(client, await _rogue(client, 6), "save", ability="dexterity")


# ---------------------------------------------------------------------------
# Dote Affidabile
# ---------------------------------------------------------------------------

async def test_reliable_talent_raises_a_low_d20_on_a_proficient_check(client):
    cid = await _rogue(client, 11, dexterity=14)
    await _skills(client, cid, stealth=True, acrobatics="expert")
    body = await _skill_roll(client, cid, "stealth", die=5)
    assert body["die"] == 10 and f"feature:{RELIABLE}" in body["notes"]
    assert (await _skill_roll(client, cid, "acrobatics", die=9))["die"] == 10
    assert (await _skill_roll(client, cid, "stealth", die=14))["die"] == 14


async def test_reliable_talent_does_not_help_without_proficiency_or_before_level_11(client):
    cid = await _rogue(client, 11, dexterity=14)
    await _skills(client, cid, stealth=True)
    body = await _skill_roll(client, cid, "insight", die=5)
    assert body["die"] == 5 and f"feature:{RELIABLE}" not in body["notes"]
    other = await _rogue(client, 10, dexterity=14)
    await _skills(client, other, stealth=True)
    assert (await _skill_roll(client, other, "stealth", die=5))["die"] == 5


async def test_reliable_talent_does_not_apply_to_a_pure_ability_check(client):
    cid = await _rogue(client, 11)
    r = await client.post(f"/characters/{cid}/ability_checks/dexterity/roll", json={"die": 4})
    assert r.status_code == 200, r.text
    assert r.json()["die"] == 4


# ---------------------------------------------------------------------------
# Percezione Cieca, Mente Sfuggente
# ---------------------------------------------------------------------------

async def test_blindsense_adds_the_sense_from_level_14_and_needs_hearing(client):
    assert not (await _full(client, await _rogue(client, 13)))["computed"]["senses"]
    cid = await _rogue(client, 14)
    assert (await _full(client, cid))["computed"]["senses"] == [{"type": "blindsight", "range_ft": 10}]
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"deafened": True}})
    assert not (await _full(client, cid))["computed"]["senses"]


async def test_blindsense_does_not_replace_a_longer_sense_written_by_hand(client):
    cid = await _rogue(client, 14)
    r = await client.patch(f"/characters/{cid}", json={"settings": {"senses": [{"type": "blindsight", "range_ft": 30}]}})
    assert r.status_code == 200, r.text
    full = await _full(client, cid)
    assert full["settings"]["senses"] == [{"type": "blindsight", "range_ft": 30}]
    assert full["computed"]["senses"] == [{"type": "blindsight", "range_ft": 10}]


async def test_slippery_mind_gives_wisdom_saves_proficiency_from_level_15_and_not_twice(client):
    cid = await _rogue(client, 15, wisdom=14)  # competenza +5, Saggezza +2
    assert (await _save(client, cid, "wisdom"))["bonus"] == 2 + 5
    await client.patch(f"/characters/{cid}/saving_throws", json={"saving_throws": {"wisdom": True}})
    assert (await _save(client, cid, "wisdom"))["bonus"] == 2 + 5
    assert (await _save(client, cid, "charisma"))["bonus"] == 0


async def test_slippery_mind_goes_away_when_the_level_drops(client):
    cid = await _rogue(client, 15, wisdom=14)
    row = (await _full(client, cid))["classes"][0]["id"]
    await client.patch(f"/characters/{cid}/classes/{row}", json={"level": 14})
    assert (await _save(client, cid, "wisdom"))["bonus"] == 2


# ---------------------------------------------------------------------------
# Inafferrabile
# ---------------------------------------------------------------------------

async def test_elusive_is_a_permanent_note_for_the_gm_and_the_group_and_stops_when_incapacitated(client, test_session_factory, monkeypatch):
    sid, cid = await _in_encounter(client, test_session_factory, monkeypatch)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "rogue", "level": 18, "hit_die": 8})
    assert r.status_code == 201, r.text
    for viewer in (GM_ID, PLAYER_ID):
        states = {s["key"]: s for s in await _combatant_states(client, sid, viewer)}
        assert [o["key"] for o in states["elusive"]["others"]] == [ELUSIVE], viewer
        assert states["elusive"]["others"][0]["text"] and states["elusive"]["others"][0]["name"]
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"incapacitated": True}})
    assert "elusive" not in {s["key"] for s in await _combatant_states(client, sid, GM_ID)}
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"incapacitated": False}})
    assert "elusive" in {s["key"] for s in await _combatant_states(client, sid, GM_ID)}


async def test_elusive_needs_level_18(client):
    assert ELUSIVE not in await _keys_of(client, await _rogue(client, 17))
    assert ELUSIVE in await _keys_of(client, await _rogue(client, 18))


# ---------------------------------------------------------------------------
# Colpo di Fortuna
# ---------------------------------------------------------------------------

async def test_stroke_of_luck_is_one_use_per_short_or_long_rest_from_level_20(client):
    assert LUCK not in await _keys_of(client, await _rogue(client, 19))
    row = await _ability(client, await _rogue(client, 20), LUCK)
    assert (row["max_uses"], row["uses"], row["restoration_type"]) == (1, 1, "short_rest")


async def test_stroke_of_luck_turns_a_missed_attack_into_a_hit_and_spends_the_use(client):
    cid = await _rogue(client, 20)
    wid = await _rapier(client, cid)
    hit = await _hit(client, cid, wid, die=3)
    assert LUCK in await _roll_keys(client, cid, "attack", item_id=wid)
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [LUCK]})
    assert r.status_code == 200, r.text
    assert r.json()["forced_hit"] is True and r.json()["is_fumble"] is False
    assert (await _ability(client, cid, LUCK))["uses"] == 0
    assert (await _damage(client, cid, hit)).status_code == 200  # il danno resta da tirare
    assert LUCK not in await _roll_keys(client, cid, "attack", item_id=wid)


async def test_stroke_of_luck_turns_a_failed_skill_check_into_a_twenty(client):
    cid = await _rogue(client, 20, dexterity=14)
    await _skills(client, cid, stealth=True)
    await _skill_roll(client, cid, "stealth", die=3)
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [LUCK]})
    assert r.status_code == 200, r.text
    assert r.json()["die"] == 20 and r.json()["total"] == 20 + 2 + 6
    assert (await _ability(client, cid, LUCK))["uses"] == 0
    again = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [LUCK]})
    assert again.status_code == 409


async def test_stroke_of_luck_also_saves_a_pure_ability_check_and_is_recovered_by_a_short_rest(client):
    cid = await _rogue(client, 20)
    r = await client.post(f"/characters/{cid}/ability_checks/strength/roll", json={"die": 2})
    assert r.status_code == 200, r.text
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [LUCK]})
    assert r.status_code == 200, r.text
    assert r.json()["die"] == 20
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})
    assert (await _ability(client, cid, LUCK))["uses"] == 1


def test_the_catalog_has_no_duplicate_keys_and_every_row_is_level_1_to_20():
    rows = features_for("2014", "rogue")
    assert len({f.key for f in rows}) == len(rows) and all(1 <= f.level <= 20 for f in rows)
