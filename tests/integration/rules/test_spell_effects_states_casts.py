"""Effetti degli incantesimi, stati e lanci (minori 60-70): due lanciatori, metamagia, solo-sé, oggetti, Velocità, Morte Apparente."""
from __future__ import annotations

import random
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from api.services.spell_effects import apply_spell_effects, item_spell
from core.db.models import AbilityScore, Character, SessionParticipant, SessionRole
from core.rules.catalog.spells import spell_effect
from tests.integration._encounter_helpers import GM_ID, NOW, PLAYER_ID, as_user, seed_session
from tests.integration.rules.test_2014_bard_inspiration import _seat
from tests.integration.rules.test_2014_sorcerer_metamagic import EXTENDED, TWINNED, _caster as _sorcerer_with
from tests.integration.rules.test_spell_effects_cast import SOF, SOF_ROUNDS, STATE, _ac, _caster, _cast, _full, _states
from tests.integration.rules.test_spell_effects_defenses import _sheet
from tests.integration.rules.test_spell_effects_defenses import _table as _defense_table
from tests.integration.test_magic_items import _item


async def _second_caster(client, factory, sid, user=9001):
    """Un secondo chierico con Scudo della Fede, seduto alla stessa serata."""
    async with factory() as s:
        other = Character(user_id=user, name="Secondo")
        s.add(other)
        await s.flush()
        s.add(AbilityScore(character_id=other.id, name="dexterity", value=12))
        s.add(SessionParticipant(session_id=sid, user_id=user, character_id=other.id, role=SessionRole.PLAYER, display_name="Secondo", joined_at=NOW))
        await s.commit()
    second, spell = await _caster(client, factory, "Secondo", user=user, seat=False)
    async with factory() as s:
        part = (await s.execute(select(SessionParticipant).where(SessionParticipant.user_id == user))).scalar_one()
        part.character_id = second
        await s.commit()
    return second, spell


# 62: uno stato per coppia (incantesimo, lanciatore)

@pytest.mark.parametrize("first_ends_first", [True, False])
async def test_spells_62_two_casters_each_keep_their_own_state(client, test_session_factory, first_ends_first):
    sid, hero, first, spell1 = await _caster_table(client, test_session_factory)
    second, spell2 = await _second_caster(client, test_session_factory, sid)
    base = await _ac(client, hero, PLAYER_ID)
    await _cast(client, first, spell1, [hero])
    assert (await _cast(client, second, spell2, [hero], user=9001)).status_code == 200
    states = await _states(client, hero, PLAYER_ID)
    assert {s["data"]["caster_id"] for s in states} == {first, second} and await _ac(client, hero, PLAYER_ID) == base + 2  # non si somma
    order = [(first, GM_ID), (second, 9001)] if first_ends_first else [(second, 9001), (first, GM_ID)]
    survivor = order[1][0]
    as_user(order[0][1])
    await client.patch(f"/characters/{order[0][0]}/concentration", json={"spell_id": None})
    assert await _ac(client, hero, PLAYER_ID) == base + 2  # resta quello dell'altro, qualunque sia l'ordine
    assert [s["data"]["caster_id"] for s in await _states(client, hero, PLAYER_ID)] == [survivor]
    as_user(order[1][1])
    await client.patch(f"/characters/{order[1][0]}/concentration", json={"spell_id": None})
    assert await _ac(client, hero, PLAYER_ID) == base and await _states(client, hero, PLAYER_ID) == []


async def _caster_table(client, factory):
    sid, hero = await seed_session(factory)
    caster, spell = await _caster(client, factory)
    return sid, hero, caster, spell


# 60 e 61: Incantesimo Esteso e Raddoppiato sugli stati dei bersagli

async def _sorcerer_table(client, factory, *picks):
    sid, hero = await seed_session(factory)
    as_user(GM_ID)
    cid = await _sorcerer_with(client, 3, *picks)
    r = await client.post(f"/characters/{cid}/spells", json={
        "name": "Shield of Faith", "srd_index": SOF, "level": 1, "is_concentration": True, "range_area": "18 m",
        "duration": "Concentrazione, fino a 10 minuti"})
    assert r.status_code == 201, r.text
    await _seat(factory, cid, GM_ID)
    return sid, hero, cid, r.json()["id"]


