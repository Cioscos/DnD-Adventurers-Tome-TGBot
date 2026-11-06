"""Barbaro 2024 (Task 31): progressione, Ira e durata, privilegi passivi, Padronanza delle Armi e Conoscenza Primordiale."""
from __future__ import annotations

import pytest

from core.rules.catalog import features_for
from tests.integration.rules.test_2014_barbarian import (
    _ability, _armor, _attack, _full, _hit, _hp, _keys, _states, _turn, _weapon,
)

RAGE = "barbarian.rage"


async def _barbarian(client, level=5, subclass=None, **scores) -> int:
    body = {"name": "Barbaro", "initial_class": {"class_name": "barbarian", "level": level, "subclass": subclass}}
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    for ability, value in scores.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})
        assert r.status_code == 200, r.text
    return cid


async def _rage(client, cid, **params):
    return await client.post(f"/characters/{cid}/features/{RAGE}/use", json={"params": params} if params else {})


async def _new_turn(client, cid) -> None:
    assert (await client.post(f"/characters/{cid}/turn/new")).status_code == 200


async def _rage_state(client, cid) -> dict | None:
    return next((s for s in await _states(client, cid) if s["key"] == "rage"), None)


# ---------------------------------------------------------------------------
# Progressione e catalogo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,uses", [(1, 2), (2, 2), (3, 3), (5, 3), (6, 4), (11, 4), (12, 5), (16, 5), (17, 6), (20, 6)])
async def test_rage_uses_follow_the_2024_table_and_are_never_unlimited(client, level, uses):
    cid = await _barbarian(client, level)
    rage = await _ability(client, cid, RAGE)
    assert (rage["name"], rage["max_uses"], rage["uses"], rage["restoration_type"]) == ("Ira", uses, uses, "long_rest")


async def test_a_short_rest_gives_back_one_rage_and_a_long_rest_all_of_them(client):
    cid = await _barbarian(client, 3)
    for _ in range(3):
        assert (await _rage(client, cid)).status_code == 200
        assert (await client.delete(f"/characters/{cid}/active-states/rage")).status_code == 200
        await _new_turn(client, cid)
    assert (await _ability(client, cid, RAGE))["uses"] == 0
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "short", "confirm_early": True})
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, RAGE))["uses"] == 1
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})
    assert (await _ability(client, cid, RAGE))["uses"] == 3


@pytest.mark.parametrize("level,present", [
    (1, {"rage", "unarmored_defense", "weapon_mastery"}), (2, {"reckless_attack", "danger_sense"}),
    (3, {"primal_knowledge"}), (5, {"extra_attack", "fast_movement"}), (7, {"feral_instinct", "instinctive_pounce"}),
    (9, {"brutal_strike"}), (11, {"relentless_rage"}), (13, {"improved_brutal_strike"}), (15, {"persistent_rage"}),
    (18, {"indomitable_might"}), (20, {"primal_champion"}),
])
async def test_features_appear_at_their_level(client, level, present):
    cid = await _barbarian(client, level)
    keys = {a["feature_key"] for a in (await _full(client, cid))["abilities"]}
    assert {f"barbarian.{k}" for k in present} <= keys
    if level > 1:
        low = {a["feature_key"] for a in (await _full(client, await _barbarian(client, level - 1)))["abilities"]}
        assert not {f"barbarian.{k}" for k in present} & low


async def test_rules_only_rows_stay_off_the_sheet_but_in_the_catalog(client):
    cid = await _barbarian(client, 20)
    keys = {a["feature_key"] for a in (await _full(client, cid))["abilities"]}
    assert not keys & {f"barbarian.{k}" for k in ("core_traits", "subclass", "ability_score_improvement", "epic_boon", "multiclassing")}
    titles = {s.source_title for s in features_for("2024", "barbarian")}
    assert {"Tratti Fondamentali del Barbaro / Core Barbarian Traits (Barbaro 1, pag. 51)",
            "Ira / Rage (Barbaro 1, pag. 51)"} <= titles


