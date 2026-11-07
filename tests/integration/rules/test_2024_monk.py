"""Monaco 2024 (Task 36, parte A): Arti Marziali, Difesa Senza Armatura, Concentrazione, Raffica di Colpi, Difesa Paziente,
Passo del Vento, Movimento Senza Armatura, Metabolismo Prodigioso, Deviare Attacchi, Caduta Lenta, Colpo Stordente, Colpi
Potenziati, Elusione, Autoguarigione, Sopravvissuto Disciplinato, Concentrazione Perfetta, Difesa Superiore, Corpo e Mente.
Valori dalla scheda ``docs/superpowers/rules/2024/classes/monk.md``."""
from __future__ import annotations

import pytest

from core.rules.catalog import features_for
from core.rules.proficiencies import class_proficiencies
from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _roll_keys, _use
from tests.integration.rules.test_2014_monk import ARMOR, KI, SHIELD, _equip, _rest, _turn
from tests.integration.rules.test_2014_monk_ki import (
    _bow, _conditions, _damage, _dex_save, _fixed, _full_hp, _heavy_weapon, _hit, _hurt, _ki, _set_ki, _shortsword,
    _states as _state_map, _strike, _wis_save,
)

FLURRY, STRIKE, BONUS = "monk.flurry_of_blows", "monk.flurry_strike", "monk.martial_arts_bonus"
PD, PD_FOCUS = "monk.patient_defense", "monk.patient_defense_focus"
STEP, STEP_FOCUS = "monk.step_of_the_wind", "monk.step_of_the_wind_focus"
META, PERFECT = "monk.uncanny_metabolism", "monk.perfect_focus"
DEFLECT, REDIRECT, SLOW_FALL = "monk.deflect_attacks", "monk.deflect_redirect", "monk.slow_fall"
STUN, FORCE = "monk.stunning_strike", "monk.empowered_strikes_force"
EVASION, EVASION_OK, EVASION_KO = "monk.evasion", "monk.evasion_success", "monk.evasion_failed"
RESTORE, SURVIVOR, SUPERIOR = "monk.self_restoration", "monk.disciplined_survivor", "monk.superior_defense"


async def _monk24(client, level=5, **scores) -> int:
    body = {"name": "Monaco", "initial_class": {"class_name": "monk", "level": level, "subclass": None}}
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    for ability, value in scores.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})
        assert r.status_code == 200, r.text
    return cid


async def _new_turn(client, cid) -> None:
    assert (await client.post(f"/characters/{cid}/turn/new")).status_code == 200


# ---------------------------------------------------------------------------
# Tabelle, righe di sola regola, Punti Ferita, competenze
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,present", [
    (1, {"martial_arts", "unarmored_defense"}), (2, {"ki", "flurry_of_blows", "patient_defense", "step_of_the_wind",
                                                      "unarmored_movement", "uncanny_metabolism"}),
    (3, {"deflect_attacks"}), (4, {"slow_fall"}), (5, {"extra_attack", "stunning_strike"}), (6, {"empowered_strikes"}),
    (7, {"evasion"}), (9, {"acrobatic_movement"}), (10, {"heightened_focus", "self_restoration"}), (13, {"deflect_energy"}),
    (14, {"disciplined_survivor"}), (15, {"perfect_focus"}), (18, {"superior_defense"}), (20, {"body_and_mind"}),
])
async def test_features_appear_at_their_level(client, level, present):
    keys = await _keys_of(client, await _monk24(client, level))
    assert {f"monk.{k}" for k in present} <= keys
    if level > 1:
        low = await _keys_of(client, await _monk24(client, level - 1))
        assert not {f"monk.{k}" for k in present} & low


async def test_rules_only_rows_stay_off_the_sheet_but_in_the_catalog(client):
    keys = await _keys_of(client, await _monk24(client, 20))
    assert not keys & {f"monk.{k}" for k in ("hit_points", "proficiencies", "equipment", "subclass", "ability_score_improvement",
                                              "epic_boon", "multiclassing")}
    titles = {s.source_title for s in features_for("2024", "monk")}
    assert {"Arti Marziali / Martial Arts (Monaco 1, pag. 101)", "Corpo e Mente / Body and Mind (Monaco 20, pag. 103)",
            "Multiclasse: Monaco / Multiclassing: Monk (Capitolo 2, pag. 44)"} <= titles


