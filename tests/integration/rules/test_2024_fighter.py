"""Guerriero 2024 (Task 35, parte A): tabelle, Stile di Combattimento, Recuperare Energie, Maestria nelle Armi, Azione
Impetuosa, Mente Tattica, Attacco Extra, Spostamento Tattico, Indomito, Maestro Tattico, Attacchi Studiati, Dono Epico e
multiclasse. Valori dalla scheda ``docs/superpowers/rules/2024/classes/fighter.md``."""
from __future__ import annotations

import pytest

from core.rules.catalog import features_for
from core.rules.proficiencies import class_proficiencies
from tests.integration.rules.test_2014_barbarian import _armor, _attack, _keys, _weapon
from tests.integration.rules.test_2014_bard import _ability, _choice, _full, _keys_of, _resolve, _roll_keys, _use
from tests.integration.rules.test_2014_fighter import _hurt, _rest, _save, _turn
from tests.integration.rules.test_2014_fighter_styles import _item

SW, AS, IND = "fighter.second_wind", "fighter.action_surge", "fighter.indomitable"
MIND, STUDIED = "fighter.tactical_mind", "fighter.studied_attacks"
STYLES = {"archery", "blind_fighting", "defense", "dueling", "great_weapon", "interception", "protection", "thrown_weapon",
          "two_weapon", "unarmed"}


async def _fighter24(client, level=5, **scores) -> int:
    body = {"name": "Guerriero", "initial_class": {"class_name": "fighter", "level": level, "subclass": None}}
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    for ability, value in scores.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})
        assert r.status_code == 200, r.text
    return cid


async def _styled(client, style, level=3, **scores) -> int:
    cid = await _fighter24(client, level, **scores)
    r = await _resolve(client, cid, "fighting_style", [style])
    assert r.status_code == 200, r.text
    return cid


async def _masters(client, cid, *weapons) -> None:
    r = await _resolve(client, cid, "weapon_mastery", list(weapons))
    assert r.status_code == 200, r.text


async def _new_turn(client, cid) -> None:
    assert (await client.post(f"/characters/{cid}/turn/new")).status_code == 200


# ---------------------------------------------------------------------------
# Tabelle e catalogo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,uses", [(1, 2), (3, 2), (4, 3), (9, 3), (10, 4), (20, 4)])
async def test_second_wind_uses_follow_the_2024_table(client, level, uses):
    assert (await _ability(client, await _fighter24(client, level), SW))["max_uses"] == uses


@pytest.mark.parametrize("level,uses", [(2, 1), (16, 1), (17, 2), (20, 2)])
async def test_action_surge_uses_follow_the_level(client, level, uses):
    assert (await _ability(client, await _fighter24(client, level), AS))["max_uses"] == uses


@pytest.mark.parametrize("level,uses", [(9, 1), (12, 1), (13, 2), (16, 2), (17, 3), (20, 3)])
async def test_indomitable_uses_follow_the_level(client, level, uses):
    assert (await _ability(client, await _fighter24(client, level), IND))["max_uses"] == uses


@pytest.mark.parametrize("level,picks", [(1, 3), (3, 3), (4, 4), (9, 4), (10, 5), (15, 5), (16, 6), (20, 6)])
async def test_weapon_mastery_picks_follow_the_table(client, level, picks):
    choice = _choice(await _full(client, await _fighter24(client, level)), "weapon_mastery")
    keys = {o["key"] for o in choice["options"]}
    assert choice["count"] == picks and {"greatsword", "longbow", "dagger"} <= keys  # armi semplici e da guerra, anche a distanza


@pytest.mark.parametrize("level,present", [
    (1, {"second_wind", "weapon_mastery"}), (2, {"action_surge", "tactical_mind"}), (5, {"extra_attack", "tactical_shift"}),
    (9, {"indomitable", "tactical_master"}), (11, {"two_extra_attacks"}), (13, {"studied_attacks"}),
    (20, {"three_extra_attacks"}),
])
async def test_features_appear_at_their_level(client, level, present):
    keys = await _keys_of(client, await _fighter24(client, level))
    assert {f"fighter.{k}" for k in present} <= keys
    if level > 1:
        low = await _keys_of(client, await _fighter24(client, level - 1))
        assert not {f"fighter.{k}" for k in present} & low


