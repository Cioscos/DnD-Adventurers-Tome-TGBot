"""Scuola di Necromanzia e di Trasmutazione 2014 (Task 30): Raccolto Macabro, Servitori Non Morti, Impervio alla Non Morte,
Comandare Non Morti; Alchimia Minore, Pietra del Trasmutatore, Mutaforma, Maestro Trasmutatore e le sue quattro opzioni."""
from __future__ import annotations

import random

import pytest

from tests.integration.rules.test_2014_bard import _ability, _full, _roll_keys, _spells, _use
from tests.integration.rules.test_2014_fighter_eldritch_knight import _cast, _spell
from tests.integration.rules.test_2014_paladin import _rest
from tests.integration.rules.test_2014_wizard import _wizard

HARVEST, THRALLS, INURED, COMMAND = "wizard.grim_harvest", "wizard.undead_thralls", "wizard.inured_to_undeath", "wizard.command_undead"
ALCHEMY, STONE, STONE_CHANGE, SHAPE = "wizard.minor_alchemy", "wizard.transmuters_stone", "wizard.transmuters_stone_change", "wizard.shapechanger"
MASTER = "wizard.master_transmuter"
PANACEA, YOUTH, LIFE, MAJOR = "wizard.panacea", "wizard.restore_youth", "wizard.restore_life", "wizard.major_transformation"


async def _turn(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]


async def _states(client, cid) -> dict[str, dict]:
    return {s["key"]: s for s in (await _full(client, cid))["active_states"] or []}


async def _hp(client, cid, maximum=100, current=None) -> None:
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": maximum})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": current if current is not None else maximum})


async def _effect(client, cid, key) -> dict:
    return (await client.get(f"/characters/{cid}/target-effects/{key}")).json()["result"]


# ---------------------------------------------------------------------------
# Raccolto Macabro
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,school,healed", [(1, "other", 2), (3, "other", 6), (3, "necromancy", 9), (9, "necromancy", 27)])
async def test_grim_harvest_heals_twice_the_spell_level_or_three_times_for_necromancy(client, level, school, healed):
    cid = await _wizard(client, 5, "necromancy")
    await _hp(client, cid, 100, 40)
    r = await _use(client, cid, HARVEST, params={"level": str(level), "school": school, "creature": "living"})
    assert r.status_code == 200, r.text
    assert r.json()["healed"] == healed and (await _full(client, cid))["current_hit_points"] == 40 + healed
    assert (await _turn(client, cid)).get("action_used") is not True  # nessuna azione


async def test_grim_harvest_works_once_per_turn_and_never_beyond_the_maximum(client):
    cid = await _wizard(client, 5, "necromancy")
    await _hp(client, cid, 100, 95)
    first = await _use(client, cid, HARVEST, params={"level": "3", "school": "necromancy", "creature": "living"})
    assert first.json()["healed"] == 5 and (await _full(client, cid))["current_hit_points"] == 100
    again = await _use(client, cid, HARVEST, params={"level": "3", "school": "necromancy", "creature": "living"})
    assert again.status_code == 409 and again.json()["detail"]["code"] == "once_per_turn"
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _use(client, cid, HARVEST, params={"level": "1", "school": "other", "creature": "living"})).status_code == 200


