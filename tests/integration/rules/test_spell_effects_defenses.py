"""Effetti degli incantesimi: resistenze, immunità, vantaggi, velocità, sensi, tratti e condizioni."""
from __future__ import annotations

import random

import pytest

from core.rules.catalog.spells import spell_effect
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session
from tests.integration.rules.test_2014_bard import _roll_keys
from tests.integration.rules.test_2014_bard_inspiration import _seat
from tests.integration.rules.test_spell_effects_cast import _full, _states


async def _table(client, factory, name, srd, level, hero_edition=None, caster_edition=None):
    """Una serata con un eroe e un chierico che conosce l'incantesimo, con uno slot del suo livello. `(eroe, lanciatore, incantesimo)`."""
    _, hero = await seed_session(factory)
    as_user(GM_ID)
    caster = (await client.post("/characters", json={"name": "Chierico"})).json()["id"]
    if caster_edition:
        await client.patch(f"/characters/{caster}", json={"rules_edition": caster_edition})
    r = await client.post(f"/characters/{caster}/spells", json={"name": name, "srd_index": srd, "level": level, "is_concentration": True})
    assert r.status_code == 201, r.text
    if level:
        assert (await client.post(f"/characters/{caster}/spell_slots", json={"level": level, "total": 2})).status_code == 201
    await _seat(factory, caster, GM_ID)
    as_user(PLAYER_ID)
    if hero_edition:
        await client.patch(f"/characters/{hero}", json={"rules_edition": hero_edition})
    await client.patch(f"/characters/{hero}/hp", json={"op": "set_max", "value": 200})
    await client.patch(f"/characters/{hero}/hp", json={"op": "set_current", "value": 200})
    return hero, caster, r.json()["id"]


async def _cast(client, caster, spell, targets, level=None, **extra):
    as_user(GM_ID)
    body = {"targets": targets, **({"slot_level": level} if level else {}), **extra}
    r = await client.post(f"/characters/{caster}/spells/{spell}/use", json=body)
    assert r.status_code == 200, r.text
    return r


async def _sheet(client, cid, user=PLAYER_ID):
    as_user(user)
    return await _full(client, cid)


async def _hit(client, cid, value, damage_type, **extra):
    as_user(PLAYER_ID)
    before = (await _full(client, cid))["current_hit_points"]
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": value, "damage_type": damage_type, **extra})
    assert r.status_code == 200, r.text
    return before - (await _full(client, cid))["current_hit_points"]


# --- catalogo -----------------------------------------------------------------------------------------------------

BOTH = ["stoneskin", "aura-of-life", "aura-of-purity", "fire-shield", "feign-death", "protection-from-energy",
        "protection-from-poison", "beacon-of-hope", "blur", "foresight", "holy-aura", "protection-from-evil-and-good",
        "circle-of-power", "dispel-evil-and-good", "invisibility", "greater-invisibility", "heroism", "mind-blank",
        "heroes-feast", "fly", "haste", "jump", "freedom-of-movement", "enhance-ability", "darkvision", "true-seeing",
        "see-invisibility", "levitate", "water-breathing", "water-walk", "feather-fall", "blade-ward", "resistance"]


@pytest.mark.parametrize("edition", ["2014", "2024"])
@pytest.mark.parametrize("srd", BOTH)
def test_every_listed_spell_is_in_the_catalog_and_does_something(edition, srd):
    found = spell_effect(edition, srd)
    if srd == "blade-ward" and edition == "2024":
        assert found is not None  # il dado negativo è sugli attaccanti: solo testo
        return
    assert found is not None, (edition, srd)
    _, variant = found
    d = {"slot_level": 4, "edition": edition, "choices": {"damage_type": "fire", "shield": "warm", "ability": "strength"}}
    assert variant.modifiers(d) or variant.options or variant.condition or variant.track, (edition, srd)


def test_only_2024_has_fount_of_moonlight_and_2014_has_no_blur_difference():
    assert spell_effect("2014", "fount-of-moonlight") is None and spell_effect("2024", "fount-of-moonlight") is not None