async def test_rules_only_rows_stay_off_the_sheet_but_in_the_catalog(client):
    keys = await _keys_of(client, await _fighter24(client, 20))
    assert not keys & {f"fighter.{k}" for k in ("core_traits", "subclass", "ability_score_improvement", "epic_boon", "multiclassing",
                                                 "fighting_style")}
    titles = {s.source_title for s in features_for("2024", "fighter")}
    assert {"Tratti Fondamentali / Core Fighter Traits (Guerriero 1, pag. 91)",
            "Recuperare Energie / Second Wind (Guerriero 1, pag. 91)",
            "Tre Attacchi Extra / Three Extra Attacks (Guerriero 20, pag. 92)"} <= titles


@pytest.mark.parametrize("level,asi", [(3, []), (4, [4]), (6, [4, 6]), (14, [4, 6, 8, 12, 14]), (19, [4, 6, 8, 12, 14, 16])])
async def test_asi_at_4_6_8_12_14_16_and_the_19th_is_an_epic_boon_not_an_asi(client, level, asi):
    pending = (await _full(client, await _fighter24(client, level)))["pending_choices"]
    assert sorted(c["level"] for c in pending if c["kind"] == "asi") == asi
    assert [c["level"] for c in pending if c["kind"] == "epic_boon"] == ([19] if level >= 19 else [])


async def test_hit_points_use_the_d10_and_follow_constitution(client):
    cid = await _fighter24(client, 3)
    full = await _full(client, cid)
    assert full["classes"][0]["hit_die"] == 10 and full["hit_points"] == 10 + 6 + 6
    await client.patch(f"/characters/{cid}/ability_scores/constitution", json={"value": 14})
    assert (await _full(client, cid))["hit_points"] == 10 + 6 + 6 + 2 * 3


def test_core_traits_and_multiclass_proficiencies_come_from_the_2024_class_table():
    first = class_proficiencies("2024", "fighter", False)
    assert set(first.armor) == {"light", "medium", "heavy", "shields"} and set(first.weapons) == {"simple", "martial"}
    assert set(first.saves) == {"strength", "constitution"} and first.skills_count == 2
    assert set(first.skills_from) == {"acrobatics", "animal_handling", "athletics", "history", "insight", "intimidation",
                                      "persuasion", "perception", "survival"}
    multi = class_proficiencies("2024", "fighter", True)
    assert set(multi.armor) == {"light", "medium", "shields"} and multi.weapons == ("martial",)
    assert not multi.saves and multi.skills_count == 0


@pytest.mark.parametrize("level,attacks", [(1, 1), (4, 1), (5, 2), (10, 2), (11, 3), (19, 3), (20, 4)])
async def test_extra_attacks_follow_the_level(client, level, attacks):
    assert (await client.get(f"/characters/{await _fighter24(client, level)}/turn-state")).json()["attacks_allowed"] == attacks


async def test_extra_attack_does_not_stack_with_another_class_and_the_fighter_exceeds_two(client):
    cid = await _fighter24(client, 11)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "barbarian", "level": 5, "hit_die": 12})
    assert r.status_code == 201, r.text
    assert (await client.get(f"/characters/{cid}/turn-state")).json()["attacks_allowed"] == 3


async def test_fighter_added_as_second_class_has_no_fighter_level_1_rows_beyond_its_level(client):
    cid = await _fighter24(client, 5)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "wizard", "level": 3, "hit_die": 6})
    assert r.status_code == 201
    assert (await client.get(f"/characters/{cid}/turn-state")).json()["attacks_allowed"] == 2
    assert [a["feature_key"] for a in (await _full(client, cid))["abilities"]].count(SW) == 1


# ---------------------------------------------------------------------------
# Stile di Combattimento
# ---------------------------------------------------------------------------

async def test_the_style_is_one_of_ten_feats_chosen_at_level_1_and_can_be_replaced(client):
    cid = await _fighter24(client, 1)
    choice = _choice(await _full(client, cid), "fighting_style")
    assert choice["count"] == 1 and {o["key"] for o in choice["options"]} == STYLES
    assert all(o["name"]["it"] and o["name"]["en"] and o["summary"]["it"] for o in choice["options"])
    assert (await _resolve(client, cid, "fighting_style", ["defense"])).status_code == 200
    assert "fighter.style_defense" in await _keys_of(client, cid)
    assert (await _resolve(client, await _fighter24(client, 1), "fighting_style", ["archery", "defense"])).status_code == 422


