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
    assert after["to_hit_bonus"] == before["to_hit_bonus"] + 1 and after.get("is_magic") is True
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
    assert not after["conditions"].get("incapacitated") and after["computed"]["incapacitated"] and after["computed"]["speed"] == 0  # 2014: niente azioni, non Incapacitato
    await _new_turn(client, hero)  # fino alla fine del suo turno successivo
    assert (await _sheet(client, hero))["computed"]["incapacitated"]
    await _new_turn(client, hero)
    done = await _sheet(client, hero)
    assert not done["computed"]["incapacitated"] and done["computed"]["speed"] == base["computed"]["speed"]
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
    effects = r.json()["spell_effects"]  # non «su <lanciatore>»: vale per i seduti alla serata
    assert effects["applied"] == [] and "seduti alla serata" in effects["text"]["it"] and "everyone seated" in effects["text"]["en"]
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


async def test_undo_71_going_back_a_turn_after_a_heal_from_zero_gives_back_the_death_saves_and_unconsciousness(client, test_session_factory):
    from sqlalchemy import select
    from core.db.models import GameSession
    hero, caster, spell = await _table(client, test_session_factory, "Aura of Life", "aura-of-life", 4)
    await _cast(client, caster, spell, [], level=4)
    async with test_session_factory() as s:
        sid = (await s.execute(select(GameSession.id))).scalar_one()
    as_user(GM_ID)
    assert (await client.post(f"/sessions/{sid}/encounter", json={"mode": "full"})).status_code == 201
    enc = (await client.post(f"/sessions/{sid}/encounter/combatants", json={"name": "Goblin", "count": 1, "initiative_mod": 0, "max_hp": 7, "ac": 15})).json()
    pcs = [c for c in enc["combatants"] if c["kind"] == "pc"]
    gob = next(c for c in enc["combatants"] if c["kind"] == "monster")
    hero_c = next(c for c in pcs if c["character_id"] == hero)
    caster_c = next(c for c in pcs if c["character_id"] == caster)
    as_user(PLAYER_ID)
    await client.post(f"/sessions/{sid}/encounter/combatants/{hero_c['id']}/initiative", json={"die": 15})
    as_user(GM_ID)
    await client.post(f"/sessions/{sid}/encounter/combatants/{gob['id']}/initiative", json={"die": 10})
    await client.post(f"/sessions/{sid}/encounter/combatants/{caster_c['id']}/initiative", json={"die": 1})
    assert (await client.post(f"/sessions/{sid}/encounter/start", json={})).status_code == 200
    as_user(PLAYER_ID)
    assert (await client.patch(f"/characters/{hero}/hp", json={"op": "set_current", "value": 0})).status_code == 200
    assert (await client.post(f"/characters/{hero}/death_saves/roll", json={"die": 5})).status_code == 200
    as_user(GM_ID)
    assert (await client.post(f"/sessions/{sid}/encounter/next-turn")).status_code == 200  # goblin
    assert (await client.post(f"/sessions/{sid}/encounter/next-turn")).status_code == 200  # lanciatore
    assert (await client.post(f"/sessions/{sid}/encounter/next-turn")).status_code == 200  # eroe: Aura di Vita lo cura
    healed = await _sheet(client, hero)
    assert healed["current_hit_points"] == 1 and healed["death_saves"]["failures"] == 0 and not healed["conditions"].get("unconscious")
    as_user(GM_ID)
    assert (await client.post(f"/sessions/{sid}/encounter/prev-turn")).status_code == 200
    back = await _sheet(client, hero)
    assert back["current_hit_points"] == 0 and back["death_saves"]["failures"] == 1 and back["conditions"].get("unconscious")


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


