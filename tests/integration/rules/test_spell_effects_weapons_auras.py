"""Effetti degli incantesimi (Task 9): armi incantate, danni extra agli attacchi, Velocità (azione extra e letargia) e aure vive."""
from __future__ import annotations

import pytest

from core.rules.catalog.spells import spell_effect
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user
from tests.integration.rules.test_2014_bard import _roll_keys
from tests.integration.rules.test_2014_fighter_eldritch_knight import _sword
from tests.integration.rules.test_spell_effects_cast import _states
from tests.integration.rules.test_spell_effects_defenses import _cast, _hit, _sheet, _table


async def _attack(client, cid, wid, die=10, **body):
    as_user(PLAYER_ID)
    r = await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": die, "confirm_extra_attack": True, **body})
    assert r.status_code == 200, r.text
    return r.json()


async def _new_turn(client, cid, user=PLAYER_ID):
    as_user(user)
    r = await client.post(f"/characters/{cid}/turn/new")
    assert r.status_code == 200, r.text
    return r.json()


async def _end_concentration(client, caster):
    as_user(GM_ID)
    assert (await client.patch(f"/characters/{caster}/concentration", json={"spell_id": None})).status_code == 200


# --- catalogo -----------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("edition,srd", [("2014", "magic-weapon"), ("2024", "magic-weapon"), ("2014", "elemental-weapon"), ("2024", "elemental-weapon"),
                                         ("2014", "divine-favor"), ("2024", "divine-favor"), ("2014", "crusaders-mantle"), ("2024", "crusaders-mantle"),
                                         ("2024", "fount-of-moonlight"), ("2024", "conjure-minor-elementals"), ("2014", "haste"), ("2024", "haste")])
def test_every_entry_is_in_the_catalog_for_its_edition(edition, srd):
    assert spell_effect(edition, srd) is not None


def test_the_aura_spells_are_live_auras_not_up_to_twenty_targets():
    for srd in ("aura-of-life", "aura-of-purity", "circle-of-power", "holy-aura", "pass-without-trace", "crusaders-mantle"):
        effect, _ = spell_effect("2014", srd)
        assert effect.target.kind == "aura" and effect.max_targets("2014", 5) == 1, srd


def test_magic_weapon_bonus_follows_the_manual_of_each_edition():
    def bonus(edition, slot):
        _, variant = spell_effect(edition, "magic-weapon")
        return next(m.value for m in variant.modifiers({"slot_level": slot, "choices": {"item_id": "1"}}) if m.target == "attack")
    assert [bonus("2014", s) for s in (2, 3, 4, 5, 6, 9)] == [1, 1, 2, 2, 3, 3]
    assert [bonus("2024", s) for s in (2, 3, 5, 6, 9)] == [1, 2, 2, 3, 3]
    assert spell_effect("2014", "magic-weapon")[1].concentration and not spell_effect("2024", "magic-weapon")[1].concentration


# --- Arma Magica ---------------------------------------------------------------------------------------------------
async def _weapon_table(client, factory, srd="magic-weapon", name="Magic Weapon", level=2, **kw):
    hero, caster, spell = await _table(client, factory, name, srd, level, **kw)
    as_user(PLAYER_ID)
    sword = await _sword(client, hero)
    other = await _sword(client, hero)
    return hero, caster, spell, sword, other


async def test_magic_weapon_on_an_allys_weapon_adds_to_hit_and_damage_only_with_that_weapon(client, test_session_factory):
    hero, caster, spell, sword, other = await _weapon_table(client, test_session_factory)
    before = await _attack(client, hero, sword)
    await _cast(client, caster, spell, [hero], level=2, choices={"item_id": str(sword)})
    after = await _attack(client, hero, sword)
    assert after["to_hit_bonus"] == before["to_hit_bonus"] + 1 and after["is_magic"] is True
    assert after["damage_bonus"] == before["damage_bonus"] + 1
    plain = await _attack(client, hero, other)
    assert plain["to_hit_bonus"] == before["to_hit_bonus"] and plain["damage_bonus"] == before["damage_bonus"]
    assert await _states(client, hero, PLAYER_ID, "spell:magic_weapon")


