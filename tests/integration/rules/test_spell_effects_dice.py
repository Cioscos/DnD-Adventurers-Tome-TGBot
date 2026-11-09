"""Effetti degli incantesimi, dadi bonus sui tiri: Benedizione, Guida, Resistenza, Passare senza Tracce, Protezione dalle Lame."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.rules.catalog.spells import spell_effect
from core.rules.modifiers import modifiers_for
from core.rules.roll_options import refund_spent
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session
from tests.integration.rules.test_2014_bard_inspiration import _seat
from tests.integration.rules.test_2014_bard import _roll_keys
from tests.integration.rules.test_spell_effects_cast import _full, _states

BLESS, GUIDANCE, RESISTANCE = "bless", "guidance", "resistance"


async def _caster(client, factory, spell_name, srd, level):
    as_user(GM_ID)
    cid = (await client.post("/characters", json={"name": "Chierico"})).json()["id"]
    r = await client.post(f"/characters/{cid}/spells", json={
        "name": spell_name, "srd_index": srd, "level": level, "is_concentration": True})
    assert r.status_code == 201, r.text
    assert (await client.post(f"/characters/{cid}/spell_slots", json={"level": 1, "total": 2})).status_code == 201
    await _seat(factory, cid, GM_ID)
    return cid, r.json()["id"]


async def _table(client, factory, spell_name, srd, level, hero_edition=None):
    _, hero = await seed_session(factory)
    caster, spell = await _caster(client, factory, spell_name, srd, level)
    if hero_edition:
        as_user(PLAYER_ID)
        await client.patch(f"/characters/{hero}", json={"rules_edition": hero_edition})
    return hero, caster, spell


async def _cast(client, caster, spell, targets, edition_choices=None, level=1):
    as_user(GM_ID)
    body = {"targets": targets, **({"slot_level": 1} if level else {}), **({"choices": edition_choices} if edition_choices else {})}
    r = await client.post(f"/characters/{caster}/spells/{spell}/use", json=body)
    assert r.status_code == 200, r.text
    return r


async def _roll(client, hero, kind, **extra):
    as_user(PLAYER_ID)
    paths = {"skill": "skills/athletics/roll", "save": "saving_throws/wisdom/roll", "ability": "ability_checks/strength/roll"}
    r = await client.post(f"/characters/{hero}/{paths[kind]}", json={"die": 10})
    assert r.status_code == 200, r.text
    return r.json()


async def _add(client, hero, key):
    as_user(PLAYER_ID)
    return await client.post(f"/characters/{hero}/last-roll/options", json={"options": [key]})


async def test_bless_offers_a_d4_on_attacks_and_saves_and_adds_it(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Bless", "bless", 1)
    await _cast(client, caster, spell, [hero])
    as_user(PLAYER_ID)
    for roll, query in (("attack", {}), ("save", {"ability": "wisdom"}), ("death_save", {})):
        assert "spell:bless:add" in await _roll_keys(client, hero, roll, **query)
    first = await _roll(client, hero, "save")
    r = await _add(client, hero, "spell:bless:add")
    assert r.status_code == 200, r.text
    extra = r.json()["option_result"]
    assert len(extra["extra_rolls"]) == 1 and 1 <= extra["extra_total"] <= 4
    assert r.json()["total"] == first["total"] + extra["extra_total"]
    assert [s["key"] for s in await _states(client, hero, PLAYER_ID, "spell:bless")] == ["spell:bless"]  # non si consuma


async def test_bless_is_not_offered_on_ability_checks(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Bless", "bless", 1)
    await _cast(client, caster, spell, [hero])
    as_user(PLAYER_ID)
    assert "spell:bless:add" not in await _roll_keys(client, hero, "skill", skill="athletics")
    assert "spell:bless:add" not in await _roll_keys(client, hero, "initiative")


async def test_nothing_is_offered_without_the_state(client, test_session_factory):
    hero, *_ = await _table(client, test_session_factory, "Bless", "bless", 1)
    as_user(PLAYER_ID)
    assert not [k for k in await _roll_keys(client, hero, "attack") if k.startswith("spell:")]


@pytest.mark.parametrize("roll,query", [("skill", {"skill": "athletics"}), ("ability", {"ability": "strength"}), ("initiative", {})])
async def test_guidance_2014_is_offered_on_any_ability_check_and_spent_at_first_use(client, test_session_factory, roll, query):
    hero, caster, spell = await _table(client, test_session_factory, "Guidance", "guidance", 0)
    await _cast(client, caster, spell, [hero], level=0)
    as_user(PLAYER_ID)
    assert "spell:guidance:add" in await _roll_keys(client, hero, roll, **query)
    assert "spell:guidance:add" not in await _roll_keys(client, hero, "attack")
    assert "spell:guidance:add" not in await _roll_keys(client, hero, "save", ability="wisdom")


async def test_guidance_2014_adds_one_d4_then_the_state_is_gone(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Guidance", "guidance", 0)
    await _cast(client, caster, spell, [hero], level=0)
    first = await _roll(client, hero, "skill")
    r = await _add(client, hero, "spell:guidance:add")
    assert r.status_code == 200, r.text
    extra = r.json()["option_result"]
    assert len(extra["extra_rolls"]) == 1 and 1 <= extra["extra_total"] <= 4
    assert r.json()["total"] == first["total"] + extra["extra_total"]
    assert await _states(client, hero, PLAYER_ID, "spell:guidance") == []
    assert (await _add(client, hero, "spell:guidance:add")).status_code == 409
    # il lanciatore tiene l'orologio: il rilascio al termine salta il bersaglio senza stato
    as_user(GM_ID)
    assert (await client.patch(f"/characters/{caster}/concentration", json={"spell_id": None})).status_code == 200


async def test_guidance_2024_is_for_the_chosen_skill_and_lasts(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Guidance", "guidance", 0, hero_edition="2024")
    as_user(GM_ID)
    await client.patch(f"/characters/{caster}", json={"rules_edition": "2024"})
    await _cast(client, caster, spell, [hero], {"skill": "athletics"}, level=0)
    as_user(PLAYER_ID)
    assert "spell:guidance:add" in await _roll_keys(client, hero, "skill", skill="athletics")
    assert "spell:guidance:add" not in await _roll_keys(client, hero, "skill", skill="stealth")
    assert "spell:guidance:add" not in await _roll_keys(client, hero, "initiative")
    await _roll(client, hero, "skill")
    assert (await _add(client, hero, "spell:guidance:add")).status_code == 200
    assert len(await _states(client, hero, PLAYER_ID, "spell:guidance")) == 1  # nel 2024 non si consuma


async def test_resistance_2014_is_for_one_saving_throw_only(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Resistance", "resistance", 0)
    await _cast(client, caster, spell, [hero], level=0)
    as_user(PLAYER_ID)
    assert "spell:resistance:add" in await _roll_keys(client, hero, "save", ability="wisdom")
    assert "spell:resistance:add" not in await _roll_keys(client, hero, "skill", skill="athletics")
    await _roll(client, hero, "save")
    r = await _add(client, hero, "spell:resistance:add")
    assert r.status_code == 200 and 1 <= r.json()["option_result"]["extra_total"] <= 4
    assert await _states(client, hero, PLAYER_ID, "spell:resistance") == []


def test_a_refund_gives_a_spell_state_back():
    state = {"key": "spell:guidance", "data": {"spell_key": "guidance", "edition": "2014"}, "rounds_left": None}
    char = SimpleNamespace(active_states=[state], turn_state={}, abilities=[], spell_slots=[], settings={})
    from core.rules.roll_options import _spend_state_token

    token = _spend_state_token(char, "spell:guidance")
    assert char.active_states == []
    refund_spent(char, [token])
    assert char.active_states == [state]


def test_pass_without_trace_is_plus_ten_on_stealth_only():
    char = SimpleNamespace(
        rules_edition="2014", conditions={}, items=[], classes=[], settings={}, general_proficiencies={}, hit_points=40,
        damage_modifiers={}, proficiency_bonus=2, skills={}, saving_throws={}, shield_armor_class=0,
        active_states=[{"key": "spell:pass_without_trace", "data": {"spell_key": "pass_without_trace", "slot_level": 2, "edition": "2014"}}])
    assert modifiers_for(char, "skill", skill="stealth").flat == 10
    assert modifiers_for(char, "skill", skill="athletics").flat == 0
    assert modifiers_for(char, "save", ability="dexterity").flat == 0


@pytest.mark.parametrize("edition,name", [("2014", "Benedizione"), ("2024", "Bless"), ("2014", "Guida"), ("2024", "Guidance"),
                                          ("2014", "Resistenza"), ("2014", "Passare Senza Tracce"), ("2024", "Pass without Trace"),
                                          ("2024", "Protezione dalle Lame"), ("2024", "Blade Ward")])
def test_catalog_knows_the_dice_spells_in_both_languages(edition, name):
    assert spell_effect(edition, None, name) is not None


def test_bless_targets_grow_with_the_slot_and_blade_ward_is_only_text():
    effect, _ = spell_effect("2014", "bless")
    assert [effect.target.count(s) for s in (1, 2, 3)] == [3, 4, 5]
    _, ward = spell_effect("2024", "blade-ward")
    assert ward.text and not ward.options and not ward.modifiers({})
    assert spell_effect("2014", "blade-ward") is None  # 2014: resistenza, altra primitiva