@pytest.mark.parametrize("level,asi", [(3, []), (4, [4]), (8, [4, 8]), (16, [4, 8, 12, 16]), (19, [4, 8, 12, 16])])
async def test_asi_at_4_8_12_16_and_the_19th_is_an_epic_boon_not_an_asi(client, level, asi):
    pending = (await _full(client, await _monk24(client, level)))["pending_choices"]
    assert sorted(c["level"] for c in pending if c["kind"] == "asi") == asi
    assert [c["level"] for c in pending if c["kind"] == "epic_boon"] == ([19] if level >= 19 else [])


async def test_hit_points_use_the_d8(client):
    full = await _full(client, await _monk24(client, 3))
    assert full["classes"][0]["hit_die"] == 8 and full["hit_points"] == 8 + 5 + 5


def test_proficiencies_come_from_the_2024_class_table_and_a_second_class_gets_none():
    first = class_proficiencies("2024", "monk", False)
    assert not first.armor and set(first.weapons) == {"simple", "martial_light"}
    assert set(first.saves) == {"strength", "dexterity"} and first.skills_count == 2
    multi = class_proficiencies("2024", "monk", True)
    assert not multi.armor and not multi.weapons and not multi.saves and not multi.skills_count


# ---------------------------------------------------------------------------
# Difesa Senza Armatura, Movimento Senza Armatura
# ---------------------------------------------------------------------------

async def test_unarmored_defense_is_automatic_and_armor_or_shield_suspend_it(client):
    cid = await _monk24(client, 3, dexterity=16, wisdom=14)
    full = await _full(client, cid)
    assert full["ac_breakdown"]["base"] == 10 + 3 + 2 and full["unarmored_formula"] == ["dexterity", "wisdom"]
    shield = await _equip(client, cid, slot="off_hand", **SHIELD)
    assert shield["ac_breakdown"]["base"] == 13 and shield["unarmored_formula"] is None
    r = await client.patch(f"/characters/{cid}/items/{shield['item_id']}", json={"is_equipped": False})
    assert r.json()["ac_breakdown"]["base"] == 15
    assert (await _equip(client, cid, **ARMOR))["ac_breakdown"]["base"] == 14


@pytest.mark.parametrize("level,bonus", [(1, 0), (2, 10), (5, 10), (6, 15), (9, 15), (10, 20), (13, 20), (14, 25), (17, 25), (18, 30), (20, 30)])
async def test_unarmored_movement_grows_with_the_level_3_4_5_6_7_5_9_metres(client, level, bonus):
    assert (await _full(client, await _monk24(client, level)))["computed"]["speed"] == 30 + bonus


async def test_armor_or_shield_cancel_the_speed_bonus(client):
    cid = await _monk24(client, 10)
    shield = await _equip(client, cid, slot="off_hand", **SHIELD)
    assert shield["computed"]["speed"] == 30
    assert (await client.patch(f"/characters/{cid}/items/{shield['item_id']}", json={"is_equipped": False})).json()["computed"]["speed"] == 50


async def test_acrobatic_movement_is_a_text_row(client):
    row = await _ability(client, await _monk24(client, 9), "monk.acrobatic_movement")
    assert row["is_passive"] is True and row["has_on_use"] is False


# ---------------------------------------------------------------------------
# Arti Marziali
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,die", [(1, "1d6"), (4, "1d6"), (5, "1d8"), (10, "1d8"), (11, "1d10"), (16, "1d10"), (17, "1d12"), (20, "1d12")])
async def test_martial_arts_die_follows_the_2024_table(client, level, die):
    cid = await _monk24(client, level, dexterity=16)
    r = await _strike(client, cid)
    assert r.status_code == 200, r.text
    assert r.json()["damage_dice"] == die


async def test_unarmed_strike_uses_dexterity_and_a_shield_cancels_the_die(client, monkeypatch):
    monkeypatch.setattr("random.randint", lambda a, b: min(10, b))
    cid = await _monk24(client, 5, strength=8, dexterity=16)
    body = (await _strike(client, cid)).json()
    assert body["to_hit_bonus"] == 3 + 3 and body["damage_bonus"] == 3
    await _equip(client, cid, slot="off_hand", **SHIELD)
    body = (await _strike(client, cid)).json()
    assert body["damage_dice"] == "1" and body["damage_bonus"] == -1


async def test_the_grapple_dc_of_an_unarmed_strike_uses_dexterity_for_a_monk(client):
    cid = await _monk24(client, 5, strength=8, dexterity=16)  # competenza +3, Destrezza +3
    r = await client.post(f"/characters/{cid}/attack/unarmed", json={"effect": "grapple"})
    assert r.status_code == 200, r.text
    assert (r.json()["effect"], r.json()["save_dc"]) == ("grapple", 8 + 3 + 3)