async def test_grim_harvest_gives_nothing_for_constructs_and_undead_and_does_not_use_up_the_turn(client):
    cid = await _wizard(client, 5, "necromancy")
    await _hp(client, cid, 100, 40)
    r = await _use(client, cid, HARVEST, params={"level": "3", "school": "necromancy", "creature": "construct_or_undead"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_benefit"
    assert (await _full(client, cid))["current_hit_points"] == 40
    assert (await _use(client, cid, HARVEST, params={"level": "3", "school": "necromancy", "creature": "living"})).status_code == 200


@pytest.mark.parametrize("params", [{"level": "0", "school": "other", "creature": "living"}, {"level": "10", "school": "other", "creature": "living"},
                                    {"level": "3", "school": "evocation", "creature": "living"}, {"level": "3", "school": "other"}])
async def test_grim_harvest_refuses_bad_choices(client, params):
    cid = await _wizard(client, 5, "necromancy")
    assert (await _use(client, cid, HARVEST, params=params)).status_code == 422


async def test_grim_harvest_is_the_necromancers(client):
    assert await _ability(client, await _wizard(client, 5, "evocation"), HARVEST) is None
    assert await _ability(client, await _wizard(client, 1), HARVEST) is None


# ---------------------------------------------------------------------------
# Servitori Non Morti
# ---------------------------------------------------------------------------

async def test_undead_thralls_adds_animate_dead_to_the_book_unprepared(client):
    assert "Animare morti" not in await _spells(client, await _wizard(client, 5, "necromancy"))
    cid = await _wizard(client, 6, "necromancy")
    spell = (await _spells(client, cid))["Animare morti"]
    assert spell["in_spellbook"] is True and spell["is_prepared"] is False and spell["always_prepared"] is False
    assert spell["srd_index"] == "animate-dead" and spell["level"] == 3 and spell["school"] == "necromancy"
    assert spell["class_id"] == (await _full(client, cid))["classes"][0]["id"]


async def test_undead_thralls_does_not_duplicate_a_spell_the_wizard_already_has(client):
    cid = await _wizard(client, 5, "necromancy")
    sid = await _spell(client, cid, "Animare morti", 3, srd_index="animate-dead", school="necromancy")
    r = await client.patch(f"/characters/{cid}/classes/{(await _full(client, cid))['classes'][0]['id']}", json={"level": 6})
    assert r.status_code == 200, r.text
    rows = [s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["srd_index"] == "animate-dead"]
    assert len(rows) == 1 and rows[0]["id"] == sid and rows[0]["in_spellbook"] is True


async def _summon(client, cid, **extra):
    body = {"kind": "summon", "name": "Scheletro", "max_hp": 13, "armor_class": 13, **extra}
    return await client.post(f"/characters/{cid}/companions", json=body)


async def test_a_summoned_undead_gets_the_wizard_level_in_hit_points_and_proficiency_in_damage(client):
    cid = await _wizard(client, 6, "necromancy")  # competenza +3
    r = await _summon(client, cid, spell_school="necromancy")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["max_hp"] == 13 + 6 and body["current_hp"] == 13 + 6 and body["damage_bonus_extra"] == 3


@pytest.mark.parametrize("level,school", [(5, "necromancy"), (6, "conjuration"), (6, None)])
async def test_thralls_help_only_necromancy_undead_of_a_necromancer_of_level_6(client, level, school):
    cid = await _wizard(client, level, "necromancy")
    r = await _summon(client, cid, **({"spell_school": school} if school else {}))
    assert r.status_code == 201 and r.json()["max_hp"] == 13 and r.json()["damage_bonus_extra"] == 0


# ---------------------------------------------------------------------------
# Impervio alla Non Morte
# ---------------------------------------------------------------------------

async def test_inured_to_undeath_gives_resistance_to_necrotic_damage_from_level_10(client):
    low = await _wizard(client, 9, "necromancy")
    await _hp(client, low)
    r = await client.patch(f"/characters/{low}/hp", json={"op": "damage", "value": 20, "damage_type": "necrotic"})
    assert r.json()["current_hit_points"] == 80
    cid = await _wizard(client, 10, "necromancy")
    await _hp(client, cid)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 20, "damage_type": "necrotic"})
    assert r.json()["current_hit_points"] == 90
    assert await _ability(client, cid, INURED) is not None


async def test_inured_to_undeath_keeps_the_maximum_hit_points_from_being_reduced(client):
    plain = await _wizard(client, 10, "evocation")
    cid = await _wizard(client, 10, "necromancy")
    for who in (plain, cid):
        await _hp(client, who)
        await client.patch(f"/characters/{who}/conditions", json={"conditions": {"exhaustion": 4}})
    assert (await _full(client, plain))["computed"]["hp_max_effective"] == 50  # la spossatezza 4 dimezza il massimo
    assert (await _full(client, cid))["computed"]["hp_max_effective"] == 100