async def test_a_style_taken_by_another_class_is_not_offered_again(client):
    cid = await _styled(client, "defense", 5)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "paladin", "level": 2, "hit_die": 10})
    assert r.status_code == 201, r.text
    paladin_choices = [c for c in (await _full(client, cid))["pending_choices"] if c.get("group") == "fighting_style"]
    assert all("defense" not in {o["key"] for o in c["options"]} for c in paladin_choices)


async def test_defense_adds_one_to_ac_only_while_wearing_armor(client):
    cid = await _fighter24(client, 3)
    await _armor(client, cid, "light", 11)
    plain = (await _full(client, cid))["ac"]
    await _resolve(client, cid, "fighting_style", ["defense"])
    assert (await _full(client, cid))["ac"] == plain + 1


async def test_archery_adds_two_to_ranged_attacks_only(client):
    cid = await _styled(client, "archery", dexterity=14)
    bow = await _item(client, cid, "Arco lungo", damage_dice="1d8", weapon_type="ranged", properties=["ammunition"])
    sword = await _item(client, cid, "Spada", damage_dice="1d8", weapon_type="melee", properties=[])
    assert "feature:fighter.style_archery" in (await _attack(client, cid, bow))["notes"]
    assert "feature:fighter.style_archery" not in (await _attack(client, cid, sword))["notes"]


async def test_great_weapon_fighting_counts_a_one_or_a_two_as_a_three_and_shows_it(client, monkeypatch):
    cid = await _styled(client, "great_weapon", strength=10)
    wid = await _item(client, cid, "Spadone", damage_dice="2d6", weapon_type="melee", properties=["two-handed"])
    dice = iter((1, 2))
    monkeypatch.setattr("api.routers.items.random.randint", lambda a, b: next(dice))
    body = await _attack(client, cid, wid)
    assert body["damage_rolls"] == [3, 3] and body["rerolled"] == [[1, 3], [2, 3]] and body["damage_total"] == 6
    sword = await _item(client, cid, "Spada", damage_dice="1d8", weapon_type="melee", properties=[])
    monkeypatch.setattr("api.routers.items.random.randint", lambda a, b: 1)
    assert (await _attack(client, cid, sword))["damage_rolls"] == [1]  # una mano: niente


async def test_thrown_weapon_fighting_adds_two_to_thrown_damage_only(client):
    cid = await _fighter24(client, 3, strength=10)
    axe = await _item(client, cid, "Accetta", damage_dice="1d6", weapon_type="melee", properties=["thrown"])
    thrown = (await _attack(client, cid, axe, attack_mode="thrown"))["damage_bonus"]
    melee = (await _attack(client, cid, axe))["damage_bonus"]
    await _resolve(client, cid, "fighting_style", ["thrown_weapon"])
    assert (await _attack(client, cid, axe, attack_mode="thrown"))["damage_bonus"] == thrown + 2
    assert (await _attack(client, cid, axe))["damage_bonus"] == melee


async def test_blind_fighting_gives_blindsight_to_ten_feet(client):
    cid = await _styled(client, "blind_fighting")
    assert (await _full(client, cid))["computed"]["senses"] == [{"type": "blindsight", "range_ft": 10}]


async def test_interception_is_a_reaction_that_tells_the_damage_reduction(client, monkeypatch):
    cid = await _styled(client, "interception")
    monkeypatch.setattr("api.services.rules_states.random.randint", lambda a, b: 7)
    r = await _use(client, cid, "fighter.style_interception")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "feature_unavailable"  # senza scudo né arma
    await _item(client, cid, "Spada", damage_dice="1d8", weapon_type="melee", properties=[], equip="main_hand")
    r = await _use(client, cid, "fighter.style_interception")
    assert r.status_code == 200 and r.json()["given"] == 7 + 2 and (await _turn(client, cid))["reaction_used"] is True


# ---------------------------------------------------------------------------
# Recuperare Energie e Spostamento Tattico
# ---------------------------------------------------------------------------