async def test_spells_60_extended_spell_doubles_the_clock_of_the_effect(client, test_session_factory):
    _, hero, cid, spell = await _sorcerer_table(client, test_session_factory, "extended")
    r = await client.post(f"/characters/{cid}/spells/{spell}/use", json={"slot_level": 1, "targets": [hero], "options": [EXTENDED]})
    assert r.status_code == 200, r.text
    [clock] = await _states(client, cid, GM_ID, "spell_cast:shield_of_faith")
    assert clock["rounds_left"] == SOF_ROUNDS * 2 and clock["data"]["state_data"]["duration"]["rounds"] == SOF_ROUNDS * 2


async def test_spells_60_without_the_option_the_clock_is_the_normal_one(client, test_session_factory):
    _, hero, cid, spell = await _sorcerer_table(client, test_session_factory, "extended")
    await client.post(f"/characters/{cid}/spells/{spell}/use", json={"slot_level": 1, "targets": [hero]})
    [clock] = await _states(client, cid, GM_ID, "spell_cast:shield_of_faith")
    assert clock["rounds_left"] == SOF_ROUNDS


async def test_spells_61_twinned_spell_gives_the_effect_to_a_second_ally(client, test_session_factory):
    sid, hero, cid, spell = await _sorcerer_table(client, test_session_factory, "twinned")
    second, _ = await _second_caster(client, test_session_factory, sid)
    as_user(GM_ID)
    body = {"slot_level": 1, "targets": [hero, second]}
    refused = await client.post(f"/characters/{cid}/spells/{spell}/use", json=body)
    assert refused.status_code == 422 and refused.json()["detail"]["code"] == "invalid_target"  # senza l'opzione un solo bersaglio
    r = await client.post(f"/characters/{cid}/spells/{spell}/use", json={**body, "options": [TWINNED]})
    assert r.status_code == 200, r.text
    assert {a["id"] for a in r.json()["spell_effects"]["applied"]} == {hero, second}
    assert len(await _states(client, hero, PLAYER_ID)) == 1 and len(await _states(client, second, 9001)) == 1


# 65: lancio senza concentrazione

async def test_spells_65_a_cast_without_concentration_is_not_tied_to_it(client, test_session_factory):
    caster, _ = await _caster(client, test_session_factory, seat=False)
    async with test_session_factory() as s:
        char = await s.get(Character, caster)
        fx = item_spell({"name": "Shield of Faith", "srd_index": SOF, "level": 1})
        await apply_spell_effects(s, char, fx, 1, None, None, (), no_concentration=True)
        clock = next(st for st in char.active_states if st["key"] == "spell_cast:shield_of_faith")
        assert "concentration_end" not in clock["ends_on"] and clock["data"]["state_data"]["duration"]["concentration"] is False
        char.active_states = []
        await apply_spell_effects(s, char, fx, 1, None, None, ())
        clock = next(st for st in char.active_states if st["key"] == "spell_cast:shield_of_faith")
        assert "concentration_end" in clock["ends_on"]


# 66: effetti solo su sé stessi

async def test_spells_66_other_targets_on_a_self_only_spell_are_refused(client, test_session_factory):
    _, hero = await seed_session(test_session_factory)
    as_user(GM_ID)
    cid = (await client.post("/characters", json={"name": "Mago"})).json()["id"]
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Blade Ward", "srd_index": "blade-ward", "level": 0})
    spell = r.json()["id"]
    refused = await client.post(f"/characters/{cid}/spells/{spell}/use", json={"targets": [hero]})
    assert refused.status_code == 422 and refused.json()["detail"]["code"] == "self_only_spell"
    assert (await client.post(f"/characters/{cid}/spells/{spell}/use", json={"targets": [cid]})).status_code == 200
    assert (await client.post(f"/characters/{cid}/spells/{spell}/use", json={})).status_code == 200


async def test_spells_66_no_gm_text_outside_an_evening_when_only_the_caster_is_involved(client, test_session_factory):
    caster, spell = await _caster(client, test_session_factory, seat=False)
    r = await _cast(client, caster, spell, [caster])
    assert r.status_code == 200
    assert "Fuori da una serata" not in str((r.json().get("spell_effects") or {}).get("text"))


# 67: livello dell'oggetto

async def test_spells_67_item_cast_uses_the_slot_level_of_the_item(client, test_session_factory):
    _, hero, caster, _ = await _caster_table(client, test_session_factory)
    spell = {"name": "Shield of Faith", "srd_index": SOF, "level": 1, "slot_level": 3, "charges_cost": 1}
    as_user(GM_ID)
    iid = await _item(client, caster, charges={"current": 3, "max": 3}, granted_spells=[spell])
    r = await client.post(f"/characters/{caster}/items/{iid}/cast", json={"spell_index": 0, "targets": [hero]})
    assert r.status_code == 200, r.text
    [state] = await _states(client, hero, PLAYER_ID)
    assert state["data"]["slot_level"] == 3