async def test_monk_weapons_are_simple_melee_or_martial_melee_with_light(client):
    cid = await _monk24(client, 11, strength=10, dexterity=16)
    sword = await _shortsword(client, cid)  # da guerra, Leggera: arma del Monaco (1d6 -> dado Arti Marziali 1d10)
    r = await client.post(f"/characters/{cid}/items/{sword}/attack", json={"die": 10})
    assert r.status_code == 200, r.text
    assert r.json()["damage_dice"] == "1d10" and r.json()["damage_bonus"] == 3
    await client.patch(f"/characters/{cid}/items/{sword}", json={"is_equipped": False})
    axe = await _heavy_weapon(client, cid)  # non è dei Monaco: nessun dado Arti Marziali
    r = await client.post(f"/characters/{cid}/items/{axe}/attack", json={"die": 10})
    assert r.json()["damage_dice"] == "1d12" and r.json()["damage_bonus"] == 0


async def test_the_bonus_unarmed_strike_needs_no_attack_action_and_costs_the_bonus_action(client):
    cid = await _monk24(client, 1, dexterity=16)
    assert BONUS in await _roll_keys(client, cid, "attack")  # nessuna azione Attacco prima
    r = await _strike(client, cid, BONUS)
    assert r.status_code == 200, r.text
    turn = await _turn(client, cid)
    assert (turn["bonus_used"], turn["action_attacks"]) == (True, 0)
    assert BONUS not in await _roll_keys(client, cid, "attack")
    again = await _strike(client, cid, BONUS)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "option_unavailable"


async def test_the_bonus_unarmed_strike_is_lost_with_a_shield_or_a_non_monk_weapon(client):
    cid = await _monk24(client, 1, dexterity=16)
    axe = await _heavy_weapon(client, cid)
    assert BONUS not in await _roll_keys(client, cid, "attack")
    await client.patch(f"/characters/{cid}/items/{axe}", json={"is_equipped": False})
    assert BONUS in await _roll_keys(client, cid, "attack")
    await _equip(client, cid, slot="off_hand", **SHIELD)
    assert BONUS not in await _roll_keys(client, cid, "attack")


# ---------------------------------------------------------------------------
# Concentrazione del Monaco
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level", [2, 3, 10, 20])
async def test_focus_points_equal_the_monk_level_and_come_back_with_any_rest(client, level):
    cid = await _monk24(client, level)
    row = await _ability(client, cid, KI)
    assert (row["max_uses"], row["restoration_type"]) == (level, "short_rest")
    await _set_ki(client, cid, 0)
    await _rest(client, cid, "short")
    assert await _ki(client, cid) == level
    await _set_ki(client, cid, 0)
    await _rest(client, cid, "long")
    assert await _ki(client, cid) == level


async def test_focus_is_named_and_shows_the_dc_and_there_is_none_at_level_1(client):
    assert KI not in await _keys_of(client, await _monk24(client, 1))
    cid = await _monk24(client, 5, wisdom=16)  # competenza +3, Saggezza +3
    row = await _ability(client, cid, KI)
    assert row["name"] == "Punti Concentrazione" and row["dc"] == 8 + 3 + 3 and row["has_on_use"] is False
    assert "Difesa Paziente" in (row["description"] or "") and "ki" not in (row["description"] or "").lower().split()


# ---------------------------------------------------------------------------
# Raffica di Colpi
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,hits", [(2, 2), (9, 2), (10, 3), (20, 3)])
async def test_flurry_gives_two_strikes_and_three_from_level_10(client, level, hits):
    cid = await _monk24(client, level, dexterity=16)
    r = await _use(client, cid, FLURRY)  # niente azione Attacco prima
    assert r.status_code == 200, r.text
    assert await _ki(client, cid) == level - 1 and (await _turn(client, cid))["bonus_used"] is True
    assert (await _state_map(client, cid))["flurry_of_blows"]["data"]["charges"] == hits
    for _ in range(hits):
        assert (await _strike(client, cid, STRIKE)).status_code == 200
    assert (await _strike(client, cid, STRIKE)).status_code == 409
    assert (await _turn(client, cid))["action_attacks"] == 0