@pytest.mark.parametrize("level,asi_levels", [(3, []), (4, [4]), (16, [4, 8, 12, 16]), (19, [4, 8, 12, 16]), (20, [4, 8, 12, 16])])
async def test_asi_at_4_8_12_16_and_the_19th_is_an_epic_boon_not_an_asi(client, level, asi_levels):
    full = await _full(client, await _barbarian(client, level))
    pending = full["pending_choices"]
    assert sorted(c["level"] for c in pending if c["kind"] == "asi") == asi_levels
    assert [c["level"] for c in pending if c["kind"] == "epic_boon"] == ([19] if level >= 19 else [])


async def test_hit_points_use_the_d12_and_follow_constitution(client):
    cid = await _barbarian(client, 3)
    full = await _full(client, cid)
    assert full["classes"][0]["hit_die"] == 12
    assert full["hit_points"] == 12 + 7 + 7
    await client.patch(f"/characters/{cid}/ability_scores/constitution", json={"value": 14})
    assert (await _full(client, cid))["hit_points"] == 12 + 7 + 7 + 2 * 3


def test_core_traits_and_multiclass_proficiencies_come_from_the_2024_class_table():
    from core.rules.proficiencies import class_proficiencies

    first = class_proficiencies("2024", "barbarian", False)
    assert set(first.armor) == {"light", "medium", "shields"} and set(first.weapons) == {"simple", "martial"}
    assert set(first.saves) == {"strength", "constitution"} and first.skills_count == 2
    assert set(first.skills_from) == {"animal_handling", "athletics", "intimidation", "nature", "perception", "survival"}
    multi = class_proficiencies("2024", "barbarian", True)
    assert multi.armor == ("shields",) and multi.weapons == ("martial",) and not multi.saves and multi.skills_count == 0


async def test_barbarian_added_as_second_class_keeps_one_rage_and_extra_attack_at_two(client):
    cid = await _barbarian(client, 5)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "wizard", "level": 3, "hit_die": 6})
    assert r.status_code == 201
    assert [a["feature_key"] for a in (await _full(client, cid))["abilities"]].count(RAGE) == 1
    assert (await client.get(f"/characters/{cid}/turn-state")).json()["attacks_allowed"] == 2


async def test_extra_attack_is_two_attacks_only_from_level_5(client):
    assert (await client.get(f"/characters/{await _barbarian(client, 4)}/turn-state")).json()["attacks_allowed"] == 1
    assert (await client.get(f"/characters/{await _barbarian(client, 5)}/turn-state")).json()["attacks_allowed"] == 2


# ---------------------------------------------------------------------------
# Difesa Senza Armatura, Movimento Veloce, Istinto Ferino, Percezione del Pericolo
# ---------------------------------------------------------------------------

async def test_unarmored_defense_uses_dex_and_con_and_yields_to_armor(client):
    cid = await _barbarian(client, 1, dexterity=14, constitution=16)
    assert (await _full(client, cid))["ac"] == 15
    await _armor(client, cid, "heavy", 16)
    assert (await _full(client, cid))["ac"] == 16


async def test_unarmored_defense_with_a_second_formula_takes_the_better_one_once(client):
    cid = await _barbarian(client, 1, dexterity=14, constitution=16, wisdom=18)
    r = await client.post(f"/characters/{cid}/ac/unarmored-defense", json={"ability": "wisdom"})  # il Monaco
    assert r.status_code == 200, r.text
    assert (await _full(client, cid))["ac"] == 16  # 10 + DES 2 + SAG 4, non 10 + 2 + 3 + 4


@pytest.mark.parametrize("level,speed", [(4, 30), (5, 40), (20, 40)])
async def test_fast_movement(client, level, speed):
    assert (await _full(client, await _barbarian(client, level)))["computed"]["speed"] == speed


async def test_fast_movement_not_in_heavy_armor(client):
    cid = await _barbarian(client, 5, strength=18)
    await _armor(client, cid, "heavy")
    assert (await _full(client, cid))["computed"]["speed"] == 30


async def test_feral_instinct_gives_advantage_on_initiative_from_level_7(client):
    early, late = await _barbarian(client, 6), await _barbarian(client, 7)
    assert (await client.post(f"/characters/{early}/dice/initiative", json={"die": 9})).json()["mode_applied"] == "normal"
    assert (await client.post(f"/characters/{late}/dice/initiative", json={"die": 9})).json()["mode_applied"] == "advantage"