# 64: i dadi extra di un attacco non passano a un altro lancio

async def test_spells_64_carried_attack_dice_do_not_survive_a_new_cast(client, test_session_factory):
    caster, spell = await _caster(client, test_session_factory, seat=False)
    async with test_session_factory() as s:
        char = await s.get(Character, caster)
        char.turn_state = {**(char.turn_state or {}), "spell_attack_dice": {"spell_id": spell, "dice": [["d6", 4]], "block": {}}}
        await s.commit()
    assert (await _cast(client, caster, spell, [caster])).status_code == 200
    async with test_session_factory() as s:
        assert "spell_attack_dice" not in ((await s.get(Character, caster)).turn_state or {})


# 68: Guida 2014 usata non torna con un annullo

async def test_spells_68_a_spent_guidance_is_not_given_back_by_the_casters_undo(client, test_session_factory):
    from tests.integration.rules.test_spell_effects_dice import _add, _cast as _dice_cast, _roll, _table
    hero, caster, spell = await _table(client, test_session_factory, "Guidance", "guidance", 0)
    await _dice_cast(client, caster, spell, [hero], level=0)
    as_user(GM_ID)
    hit = await client.patch(f"/characters/{caster}/hp", json={"op": "set_temp", "value": 3})  # un'operazione sui PF annullabile, che non rompe la concentrazione
    assert hit.json()["concentrating_spell_id"] is not None
    op_id = hit.json()["hp_undo_id"]
    await _roll(client, hero, "skill")
    spent = await _add(client, hero, "spell:guidance:add")
    assert spent.status_code == 200, (spent.text, hit.text)  # usata: lo stato è chiuso
    as_user(GM_ID)
    undo = await client.post(f"/characters/{caster}/hp/undo", json={"op_id": op_id})
    assert undo.status_code == 409
    assert await _states(client, hero, PLAYER_ID, "spell:guidance") == []


# 69: Velocità raddoppia la velocità effettiva

async def test_spells_69_haste_doubles_the_effective_speed_with_items(client, test_session_factory):
    hero, caster, spell = await _defense_table(client, test_session_factory, "Haste", "haste", 3)
    as_user(PLAYER_ID)
    await _item(client, hero, slot="neck", bonuses=[{"target": "speed", "value": 10}])
    before = (await _sheet(client, hero))["computed"]["speed"]
    as_user(GM_ID)
    r = await client.post(f"/characters/{caster}/spells/{spell}/use", json={"targets": [hero], "slot_level": 3})
    assert r.status_code == 200, r.text
    assert (await _sheet(client, hero))["computed"]["speed"] == before * 2  # (30 + 10) * 2, non 30 * 2 + 10


# 70: Morte Apparente accieca

@pytest.mark.parametrize("edition", ["2014", "2024"])
async def test_spells_70_feign_death_also_blinds(client, test_session_factory, edition):
    hero, caster, spell = await _defense_table(client, test_session_factory, "Feign Death", "feign-death", 3,
                                               hero_edition=edition, caster_edition=edition)
    as_user(GM_ID)
    r = await client.post(f"/characters/{caster}/spells/{spell}/use", json={"targets": [hero], "slot_level": 3})
    assert r.status_code == 200, r.text
    sheet = await _sheet(client, hero)
    assert sheet["conditions"].get("incapacitated") and sheet["conditions"].get("blinded")
    as_user(PLAYER_ID)
    assert (await client.delete(f"/characters/{hero}/active-states/spell:feign_death")).status_code == 200
    after = (await _sheet(client, hero))["conditions"]
    assert not after.get("incapacitated") and not after.get("blinded")  # finito lo stato, tornano via entrambe


# 62 (giro 1): Aiuto da due lanciatori, vale il massimo più forte e i PF correnti non lo superano mai

async def _aid_second(client, factory, user=9001, slot=2):
    """Un secondo lanciatore di Aiuto seduto alla serata del tavolo di ``_table``."""
    async with factory() as s:
        sid = (await s.execute(select(SessionParticipant.session_id).limit(1))).scalar_one()
    as_user(user)
    cid = (await client.post("/characters", json={"name": "Secondo"})).json()["id"]
    spell = (await client.post(f"/characters/{cid}/spells", json={"name": "Aid", "srd_index": "aid", "level": 2})).json()["id"]
    assert (await client.post(f"/characters/{cid}/spell_slots", json={"level": slot, "total": 1})).status_code == 201
    async with factory() as s:
        s.add(SessionParticipant(session_id=sid, user_id=user, character_id=cid, role=SessionRole.PLAYER, display_name="Secondo", joined_at=NOW))
        await s.commit()
    return cid, spell


