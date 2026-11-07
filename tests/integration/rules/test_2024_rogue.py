"""Ladro 2024 (Task 39, parte A): tabelle, competenze, Maestria, Attacco Furtivo, Gergo Ladresco, Maestria nelle Armi, Azione
Scaltra, Mira Costante, Colpo Astuto (e Migliorato, Colpi Subdoli), Schivata Prodigiosa, Elusione, Dote Affidabile, Mente
Sfuggente, Inafferrabile, Dono Epico, Colpo di Fortuna e multiclasse. Valori da ``docs/superpowers/rules/2024/classes/rogue.md``."""
from __future__ import annotations

import pytest

from core.rules.catalog import features_for
from core.rules.proficiencies import class_proficiencies
from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _roll_keys, _skills, _use
from tests.integration.rules.test_2014_fighter_styles import _item
from tests.integration.rules.test_2014_paladin import _new_turn, _rest, _turn
from tests.integration.rules.test_2014_rogue import (
    _choice, _damage, _full_hp, _hit, _hurt, _rapier, _resolve, _save, _skill_roll,
)

SNEAK, CUNNING, STEADY, UNCANNY = "rogue.sneak_attack", "rogue.cunning_action", "rogue.steady_aim", "rogue.uncanny_dodge"
STEADY_ADV = "rogue.steady_aim_advantage"
POISON, TRIP, WITHDRAW = "rogue.poison", "rogue.trip", "rogue.withdraw"
DAZE, KNOCK_OUT, OBSCURE = "rogue.daze", "rogue.knock_out", "rogue.obscure"
EVASION, EVASION_OK, EVASION_KO = "rogue.evasion", "rogue.evasion_success", "rogue.evasion_failed"
RELIABLE, SLIPPERY, ELUSIVE, LUCK = "rogue.reliable_talent", "rogue.slippery_mind", "rogue.elusive", "rogue.stroke_of_luck"
SKILLS = {"acrobatics", "athletics", "deception", "insight", "intimidation", "investigation", "perception", "persuasion",
          "sleight_of_hand", "stealth"}


async def _rogue24(client, level=5, **scores) -> int:
    body = {"name": "Ladro", "initial_class": {"class_name": "rogue", "level": level, "subclass": None}}
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    for ability, value in scores.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})
        assert r.status_code == 200, r.text
    return cid


async def _strike(client, cid, wid, *options, **body):
    """Un colpo con vantaggio e il danno differito con le opzioni date: restituisce la risposta del danno."""
    hit = await _hit(client, cid, wid, mode="advantage", dice=[10, 12], **body)
    return await _damage(client, cid, hit, *options)


# ---------------------------------------------------------------------------
# Tabelle, righe di sola regola, PF, competenze, livelli
# ---------------------------------------------------------------------------

async def test_hit_points_use_the_d8(client):
    full = await _full(client, await _rogue24(client, 3))
    assert full["classes"][0]["hit_die"] == 8 and full["hit_points"] == 8 + 5 + 5


def test_class_and_multiclass_proficiencies():
    first = class_proficiencies("2024", "rogue", False)
    assert set(first.armor) == {"light"} and set(first.weapons) == {"simple", "martial_finesse_light"}
    assert set(first.tools) == {"thieves_tools"} and set(first.saves) == {"dexterity", "intelligence"}
    assert first.skills_count == 4 and set(first.skills_from) == SKILLS and first.languages == ("thieves_cant",)
    multi = class_proficiencies("2024", "rogue", True)
    assert set(multi.armor) == {"light"} and not multi.weapons and set(multi.tools) == {"thieves_tools"}
    assert not multi.saves and multi.skills_count == 1 and set(multi.skills_from) == SKILLS


@pytest.mark.parametrize("level,asi", [(4, [4]), (10, [4, 8, 10]), (16, [4, 8, 10, 12, 16]), (19, [4, 8, 10, 12, 16])])
async def test_asi_at_4_8_10_12_16_and_the_19th_is_an_epic_boon(client, level, asi):
    pending = (await _full(client, await _rogue24(client, level)))["pending_choices"]
    assert sorted(c["level"] for c in pending if c["kind"] == "asi") == asi
    assert any(c["kind"] == "epic_boon" for c in pending) == (level == 19)