async def test_danger_sense_is_automatic_on_dexterity_saves_unless_incapacitated(client):
    cid = await _barbarian(client, 2)
    roll = lambda ab: client.post(f"/characters/{cid}/saving_throws/{ab}/roll", json={"die": 8})  # noqa: E731
    dex, strength = (await roll("dexterity")).json(), (await roll("strength")).json()
    assert dex["mode_applied"] == "advantage" and "feature:barbarian.danger_sense" in dex["notes"]
    assert strength["mode_applied"] == "normal"
    assert (await roll("dexterity")).status_code == 200 and "barbarian.danger_sense" not in await _keys(client, cid, "save", ability="dexterity")
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"stunned": True}})
    assert (await roll("dexterity")).json()["mode_applied"] == "normal"
    young = await _barbarian(client, 1)
    assert (await client.post(f"/characters/{young}/saving_throws/dexterity/roll", json={"die": 8})).json()["mode_applied"] == "normal"


async def test_danger_sense_is_not_cancelled_by_blindness_or_deafness(client):
    cid = await _barbarian(client, 2)
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"blinded": True, "deafened": True}})
    assert (await client.post(f"/characters/{cid}/saving_throws/dexterity/roll", json={"die": 8})).json()["mode_applied"] == "advantage"


# ---------------------------------------------------------------------------
# Ira
# ---------------------------------------------------------------------------

async def test_rage_spends_bonus_action_and_a_use_and_starts_a_ten_minute_state(client):
    cid = await _barbarian(client, 5)
    r = await _rage(client, cid)
    assert r.status_code == 200, r.text
    assert (await _turn(client, cid))["bonus_used"] is True and (await _ability(client, cid, RAGE))["uses"] == 2
    state = await _rage_state(client, cid)
    assert (state["name"], state["rounds_left"], state["data"]["damage"], state["data"]["fresh"]) == ("Ira", 100, 2, True)
    again = await _rage(client, cid)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "turn_slot_used"
    assert (await _ability(client, cid, RAGE))["uses"] == 2


async def test_rage_cannot_be_entered_in_heavy_armor_and_donning_it_ends_the_rage(client):
    cid = await _barbarian(client, 5, strength=16)
    await _armor(client, cid, "heavy")
    refused = await _rage(client, cid)
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "feature_unavailable"
    assert (await _ability(client, cid, RAGE))["uses"] == 3
    other = await _barbarian(client, 5, strength=16)
    await _rage(client, other)
    assert await _rage_state(client, other) is not None
    await _armor(client, other, "heavy")
    assert await _rage_state(client, other) is None


@pytest.mark.parametrize("level,bonus", [(1, 2), (8, 2), (9, 3), (15, 3), (16, 4), (20, 4)])
async def test_rage_damage_bonus_by_level_on_strength_attacks(client, level, bonus):
    cid = await _barbarian(client, level, strength=16, dexterity=10)
    sword = await _weapon(client, cid)
    plain = (await _attack(client, cid, sword))["damage_bonus"]
    await _rage(client, cid)
    assert (await _attack(client, cid, sword))["damage_bonus"] == plain + bonus


async def test_rage_damage_applies_to_thrown_strength_attacks_but_not_to_bows_or_dexterity(client):
    cid = await _barbarian(client, 5, strength=16, dexterity=18)
    javelin = await _weapon(client, cid, "Giavellotto", None, properties=["thrown"], damage_dice="1d6")
    bow = await _weapon(client, cid, "Arco", None, weapon_type="ranged", damage_dice="1d8")
    rapier = await _weapon(client, cid, "Stocco", None, properties=["finesse"], damage_dice="1d8")
    kw = lambda w: {"attack_mode": "thrown"} if w == javelin else {}  # noqa: E731
    before = {w: (await _attack(client, cid, w, **kw(w)))["damage_bonus"] for w in (javelin, bow, rapier)}
    await _new_turn(client, cid)
    await _rage(client, cid)
    after = {w: (await _attack(client, cid, w, **kw(w)))["damage_bonus"] for w in (javelin, bow, rapier)}
    assert after[javelin] == before[javelin] + 2 and after[bow] == before[bow] and after[rapier] == before[rapier]