# ---------------------------------------------------------------------------
# Comandare Non Morti
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("intelligence,note", [("lt8", "command_undead_low"), ("8_11", "command_undead_mid"), ("12plus", "command_undead_high")])
async def test_command_undead_is_a_charisma_save_with_a_note_for_the_creatures_intelligence(client, intelligence, note):
    cid = await _wizard(client, 14, "necromancy", intelligence=16)  # competenza +5, Int +3
    assert (await _use(client, cid, COMMAND, params={"intelligence": "mud"})).status_code == 422
    r = await _use(client, cid, COMMAND, params={"intelligence": intelligence})
    assert r.status_code == 200, r.text
    assert (await _turn(client, cid))["action_used"] is True and r.json()["targets"] == [COMMAND]
    effect = await _effect(client, cid, COMMAND)
    assert (effect["condition"], effect["save_ability"], effect["save_dc"], effect["note"]) == ("custom:commanded_undead", "charisma", 16, note)
    assert effect["immune_on_success"] is True
    assert (await _states(client, cid))["command_undead"]["data"]["intelligence"] == intelligence


async def test_a_new_command_replaces_the_creature_that_was_commanded(client):
    cid = await _wizard(client, 14, "necromancy")
    await _use(client, cid, COMMAND, params={"intelligence": "lt8"})
    await client.post(f"/characters/{cid}/turn/new")
    await _use(client, cid, COMMAND, params={"intelligence": "12plus"})
    states = [s for s in (await _full(client, cid))["active_states"] if s["key"] == "command_undead"]
    assert len(states) == 1 and states[0]["data"]["intelligence"] == "12plus"


# ---------------------------------------------------------------------------
# Alchimia Minore
# ---------------------------------------------------------------------------

async def test_minor_alchemy_lasts_an_hour_while_the_wizard_concentrates(client):
    cid = await _wizard(client, 2, "transmutation")
    r = await _use(client, cid, ALCHEMY)
    assert r.status_code == 200, r.text
    state = (await _states(client, cid))["minor_alchemy"]
    assert state["rounds_left"] == 600
    assert (await _full(client, cid))["settings"]["concentration_item_spell"]["feature_key"] == ALCHEMY
    await client.patch(f"/characters/{cid}/concentration", json={"spell_id": None})
    assert "minor_alchemy" not in await _states(client, cid)


# ---------------------------------------------------------------------------
# Pietra del Trasmutatore
# ---------------------------------------------------------------------------

async def _stone(client, cid, benefit, **extra):
    return await _use(client, cid, STONE, params={"benefit": benefit, **extra})


async def test_the_stone_is_made_with_one_chosen_benefit_and_a_new_one_replaces_it(client):
    cid = await _wizard(client, 6, "transmutation")
    assert (await _stone(client, cid, "mud")).status_code == 422
    assert (await _stone(client, cid, "resistance")).status_code == 422  # serve il tipo di danno
    assert (await _stone(client, cid, "resistance", damage_type="necrotic")).status_code == 422
    assert (await _stone(client, cid, "darkvision")).status_code == 200
    assert (await _states(client, cid))["transmuters_stone"]["data"]["benefit"] == "darkvision"
    await _stone(client, cid, "constitution_save")
    stones = [s for s in (await _full(client, cid))["active_states"] if s["key"] == "transmuters_stone"]
    assert len(stones) == 1 and stones[0]["data"]["benefit"] == "constitution_save"


async def test_the_stone_benefits_apply_while_it_is_with_the_wizard(client):
    cid = await _wizard(client, 6, "transmutation")
    base = (await _full(client, cid))["computed"]
    await _stone(client, cid, "darkvision")
    assert {"type": "darkvision", "range_ft": 60} in (await _full(client, cid))["computed"]["senses"]
    await _stone(client, cid, "speed")
    assert (await _full(client, cid))["computed"]["speed"] == base["speed"] + 10
    await _stone(client, cid, "constitution_save")
    plain = await _wizard(client, 6, "transmutation")
    stoned = (await client.post(f"/characters/{cid}/saving_throws/constitution/roll", json={"die": 10})).json()
    unstoned = (await client.post(f"/characters/{plain}/saving_throws/constitution/roll", json={"die": 10})).json()
    assert stoned["bonus"] == unstoned["bonus"] + 3  # la competenza (+3 al 6° livello) vale per i TS Costituzione