async def test_rules_only_rows_stay_off_the_sheet(client):
    keys = await _keys_of(client, await _rogue24(client, 20))
    assert not keys & {f"rogue.{k}" for k in ("hit_points", "proficiencies", "equipment", "rogue_subclass", "ability_score_improvement",
                                              "epic_boon", "multiclassing", "cunning_strike_options")}
    assert {SNEAK, CUNNING, STEADY, UNCANNY, EVASION, LUCK, "rogue.cunning_strike", "rogue.devious_strikes"} <= keys


@pytest.mark.parametrize("level,key", [(1, "sneak_attack"), (1, "expertise"), (2, "cunning_action"), (3, "steady_aim"),
                                       (5, "cunning_strike"), (5, "uncanny_dodge"), (5, "poison"), (5, "trip"), (5, "withdraw"),
                                       (7, "evasion"), (7, "reliable_talent"), (11, "improved_cunning_strike"),
                                       (14, "devious_strikes"), (14, "daze"), (14, "knock_out"), (14, "obscure"),
                                       (15, "slippery_mind"), (18, "elusive"), (20, "stroke_of_luck")])
def test_a_row_appears_exactly_at_its_level(level, key):
    rows = {f.key: f for f in features_for("2024", "rogue")}
    assert rows[f"rogue.{key}"].level == level


def test_every_base_mapping_title_has_its_row_with_both_languages():
    titles = {f.source_title for f in features_for("2024", "rogue")}
    mapping = open("docs/superpowers/rules/mapping/2024/rogue.md", encoding="utf-8").read().splitlines()[4:]
    wanted = [line.split("|")[1].strip() for line in mapping if line.startswith("|")]
    base = [t for t in wanted if "(Ladro " in t or "(Colpo Astuto, Ladro " in t or t.startswith("Multiclasse")]
    assert len(base) == 28 and [t for t in base if t not in titles] == []
    assert all(f.summary["it"] and f.summary["en"] and len(f.summary["it"]) <= 200 for f in features_for("2024", "rogue"))


async def test_the_2014_only_rows_are_gone_after_the_switch_to_2024(client):
    body = {"name": "Vecchio", "initial_class": {"class_name": "rogue", "level": 14, "subclass": None}}
    cid = (await client.post("/characters", json=body)).json()["id"]
    assert "rogue.blindsense" in await _keys_of(client, cid) and "rogue.devious_strikes" not in await _keys_of(client, cid)
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    keys = await _keys_of(client, cid)
    assert not keys & {"rogue.blindsense"} and {"rogue.devious_strikes", STEADY, "rogue.cunning_strike"} <= keys


# ---------------------------------------------------------------------------
# Maestria, Gergo Ladresco, Maestria nelle Armi
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,count", [(1, 2), (5, 2), (6, 4), (20, 4)])
async def test_expertise_comes_at_levels_1_and_6(client, level, count):
    assert _choice(await _full(client, await _rogue24(client, level)), "expertise")["count"] == count


async def test_expertise_doubles_the_bonus_and_needs_the_proficiency(client):
    cid = await _rogue24(client, 1, dexterity=16)
    await _skills(client, cid, stealth=True, acrobatics=True)
    assert (await _resolve(client, cid, "expertise", "stealth", "insight")).status_code == 422
    assert (await _resolve(client, cid, "expertise", "stealth", "acrobatics")).status_code == 200
    assert (await _skill_roll(client, cid, "stealth"))["bonus"] == 3 + 2 * 2


async def test_thieves_cant_adds_one_language_of_choice(client):
    cid = await _rogue24(client, 1)
    assert "Gergo Ladresco" in (await _full(client, cid))["languages"]
    choice = _choice(await _full(client, cid), "thieves_cant_language")
    assert choice["count"] == 1 and "thieves_cant" not in {o["key"] for o in choice["options"]}
    pick = choice["options"][0]["key"]
    assert (await _resolve(client, cid, "thieves_cant_language", pick)).status_code == 200
    assert len((await _full(client, cid))["languages"]) >= 2