@pytest.mark.parametrize("damage_type,taken", [("slashing", 5), ("piercing", 5), ("bludgeoning", 5), ("fire", 10), ("psychic", 10)])
async def test_rage_resists_physical_damage_only(client, damage_type, taken):
    cid = await _barbarian(client, 5)
    await _hp(client, cid, 60, 60)
    await _rage(client, cid)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10, "damage_type": damage_type})
    assert r.json()["current_hit_points"] == 60 - taken


async def test_rage_advantage_on_strength_checks_and_saves_only(client):
    cid = await _barbarian(client, 5)
    await _rage(client, cid)
    modes = [(await client.post(f"/characters/{cid}/{path}/roll", json={"die": 8})).json()["mode_applied"]
             for path in ("skills/athletics", "skills/acrobatics", "saving_throws/strength", "saving_throws/constitution")]
    assert modes == ["advantage", "normal", "advantage", "normal"]


async def test_rage_ends_concentration_and_blocks_casting(client):
    cid = await _barbarian(client, 5)
    spell = (await client.post(f"/characters/{cid}/spells", json={
        "name": "Luce guida", "level": 0, "is_concentration": True, "duration": "Concentrazione, fino a 1 minuto"})).json()
    assert (await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={})).status_code == 200
    await _rage(client, cid)
    assert (await _full(client, cid))["concentrating_spell_id"] is None
    assert "state_blocks_casting" in (await client.get(f"/characters/{cid}/spells/{spell['id']}/cast-check")).json()


async def test_rage_ends_with_a_rest_and_gives_no_use_back(client):
    cid = await _barbarian(client, 5)
    await _rage(client, cid)
    assert (await client.post(f"/characters/{cid}/rest", json={"rest_type": "short", "confirm_early": True})).status_code == 200
    assert await _rage_state(client, cid) is None and (await _ability(client, cid, RAGE))["uses"] == 3  # 2 + la ricarica breve


@pytest.mark.parametrize("level,ends", [(14, {"unconscious", "incapacitated", "turn_end_unextended", "heavy_armor"}),
                                         (15, {"unconscious", "heavy_armor"})])
async def test_rage_end_conditions_change_with_persistent_rage(client, level, ends):
    state = (await _rage(client, await _barbarian(client, level))).json()["state"]
    assert set(state["ends_on"]) == ends


async def test_rage_ends_when_incapacitated_before_15_but_not_at_15(client):
    for level, alive in ((14, False), (15, True)):
        cid = await _barbarian(client, level)
        await _rage(client, cid)
        await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"stunned": True}})
        assert (await _rage_state(client, cid) is not None) is alive, level
        await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"unconscious": True}})
        assert await _rage_state(client, cid) is None, level


# --- durata: prolungamento fuori e dentro un incontro ---------------------------------------------------------------

async def test_the_rage_lasts_through_the_next_turn_and_needs_an_extension_after_that(client):
    cid = await _barbarian(client, 5, strength=16)
    await _rage(client, cid)
    await _new_turn(client, cid)  # finisce il turno in cui è nata: dura fino alla fine del successivo
    assert await _rage_state(client, cid) is not None
    await _new_turn(client, cid)  # il turno successivo finisce senza prolungamento
    assert await _rage_state(client, cid) is None


async def test_an_attack_roll_extends_the_rage(client):
    cid = await _barbarian(client, 5, strength=16)
    sword = await _weapon(client, cid)
    await _rage(client, cid)
    await _new_turn(client, cid)
    await _attack(client, cid, sword)
    await _new_turn(client, cid)
    assert await _rage_state(client, cid) is not None
    await _new_turn(client, cid)  # niente di nuovo: finisce
    assert await _rage_state(client, cid) is None


async def test_a_bonus_action_extends_without_spending_a_rage_use(client):
    cid = await _barbarian(client, 5)
    await _rage(client, cid)
    await _new_turn(client, cid)
    r = await _rage(client, cid)  # già in ira: prolunga
    assert r.status_code == 200 and r.json()["state"] is None
    assert (await _turn(client, cid))["bonus_used"] is True and (await _ability(client, cid, RAGE))["uses"] == 2
    await _new_turn(client, cid)
    assert (await _rage_state(client, cid))["rounds_left"] == 100  # il tetto di 10 minuti non si rinnova
    await _new_turn(client, cid)
    assert await _rage_state(client, cid) is None