async def test_flurry_is_refused_without_a_focus_point_or_the_bonus_action_and_costs_nothing(client):
    cid = await _monk24(client, 2)
    await _set_ki(client, cid, 0)
    r = await _use(client, cid, FLURRY)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses" and not (await _turn(client, cid))["bonus_used"]
    other = await _monk24(client, 2)
    await client.post(f"/characters/{other}/turn/use", json={"slot": "bonus"})
    r = await _use(client, other, FLURRY)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "turn_slot_used" and await _ki(client, other) == 2


# ---------------------------------------------------------------------------
# Difesa Paziente, Passo del Vento
# ---------------------------------------------------------------------------

async def test_patient_defense_is_free_as_disengage_and_costs_a_point_with_the_dodge(client):
    cid = await _monk24(client, 5)
    assert (await _use(client, cid, PD)).status_code == 200
    assert await _ki(client, cid) == 5 and (await _turn(client, cid))["bonus_used"] is True
    state = (await _state_map(client, cid))["patient_defense"]
    assert state["data"]["mode"] == "disengage" and not state["data"].get("others")
    await _new_turn(client, cid)
    assert (await _use(client, cid, PD_FOCUS)).status_code == 200
    assert await _ki(client, cid) == 4
    state = (await _state_map(client, cid))["patient_defense"]
    assert state["data"]["mode"] == "disengage_dodge" and state["data"]["others"] == [PD_FOCUS]


@pytest.mark.parametrize("level,temp", [(9, 0), (10, 2 * 4)])
async def test_patient_defense_with_a_point_gives_two_martial_dice_of_temp_hp_from_level_10(client, monkeypatch, level, temp):
    cid = await _monk24(client, level)
    _fixed(monkeypatch, 4)
    r = await _use(client, cid, PD_FOCUS)
    assert r.status_code == 200, r.text
    assert (await _full(client, cid))["temp_hp"] == temp


async def test_the_free_patient_defense_never_gives_temp_hp(client, monkeypatch):
    cid = await _monk24(client, 10)
    _fixed(monkeypatch, 4)
    assert (await _use(client, cid, PD)).status_code == 200
    assert (await _full(client, cid))["temp_hp"] == 0


async def test_step_of_the_wind_is_a_free_dash_or_a_point_for_disengage_dash_and_double_jump(client):
    cid = await _monk24(client, 5)
    assert (await _use(client, cid, STEP)).status_code == 200
    state = (await _state_map(client, cid))["step_of_the_wind"]
    assert state["data"]["mode"] == "dash" and not state["data"].get("jump_doubled") and await _ki(client, cid) == 5
    await _new_turn(client, cid)
    assert (await _use(client, cid, STEP_FOCUS)).status_code == 200
    state = (await _state_map(client, cid))["step_of_the_wind"]
    assert state["data"]["mode"] == "disengage_dash" and state["data"]["jump_doubled"] is True and await _ki(client, cid) == 4
    assert not state["data"].get("carry")


async def test_step_of_the_wind_carries_a_creature_only_from_level_10_with_the_point(client):
    cid = await _monk24(client, 10)
    await _use(client, cid, STEP)
    assert not (await _state_map(client, cid))["step_of_the_wind"]["data"].get("others")
    await _new_turn(client, cid)
    r = await _use(client, cid, STEP_FOCUS)
    assert r.status_code == 200, r.text
    assert (await _state_map(client, cid))["step_of_the_wind"]["data"]["others"] == [STEP_FOCUS]


async def test_the_focus_variants_are_refused_without_points_and_cost_nothing(client):
    cid = await _monk24(client, 2)
    await _set_ki(client, cid, 0)
    for key in (PD_FOCUS, STEP_FOCUS):
        r = await _use(client, cid, key)
        assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses"
    assert not (await _turn(client, cid))["bonus_used"]


# ---------------------------------------------------------------------------
# Metabolismo Prodigioso, Concentrazione Perfetta
# ---------------------------------------------------------------------------

async def test_uncanny_metabolism_restores_every_point_and_heals_level_plus_a_martial_die(client, monkeypatch):
    cid = await _monk24(client, 5)
    await _full_hp(client, cid, 60)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 20})
    await _set_ki(client, cid, 1)
    assert META in await _roll_keys(client, cid, "initiative")
    _fixed(monkeypatch, 5)
    r = await client.post(f"/characters/{cid}/dice/initiative", json={"die": 8, "options": [META]})
    assert r.status_code == 200, r.text
    assert await _ki(client, cid) == 5
    assert (await _full(client, cid))["current_hit_points"] == 20 + 5 + 5  # livello 5 + d8 (5)
    assert "Metabolismo" in r.json()["option_result"]["effects"][0]["it"]
    assert (await _ability(client, cid, META))["uses"] == 0
    assert META not in await _roll_keys(client, cid, "initiative")
    await _rest(client, cid, "long")
    assert META in await _roll_keys(client, cid, "initiative")