async def test_weapon_mastery_is_a_choice_of_two_kinds_of_weapon(client):
    choice = _choice(await _full(client, await _rogue24(client, 1)), "weapon_mastery")
    assert choice["count"] == 2 and {"dagger", "shortbow"} <= {o["key"] for o in choice["options"]}


# ---------------------------------------------------------------------------
# Attacco Furtivo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,dice", [(1, 1), (2, 1), (3, 2), (5, 3), (11, 6), (19, 10), (20, 10)])
async def test_sneak_attack_dice_follow_the_table(client, level, dice):
    cid = await _rogue24(client, level)
    r = await _strike(client, cid, await _rapier(client, cid), SNEAK)
    assert r.status_code == 200, r.text
    assert len(r.json()["option_result"]["extra_rolls"]) == dice


async def test_sneak_attack_label_says_the_ally_must_not_be_incapacitated(client):
    cid = await _rogue24(client, 5)
    wid = await _rapier(client, cid)
    listed = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack", "item_id": wid})).json()
    label = next(o["label"] for o in listed if o["key"] == SNEAK)
    assert "incapacitato" in label


async def test_sneak_attack_needs_finesse_or_ranged_and_is_once_per_turn(client):
    cid = await _rogue24(client, 5)
    sword = await _item(client, cid, "Spada", damage_dice="1d8", weapon_type="melee", properties=[], equip="main_hand")
    assert SNEAK not in await _roll_keys(client, cid, "attack", item_id=sword)
    wid = await _rapier(client, cid, equip="off_hand")
    assert (await _strike(client, cid, wid, SNEAK)).status_code == 200
    assert SNEAK not in await _roll_keys(client, cid, "attack", item_id=wid)
    await _new_turn(client, cid)
    assert SNEAK in await _roll_keys(client, cid, "attack", item_id=wid)


# ---------------------------------------------------------------------------
# Azione Scaltra e Mira Costante
# ---------------------------------------------------------------------------

async def test_cunning_action_is_a_bonus_action_from_level_2_with_three_actions(client):
    assert CUNNING not in await _keys_of(client, await _rogue24(client, 1))
    cid = await _rogue24(client, 2)
    row = await _ability(client, cid, CUNNING)
    assert row["action_type"] == "bonus_action" and [o["key"] for o in row["use_choices"][0]["options"]] == ["dash", "disengage", "hide"]
    assert (await _use(client, cid, CUNNING, params={"action": "hide"})).status_code == 200
    assert (await _turn(client, cid))["bonus_used"] is True
    again = await _use(client, cid, CUNNING, params={"action": "dash"})
    assert again.status_code == 409 and again.json()["detail"]["code"] == "turn_slot_used"


async def test_steady_aim_starts_at_level_3(client):
    assert STEADY not in await _keys_of(client, await _rogue24(client, 2))
    assert STEADY in await _keys_of(client, await _rogue24(client, 3))


async def test_steady_aim_refuses_a_rogue_who_moved_and_costs_nothing(client):
    cid = await _rogue24(client, 3)
    r = await _use(client, cid, STEADY, params={"moved": True})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "already_moved"
    assert (await _turn(client, cid))["bonus_used"] is False


async def test_steady_aim_gives_advantage_to_the_next_attack_and_zeroes_the_speed_until_the_turn_ends(client):
    cid = await _rogue24(client, 3)
    wid = await _rapier(client, cid)
    base = (await _full(client, cid))["computed"]["speed"]
    assert base > 0
    assert STEADY_ADV not in await _roll_keys(client, cid, "attack", item_id=wid)
    r = await _use(client, cid, STEADY, params={"moved": False})
    assert r.status_code == 200, r.text
    assert (await _turn(client, cid))["bonus_used"] is True and (await _full(client, cid))["computed"]["speed"] == 0
    assert STEADY_ADV in await _roll_keys(client, cid, "attack", item_id=wid)
    hit = await _hit(client, cid, wid, options=[STEADY_ADV])
    assert hit["attack_id"]
    assert STEADY_ADV not in await _roll_keys(client, cid, "attack", item_id=wid)  # solo il prossimo tiro
    assert (await _full(client, cid))["computed"]["speed"] == 0  # la velocità resta 0 fino a fine turno
    await _new_turn(client, cid)
    assert (await _full(client, cid))["computed"]["speed"] == base