async def test_forcing_a_save_extends_the_rage_without_the_bonus_action(client):
    cid = await _barbarian(client, 5)
    await _rage(client, cid)
    await _new_turn(client, cid)
    r = await _rage(client, cid, extend_via="save")
    assert r.status_code == 200, r.text
    assert (await _turn(client, cid))["bonus_used"] is False and (await _ability(client, cid, RAGE))["uses"] == 2
    await _new_turn(client, cid)
    assert await _rage_state(client, cid) is not None


async def test_persistent_rage_needs_no_extension(client):
    cid = await _barbarian(client, 15)
    await _rage(client, cid)
    for _ in range(4):
        await _new_turn(client, cid)
    assert await _rage_state(client, cid) is not None


async def test_rage_duration_in_an_encounter_follows_the_turn_edges(client, test_session_factory, monkeypatch):
    from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user
    from tests.integration.rules.test_2014_barbarian_round1 import _in_encounter
    sid, cid = await _in_encounter(client, test_session_factory, monkeypatch)
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "barbarian", "level": 5, "hit_die": 12})
    assert r.status_code == 201, r.text

    async def next_turn(times):
        as_user(GM_ID)
        for _ in range(times):
            assert (await client.post(f"/sessions/{sid}/encounter/next-turn")).status_code == 200
        as_user(PLAYER_ID)

    await _rage(client, cid)
    await next_turn(3)  # fine del primo turno e giro dei due goblin: tocca di nuovo al PG
    assert await _rage_state(client, cid) is not None
    await next_turn(1)  # fine del secondo turno senza prolungamento
    assert await _rage_state(client, cid) is None


# --- Balzo Istintivo ----------------------------------------------------------------------------------------------------

async def test_instinctive_pounce_tells_how_far_to_move_when_entering_the_rage(client):
    cid = await _barbarian(client, 7)  # velocità 30 + 10 di Movimento Veloce
    message = (await _rage(client, cid)).json()["message"]
    assert "6 m" in message["it"] and "20 ft" in message["en"]
    early = (await _rage(client, await _barbarian(client, 6))).json()["message"]
    assert early is None or "6 m" not in early["it"]


# --- Ira Implacabile --------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("level", [11, 14, 20])
async def test_relentless_rage_restores_twice_the_barbarian_level(client, monkeypatch, level):
    monkeypatch.setattr("api.services.d20.random.randint", lambda a, b: 20)
    cid = await _barbarian(client, level, constitution=14)
    await _hp(client, cid, 40, 40)
    await _rage(client, cid)
    body = await _hit(client, cid, 45)
    assert body["zero_hp_save"]["dc"] == 10 and body["zero_hp_save"]["success"] is True
    assert body["current_hit_points"] == 2 * level and body["is_dead"] is False


async def test_relentless_rage_dc_grows_by_five_and_resets_with_any_rest(client, monkeypatch):
    monkeypatch.setattr("api.services.d20.random.randint", lambda a, b: 20)
    cid = await _barbarian(client, 11, constitution=14)
    await _hp(client, cid)
    await _rage(client, cid)
    dcs = []
    for _ in range(3):
        dcs.append((await _hit(client, cid, 50))["zero_hp_save"]["dc"])
        await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 40})
    assert dcs == [10, 15, 20]
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "short", "confirm_early": True})
    await _new_turn(client, cid)
    await _rage(client, cid)
    assert (await _hit(client, cid, 50))["zero_hp_save"]["dc"] == 10


async def test_relentless_rage_needs_the_rage_level_11_and_no_instant_death(client, monkeypatch):
    monkeypatch.setattr("api.services.d20.random.randint", lambda a, b: 20)
    cid = await _barbarian(client, 11)
    await _hp(client, cid)
    await _rage(client, cid)
    assert (await _hit(client, cid, 80))["is_dead"] is True
    calm = await _barbarian(client, 11)
    await _hp(client, calm)
    assert (await _hit(client, calm, 45)).get("zero_hp_save") is None
    young = await _barbarian(client, 10)
    await _hp(client, young)
    await _rage(client, young)
    assert (await _hit(client, young, 45)).get("zero_hp_save") is None


# --- Ira Persistente --------------------------------------------------------------------------------------------------