async def test_the_stone_resistance_halves_the_chosen_damage_type_only(client):
    cid = await _wizard(client, 6, "transmutation")
    await _hp(client, cid)
    await _stone(client, cid, "resistance", damage_type="fire")
    assert (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 20, "damage_type": "fire"})).json()["current_hit_points"] == 90
    assert (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 20, "damage_type": "cold"})).json()["current_hit_points"] == 70


async def test_a_transmutation_cast_lets_the_wizard_change_the_benefit(client):
    cid = await _wizard(client, 6, "transmutation")
    refused = await _use(client, cid, STONE_CHANGE, params={"benefit": "speed"})
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "feature_unavailable"  # nessuna pietra
    await _stone(client, cid, "darkvision")
    assert (await _use(client, cid, STONE_CHANGE, params={"benefit": "speed"})).status_code == 409  # nessun lancio
    spell = await _spell(client, cid, "Passo velato", 2, school="transmutation", casting_time="1 azione")
    assert (await _cast(client, cid, spell, slot_level=2)).status_code == 200
    r = await _use(client, cid, STONE_CHANGE, params={"benefit": "speed"})
    assert r.status_code == 200, r.text
    assert (await _states(client, cid))["transmuters_stone"]["data"]["benefit"] == "speed"
    assert (await _use(client, cid, STONE_CHANGE, params={"benefit": "darkvision"})).status_code == 409  # una volta per lancio


async def test_a_cantrip_or_another_school_does_not_let_the_wizard_change_the_stone(client):
    cid = await _wizard(client, 6, "transmutation")
    await _stone(client, cid, "darkvision")
    for level, school in ((0, "transmutation"), (1, "evocation")):
        spell = await _spell(client, cid, f"Prova {school}{level}", level, school=school, casting_time="1 azione")
        await _cast(client, cid, spell, slot_level=max(1, level))
        assert (await _use(client, cid, STONE_CHANGE, params={"benefit": "speed"})).status_code == 409


# ---------------------------------------------------------------------------
# Mutaforma
# ---------------------------------------------------------------------------

async def test_shapechanger_adds_polymorph_to_the_book_and_casts_it_once_without_a_slot(client):
    assert "Metamorfosi" not in await _spells(client, await _wizard(client, 9, "transmutation"))
    cid = await _wizard(client, 10, "transmutation")
    poly = (await _spells(client, cid))["Metamorfosi"]
    assert poly["in_spellbook"] is True and poly["is_prepared"] is False and poly["school"] == "transmutation"
    assert poly["pact_cast"]["kind"] == "arcanum" and poly["pact_cast"]["feature_key"] == SHAPE and poly["pact_cast"]["uses_left"] == 1
    before = {s["level"]: s["used"] for s in (await _full(client, cid))["spell_slots"]}
    r = await _cast(client, cid, poly["id"], free_cast=True)
    assert r.status_code == 200, r.text
    assert {s["level"]: s["used"] for s in (await _full(client, cid))["spell_slots"]} == before
    assert (await _ability(client, cid, SHAPE))["uses"] == 0
    await client.post(f"/characters/{cid}/turn/new")
    again = await _cast(client, cid, poly["id"], free_cast=True)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "no_uses"
    await _rest(client, cid, "short")
    assert (await _ability(client, cid, SHAPE))["uses"] == 1


async def test_shapechanger_can_still_be_cast_normally_with_a_slot(client):
    cid = await _wizard(client, 10, "transmutation")
    poly = (await _spells(client, cid))["Metamorfosi"]["id"]
    r = await _cast(client, cid, poly, slot_level=4)
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, SHAPE))["uses"] == 1


# ---------------------------------------------------------------------------
# Maestro Trasmutatore e le sue opzioni
# ---------------------------------------------------------------------------

async def _master(client, cid):
    await _stone(client, cid, "darkvision")
    await client.post(f"/characters/{cid}/turn/new")