# ---------------------------------------------------------------------------
# Colpo Astuto
# ---------------------------------------------------------------------------

async def _kit(client, cid) -> None:
    await _item(client, cid, "Kit da Avvelenatore", item_type="tool")


async def _offered(client, cid, wid) -> set[str]:
    listed = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack", "item_id": wid})).json()
    return {o["key"] for o in listed if o["phase"] == "after_hit"}


@pytest.mark.parametrize("level,extra", [(5, set()), (14, {DAZE, KNOCK_OUT, OBSCURE})])
async def test_cunning_strike_offers_its_options_by_level(client, level, extra):
    cid = await _rogue24(client, level)
    await _kit(client, cid)
    wid = await _rapier(client, cid)
    assert await _offered(client, cid, wid) >= {SNEAK, TRIP, WITHDRAW, POISON}
    assert (await _offered(client, cid, wid) & {DAZE, KNOCK_OUT, OBSCURE}) == extra


async def test_an_option_costs_dice_taken_from_the_sneak_attack(client):
    cid = await _rogue24(client, 5)  # 3d6
    wid = await _rapier(client, cid)
    r = await _strike(client, cid, wid, SNEAK, TRIP)
    assert r.status_code == 200, r.text
    assert len(r.json()["option_result"]["extra_rolls"]) == 3 - 1
    await _new_turn(client, cid)
    r = await _strike(client, cid, wid, SNEAK, WITHDRAW)
    assert len(r.json()["option_result"]["extra_rolls"]) == 2


async def test_poison_needs_the_poisoners_kit_in_the_inventory(client):
    cid = await _rogue24(client, 5)
    wid = await _rapier(client, cid)
    assert POISON not in await _offered(client, cid, wid)
    refused = await _strike(client, cid, wid, SNEAK, POISON)
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "option_unavailable"
    await _kit(client, cid)
    assert POISON in await _offered(client, cid, wid)
    assert (await _strike(client, cid, wid, SNEAK, POISON)).status_code == 200


async def test_one_effect_up_to_level_10_and_two_from_level_11(client):
    cid = await _rogue24(client, 10)
    wid = await _rapier(client, cid)
    assert (await _strike(client, cid, wid, SNEAK, TRIP, WITHDRAW)).status_code == 409
    cid = await _rogue24(client, 11)
    wid = await _rapier(client, cid)
    ok = await _strike(client, cid, wid, SNEAK, TRIP, WITHDRAW)
    assert ok.status_code == 200, ok.text
    assert len(ok.json()["option_result"]["extra_rolls"]) == 6 - 2
    listed = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack", "item_id": wid})).json()
    assert {o["group_max"] for o in listed if o["key"] == TRIP} == {2}


async def test_an_option_dearer_than_the_dice_left_is_refused(client):
    cid = await _rogue24(client, 14)  # 7d6: Mettere K.O. costa 6d6, Stordimento 2d6
    wid = await _rapier(client, cid)
    assert (await _strike(client, cid, wid, SNEAK, KNOCK_OUT, DAZE)).status_code == 409
    r = await _strike(client, cid, wid, SNEAK, KNOCK_OUT)
    assert r.status_code == 200, r.text
    assert len(r.json()["option_result"]["extra_rolls"]) == 1
    low = await _rogue24(client, 5)  # 3d6: Mettere K.O. non c'è prima del 14°
    assert (await _strike(client, low, await _rapier(client, low), SNEAK, KNOCK_OUT)).status_code == 409


async def test_an_option_without_the_sneak_attack_is_refused(client):
    cid = await _rogue24(client, 5)
    hit = await _hit(client, cid, await _rapier(client, cid), mode="advantage", dice=[10, 12])
    assert (await _damage(client, cid, hit, TRIP)).status_code == 409