async def test_uncanny_metabolism_never_heals_above_the_maximum(client, monkeypatch):
    cid = await _monk24(client, 5)
    await _full_hp(client, cid, 60)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 58})
    _fixed(monkeypatch, 8)
    await client.post(f"/characters/{cid}/dice/initiative", json={"die": 8, "options": [META]})
    assert (await _full(client, cid))["current_hit_points"] == 60


async def test_perfect_focus_brings_the_points_back_to_four_when_metabolism_is_not_used(client):
    low = await _monk24(client, 14)
    assert PERFECT not in await _roll_keys(client, low, "initiative")
    cid = await _monk24(client, 15)
    assert PERFECT not in await _roll_keys(client, cid, "initiative")  # 15 punti, nessun bisogno
    await _set_ki(client, cid, 4)
    assert PERFECT not in await _roll_keys(client, cid, "initiative")
    await _set_ki(client, cid, 1)
    assert PERFECT in await _roll_keys(client, cid, "initiative")
    r = await client.post(f"/characters/{cid}/dice/initiative", json={"die": 8, "options": [PERFECT]})
    assert r.status_code == 200, r.text
    assert await _ki(client, cid) == 4 and "4" in r.json()["option_result"]["effects"][0]["it"]
    assert (await _ability(client, cid, META))["uses"] == 1  # non ha speso il Metabolismo


async def test_perfect_focus_and_metabolism_exclude_each_other_in_the_same_roll(client):
    cid = await _monk24(client, 15)
    await _set_ki(client, cid, 1)
    r = await client.post(f"/characters/{cid}/dice/initiative", json={"die": 8, "options": [META, PERFECT]})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "option_unavailable"
    assert await _ki(client, cid) == 1


async def test_metabolism_works_at_the_initiative_of_an_encounter_too(client, test_session_factory, monkeypatch):
    from tests.integration._encounter_helpers import PLAYER_ID, as_user, seed_session
    from tests.integration._telegram_stub import install_fake_telegram
    install_fake_telegram(monkeypatch)
    sid, cid = await seed_session(test_session_factory)
    r = await client.post(f"/sessions/{sid}/encounter", json={"mode": "full"})
    assert r.status_code == 201, r.text
    pc = next(c for c in r.json()["combatants"] if c["kind"] == "pc")
    as_user(PLAYER_ID)
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    assert (await client.post(f"/characters/{cid}/classes", json={"class_name": "monk", "level": 15, "hit_die": 8})).status_code == 201
    await _full_hp(client, cid, 60)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 30})
    await _set_ki(client, cid, 2)
    _fixed(monkeypatch, 3)
    r = await client.post(f"/sessions/{sid}/encounter/combatants/{pc['id']}/initiative", json={"die": 8, "options": [META]})
    assert r.status_code == 200, r.text
    assert await _ki(client, cid) == 15 and (await _full(client, cid))["current_hit_points"] == 30 + 15 + 3


# ---------------------------------------------------------------------------
# Deviare Attacchi, Deviare Energia, Caduta Lenta
# ---------------------------------------------------------------------------

async def test_deflect_attacks_is_a_reaction_on_damage_from_level_3(client):
    assert DEFLECT not in await _roll_keys(client, await _monk24(client, 2), "damage_taken", damage_type="piercing")
    cid = await _monk24(client, 3)
    option = next(o for o in (await client.get(f"/characters/{cid}/roll-options", params={
        "roll": "damage_taken", "damage_type": "piercing"})).json() if o["key"] == DEFLECT)
    assert option["slot"] == "reaction" and option["phase"] == "damage_in"


async def test_deflect_attacks_reduces_by_d10_plus_dexterity_plus_level_and_spends_the_reaction(client, monkeypatch):
    cid = await _monk24(client, 5, dexterity=16)
    await _full_hp(client, cid)
    _fixed(monkeypatch, 6)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 20, "damage_type": "slashing", "options": [DEFLECT]})
    assert r.status_code == 200, r.text
    assert r.json()["current_hit_points"] == 60 - (20 - (6 + 3 + 5)) and r.json()["option_result"]["damage_after"] == 6
    assert (await _turn(client, cid))["reaction_used"] is True and await _ki(client, cid) == 5
    assert DEFLECT not in await _roll_keys(client, cid, "damage_taken", damage_type="slashing")