async def test_each_master_transmuter_option_consumes_the_stone_and_blocks_a_new_one_until_a_long_rest(client):
    for key, params in ((PANACEA, {"mode": "other", "removal": {"targets": ["other"]}}), (YOUTH, {}), (MAJOR, {})):
        cid = await _wizard(client, 14, "transmutation")
        assert (await _use(client, cid, key, params=params)).status_code == 409  # senza pietra
        await _master(client, cid)
        r = await _use(client, cid, key, params=params)
        assert r.status_code == 200, r.text
        assert (await _turn(client, cid))["action_used"] is True and "transmuters_stone" not in await _states(client, cid)
        await client.post(f"/characters/{cid}/turn/new")
        blocked = await _stone(client, cid, "speed")
        assert blocked.status_code == 409 and blocked.json()["detail"]["code"] == "feature_unavailable"
        await _rest(client, cid, "long")
        assert (await _stone(client, cid, "speed")).status_code == 200


async def test_master_transmuter_options_need_level_14_and_the_school(client):
    for level, school in ((13, "transmutation"), (14, "necromancy")):
        cid = await _wizard(client, level, school)
        for key in (PANACEA, YOUTH, LIFE, MAJOR):
            assert await _ability(client, cid, key) is None


async def test_panacea_on_oneself_restores_every_hit_point_and_cures_poison(client):
    cid = await _wizard(client, 14, "transmutation")
    await _hp(client, cid, 100, 10)
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"poisoned": True}})
    await _master(client, cid)
    r = await _use(client, cid, PANACEA, params={"mode": "self", "removal": {"targets": ["self"]}})
    assert r.status_code == 200, r.text
    full = await _full(client, cid)
    assert full["current_hit_points"] == 100 and not full["conditions"].get("poisoned")


async def test_panacea_on_another_creature_outside_the_evening_is_a_visible_note(client):
    cid = await _wizard(client, 14, "transmutation")
    await _hp(client, cid, 100, 10)
    await _master(client, cid)
    assert (await _use(client, cid, PANACEA, params={"mode": "mud"})).status_code == 422
    assert (await _use(client, cid, PANACEA, params={"mode": "other"})).status_code == 422  # senza il foglio comune non si usa
    r = await _use(client, cid, PANACEA, params={"mode": "other", "removal": {"targets": ["other"]}})
    assert r.status_code == 200 and (await _full(client, cid))["current_hit_points"] == 10
    assert "maledizione" in " ".join(x["it"] for x in r.json()["removal"])
    assert "PF" in r.json()["message"]["it"] and "hit points" in r.json()["message"]["en"]


async def test_restore_youth_rolls_3d10_years(client, monkeypatch):
    cid = await _wizard(client, 14, "transmutation")
    await _master(client, cid)
    monkeypatch.setattr(random, "randint", lambda a, b: 4)
    r = await _use(client, cid, YOUTH)
    assert r.status_code == 200 and r.json()["rolls"] == [4, 4, 4] and "13" in r.json()["message"]["it"]


async def test_restore_life_lets_the_wizard_cast_raise_dead_once_without_a_slot_or_the_book(client):
    cid = await _wizard(client, 14, "transmutation")
    assert "Rianimare morti" not in await _spells(client, cid)
    await _master(client, cid)
    assert (await _use(client, cid, LIFE)).status_code == 200
    spell = (await _spells(client, cid))["Rianimare morti"]
    assert spell["level"] == 5 and spell["in_spellbook"] is False
    await client.post(f"/characters/{cid}/turn/new")
    before = {s["level"]: s["used"] for s in (await _full(client, cid))["spell_slots"]}
    r = await _cast(client, cid, spell["id"], free_cast=True)
    assert r.status_code == 200, r.text
    assert {s["level"]: s["used"] for s in (await _full(client, cid))["spell_slots"]} == before
    assert "Rianimare morti" not in await _spells(client, cid)  # il lancio chiude lo stato e l'incantesimo sparisce


async def test_restore_life_without_casting_leaves_no_permanent_spell_after_a_long_rest(client):
    cid = await _wizard(client, 14, "transmutation")
    await _master(client, cid)
    await _use(client, cid, LIFE)
    await _rest(client, cid, "long")
    assert "Rianimare morti" not in await _spells(client, cid)