async def test_persistent_rage_gives_back_every_rage_when_rolling_initiative_once_per_long_rest(client):
    cid = await _barbarian(client, 15)
    for _ in range(2):
        await _rage(client, cid)
        await client.delete(f"/characters/{cid}/active-states/rage")
        await _new_turn(client, cid)
    assert (await _ability(client, cid, RAGE))["uses"] == 3  # 5 al 15° livello
    assert "barbarian.persistent_rage" in await _keys(client, cid, "initiative")
    r = await client.post(f"/characters/{cid}/dice/initiative", json={"die": 9, "options": ["barbarian.persistent_rage"]})
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, RAGE))["uses"] == 5
    assert "barbarian.persistent_rage" not in await _keys(client, cid, "initiative")
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})
    assert "barbarian.persistent_rage" not in await _keys(client, cid, "initiative")  # nessun uso da recuperare
    await _rage(client, cid)
    await client.delete(f"/characters/{cid}/active-states/rage")
    assert "barbarian.persistent_rage" in await _keys(client, cid, "initiative")


async def test_persistent_rage_is_not_offered_with_all_rages_available_or_before_15(client):
    assert "barbarian.persistent_rage" not in await _keys(client, await _barbarian(client, 15), "initiative")
    young = await _barbarian(client, 14)
    await _rage(client, young)
    assert "barbarian.persistent_rage" not in await _keys(client, young, "initiative")


# --- Potenza Indomabile ------------------------------------------------------------------------------------------------

async def test_indomitable_might_raises_strength_checks_and_saves_to_the_score(client):
    cid = await _barbarian(client, 18, strength=20)
    assert (await client.post(f"/characters/{cid}/skills/athletics/roll", json={"die": 1})).json()["total"] >= 20
    assert (await client.post(f"/characters/{cid}/saving_throws/strength/roll", json={"die": 1})).json()["total"] >= 20
    assert (await client.post(f"/characters/{cid}/saving_throws/dexterity/roll", json={"die": 1})).json()["total"] < 20
    assert (await client.post(f"/characters/{cid}/skills/acrobatics/roll", json={"die": 1})).json()["total"] < 20
    plain = await _barbarian(client, 17, strength=20)
    assert (await client.post(f"/characters/{plain}/saving_throws/strength/roll", json={"die": 1})).json()["total"] < 20


# --- Campione Primordiale e passaggio di edizione ---------------------------------------------------------------------

async def _scores(client, cid) -> dict[str, int]:
    return {a["name"]: a["value"] for a in (await _full(client, cid))["ability_scores"]}


async def test_primal_champion_adds_four_to_strength_and_constitution_with_cap_25(client):
    cid = await _barbarian(client, 19, strength=18, constitution=22)
    cls = (await _full(client, cid))["classes"][0]["id"]
    assert (await client.patch(f"/characters/{cid}/classes/{cls}", json={"level": 20})).status_code == 200
    got = await _scores(client, cid)
    assert (got["strength"], got["constitution"]) == (22, 25)
    await client.patch(f"/characters/{cid}/classes/{cls}", json={"level": 19})
    got = await _scores(client, cid)
    assert (got["strength"], got["constitution"]) == (18, 22)


async def test_the_primal_champion_bonus_is_not_given_twice_when_the_edition_changes(client):
    """Ruling del Task 19, ricontrollato: 2024 -> 2014 e 2014 -> 2024 non aggiungono un secondo +4."""
    cid = await _barbarian(client, 19, strength=18, constitution=14)
    cls = (await _full(client, cid))["classes"][0]["id"]
    await client.patch(f"/characters/{cid}/classes/{cls}", json={"level": 20})
    assert (await _scores(client, cid))["strength"] == 22
    for edition in ("2014", "2024", "2014"):
        assert (await client.patch(f"/characters/{cid}", json={"rules_edition": edition})).status_code == 200
        got = await _scores(client, cid)
        assert (got["strength"], got["constitution"]) == (22, 18), edition


async def test_scores_written_by_hand_at_level_20_are_not_raised_by_an_edition_change(client):
    cid = await _barbarian(client, 20)
    await client.patch(f"/characters/{cid}/ability_scores/strength", json={"value": 18})
    for edition in ("2014", "2024"):
        assert (await client.patch(f"/characters/{cid}", json={"rules_edition": edition})).status_code == 200
        assert (await _scores(client, cid))["strength"] == 18, edition