@pytest.mark.parametrize("damage_type", ["bludgeoning", "piercing", "slashing"])
async def test_deflect_attacks_before_level_13_covers_only_physical_damage(client, damage_type):
    cid = await _monk24(client, 12)
    assert DEFLECT in await _roll_keys(client, cid, "damage_taken", damage_type=damage_type)


@pytest.mark.parametrize("level,offered", [(12, False), (13, True)])
async def test_deflect_energy_extends_the_reaction_to_every_damage_type_from_level_13(client, level, offered):
    cid = await _monk24(client, level)
    assert (DEFLECT in await _roll_keys(client, cid, "damage_taken", damage_type="fire")) is offered
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 5, "damage_type": "fire", "options": [DEFLECT]})
    assert r.status_code == (200 if offered else 409)


async def test_a_deflected_attack_that_reaches_zero_can_be_redirected_for_a_point_with_a_dexterity_save(client, monkeypatch):
    cid = await _monk24(client, 5, dexterity=16, wisdom=14)  # competenza +3, Saggezza +2, Destrezza +3
    await _full_hp(client, cid)
    assert (await _use(client, cid, REDIRECT)).status_code == 409  # niente da rinviare prima della deviazione
    _fixed(monkeypatch, 10)
    await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 5, "damage_type": "piercing", "options": [DEFLECT]})
    assert "deflected_attack" in await _state_map(client, cid)
    assert await _ki(client, cid) == 5
    _fixed(monkeypatch, 4)
    r = await _use(client, cid, REDIRECT)
    assert r.status_code == 200, r.text
    assert await _ki(client, cid) == 4 and "deflected_attack" not in await _state_map(client, cid)
    effect = (await client.get(f"/characters/{cid}/target-effects/{REDIRECT}")).json()["result"]
    assert (effect["save_ability"], effect["save_dc"]) == ("dexterity", 8 + 3 + 2)
    assert effect["damage_dice"] == "2d8+3" and r.json()["rolls"] == [4, 4]
    again = await _use(client, cid, REDIRECT)
    assert again.status_code == 409


async def test_the_redirect_is_not_available_when_the_damage_did_not_drop_to_zero(client, monkeypatch):
    cid = await _monk24(client, 5, dexterity=16)
    await _full_hp(client, cid)
    _fixed(monkeypatch, 3)
    await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 40, "damage_type": "piercing", "options": [DEFLECT]})
    r = await _use(client, cid, REDIRECT)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "feature_unavailable" and await _ki(client, cid) == 5


async def test_slow_fall_cuts_five_times_the_level_with_the_reaction(client):
    assert SLOW_FALL not in await _roll_keys(client, await _monk24(client, 3), "damage_taken", damage_type="bludgeoning")
    cid = await _monk24(client, 6)
    await _full_hp(client, cid)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 40, "damage_type": "bludgeoning", "options": [SLOW_FALL]})
    assert r.status_code == 200, r.text
    assert r.json()["current_hit_points"] == 60 - 10 and (await _turn(client, cid))["reaction_used"] is True


# ---------------------------------------------------------------------------
# Attacco Extra, Colpo Stordente, Colpi Potenziati
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,attacks", [(4, 1), (5, 2), (20, 2)])
async def test_extra_attack_is_two_attacks_and_never_more(client, level, attacks):
    cid = await _monk24(client, level)
    assert (await client.get(f"/characters/{cid}/turn-state")).json()["attacks_allowed"] == attacks


async def test_extra_attack_does_not_stack_with_another_class(client):
    cid = await _monk24(client, 5)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 5, "hit_die": 10})
    assert r.status_code == 201, r.text
    assert (await client.get(f"/characters/{cid}/turn-state")).json()["attacks_allowed"] == 2