async def test_second_wind_heals_a_d10_plus_the_fighter_level_and_spends_the_bonus_action(client, test_session_factory, monkeypatch):
    monkeypatch.setattr("api.services.rules_states.random.randint", lambda a, b: 7)
    cid = await _fighter24(client, 4)
    await _hurt(test_session_factory, cid, 5)
    body = (await _use(client, cid, SW)).json()
    assert body["rolls"] == [7] and body["healed"] == 7 + 4
    assert (await _full(client, cid))["current_hit_points"] == 5 + 11
    assert (await _turn(client, cid))["bonus_used"] is True
    assert (await _ability(client, cid, SW))["uses"] == 2


async def test_a_short_rest_gives_back_one_second_wind_and_a_long_rest_all_of_them(client):
    cid = await _fighter24(client, 10)  # 4 usi
    for _ in range(3):
        assert (await _use(client, cid, SW)).status_code == 200
        await _new_turn(client, cid)
    assert (await _ability(client, cid, SW))["uses"] == 1
    await _rest(client, cid, "short")
    assert (await _ability(client, cid, SW))["uses"] == 2
    await _rest(client, cid, "long")
    assert (await _ability(client, cid, SW))["uses"] == 4


async def test_tactical_shift_tells_the_free_movement_after_second_wind_from_level_5(client):
    five, four = await _fighter24(client, 5), await _fighter24(client, 4)
    shift = (await _use(client, five, SW)).json()["message"]
    assert "4,5 m" in shift["it"] and "15 ft" in shift["en"] and "opportunità" in shift["it"]  # metà di 9 m / 30 ft
    assert (await _use(client, four, SW)).json().get("message") is None


# ---------------------------------------------------------------------------
# Azione Impetuosa
# ---------------------------------------------------------------------------

async def test_action_surge_gives_one_more_action_but_not_to_cast_a_spell(client):
    cid = await _fighter24(client, 5)
    wid = await _item(client, cid, "Spada", damage_dice="1d8", weapon_type="melee", properties=[])
    spell = (await client.post(f"/characters/{cid}/spells", json={"name": "Dardo", "level": 0, "casting_time": "1 azione"})).json()["id"]
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "action"})
    assert (await _use(client, cid, AS)).status_code == 200
    assert (await _turn(client, cid))["extra_actions"] == 1
    r = await client.post(f"/characters/{cid}/spells/{spell}/use", json={})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "surge_no_magic"
    assert (await _turn(client, cid))["extra_actions"] == 1  # il rifiuto non consuma l'azione
    assert (await _attack(client, cid, wid))["weapon_name"]


async def test_action_surge_twice_in_one_turn_is_refused_at_17_and_a_short_rest_gives_it_back(client):
    cid = await _fighter24(client, 17)
    assert (await _use(client, cid, AS)).status_code == 200
    assert (await _use(client, cid, AS)).json()["detail"]["code"] == "once_per_turn"
    await _new_turn(client, cid)
    assert (await _use(client, cid, AS)).status_code == 200
    await _rest(client, cid, "short")
    assert (await _ability(client, cid, AS))["uses"] == 2


# ---------------------------------------------------------------------------
# Mente Tattica
# ---------------------------------------------------------------------------

async def test_tactical_mind_adds_a_d10_after_a_failed_check_spends_a_second_wind_and_heals_nothing(client, test_session_factory):
    cid = await _fighter24(client, 2)
    await _hurt(test_session_factory, cid, 3)
    for roll, query in (("skill", {"skill": "athletics"}), ("ability", {"ability": "strength"})):
        assert MIND in await _roll_keys(client, cid, roll, **query)
    assert MIND not in await _roll_keys(client, cid, "save", ability="wisdom")
    assert MIND not in await _roll_keys(client, cid, "attack")
    first = (await client.post(f"/characters/{cid}/skills/athletics/roll", json={"die": 5})).json()
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [MIND]})
    assert r.status_code == 200, r.text
    extra = r.json()["option_result"]
    assert len(extra["extra_rolls"]) == 1 and 1 <= extra["extra_total"] <= 10  # 1d10
    assert r.json()["total"] == first["total"] + extra["extra_total"]
    assert (await _ability(client, cid, SW))["uses"] == 1 and (await _full(client, cid))["current_hit_points"] == 3
    assert (await _turn(client, cid))["bonus_used"] is False