# ---------------------------------------------------------------------------
# Padronanza delle Armi
# ---------------------------------------------------------------------------

def _mastery_choice(full: dict) -> dict | None:
    return next((c for c in full["pending_choices"] if c.get("group") == "weapon_mastery"), None)


@pytest.mark.parametrize("level,count", [(1, 2), (3, 2), (4, 3), (9, 3), (10, 4), (20, 4)])
async def test_weapon_mastery_picks_follow_the_table(client, level, count):
    cid = await _barbarian(client, level)
    choice = _mastery_choice(await _full(client, cid))
    assert choice["count"] == count
    keys = {o["key"] for o in choice["options"]}
    assert {"greataxe", "handaxe", "dagger"} <= keys and not keys & {"longbow", "shortbow", "handaxe_x"}
    assert "greataxe" in keys


async def test_a_chosen_weapon_activates_its_mastery_on_attacks(client):
    cid = await _barbarian(client, 1, strength=16)
    choice = _mastery_choice(await _full(client, cid))
    r = await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve",
                          json={"kind": "class_option", "options": ["greataxe", "handaxe"]})
    assert r.status_code == 200, r.text
    axe = await _weapon(client, cid, "Ascia bipenne", damage_dice="1d12", properties=["heavy", "two_handed"])
    assert "mastery_cleave" in await _keys(client, cid, "attack", item_id=axe)
    mace = await _weapon(client, cid, "Mazza", None, damage_dice="1d6")
    assert not [k for k in await _keys(client, cid, "attack", item_id=mace) if k.startswith("mastery_")]


# ---------------------------------------------------------------------------
# Conoscenza Primordiale
# ---------------------------------------------------------------------------

def _primal_choice(full: dict) -> dict | None:
    return next((c for c in full["pending_choices"] if c.get("group") == "primal_knowledge"), None)


async def test_primal_knowledge_adds_a_skill_of_the_level_1_list(client):
    assert _primal_choice(await _full(client, await _barbarian(client, 2))) is None
    cid = await _barbarian(client, 3)
    choice = _primal_choice(await _full(client, cid))
    assert choice["count"] == 1
    assert {o["key"] for o in choice["options"]} == {"animal_handling", "athletics", "intimidation", "nature", "perception", "survival"}
    r = await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve", json={"kind": "class_option", "options": ["survival"]})
    assert r.status_code == 200, r.text
    assert (await _full(client, cid))["skills"]["survival"] in ("proficient", True)


async def test_primal_knowledge_does_not_offer_skills_already_proficient(client):
    cid = await _barbarian(client, 3)
    await client.patch(f"/characters/{cid}/skills", json={"skills": {"athletics": "proficient"}})
    assert "athletics" not in {o["key"] for o in _primal_choice(await _full(client, cid))["options"]}


async def test_with_the_rage_active_five_skills_can_be_rolled_as_strength_checks(client):
    cid = await _barbarian(client, 3, strength=18, dexterity=8)
    key = "barbarian.primal_knowledge"
    assert key not in await _keys(client, cid, "skill", skill="acrobatics", ability="dexterity")  # niente ira
    await _rage(client, cid)
    for skill in ("acrobatics", "intimidation", "perception", "stealth", "survival"):
        ability = {"acrobatics": "dexterity", "stealth": "dexterity", "perception": "wisdom", "survival": "wisdom", "intimidation": "charisma"}[skill]
        assert key in await _keys(client, cid, "skill", skill=skill, ability=ability), skill
    assert key not in await _keys(client, cid, "skill", skill="athletics", ability="strength")
    assert key not in await _keys(client, cid, "skill", skill="arcana", ability="intelligence")
    plain = (await client.post(f"/characters/{cid}/skills/acrobatics/roll", json={"die": 10})).json()
    forced = (await client.post(f"/characters/{cid}/skills/acrobatics/roll", json={"die": 10, "options": [key]})).json()
    assert forced["bonus"] - plain["bonus"] == 4 - (-1)
    assert forced["mode_applied"] == "advantage" and plain["mode_applied"] == "normal"  # è una prova di Forza: vantaggio dell'Ira