@pytest.mark.parametrize("key,level,condition,save,extra", [
    (POISON, 5, "poisoned", "constitution", {"rounds": 10, "repeat_save": "end"}),
    (TRIP, 5, "prone", "dexterity", {}),
    (DAZE, 14, "custom:dazed", "constitution", {"ends_at": {"anchor": "owner", "edge": "end", "count": 1}}),
    (KNOCK_OUT, 14, "unconscious", "constitution", {"rounds": 10, "repeat_save": "end"}),
    (OBSCURE, 14, "blinded", "dexterity", {"ends_at": {"anchor": "owner", "edge": "end", "count": 1}}),
])
async def test_the_effect_is_a_saving_throw_of_the_target_with_the_rogue_dc(client, key, level, condition, save, extra):
    cid = await _rogue24(client, level, dexterity=16)  # CD 8 + 3 + competenza
    await _kit(client, cid)
    wid = await _rapier(client, cid)
    r = await _strike(client, cid, wid, SNEAK, key)
    assert r.status_code == 200, r.text
    assert r.json()["option_result"]["targets"] == [key]
    pb = 3 if level == 5 else 5
    effect = r.json()["option_result"]["effects"][0]
    assert f"CD {8 + 3 + pb}" in effect["it"] and f"DC {8 + 3 + pb}" in effect["en"]
    preview = (await client.get(f"/characters/{cid}/target-effects/{key}")).json()["result"]
    assert (preview["condition"], preview["save_ability"], preview["save_dc"]) == (condition, save, 8 + 3 + pb)
    assert all(preview[k] == v for k, v in extra.items())


async def test_trip_only_works_on_a_target_large_or_smaller_and_says_so(client):
    cid = await _rogue24(client, 5)
    r = await _strike(client, cid, await _rapier(client, cid), SNEAK, TRIP)
    assert "Grande" in r.json()["option_result"]["effects"][0]["it"] and "Large" in r.json()["option_result"]["effects"][0]["en"]


async def test_withdraw_tells_the_half_speed_move_without_opportunity_attacks(client):
    cid = await _rogue24(client, 5)
    r = await _strike(client, cid, await _rapier(client, cid), SNEAK, WITHDRAW)
    effect = r.json()["option_result"]["effects"][0]
    assert "4,5 m" in effect["it"] and "15 ft" in effect["en"]  # velocità 30 ft: metà = 15 ft


# ---------------------------------------------------------------------------
# Schivata Prodigiosa, Elusione
# ---------------------------------------------------------------------------

async def test_uncanny_dodge_halves_the_damage_and_spends_the_reaction_from_level_5(client):
    assert UNCANNY not in await _roll_keys(client, await _rogue24(client, 4), "damage_taken")
    cid = await _rogue24(client, 5)
    await _full_hp(client, cid)
    assert (await _hurt(client, cid, 21, UNCANNY)).json()["current_hit_points"] == 60 - 10
    assert (await _turn(client, cid))["reaction_used"] is True
    assert UNCANNY not in await _roll_keys(client, cid, "damage_taken")


async def test_evasion_gives_no_damage_on_a_success_and_half_on_a_failure(client):
    cid = await _rogue24(client, 7)
    await _full_hp(client, cid)
    assert EVASION in await _roll_keys(client, cid, "save", ability="dexterity")
    assert EVASION not in await _roll_keys(client, cid, "save", ability="wisdom")
    await _save(client, cid, "dexterity", EVASION)
    assert (await _hurt(client, cid, 20, EVASION_OK)).json()["current_hit_points"] == 60
    await _save(client, cid, "dexterity", EVASION)
    assert (await _hurt(client, cid, 20, EVASION_KO)).json()["current_hit_points"] == 50
    assert EVASION not in await _roll_keys(client, await _rogue24(client, 6), "save", ability="dexterity")


@pytest.mark.parametrize("condition", ["incapacitated", "stunned", "paralyzed", "unconscious"])
async def test_evasion_is_not_offered_while_incapacitated(client, condition):
    cid = await _rogue24(client, 7)
    assert EVASION in await _roll_keys(client, cid, "save", ability="dexterity")
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {condition: True}})
    assert r.status_code == 200, r.text
    assert EVASION not in await _roll_keys(client, cid, "save", ability="dexterity")


# ---------------------------------------------------------------------------
# Dote Affidabile, Mente Sfuggente, Inafferrabile
# ---------------------------------------------------------------------------