async def test_stunning_strike_is_offered_on_a_hit_with_a_monk_weapon_or_an_unarmed_strike(client):
    assert STUN not in await _roll_keys(client, await _monk24(client, 4), "attack")
    cid = await _monk24(client, 5, dexterity=16)
    assert next(o for o in (await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack"})).json()
                if o["key"] == STUN)["phase"] == "after_hit"
    sword = await _shortsword(client, cid)
    assert STUN in await _roll_keys(client, cid, "attack", item_id=sword)
    await client.patch(f"/characters/{cid}/items/{sword}", json={"is_equipped": False})
    axe = await _heavy_weapon(client, cid)
    assert STUN not in await _roll_keys(client, cid, "attack", item_id=axe)
    await client.patch(f"/characters/{cid}/items/{axe}", json={"is_equipped": False})
    bow = await _bow(client, cid)
    assert STUN not in await _roll_keys(client, cid, "attack", item_id=bow)


async def test_stunning_strike_spends_a_point_and_tells_both_outcomes_with_the_focus_dc(client):
    cid = await _monk24(client, 5, wisdom=16, dexterity=16)  # competenza +3, Saggezza +3
    hit = await _hit(client, cid)
    body = (await _damage(client, cid, hit, STUN)).json()
    assert await _ki(client, cid) == 4 and body["option_result"]["targets"] == [STUN]
    effect_text = body["option_result"]["effects"][0]
    assert "CD 14" in effect_text["it"] and "DC 14" in effect_text["en"]
    assert "dimezzata" in effect_text["it"] and "advantage" in effect_text["en"].lower()  # anche l'esito del TS superato
    effect = (await client.get(f"/characters/{cid}/target-effects/{STUN}")).json()["result"]
    assert (effect["condition"], effect["save_ability"], effect["save_dc"]) == ("stunned", "constitution", 14)
    assert effect["ends_at"] == {"anchor": "source", "edge": "start", "count": 1}


async def test_stunning_strike_is_once_per_turn_and_needs_a_point(client):
    cid = await _monk24(client, 5, dexterity=16)
    hit = await _hit(client, cid)
    assert (await _damage(client, cid, hit, STUN)).status_code == 200
    again = await _hit(client, cid)
    r = await _damage(client, cid, again, STUN)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "option_unavailable" and await _ki(client, cid) == 4
    await _new_turn(client, cid)
    assert STUN in await _roll_keys(client, cid, "attack")
    await _set_ki(client, cid, 0)
    assert STUN not in await _roll_keys(client, cid, "attack")


@pytest.mark.parametrize("level,offered", [(5, False), (6, True)])
async def test_empowered_strikes_let_the_unarmed_strike_deal_force_from_level_6(client, level, offered):
    cid = await _monk24(client, level, dexterity=16)
    assert (FORCE in await _roll_keys(client, cid, "attack")) is offered
    plain = (await _strike(client, cid)).json()
    assert plain["damage_type"] == "bludgeoning" and not plain.get("is_magic")


async def test_the_force_choice_changes_the_damage_type_and_not_the_monk_weapons(client):
    cid = await _monk24(client, 6, dexterity=16)
    body = (await _strike(client, cid, FORCE)).json()
    assert body["damage_type"] == "force"
    sword = await _shortsword(client, cid)
    assert FORCE not in await _roll_keys(client, cid, "attack", item_id=sword)


# ---------------------------------------------------------------------------
# Elusione, Autoguarigione, Sopravvissuto Disciplinato
# ---------------------------------------------------------------------------

async def test_evasion_is_asked_on_dexterity_saves_from_level_7_and_halves_damage_as_the_rule_says(client):
    assert EVASION not in await _roll_keys(client, await _monk24(client, 6), "save", ability="dexterity")
    cid = await _monk24(client, 7)
    assert EVASION in await _roll_keys(client, cid, "save", ability="dexterity")
    await _full_hp(client, cid)
    await _dex_save(client, cid, EVASION)
    assert (await _hurt(client, cid, 20, EVASION_OK)).json()["current_hit_points"] == 60
    await _dex_save(client, cid, EVASION)
    assert (await _hurt(client, cid, 20, EVASION_KO)).json()["current_hit_points"] == 50
    await _conditions(client, cid, incapacitated=True)
    assert EVASION not in await _roll_keys(client, cid, "save", ability="dexterity")


async def test_self_restoration_removes_charmed_frightened_or_poisoned_once_per_turn(client):
    low = await _monk24(client, 9)
    assert RESTORE not in await _keys_of(client, low)
    cid = await _monk24(client, 10)
    r = await _use(client, cid, RESTORE, params={"condition": "charmed"})
    assert r.status_code in (409, 422)  # nessuna condizione da togliere
    await _conditions(client, cid, charmed=True, frightened=True, poisoned=True, blinded=True)
    row = await _ability(client, cid, RESTORE)
    assert [o["key"] for o in row["use_choices"][0]["options"]] == ["charmed", "frightened", "poisoned"]
    assert (await _use(client, cid, RESTORE, params={"condition": "poisoned"})).status_code == 200
    conditions = (await _full(client, cid))["conditions"]
    assert not conditions.get("poisoned") and conditions["charmed"] and conditions["blinded"]
    assert (await _use(client, cid, RESTORE, params={"condition": "charmed"})).status_code == 409  # una per turno
    assert not (await _turn(client, cid))["action_used"]


async def test_disciplined_survivor_gives_every_save_proficiency_and_a_reroll_for_a_point(client):
    low = await _monk24(client, 13, wisdom=14)
    assert (await _wis_save(client, low))["total"] == 10 + 2
    assert "monk.disciplined_survivor" not in [k for k in await _roll_keys(client, low, "save", ability="wisdom")]
    cid = await _monk24(client, 14, wisdom=14)  # competenza +5
    first = await _wis_save(client, cid, die=2)
    assert first["total"] == 2 + 2 + 5
    assert SURVIVOR in await _roll_keys(client, cid, "save", ability="wisdom")
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [SURVIVOR], "dice": [18]})
    assert r.status_code == 200, r.text
    assert r.json()["die"] == 18 and r.json()["total"] == first["total"] + 16 and await _ki(client, cid) == 13
    await _set_ki(client, cid, 0)
    assert SURVIVOR not in await _roll_keys(client, cid, "save", ability="wisdom")