# --- Correzioni giro 1 ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("srd,name,extra", [("magic-weapon", "Magic Weapon", {}), ("elemental-weapon", "Elemental Weapon", {"choices": {"damage_type": "fire"}})])
async def test_a_weapon_spell_on_another_creature_is_cast_with_the_text_for_the_gm(client, test_session_factory, srd, name, extra):
    hero, caster, spell = await _table(client, test_session_factory, name, srd, 3)
    r = await _cast(client, caster, spell, [], level=3, **extra)
    effects = r.json()["spell_effects"]
    assert effects["applied"] == [] and effects["text"]
    assert not [s for s in (await _sheet(client, caster, GM_ID))["active_states"] or [] if s["key"] == f"spell:{srd.replace('-', '_')}"]


async def test_a_weapon_spell_outside_an_evening_on_another_creature_gives_the_text(client):
    cid = (await client.post("/characters", json={"name": "Chierico"})).json()["id"]
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Magic Weapon", "srd_index": "magic-weapon", "level": 2})
    await client.post(f"/characters/{cid}/spell_slots", json={"level": 2, "total": 1})
    r = await client.post(f"/characters/{cid}/spells/{r.json()['id']}/use", json={"targets": [], "slot_level": 2})
    assert r.status_code == 200 and r.json()["spell_effects"]["applied"] == []