async def test_reliable_talent_comes_at_level_7_with_a_proficiency(client):
    cid = await _rogue24(client, 7, dexterity=14)
    await _skills(client, cid, stealth=True, acrobatics="expert")
    body = await _skill_roll(client, cid, "stealth", die=5)
    assert body["die"] == 10 and f"feature:{RELIABLE}" in body["notes"]
    assert (await _skill_roll(client, cid, "acrobatics", die=9))["die"] == 10
    assert (await _skill_roll(client, cid, "insight", die=5))["die"] == 5  # senza competenza
    other = await _rogue24(client, 6, dexterity=14)
    await _skills(client, other, stealth=True)
    assert (await _skill_roll(client, other, "stealth", die=5))["die"] == 5


async def test_slippery_mind_gives_wisdom_and_charisma_saves_from_level_15(client):
    cid = await _rogue24(client, 15, wisdom=14, charisma=12)  # competenza +5
    wis = await _save(client, cid, "wisdom")
    cha = await _save(client, cid, "charisma")
    assert wis["bonus"] == 2 + 5 and cha["bonus"] == 1 + 5
    assert (await _save(client, cid, "strength"))["bonus"] == 0
    low = await _rogue24(client, 14, wisdom=14)
    assert (await _save(client, low, "wisdom"))["bonus"] == 2


async def test_slippery_mind_goes_away_when_the_level_drops(client):
    cid = await _rogue24(client, 15, wisdom=14)
    row = (await _full(client, cid))["classes"][0]["id"]
    assert (await client.patch(f"/characters/{cid}/classes/{row}", json={"level": 14})).status_code == 200
    assert (await _save(client, cid, "wisdom"))["bonus"] == 2


async def test_elusive_is_a_permanent_note_for_the_gm_and_suspended_while_incapacitated(client):
    assert ELUSIVE not in await _keys_of(client, await _rogue24(client, 17))
    cid = await _rogue24(client, 18)
    assert ELUSIVE in await _keys_of(client, cid)
    assert any(s["key"] == "elusive" for s in (await _full(client, cid))["active_states"])


# ---------------------------------------------------------------------------
# Colpo di Fortuna
# ---------------------------------------------------------------------------

async def test_stroke_of_luck_has_one_use_back_after_a_short_rest_and_covers_attacks_checks_and_saves(client):
    assert LUCK not in await _keys_of(client, await _rogue24(client, 19))
    cid = await _rogue24(client, 20)
    row = await _ability(client, cid, LUCK)
    assert (row["max_uses"], row["uses"], row["restoration_type"]) == (1, 1, "short_rest")
    for roll in ("attack", "skill", "save"):
        assert LUCK in await _roll_keys(client, cid, roll, **({"ability": "dexterity"} if roll == "save" else {}))
    await _save(client, cid, "dexterity", die=3)
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [LUCK]})
    assert r.status_code == 200, r.text
    assert r.json()["die"] == 20
    assert (await _ability(client, cid, LUCK))["uses"] == 0
    await _rest(client, cid, "short")
    assert (await _ability(client, cid, LUCK))["uses"] == 1


async def test_stroke_of_luck_on_a_missed_attack_makes_the_d20_a_twenty_and_so_a_critical_hit(client):
    cid = await _rogue24(client, 20)
    wid = await _rapier(client, cid)
    await _hit(client, cid, wid, die=3)
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [LUCK]})
    assert r.status_code == 200, r.text
    assert r.json()["die"] == 20 and r.json()["is_critical"] is True and r.json()["forced_hit"] is True
    assert len(r.json()["attack"]["damage_rolls"]) == 2  # M9: il danno è ritirato col critico (1d8 raddoppiato)


async def test_i10_stroke_of_luck_covers_pure_checks_and_death_saves(client):
    cid = await _rogue24(client, 20)
    for roll, query in (("ability", {"ability": "strength"}), ("death_save", {})):
        assert LUCK in await _roll_keys(client, cid, roll, **query), roll


# ---------------------------------------------------------------------------
# Multiclasse
# ---------------------------------------------------------------------------

async def test_sneak_attack_counts_only_the_rogue_levels_when_multiclassed(client):
    cid = await _rogue24(client, 5)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 5, "hit_die": 10})
    assert r.status_code == 201, r.text
    r = await _strike(client, cid, await _rapier(client, cid), SNEAK)
    assert len(r.json()["option_result"]["extra_rolls"]) == 3