@pytest.mark.parametrize("edition,slot,expected", [("2014", 3, 1), ("2014", 4, 2), ("2014", 6, 3), ("2024", 3, 2), ("2024", 6, 3)])
async def test_magic_weapon_scales_with_the_slot_of_the_edition(client, test_session_factory, edition, slot, expected):
    hero, caster, spell, sword, _ = await _weapon_table(client, test_session_factory, level=slot, caster_edition=edition)
    before = await _attack(client, hero, sword)
    await _cast(client, caster, spell, [hero], level=slot, choices={"item_id": str(sword)})
    assert (await _attack(client, hero, sword))["to_hit_bonus"] == before["to_hit_bonus"] + expected


async def test_magic_weapon_ends_with_the_concentration_2014(client, test_session_factory):
    hero, caster, spell, sword, _ = await _weapon_table(client, test_session_factory)
    before = await _attack(client, hero, sword)
    await _cast(client, caster, spell, [hero], level=2, choices={"item_id": str(sword)})
    await _end_concentration(client, caster)
    assert (await _attack(client, hero, sword))["to_hit_bonus"] == before["to_hit_bonus"]


async def test_the_weapon_must_be_a_nonmagical_weapon_of_the_target(client, test_session_factory):
    hero, caster, spell, sword, _ = await _weapon_table(client, test_session_factory)
    as_user(GM_ID)
    own = await _sword(client, caster)  # un'arma del lanciatore, non del bersaglio
    as_user(PLAYER_ID)
    magic = await _sword(client, hero, magic_bonus=1)
    as_user(GM_ID)
    for choices in ({"item_id": str(own)}, {"item_id": str(magic)}, {"item_id": "99999"}, {"item_id": "x"}, {}, {"item_id": str(sword), "damage_type": "fire"}):
        r = await client.post(f"/characters/{caster}/spells/{spell}/use", json={"targets": [hero], "slot_level": 2, "choices": choices})
        assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_choice", choices


async def test_the_weapons_of_a_seated_ally_are_listed_without_the_magical_ones(client, test_session_factory):
    hero, caster, spell, sword, other = await _weapon_table(client, test_session_factory)
    as_user(PLAYER_ID)
    await _sword(client, hero, magic_bonus=2)
    as_user(GM_ID)
    r = await client.get(f"/characters/{caster}/session-allies/{hero}/weapons")
    assert r.status_code == 200 and [w["id"] for w in r.json()] == [sword, other]
    assert (await client.get(f"/characters/{caster}/session-allies/99999/weapons")).status_code == 422


# --- Arma Elementale -----------------------------------------------------------------------------------------------
async def test_elemental_weapon_adds_to_hit_and_a_die_of_the_chosen_type_only_with_the_weapon(client, test_session_factory):
    hero, caster, spell, sword, other = await _weapon_table(client, test_session_factory, "elemental-weapon", "Elemental Weapon", 3)
    before = await _attack(client, hero, sword)
    await _cast(client, caster, spell, [hero], level=3, choices={"item_id": str(sword), "damage_type": "fire"})
    hit = await _attack(client, hero, sword)
    assert hit["to_hit_bonus"] == before["to_hit_bonus"] + 1 and hit["damage_bonus"] == before["damage_bonus"]
    assert len(hit["option_result"]["extra_rolls"]) == 1 and hit["option_result"]["extra_types"] == ["fire"]
    assert all(1 <= v <= 4 for v in hit["option_result"]["extra_rolls"])
    assert not (await _attack(client, hero, other)).get("option_result")