# ---------------------------------------------------------------------------
# Sottoclasse
# ---------------------------------------------------------------------------

async def test_subclass_features_need_a_recognised_2024_subclass(client):
    keys = lambda full: {a["feature_key"] for a in full["abilities"]}  # noqa: E731
    wild = keys(await _full(client, await _barbarian(client, 14, "Cammino del Cuore Selvaggio")))
    unknown = keys(await _full(client, await _barbarian(client, 14, "Cammino Sconosciuto")))
    old = keys(await _full(client, await _barbarian(client, 14, "Cammino del Combattente Totemico")))
    assert {"barbarian.animal_speaker", "barbarian.rage_of_the_wilds", "barbarian.power_of_the_wilds"} <= wild
    for other in (unknown, old):
        assert not {k for k in other if k.split(".")[1] in {"animal_speaker", "rage_of_the_wilds", "frenzy", "divine_fury"}}
        assert RAGE in other


async def test_changing_edition_swaps_the_19th_asi_and_the_epic_boon_both_ways(client):
    cid = await _barbarian(client, 19)  # nasce 2014, passa a 2024 nell'helper: l'ASI del 19° diventa un Dono Epico
    kinds = lambda full: sorted((c["kind"], c["level"]) for c in full["pending_choices"] if c["level"] == 19)  # noqa: E731
    assert kinds(await _full(client, cid)) == [("epic_boon", 19)]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2014"})).status_code == 200
    assert kinds(await _full(client, cid)) == [("asi", 19)]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    assert kinds(await _full(client, cid)) == [("epic_boon", 19)]


# ---------------------------------------------------------------------------
# Importazione da Beyond
# ---------------------------------------------------------------------------

async def test_beyond_options_find_the_catalog_choices(test_session_factory):
    from api.routers.transfer import _apply_class_options
    from api.services.ddb_import import ImportReport
    from core.rules.sample_characters import build_rules_character

    async with test_session_factory() as s:
        spec = {"name": "x", "edition": "2024", "classes": [("Barbaro", 6, "Cammino del Cuore Selvaggio", 12)]}
        char = await build_rules_character(s, spec, 1)
        report = ImportReport()
        names = ("Greataxe", "Handaxe", "Owl", "Otter")
        _apply_class_options(char, [{"class_index": 0, "name": n} for n in names], report, "it")
        assert char.classes[0].options == {"weapon_mastery": ["greataxe", "handaxe"], "aspect_of_the_wilds": ["owl"]}
        assert [e.name for e in report.approximated] == ["Otter"]


async def test_the_beyond_2024_fixture_imports_with_the_2024_catalog(client, monkeypatch):
    from tests.integration.rules.test_2014_monk import _import_fixture
    _import_fixture(monkeypatch, "barbarian20_2024.json")
    r = await client.post("/characters/import/ddb", json={"url": "https://www.dndbeyond.com/characters/1", "rules_edition": "2024"})
    assert r.status_code == 201, r.text
    full = r.json()["character"]
    rows = {a["feature_key"]: a for a in full["abilities"]}
    assert rows[RAGE]["max_uses"] == 6 and rows[RAGE]["restoration_type"] == "long_rest"
    assert {"barbarian.primal_champion", "barbarian.frenzy", "barbarian.retaliation", "barbarian.relentless_rage"} <= set(rows)
    assert [c["kind"] for c in full["pending_choices"] if c["kind"] in ("asi", "epic_boon")].count("asi") == 0
    scores = {a["name"]: a["value"] for a in full["ability_scores"]}
    assert scores["strength"] == 21  # il +4 del 20° livello non si somma ai punteggi scritti da Beyond (R34)


async def test_hit_points_of_a_barbarian_created_at_level_20_match_climbing(client):
    low, top = await _barbarian(client, 19), await _barbarian(client, 20)
    assert (await _full(client, low))["hit_points"] == 12 + 18 * 7  # CON 10
    # Campione Primordiale dà CON 14 (+2) su ognuno dei 20 livelli: 12 + 2 al 1°, poi 19 × (7 + 2)
    assert (await _full(client, top))["hit_points"] == 12 + 2 + 19 * (7 + 2) == 185