async def test_tactical_mind_gives_the_use_back_when_the_check_still_fails(client):
    cid = await _fighter24(client, 2)
    await client.post(f"/characters/{cid}/skills/athletics/roll", json={"die": 5})
    await client.post(f"/characters/{cid}/last-roll/options", json={"options": [MIND]})
    assert (await client.post(f"/characters/{cid}/last-roll/refund")).status_code == 200
    assert (await _ability(client, cid, SW))["uses"] == 2
    await client.post(f"/characters/{cid}/skills/athletics/roll", json={"die": 5})
    await client.post(f"/characters/{cid}/last-roll/options", json={"options": [MIND]})
    await client.post(f"/characters/{cid}/last-roll/refund", json={"succeeded": True})
    assert (await _ability(client, cid, SW))["uses"] == 1


async def test_tactical_mind_is_not_offered_without_second_wind_uses(client):
    cid = await _fighter24(client, 2)
    for _ in range(2):
        await _use(client, cid, SW)
        await _new_turn(client, cid)
    assert MIND not in await _roll_keys(client, cid, "skill", skill="athletics")


# ---------------------------------------------------------------------------
# Maestria nelle Armi e Maestro Tattico
# ---------------------------------------------------------------------------

async def test_a_chosen_weapon_activates_its_mastery_and_an_unchosen_one_does_not(client):
    cid = await _fighter24(client, 1, strength=16)
    await _masters(client, cid, "greatsword", "longsword", "dagger")
    great = await _weapon(client, cid, "Spadone", damage_dice="2d6", properties=["heavy", "two_handed"])
    assert "mastery_graze" in await _keys(client, cid, "attack", item_id=great)
    bow = await _weapon(client, cid, "Arco lungo", equip=None, damage_dice="1d8", weapon_type="ranged")
    assert not [k for k in await _keys(client, cid, "attack", item_id=bow) if k.startswith("mastery_")]


async def test_tactical_master_swaps_the_mastery_for_push_sap_or_slow_from_level_9(client):
    low, top = await _fighter24(client, 8, strength=16), await _fighter24(client, 9, strength=16)
    for cid in (low, top):
        await _masters(client, cid, "greatsword", "longsword", "dagger", "handaxe")
    keys = {}
    for cid in (low, top):
        wid = await _weapon(client, cid, "Spada lunga", damage_dice="1d8", properties=["versatile"])
        keys[cid] = await _keys(client, cid, "attack", item_id=wid)
    assert not [k for k in keys[low] if k.startswith("fighter.tactical_master_")]
    # la spada lunga ha già Sap: Maestro Tattico offre le altre due
    assert {"fighter.tactical_master_push", "fighter.tactical_master_slow"} <= set(keys[top])
    assert "fighter.tactical_master_sap" not in keys[top] and "mastery_sap" in keys[top]


async def test_tactical_master_needs_a_weapon_with_mastery_and_replaces_the_property(client):
    cid = await _fighter24(client, 9, strength=16)
    await _masters(client, cid, "greatsword", "longsword", "dagger", "handaxe")
    mace = await _weapon(client, cid, "Mazza", equip=None, damage_dice="1d6")
    assert not [k for k in await _keys(client, cid, "attack", item_id=mace) if k.startswith("fighter.tactical_master_")]
    sword = await _weapon(client, cid, "Spada lunga", equip=None, damage_dice="1d8", properties=["versatile"])
    first = (await _attack(client, cid, sword, defer_damage=True))
    r = await client.post(f"/characters/{cid}/attack/{first['attack_id']}/damage",
                          json={"options": ["mastery_sap", "fighter.tactical_master_push"]})
    assert r.status_code == 409  # una sola proprietà per attacco
    r = await client.post(f"/characters/{cid}/attack/{first['attack_id']}/damage", json={"options": ["fighter.tactical_master_push"]})
    assert r.status_code == 200, r.text
    assert r.json()["option_result"]["effects"][0]["en"]


# ---------------------------------------------------------------------------
# Indomito
# ---------------------------------------------------------------------------

async def test_indomitable_rerolls_a_failed_save_adding_the_fighter_level(client):
    cid = await _fighter24(client, 9)
    first = await _save(client, cid, die=2)
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [IND], "dice": [4]})
    assert r.status_code == 200, r.text
    assert r.json()["die"] == 4 and r.json()["total"] == first["total"] + 2 + 9  # +2 dal d20, +9 livello da guerriero
    assert (await _ability(client, cid, IND))["uses"] == 0
    await _rest(client, cid, "short")
    assert (await _ability(client, cid, IND))["uses"] == 0
    await _rest(client, cid, "long")
    assert (await _ability(client, cid, IND))["uses"] == 1