async def test_elemental_weapon_scales_to_two_and_three_dice(client, test_session_factory):
    hero, caster, spell, sword, _ = await _weapon_table(client, test_session_factory, "elemental-weapon", "Elemental Weapon", 7)
    await _cast(client, caster, spell, [hero], level=7, choices={"item_id": str(sword), "damage_type": "thunder"})
    hit = await _attack(client, hero, sword)
    assert len(hit["option_result"]["extra_rolls"]) == 3 and hit["option_result"]["extra_types"] == ["thunder"] * 3


# --- Favore Divino e altri danni extra ------------------------------------------------------------------------------
async def test_divine_favor_adds_a_d4_radiant_to_the_casters_weapon_attacks(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Divine Favor", "divine-favor", 1)
    as_user(GM_ID)
    sword = await _sword(client, caster)
    await _cast(client, caster, spell, [], level=1)
    as_user(GM_ID)
    r = await client.post(f"/characters/{caster}/items/{sword}/attack", json={"die": 10, "confirm_extra_attack": True})
    assert r.status_code == 200, r.text
    result = r.json()["option_result"]
    assert len(result["extra_rolls"]) == 1 and 1 <= result["extra_rolls"][0] <= 4 and result["extra_types"] == ["radiant"]
    as_user(PLAYER_ID)
    other = await _sword(client, hero)
    assert not (await _attack(client, hero, other)).get("option_result")  # l'effetto è del lanciatore


def test_divine_favor_needs_concentration_only_in_2014():
    assert spell_effect("2014", "divine-favor")[1].concentration and not spell_effect("2024", "divine-favor")[1].concentration


# --- Velocità ------------------------------------------------------------------------------------------------------
async def test_haste_gives_an_extra_action_each_turn_and_lethargy_at_the_end(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Haste", "haste", 3)
    base = await _sheet(client, hero)
    await _cast(client, caster, spell, [hero], level=3)
    sheet = await _sheet(client, hero)
    assert sheet["computed"]["speed"] == base["computed"]["speed"] * 2 and sheet["ac"] == base["ac"] + 2
    turn = await _new_turn(client, hero)
    assert turn["extra_actions"] == 1
    as_user(PLAYER_ID)
    for _ in range(2):  # l'azione e quella extra di Velocità
        assert (await client.post(f"/characters/{hero}/turn/use", json={"slot": "action", "used": True})).status_code == 200
    assert (await client.post(f"/characters/{hero}/turn/use", json={"slot": "action", "used": True})).status_code == 409

    await _end_concentration(client, caster)
    after = await _sheet(client, hero)
    assert "spell:haste" not in {s["key"] for s in after["active_states"]} and "spell:haste_lethargy" in {s["key"] for s in after["active_states"]}
    assert after["conditions"].get("incapacitated") and after["computed"]["speed"] == 0
    await _new_turn(client, hero)  # fino alla fine del suo turno successivo
    assert (await _sheet(client, hero))["conditions"].get("incapacitated")
    await _new_turn(client, hero)
    done = await _sheet(client, hero)
    assert not done["conditions"].get("incapacitated") and done["computed"]["speed"] == base["computed"]["speed"]
    assert "spell:haste_lethargy" not in {s["key"] for s in done["active_states"]}
    assert (await _new_turn(client, hero))["extra_actions"] == 0


async def test_haste_adds_one_attack_to_the_attacks_of_the_turn(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Haste", "haste", 3)
    await _cast(client, caster, spell, [hero], level=3)
    await _new_turn(client, hero)
    as_user(PLAYER_ID)
    r = await client.get(f"/characters/{hero}/turn-state")
    assert r.json()["attacks_allowed"] == 2


async def test_haste_2024_lethargy_is_incapacitated_with_speed_zero(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Haste", "haste", 3, hero_edition="2024", caster_edition="2024")
    await _cast(client, caster, spell, [hero], level=3)
    await _end_concentration(client, caster)
    sheet = await _sheet(client, hero)
    assert sheet["conditions"].get("incapacitated") and sheet["computed"]["speed"] == 0


# --- Aure vive -----------------------------------------------------------------------------------------------------
async def test_aura_of_life_resists_necrotic_for_every_seated_creature_without_states_on_them(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Aura of Life", "aura-of-life", 4)
    assert await _hit(client, hero, 10, "necrotic") == 10
    r = await _cast(client, caster, spell, [hero], level=4)  # i bersagli indicati non servono: l'aura è del lanciatore
    assert [a["id"] for a in r.json()["spell_effects"]["applied"]] == [caster]
    assert not [s for s in (await _sheet(client, hero))["active_states"] or [] if s["key"].startswith("spell:")]
    assert await _hit(client, hero, 10, "necrotic") == 5
    assert await _hit(client, hero, 10, "fire") == 10
    as_user(GM_ID)
    assert "necrotic" in (await _sheet(client, caster, GM_ID))["computed"]["resistances"]  # anche chi la lancia è nell'aura
    await _end_concentration(client, caster)
    assert await _hit(client, hero, 10, "necrotic") == 10


async def test_aura_of_life_heals_a_creature_at_zero_hp_at_the_start_of_its_turn(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Aura of Life", "aura-of-life", 4)
    await _cast(client, caster, spell, [], level=4)
    as_user(PLAYER_ID)
    assert (await client.patch(f"/characters/{hero}/hp", json={"op": "set_current", "value": 0})).status_code == 200
    await _new_turn(client, hero)
    assert (await _sheet(client, hero))["current_hit_points"] == 1


async def test_pass_without_trace_adds_ten_to_stealth_of_the_seated_ally(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Pass without Trace", "pass-without-trace", 2)
    before = (await _sheet(client, hero))["skill_bonuses"]["stealth"]
    await _cast(client, caster, spell, [], level=2)
    after = await _sheet(client, hero)
    assert after["skill_bonuses"]["stealth"] == before + 10 and after["skill_bonuses"]["athletics"] == (await _sheet(client, hero))["skill_bonuses"]["athletics"]


async def test_circle_of_power_offers_the_confirmation_to_the_seated_ally(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Circle of Power", "circle-of-power", 5)
    as_user(PLAYER_ID)
    assert "spell:circle_of_power:save" not in await _roll_keys(client, hero, "save", ability="dexterity")
    await _cast(client, caster, spell, [], level=5)
    as_user(PLAYER_ID)
    assert "spell:circle_of_power:save" in await _roll_keys(client, hero, "save", ability="dexterity")
    await _end_concentration(client, caster)
    as_user(PLAYER_ID)
    assert "spell:circle_of_power:save" not in await _roll_keys(client, hero, "save", ability="dexterity")


async def test_crusaders_mantle_adds_a_d4_radiant_to_the_weapon_attacks_of_everyone_seated(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Crusader's Mantle", "crusaders-mantle", 3)
    as_user(PLAYER_ID)
    sword = await _sword(client, hero)
    assert not (await _attack(client, hero, sword)).get("option_result")
    await _cast(client, caster, spell, [], level=3)
    hit = await _attack(client, hero, sword)
    assert len(hit["option_result"]["extra_rolls"]) == 1 and hit["option_result"]["extra_types"] == ["radiant"]
    await _end_concentration(client, caster)
    assert not (await _attack(client, hero, sword)).get("option_result")


async def test_an_aura_cast_outside_an_evening_still_works_for_the_caster(client):
    cid = (await client.post("/characters", json={"name": "Chierico"})).json()["id"]
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Aura of Life", "srd_index": "aura-of-life", "level": 4, "is_concentration": True})
    await client.post(f"/characters/{cid}/spell_slots", json={"level": 4, "total": 1})
    spell = r.json()["id"]
    assert (await client.post(f"/characters/{cid}/spells/{spell}/use", json={"slot_level": 4})).status_code == 200
    assert "necrotic" in (await client.get(f"/characters/{cid}")).json()["computed"]["resistances"]