# ---------------------------------------------------------------------------
# Difesa Superiore, Corpo e Mente
# ---------------------------------------------------------------------------

async def test_superior_defense_spends_three_points_and_resists_all_but_force_for_ten_rounds(client):
    cid = await _monk24(client, 18)
    await _full_hp(client, cid, 100)
    r = await _use(client, cid, SUPERIOR)
    assert r.status_code == 200, r.text
    assert await _ki(client, cid) == 15
    assert (await _state_map(client, cid))["superior_defense"]["rounds_left"] == 10
    resistances = set((await _full(client, cid))["computed"]["resistances"])
    assert {"fire", "slashing", "psychic", "necrotic"} <= resistances and "force" not in resistances
    assert (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 20, "damage_type": "fire"})).json()["current_hit_points"] == 90
    assert (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 20, "damage_type": "force"})).json()["current_hit_points"] == 70


async def test_superior_defense_ends_when_incapacitated_and_is_refused_without_three_points(client):
    cid = await _monk24(client, 18)
    await _use(client, cid, SUPERIOR)
    await _conditions(client, cid, incapacitated=True)
    assert "superior_defense" not in await _state_map(client, cid)
    other = await _monk24(client, 18)
    await _set_ki(client, other, 2)
    r = await _use(client, other, SUPERIOR)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses"


async def test_body_and_mind_adds_four_to_dexterity_and_wisdom_with_cap_25(client):
    cid = await _monk24(client, 19, dexterity=18, wisdom=22)
    cls = (await _full(client, cid))["classes"][0]["id"]
    assert (await client.patch(f"/characters/{cid}/classes/{cls}", json={"level": 20})).status_code == 200
    got = {a["name"]: a["value"] for a in (await _full(client, cid))["ability_scores"]}
    assert (got["dexterity"], got["wisdom"]) == (22, 25)
    await client.patch(f"/characters/{cid}/classes/{cls}", json={"level": 19})
    got = {a["name"]: a["value"] for a in (await _full(client, cid))["ability_scores"]}
    assert (got["dexterity"], got["wisdom"]) == (18, 22)


# ---------------------------------------------------------------------------
# Multiclasse e legacy
# ---------------------------------------------------------------------------

async def test_a_second_class_monk_has_no_extra_attack_stacking_and_one_ac_formula(client):
    cid = await _monk24(client, 5, dexterity=14, wisdom=14, constitution=18)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "barbarian", "level": 5, "hit_die": 12})
    assert r.status_code == 201, r.text
    assert (await _full(client, cid))["ac_breakdown"]["base"] == 10 + 2 + 4  # la formula migliore, non la somma


async def test_the_2014_monk_rows_do_not_survive_the_edition_change(client):
    cid = await _monk24(client, 6)
    keys = await _keys_of(client, cid)
    assert "monk.deflect_missiles" not in keys and "monk.ki_empowered_strikes" not in keys and "monk.deflect_attacks" in keys
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2014"})).status_code == 200
    keys = await _keys_of(client, cid)
    assert "monk.deflect_missiles" in keys and "monk.deflect_attacks" not in keys