def test_senses_differ_by_edition():
    d = {"edition": "x"}
    assert spell_effect("2014", "darkvision")[1].modifiers(d)[0].value == 60
    assert spell_effect("2024", "darkvision")[1].modifiers(d)[0].value == 150


@pytest.mark.parametrize("edition,name", [("2024", "Preveggenza"), ("2014", "Previsione"), ("2024", "Mente Vuota"), ("2014", "Vuoto Mentale"),
                                          ("2024", "Protezione dal Male e dal Bene"), ("2014", "Protezione dal Bene e dal Male"),
                                          ("2024", "Protezione dal Veleno"), ("2014", "Protezione dai Veleni")])
def test_names_of_both_editions_resolve(edition, name):
    assert spell_effect(edition, None, name) is not None


# --- resistenze ---------------------------------------------------------------------------------------------------

async def test_stoneskin_2014_resists_only_when_the_player_confirms_a_nonmagical_hit(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Stoneskin", "stoneskin", 4)
    await _cast(client, caster, spell, [hero], level=4)
    assert not (await _sheet(client, hero))["computed"]["resistances"]
    as_user(PLAYER_ID)
    assert "spell:stoneskin:nonmagical" in await _roll_keys(client, hero, "damage_taken", damage_type="piercing")
    assert "spell:stoneskin:nonmagical" not in await _roll_keys(client, hero, "damage_taken", damage_type="fire")
    assert await _hit(client, hero, 10, "bludgeoning") == 10  # senza conferma il colpo (magico?) resta pieno
    assert await _hit(client, hero, 10, "bludgeoning", options=["spell:stoneskin:nonmagical"]) == 5


async def test_stoneskin_2024_halves_every_physical_hit_and_ends_with_concentration(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Stoneskin", "stoneskin", 4, hero_edition="2024", caster_edition="2024")
    assert await _hit(client, hero, 10, "bludgeoning") == 10
    await _cast(client, caster, spell, [hero], level=4)
    assert "bludgeoning" in (await _sheet(client, hero))["computed"]["resistances"]
    assert await _hit(client, hero, 10, "bludgeoning") == 5
    assert await _hit(client, hero, 10, "fire") == 10
    as_user(GM_ID)
    await client.patch(f"/characters/{caster}/concentration", json={"spell_id": None})
    assert await _hit(client, hero, 10, "slashing") == 10


async def test_protection_from_energy_uses_the_chosen_type(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Protection from Energy", "protection-from-energy", 3)
    as_user(GM_ID)
    bad = await client.post(f"/characters/{caster}/spells/{spell}/use", json={"targets": [hero], "slot_level": 3, "choices": {"damage_type": "psychic"}})
    assert bad.status_code == 422 and bad.json()["detail"]["code"] == "invalid_choice"
    await _cast(client, caster, spell, [hero], level=3, choices={"damage_type": "lightning"})
    assert await _hit(client, hero, 10, "lightning") == 5
    assert await _hit(client, hero, 10, "fire") == 10


async def test_fire_shield_choice_gives_the_opposite_resistance(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Fire Shield", "fire-shield", 4)
    await _cast(client, caster, spell, [], level=4, choices={"shield": "warm"})
    as_user(GM_ID)
    sheet = await _full(client, caster)
    assert sheet["computed"]["resistances"] == ["cold"]


async def test_resistance_2024_reduces_the_chosen_type_by_a_d4_once_per_turn(client, test_session_factory, monkeypatch):
    hero, caster, spell = await _table(client, test_session_factory, "Resistance", "resistance", 0, hero_edition="2024", caster_edition="2024")
    await _cast(client, caster, spell, [hero], choices={"damage_type": "fire"})
    as_user(PLAYER_ID)
    assert "spell:resistance:reduce" in await _roll_keys(client, hero, "damage_taken", damage_type="fire")
    assert "spell:resistance:reduce" not in await _roll_keys(client, hero, "damage_taken", damage_type="cold")
    monkeypatch.setattr(random, "randint", lambda a, b: 3)
    assert await _hit(client, hero, 10, "fire", options=["spell:resistance:reduce"]) == 7
    assert "spell:resistance:reduce" not in await _roll_keys(client, hero, "damage_taken", damage_type="fire")  # una volta per turno


async def test_blade_ward_2014_halves_only_confirmed_weapon_damage_and_lasts_one_round(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Blade Ward", "blade-ward", 0)
    await _cast(client, caster, spell, [])
    as_user(GM_ID)
    assert not (await _full(client, caster))["computed"]["resistances"]
    assert "spell:blade_ward:weapon" in await _roll_keys(client, caster, "damage_taken", damage_type="slashing")
    assert "spell:blade_ward:weapon" not in await _roll_keys(client, caster, "damage_taken", damage_type="fire")
    await client.patch(f"/characters/{caster}/hp", json={"op": "set_max", "value": 100})
    await client.patch(f"/characters/{caster}/hp", json={"op": "set_current", "value": 100})
    for opts, left in (([], 90), (["spell:blade_ward:weapon"], 85)):
        r = await client.patch(f"/characters/{caster}/hp", json={"op": "damage", "value": 10, "damage_type": "slashing", "options": opts})
        assert r.status_code == 200, r.text
        assert (await _full(client, caster))["current_hit_points"] == left
    await client.post(f"/characters/{caster}/rounds/tick")
    assert "spell:blade_ward:weapon" not in await _roll_keys(client, caster, "damage_taken", damage_type="slashing")


async def test_protection_from_poison_resists_and_offers_advantage_on_the_save(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Protection from Poison", "protection-from-poison", 2)
    await _cast(client, caster, spell, [hero], level=2)
    assert await _hit(client, hero, 10, "poison") == 5
    as_user(PLAYER_ID)
    assert "spell:protection_from_poison:save" in await _roll_keys(client, hero, "save", ability="constitution")
    assert "spell:protection_from_poison:save" not in await _roll_keys(client, hero, "skill", skill="athletics")


async def test_protection_from_poison_2024_ends_poisoned(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Protection from Poison", "protection-from-poison", 2, hero_edition="2024", caster_edition="2024")
    as_user(PLAYER_ID)
    assert (await client.patch(f"/characters/{hero}/conditions", json={"conditions": {"poisoned": True}})).status_code == 200
    await _cast(client, caster, spell, [hero], level=2)
    assert not (await _sheet(client, hero))["conditions"].get("poisoned")


# --- vantaggi -----------------------------------------------------------------------------------------------------

async def test_beacon_of_hope_gives_advantage_on_wisdom_and_death_saves(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Beacon of Hope", "beacon-of-hope", 3)
    await _cast(client, caster, spell, [hero], level=3)
    as_user(PLAYER_ID)
    for path in ("saving_throws/wisdom/roll", "saving_throws/strength/roll"):
        r = await client.post(f"/characters/{hero}/{path}", json={"die": 10})
        assert r.status_code == 200, r.text
        assert (r.json().get("mode") == "advantage") == path.endswith("wisdom/roll"), (path, r.json())


async def test_foresight_advantage_on_attacks_checks_and_saves(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Foresight", "foresight", 9)
    await _cast(client, caster, spell, [hero], level=9)
    as_user(PLAYER_ID)
    for path in ("saving_throws/strength/roll", "skills/athletics/roll", "ability_checks/strength/roll"):
        r = await client.post(f"/characters/{hero}/{path}", json={"die": 10})
        assert r.status_code == 200, r.text
        assert r.json().get("mode") == "advantage", (path, r.json())


async def test_enhance_ability_advantage_only_on_the_chosen_ability(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Enhance Ability", "enhance-ability", 2)
    await _cast(client, caster, spell, [hero], level=2, choices={"ability": "strength"})
    as_user(PLAYER_ID)
    modes = {}
    for path in ("skills/athletics/roll", "skills/acrobatics/roll", "ability_checks/strength/roll"):
        modes[path] = (await client.post(f"/characters/{hero}/{path}", json={"die": 10})).json().get("mode")
    assert modes == {"skills/athletics/roll": "advantage", "skills/acrobatics/roll": "normal", "ability_checks/strength/roll": "advantage"}
    sheet = await _sheet(client, hero)
    assert sheet["carry_capacity"] > 0


async def test_enhance_ability_dexterity_gives_advantage_on_initiative_only_for_dexterity(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Enhance Ability", "enhance-ability", 2)
    await _cast(client, caster, spell, [hero], level=2, choices={"ability": "dexterity"})
    as_user(PLAYER_ID)
    assert (await client.post(f"/characters/{hero}/dice/initiative", json={"die": 10})).json().get("mode") == "advantage"
    await _cast(client, caster, spell, [hero], level=2, choices={"ability": "strength"})
    as_user(PLAYER_ID)
    assert (await client.post(f"/characters/{hero}/dice/initiative", json={"die": 10})).json().get("mode") == "normal"


# --- velocità, sensi, tratti ---------------------------------------------------------------------------------------

async def test_fly_gives_a_fly_speed_and_loses_it_with_the_effect(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Fly", "fly", 3)
    await _cast(client, caster, spell, [hero], level=3)
    assert (await _sheet(client, hero))["computed"]["fly_speed"] == 60
    as_user(GM_ID)
    await client.patch(f"/characters/{caster}/concentration", json={"spell_id": None})
    assert (await _sheet(client, hero))["computed"]["fly_speed"] is None


async def test_haste_doubles_speed_and_adds_two_ac_and_dex_save_advantage(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Haste", "haste", 3)
    before = await _sheet(client, hero)
    await _cast(client, caster, spell, [hero], level=3)
    after = await _sheet(client, hero)
    assert after["computed"]["speed"] == before["computed"]["speed"] * 2 and after["ac"] == before["ac"] + 2
    as_user(PLAYER_ID)
    r = await client.post(f"/characters/{hero}/saving_throws/dexterity/roll", json={"die": 10})
    assert r.json().get("mode") == "advantage"


async def test_darkvision_adds_a_sense_per_edition(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Darkvision", "darkvision", 2, hero_edition="2024", caster_edition="2024")
    await _cast(client, caster, spell, [hero], level=2)
    assert {"type": "darkvision", "range_ft": 150} in (await _sheet(client, hero))["computed"]["senses"]


async def test_freedom_of_movement_2024_adds_a_swim_speed(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Freedom of Movement", "freedom-of-movement", 4, hero_edition="2024", caster_edition="2024")
    await _cast(client, caster, spell, [hero], level=4)
    computed = (await _sheet(client, hero))["computed"]
    assert computed["swim_speed"] == computed["speed"]


async def test_jump_2014_triples_the_long_jump(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Jump", "jump", 1)
    await _cast(client, caster, spell, [hero], level=1)
    assert (await _sheet(client, hero))["computed"]["long_jump_bonus_ft"] == 20  # Forza 10 di base: 10 ft + 20 = 30


async def test_jump_2014_refuses_a_second_target(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Jump", "jump", 2)
    as_user(GM_ID)
    r = await client.post(f"/characters/{caster}/spells/{spell}/use", json={"targets": [hero, caster], "slot_level": 2})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_target"
    await _cast(client, caster, spell, [hero], level=2)
    spells = {s["name"]: s for s in (await client.get(f"/characters/{caster}/spells")).json()}
    assert spells["Jump"]["effect"]["max_targets_by_slot"]["2"] == 1


def test_target_counts_follow_the_edition():
    jump, freedom = spell_effect("2014", "jump")[0], spell_effect("2014", "freedom-of-movement")[0]
    assert [jump.max_targets("2014", s) for s in (1, 3)] == [1, 1] and [jump.max_targets("2024", s) for s in (1, 3)] == [1, 3]
    assert freedom.max_targets("2014", 6) == 1 and freedom.max_targets("2024", 6) == 3
    for srd in ("enhance-ability", "invisibility", "heroism", "longstrider", "bless", "fly"):  # scalano uguale nelle due edizioni
        fx = spell_effect("2014", srd)[0]
        assert fx.max_targets("2014", 5) == fx.max_targets("2024", 5) > 1, srd


async def test_feather_fall_is_tracked_with_a_clock_on_the_caster(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Feather Fall", "feather-fall", 1)
    await _cast(client, caster, spell, [hero], level=1)
    assert await _states(client, hero, PLAYER_ID, "spell:feather_fall")
    assert await _states(client, caster, GM_ID, "spell_cast:feather_fall")


# --- condizioni ---------------------------------------------------------------------------------------------------

async def test_invisibility_sets_the_condition_and_it_falls_with_the_effect(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Invisibility", "invisibility", 2)
    await _cast(client, caster, spell, [hero], level=2)
    assert (await _sheet(client, hero))["conditions"].get("invisible") is True
    as_user(GM_ID)
    await client.patch(f"/characters/{caster}/concentration", json={"spell_id": None})
    assert not (await _sheet(client, hero))["conditions"].get("invisible")
    assert await _states(client, hero, PLAYER_ID, "spell:invisibility") == []


def test_invisibility_ends_when_the_target_attacks_or_casts_but_not_the_greater_one():
    from types import SimpleNamespace

    from api.services.rules_states import end_on_action
    from core.rules.states import begin_state
    from api.services.spell_effects import spell_state_spec

    for key, edition, action, left in (("invisibility", "2014", "attack", False), ("invisibility", "2024", "cast", False),
                                       ("greater_invisibility", "2014", "attack", True)):
        char = SimpleNamespace(conditions={}, active_states=[], settings={}, turn_state={}, spells=[])
        data = {"spell_key": key, "edition": edition, "caster_id": 1}
        begin_state(char, spell_state_spec(f"spell:{key}", data), f"spell:{key}", key)
        assert char.conditions["invisible"] is True
        end_on_action(char, action)
        assert bool(char.conditions.get("invisible")) is left, (key, action)


async def test_greater_invisibility_keeps_the_condition_when_attacking(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Greater Invisibility", "greater-invisibility", 4)
    await _cast(client, caster, spell, [hero], level=4)
    assert (await _sheet(client, hero))["conditions"].get("invisible") is True


async def test_invisibility_that_was_already_on_stays_after_the_effect(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Invisibility", "invisibility", 2)
    as_user(PLAYER_ID)
    await client.patch(f"/characters/{hero}/conditions", json={"conditions": {"invisible": True}})
    await _cast(client, caster, spell, [hero], level=2)
    as_user(GM_ID)
    await client.patch(f"/characters/{caster}/concentration", json={"spell_id": None})
    assert (await _sheet(client, hero))["conditions"].get("invisible") is True


async def test_invisibility_from_a_2014_caster_on_a_2024_ally_uses_the_2014_variant(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Invisibility", "invisibility", 2, hero_edition="2024", caster_edition="2014")
    await _cast(client, caster, spell, [hero], level=2)
    [state] = await _states(client, hero, PLAYER_ID, "spell:invisibility")
    assert state["data"]["edition"] == "2014"
    assert "attack" in state["ends_on"]


async def test_heroism_blocks_frightened_while_it_lasts(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Heroism", "heroism", 1)
    await _cast(client, caster, spell, [hero], level=1)
    [state] = await _states(client, hero, PLAYER_ID, "spell:heroism")
    assert state["immune_conditions"] == ["frightened"]


async def test_feign_death_is_incapacitated_with_no_speed_and_resists_all_but_psychic(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Feign Death", "feign-death", 3)
    await _cast(client, caster, spell, [hero], level=3)
    sheet = await _sheet(client, hero)
    assert sheet["conditions"].get("incapacitated") and sheet["computed"]["speed"] == 0
    assert "psychic" not in sheet["computed"]["resistances"] and "fire" in sheet["computed"]["resistances"]
    as_user(GM_ID)
    await client.patch(f"/characters/{caster}/concentration", json={"spell_id": None})  # senza concentrazione: lo stato resta
    assert (await _sheet(client, hero))["conditions"].get("incapacitated")


async def test_mind_blank_is_immune_to_psychic_damage(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Mind Blank", "mind-blank", 8)
    await _cast(client, caster, spell, [hero], level=8)
    assert await _hit(client, hero, 10, "psychic") == 0