async def _two_aids(client, factory):
    from tests.integration.rules.test_spell_effects_defenses import _cast as cast_at
    hero, first, spell1 = await _defense_table(client, factory, "Aid", "aid", 2)
    as_user(GM_ID)
    assert (await client.post(f"/characters/{first}/spell_slots", json={"level": 3, "total": 1})).status_code == 201
    second, spell2 = await _aid_second(client, factory)
    await cast_at(client, first, spell1, [hero], level=3)  # +10
    as_user(9001)
    assert (await client.post(f"/characters/{second}/spells/{spell2}/use", json={"slot_level": 2, "targets": [hero]})).status_code == 200  # +5
    return hero, first, second


async def test_spells_62_two_aids_keep_the_strongest_maximum_and_cap_hp_when_it_drops(client, test_session_factory):
    hero, first, second = await _two_aids(client, test_session_factory)
    sheet = await _sheet(client, hero)
    assert sheet["computed"]["hp_max_effective"] == 210 and sheet["current_hit_points"] <= 210  # vale il 3°, non l'ultimo lanciato
    as_user(GM_ID)
    assert (await client.post(f"/characters/{first}/rest", json={"rest_type": "long"})).status_code == 200  # finisce quello del 3°
    sheet = await _sheet(client, hero)
    assert sheet["computed"]["hp_max_effective"] == 205 and sheet["current_hit_points"] <= 205  # resta il 2°, PF tagliati


async def test_spells_62_manual_end_caps_hp_and_closes_the_casters_clocks(client, test_session_factory):
    hero, first, second = await _two_aids(client, test_session_factory)
    as_user(PLAYER_ID)
    assert (await client.delete(f"/characters/{hero}/active-states/spell:aid")).status_code == 200
    sheet = await _sheet(client, hero)
    assert sheet["computed"]["hp_max_effective"] == 200 and sheet["current_hit_points"] <= 200
    for caster, user in ((first, GM_ID), (second, 9001)):
        as_user(user)
        assert not [s for s in (await _full(client, caster))["active_states"] or [] if s["key"] == "spell_cast:aid"]


# 70-bis (M-3): la letargia di Velocità scatta solo quando cade l'ultima Velocità del bersaglio

@pytest.mark.parametrize("edition", ["2014", "2024"])
async def test_spells_haste_lethargy_only_when_the_last_haste_ends(client, test_session_factory, edition):
    hero, first, spell1 = await _defense_table(client, test_session_factory, "Haste", "haste", 3, hero_edition=edition, caster_edition=edition)
    async with test_session_factory() as s:
        sid = (await s.execute(select(SessionParticipant.session_id).limit(1))).scalar_one()
    as_user(9001)
    second = (await client.post("/characters", json={"name": "Secondo"})).json()["id"]
    await client.patch(f"/characters/{second}", json={"rules_edition": edition})
    spell2 = (await client.post(f"/characters/{second}/spells", json={"name": "Haste", "srd_index": "haste", "level": 3, "is_concentration": True})).json()["id"]
    assert (await client.post(f"/characters/{second}/spell_slots", json={"level": 3, "total": 1})).status_code == 201
    async with test_session_factory() as s:
        s.add(SessionParticipant(session_id=sid, user_id=9001, character_id=second, role=SessionRole.PLAYER, display_name="Secondo", joined_at=NOW))
        await s.commit()
    for caster, spell, user in ((first, spell1, GM_ID), (second, spell2, 9001)):
        as_user(user)
        assert (await client.post(f"/characters/{caster}/spells/{spell}/use", json={"slot_level": 3, "targets": [hero]})).status_code == 200
    keys = lambda sheet: {s["key"] for s in sheet["active_states"] or []}  # noqa: E731
    as_user(GM_ID)
    await client.patch(f"/characters/{first}/concentration", json={"spell_id": None})
    sheet = await _sheet(client, hero)
    assert "spell:haste" in keys(sheet) and "spell:haste_lethargy" not in keys(sheet)  # resta la Velocità dell'altro
    as_user(9001)
    await client.patch(f"/characters/{second}/concentration", json={"spell_id": None})
    sheet = await _sheet(client, hero)
    assert "spell:haste" not in keys(sheet) and "spell:haste_lethargy" in keys(sheet)