async def test_indomitable_is_offered_after_a_saving_throw_only(client):
    cid = await _fighter24(client, 9)
    assert IND in await _roll_keys(client, cid, "save", ability="wisdom")
    assert IND not in await _roll_keys(client, cid, "skill", skill="athletics")
    assert IND not in await _roll_keys(client, await _fighter24(client, 8), "save", ability="wisdom")


# ---------------------------------------------------------------------------
# Attacchi Studiati
# ---------------------------------------------------------------------------

async def _studied_attack(client, cid, wid, die=5) -> dict:
    first = (await _attack(client, cid, wid, die=die, defer_damage=True))
    assert first["attack_id"]
    return first


async def test_a_declared_miss_arms_advantage_on_the_next_attack_until_the_end_of_the_next_turn(client):
    cid = await _fighter24(client, 13, strength=16)
    wid = await _weapon(client, cid, "Mazza", damage_dice="1d6")
    await _studied_attack(client, cid, wid)
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": ["fighter.studied_attacks_miss"]})
    assert r.status_code == 200, r.text
    assert r.json()["attack"]["grazed"] is True and r.json()["attack"]["damage_total"] == 0  # mancato, nessun danno
    assert "fighter.studied_attacks_advantage" in await _keys(client, cid, "attack", item_id=wid)
    await _new_turn(client, cid)  # vale ancora nel turno seguente
    assert (await _attack(client, cid, wid, options=["fighter.studied_attacks_advantage"]))["mode"] == "advantage"
    assert "fighter.studied_attacks_advantage" not in await _keys(client, cid, "attack", item_id=wid)  # consumato


async def test_studied_attacks_end_with_the_turn_after_the_next_and_are_not_offered_on_a_critical_or_before_13(client):
    cid = await _fighter24(client, 13, strength=16)
    wid = await _weapon(client, cid, "Mazza", damage_dice="1d6")
    await _studied_attack(client, cid, wid)
    await client.post(f"/characters/{cid}/last-roll/options", json={"options": ["fighter.studied_attacks_miss"]})
    await _new_turn(client, cid)
    await _new_turn(client, cid)
    assert "fighter.studied_attacks_advantage" not in await _keys(client, cid, "attack", item_id=wid)
    await _studied_attack(client, cid, wid, die=20)  # un 20 naturale colpisce sempre
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": ["fighter.studied_attacks_miss"]})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "option_unavailable"
    low = await _fighter24(client, 12, strength=16)
    wid = await _weapon(client, low, "Mazza", damage_dice="1d6")
    assert not [k for k in await _keys(client, low, "attack", item_id=wid) if k.startswith("fighter.studied")]


# ---------------------------------------------------------------------------
# Sottoclasse, edizione e importazione
# ---------------------------------------------------------------------------

async def test_the_2024_fighter_keeps_its_spent_uses_when_the_edition_changes(client):
    cid = await _fighter24(client, 5)
    await _use(client, cid, SW)
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2014"})).status_code == 200
    assert (await _ability(client, cid, SW))["max_uses"] == 1
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    row = await _ability(client, cid, SW)
    assert row["max_uses"] == 3 and row["uses"] == 2  # un uso speso resta speso: la chiave è la stessa (R17)


async def test_no_row_of_the_2024_fighter_depends_on_a_subclass_yet(client):
    assert not [s for s in features_for("2024", "fighter") if s.subclass is not None]  # le sottoclassi sono la parte B


async def test_beyond_options_find_the_fighter_choices(test_session_factory):
    from api.routers.transfer import _apply_class_options
    from api.services.ddb_import import ImportReport
    from core.rules.sample_characters import build_rules_character

    async with test_session_factory() as s:
        spec = {"name": "x", "edition": "2024", "classes": [("Guerriero", 4, None, 10)]}
        char = await build_rules_character(s, spec, 1)
        report = ImportReport()
        names = ("Defense", "Greatsword", "Longsword", "Dagger", "Handaxe")
        _apply_class_options(char, [{"class_index": 0, "name": n} for n in names], report, "it")
        assert char.classes[0].options == {"fighting_style": ["defense"],
                                           "weapon_mastery": ["greatsword", "longsword", "dagger", "handaxe"]}