async def test_a_weapon_spell_on_the_caster_still_needs_one_of_their_weapons(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Magic Weapon", "magic-weapon", 2)
    as_user(GM_ID)
    r = await client.post(f"/characters/{caster}/spells/{spell}/use", json={"targets": [caster], "slot_level": 2})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_choice"


@pytest.mark.parametrize("meta", [{"is_magic": True}, {"requires_attunement": True}, {"rarity": "rare", "is_magic": True, "requires_attunement": True, "attuned": True},
                                  {"bonuses": [{"target": "attack", "value": 1}]}])
async def test_a_magic_weapon_is_never_offered_nor_accepted_as_nonmagical(client, test_session_factory, meta):
    hero, caster, spell, sword, _ = await _weapon_table(client, test_session_factory)
    as_user(PLAYER_ID)
    magic = await _sword(client, hero, **meta)
    as_user(GM_ID)
    assert magic not in [w["id"] for w in (await client.get(f"/characters/{caster}/session-allies/{hero}/weapons")).json()]
    r = await client.post(f"/characters/{caster}/spells/{spell}/use", json={"targets": [hero], "slot_level": 2, "choices": {"item_id": str(magic)}})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_choice"


def test_a_non_numeric_magic_bonus_counts_as_magic_instead_of_failing():
    from types import SimpleNamespace
    from core.game.item_bonuses import is_magic_item
    assert is_magic_item(SimpleNamespace(item_metadata={"magic_bonus": "abc"})) and not is_magic_item(SimpleNamespace(item_metadata={"magic_bonus": 0}))


async def _concentrating_hero(client, hero, edition=None):
    as_user(PLAYER_ID)
    spell = (await client.post(f"/characters/{hero}/spells", json={"name": "Bless", "srd_index": "bless", "level": 1, "is_concentration": True})).json()["id"]
    assert (await client.patch(f"/characters/{hero}/concentration", json={"spell_id": spell})).status_code == 200
    return spell


async def test_haste_lethargy_2014_blocks_actions_without_the_incapacitated_condition(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Haste", "haste", 3)
    sword = await _sword(client, hero)
    bless = await _concentrating_hero(client, hero)
    await _cast(client, caster, spell, [hero], level=3)
    await _end_concentration(client, caster)
    sheet = await _sheet(client, hero)
    assert not sheet["conditions"].get("incapacitated") and sheet["computed"]["incapacitated"] and sheet["computed"]["speed"] == 0
    assert sheet["concentrating_spell_id"] == bless  # nel 2014 il manuale non dice Incapacitato: la concentrazione resta
    as_user(PLAYER_ID)
    r = await client.post(f"/characters/{hero}/items/{sword}/attack", json={"die": 10})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "incapacitated"
    lethargy = next(s for s in sheet["active_states"] if s["key"] == "spell:haste_lethargy")
    assert lethargy["data"]["no_actions"] is True


async def test_haste_lethargy_2024_is_incapacitated_and_drops_the_concentration_of_the_target(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Haste", "haste", 3, hero_edition="2024", caster_edition="2024")
    await _concentrating_hero(client, hero)
    await _cast(client, caster, spell, [hero], level=3)
    assert (await _sheet(client, hero))["concentrating_spell_id"] is not None
    await _end_concentration(client, caster)
    sheet = await _sheet(client, hero)
    assert sheet["conditions"].get("incapacitated") and sheet["concentrating_spell_id"] is None


@pytest.mark.parametrize("edition", ["2014", "2024"])
async def test_undoing_the_damage_that_ended_haste_also_takes_away_the_lethargy_it_left(client, test_session_factory, edition):
    hero, caster, spell = await _table(client, test_session_factory, "Haste", "haste", 3, hero_edition=edition, caster_edition=edition)
    await _cast(client, caster, spell, [hero], level=3)
    as_user(GM_ID)
    assert (await client.patch(f"/characters/{caster}/hp", json={"op": "set_current", "value": 5})).status_code == 200
    r = await client.patch(f"/characters/{caster}/hp", json={"op": "damage", "value": 100, "damage_type": "fire"})
    assert r.status_code == 200, r.text
    keys = {s["key"] for s in (await _sheet(client, hero))["active_states"] or []}
    assert "spell:haste_lethargy" in keys and "spell:haste" not in keys
    as_user(GM_ID)
    assert (await client.post(f"/characters/{caster}/hp/undo", json={"op_id": r.json()["hp_undo_id"]})).status_code == 200
    back = await _sheet(client, hero)
    keys = {s["key"] for s in back["active_states"] or []}
    assert "spell:haste" in keys and "spell:haste_lethargy" not in keys
    assert not back["conditions"].get("incapacitated") and not back["computed"]["incapacitated"]


async def test_the_turn_in_which_haste_ends_does_not_keep_its_extra_action(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Haste", "haste", 3)
    await _cast(client, caster, spell, [hero], level=3)
    assert (await _new_turn(client, hero))["extra_actions"] == 1
    await _end_concentration(client, caster)
    as_user(PLAYER_ID)
    state = (await client.get(f"/characters/{hero}/turn-state")).json()
    assert state["turn"]["extra_actions"] == 0 and state["attacks_allowed"] == 1


# --- Randello Incantato, Ritirata Rapida, Faretra Rapida: voci solo testo ---------------------------------------------
@pytest.mark.parametrize("edition", ["2014", "2024"])
@pytest.mark.parametrize("srd,concentration,needle", [("shillelagh", False, "d8"), ("expeditious-retreat", True, "Scatto"), ("swift-quiver", True, "due attacchi")])
def test_the_text_only_entries_are_in_the_catalog_with_name_and_duration(edition, srd, concentration, needle):
    effect, variant = spell_effect(edition, srd)
    assert variant.track and variant.concentration is concentration and variant.duration(5) and needle in variant.text["it"] and variant.text["en"]


def test_shillelagh_text_follows_the_dice_and_ability_of_each_edition():
    text14, text24 = (spell_effect(e, "shillelagh")[1].text["it"] for e in ("2014", "2024"))
    assert "d8" in text14 and "d10" not in text14 and "caratteristica da incantatore" in text14
    assert "d10" in text24 and "d12" in text24 and "2d6" in text24 and "caratteristica da incantatore" in text24


@pytest.mark.parametrize("srd,name,level,state", [("expeditious-retreat", "Expeditious Retreat", 1, "spell:expeditious_retreat"), ("swift-quiver", "Swift Quiver", 5, "spell:swift_quiver")])
async def test_casting_a_text_only_entry_tracks_the_state_and_gives_the_text(client, test_session_factory, srd, name, level, state):
    hero, caster, spell = await _table(client, test_session_factory, name, srd, level)
    r = await _cast(client, caster, spell, [], level=level or None)
    assert r.json()["spell_effects"]["text"]
    assert await _states(client, caster, GM_ID, state)


async def test_the_state_of_an_enchanted_weapon_says_which_weapon_it_is(client, test_session_factory):
    hero, caster, spell, sword, _ = await _weapon_table(client, test_session_factory)
    await _cast(client, caster, spell, [hero], level=2, choices={"item_id": str(sword)})
    assert (await _states(client, hero, PLAYER_ID, "spell:magic_weapon"))[0]["data"]["weapon_name"] == "Spada"


# --- Randello Incantato: arma, caratteristica da incantatore e dado --------------------------------------------------
async def _staff(client, cid, name="Bastone ferrato", dice="1d6"):
    r = await client.post(f"/characters/{cid}/items", json={"name": name, "item_type": "weapon", "item_metadata": {"damage_dice": dice, "weapon_type": "melee", "properties": []}})
    assert r.status_code == 201, r.text
    return max(i["id"] for i in r.json()["items"])


def _pick(staff, edition, damage="normal"):
    """Le scelte del lancio di Randello Incantato: l'arma e, nel 2024, il tipo di danno."""
    return {"item_id": str(staff), **({"weapon_damage": damage} if edition == "2024" else {})}


async def _druid_table(client, factory, edition, level=1):
    """Un druido (Saggezza 16, Forza 10) con Randello Incantato, un bastone ferrato e una spada."""
    _, caster, spell = await _table(client, factory, "Shillelagh", "shillelagh", 0, caster_edition=edition)
    as_user(GM_ID)
    assert (await client.post(f"/characters/{caster}/classes", json={"class_name": "druid", "level": level, "hit_die": 8})).status_code == 201
    assert (await client.patch(f"/characters/{caster}/ability_scores/wisdom", json={"value": 16})).status_code == 200
    return caster, spell, await _staff(client, caster), await _sword(client, caster)


async def _gm_attack(client, cid, wid):
    as_user(GM_ID)
    r = await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 10, "confirm_extra_attack": True})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("edition", ["2014", "2024"])
async def test_shillelagh_makes_the_staff_magical_with_a_d8_and_the_spellcasting_modifier(client, test_session_factory, edition):
    caster, spell, staff, sword = await _druid_table(client, test_session_factory, edition)
    before, plain_before = await _gm_attack(client, caster, staff), await _gm_attack(client, caster, sword)
    await _cast(client, caster, spell, [], choices=_pick(staff, edition))
    after = await _gm_attack(client, caster, staff)
    assert before["damage_dice"] == "1d6" and after["damage_dice"] == "1d8" and after.get("is_magic") is True
    assert after["to_hit_bonus"] == before["to_hit_bonus"] + 3 and after["damage_bonus"] == before["damage_bonus"] + 3  # Saggezza 16 al posto di Forza 10
    plain = await _gm_attack(client, caster, sword)  # un'altra arma: nessun effetto
    assert (plain["damage_dice"], plain["to_hit_bonus"], plain["damage_bonus"], plain.get("is_magic")) == (
        plain_before["damage_dice"], plain_before["to_hit_bonus"], plain_before["damage_bonus"], plain_before.get("is_magic"))


@pytest.mark.parametrize("edition,level,die", [("2014", 1, "1d8"), ("2014", 5, "1d8"), ("2014", 17, "1d8"), ("2024", 1, "1d8"), ("2024", 5, "1d10"),
                                               ("2024", 11, "1d12"), ("2024", 17, "2d6")])
async def test_shillelagh_die_follows_the_manual_of_each_edition(client, test_session_factory, edition, level, die):
    caster, spell, staff, _ = await _druid_table(client, test_session_factory, edition, level)
    await _cast(client, caster, spell, [], choices=_pick(staff, edition))
    assert (await _gm_attack(client, caster, staff))["damage_dice"] == die


async def test_shillelagh_accepts_only_a_club_or_quarterstaff_of_the_caster(client, test_session_factory):
    caster, spell, _, sword = await _druid_table(client, test_session_factory, "2014")
    club = await _staff(client, caster, "Randello")
    as_user(GM_ID)
    for choices in ({"item_id": str(sword)}, {"item_id": "99999"}, {"item_id": "x"}, {}):
        r = await client.post(f"/characters/{caster}/spells/{spell}/use", json={"targets": [], "choices": choices})
        assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_choice", choices
    await _cast(client, caster, spell, [], choices={"item_id": str(club)})
    assert (await _states(client, caster, GM_ID, "spell:shillelagh"))[0]["data"]["weapon_name"] == "Randello"


async def test_shillelagh_cast_again_moves_to_the_new_weapon(client, test_session_factory):
    caster, spell, staff, _ = await _druid_table(client, test_session_factory, "2014")
    club = await _staff(client, caster, "Randello", "1d4")
    await _cast(client, caster, spell, [], choices={"item_id": str(staff)})
    await _cast(client, caster, spell, [], choices={"item_id": str(club)})
    assert (await _gm_attack(client, caster, staff))["damage_dice"] == "1d6"
    assert (await _gm_attack(client, caster, club))["damage_dice"] == "1d8"


async def test_the_weapon_list_can_be_limited_to_the_kinds_of_a_spell(client, test_session_factory):
    caster, _, staff, _ = await _druid_table(client, test_session_factory, "2014")
    as_user(GM_ID)
    r = await client.get(f"/characters/{caster}/session-allies/{caster}/weapons", params={"kinds": "club,quarterstaff"})
    assert r.status_code == 200 and [w["id"] for w in r.json()] == [staff]


@pytest.mark.parametrize("edition,delta", [("2024", 0), ("2014", -2)])
async def test_shillelagh_uses_the_better_ability_in_2024_but_always_the_spellcasting_one_in_2014(client, test_session_factory, edition, delta):
    caster, spell, staff, _ = await _druid_table(client, test_session_factory, edition)
    as_user(GM_ID)
    assert (await client.patch(f"/characters/{caster}/ability_scores/strength", json={"value": 18})).status_code == 200
    assert (await client.patch(f"/characters/{caster}/ability_scores/wisdom", json={"value": 14})).status_code == 200
    before = await _gm_attack(client, caster, staff)  # Forza 18 (+4)
    await _cast(client, caster, spell, [], choices=_pick(staff, edition))
    after = await _gm_attack(client, caster, staff)
    assert after["to_hit_bonus"] == before["to_hit_bonus"] + delta and after["damage_bonus"] == before["damage_bonus"] + delta  # 2024: Forza +4; 2014: Saggezza +2


async def test_t10_79_shillelagh_2024_asks_whether_the_damage_is_the_weapons_or_force_and_the_attack_says_it(client, test_session_factory):
    caster, spell, staff, _ = await _druid_table(client, test_session_factory, "2024")
    as_user(GM_ID)
    assert spell_effect("2024", "shillelagh")[1].choices[0].options("2024") == ["normal", "force"] and not spell_effect("2014", "shillelagh")[1].choices
    r = await client.post(f"/characters/{caster}/spells/{spell}/use", json={"targets": [], "choices": {"item_id": str(staff)}})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_choice"  # il tipo si sceglie al lancio
    await _cast(client, caster, spell, [], choices=_pick(staff, "2024", "force"))
    assert (await _gm_attack(client, caster, staff))["damage_type"] == "force"
    await _cast(client, caster, spell, [], choices=_pick(staff, "2024", "normal"))
    assert "damage_type" not in await _gm_attack(client, caster, staff)  # il tipo normale dell'arma: nessun override
