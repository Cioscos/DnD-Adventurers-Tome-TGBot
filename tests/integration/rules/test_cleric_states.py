"""Chierico 2014, giro di correzione 1: stati che durano meno del riposo (I2), TS superato (I3), Manto di Ombre (I4),
concentrazione (I10), nota dell'Ingannatore (M2), Collera Distruttiva (M3), `incapacitated` (M9)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import select

from core.db.models import Character, ConditionEffect
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user
from tests.integration.rules.test_2014_barbarian import _barbarian, _weapon
from tests.integration.rules.test_2014_barbarian_round1 import _in_encounter
from tests.integration.rules.test_2014_bard import _full, _spells, _states, _use
from tests.integration.rules.test_2014_cleric import DOMAINS, _cleric
from tests.integration.rules.test_2014_cleric_late import _spell, _table


def _char(*states: dict):
    return SimpleNamespace(active_states=list(states), conditions={}, is_dead=False, settings={}, concentrating_spell_id=None)


def _state(key, rounds, ends=("manual",)):
    return {"key": key, "feature_key": "x", "rounds_left": rounds, "ends_on": list(ends), "data": {}}


# --- I2: i riposi chiudono gli stati più brevi del riposo -------------------------------------------------------------

def test_a_short_rest_closes_what_lasts_an_hour_or_less_and_a_long_rest_what_lasts_eight():
    from api.services.rules_states import end_states_on_rest
    short = _char(_state("a", 10), _state("b", 600), _state("c", 601), _state("d", None), _state("e", 4800))
    assert end_states_on_rest(short, "short") == ["a", "b"]
    assert [s["key"] for s in short.active_states] == ["c", "d", "e"]
    long = _char(_state("a", 10), _state("c", 601), _state("d", None), _state("e", 4800), _state("f", 4801))
    assert end_states_on_rest(long, "long") == ["a", "c", "e"]
    assert [s["key"] for s in long.active_states] == ["d", "f"]  # senza durata o di giorni: restano a chi li chiude


def test_a_state_that_names_the_rest_still_ends_with_it():
    from api.services.rules_states import end_states_on_rest
    c = _char(_state("rest", None, ("rest_short", "rest_long")), _state("long_only", None, ("rest_long",)))
    assert end_states_on_rest(c, "short") == ["rest"]
    assert end_states_on_rest(c, "long") == ["long_only"]


@pytest.mark.parametrize("rest", ["short", "long"])
async def test_knowledge_of_the_ages_and_read_thoughts_do_not_survive_a_rest(client, rest):
    cid = await _cleric(client, 8, "knowledge", wisdom=16)
    assert (await _use(client, cid, "cleric.knowledge_of_the_ages", params={"skill": "arcana"})).status_code == 200
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _use(client, cid, "cleric.read_thoughts")).status_code == 200
    assert {s["key"] for s in await _states(client, cid)} == {"knowledge_of_the_ages", "read_thoughts"}
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": rest, "confirm_early": True})
    assert r.status_code == 200, r.text
    assert await _states(client, cid) == []


async def test_after_a_long_rest_the_free_cast_is_no_longer_authorised(client):
    cid = await _cleric(client, 8, "knowledge", wisdom=16)
    spell = next(s for s in (await _spells(client, cid)).values() if s["srd_index"] == "suggestion")
    await _use(client, cid, "cleric.read_thoughts")
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})
    await client.post(f"/characters/{cid}/turn/new")
    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={"free_cast": True})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "free_cast_unavailable"


async def test_the_barbarian_rage_still_ends_with_a_long_rest(client):
    cid = await _barbarian(client, 5)
    assert (await _use(client, cid, "barbarian.rage")).status_code == 200
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})
    assert await _states(client, cid) == []


# --- I3: in incontro un TS superato chiude lo stato di Lettura del Pensiero ----------------------------------------------

async def test_a_passed_save_closes_read_thoughts_and_a_failed_one_keeps_it(client, test_session_factory, monkeypatch):
    sid, cid = await _in_encounter(client, test_session_factory, monkeypatch)
    r = await client.post(f"/characters/{cid}/classes", json={
        "class_name": "cleric", "level": 8, "hit_die": 8, "subclass": DOMAINS["knowledge"]})
    assert r.status_code == 201, r.text
    as_user(GM_ID)
    enc = (await client.get(f"/sessions/{sid}/live")).json()["encounter"]
    g1, g2 = [c["id"] for c in enc["combatants"] if c["kind"] == "monster"]
    as_user(PLAYER_ID)
    key = "cleric.read_thoughts"

    async def read(target):
        await client.post(f"/characters/{cid}/turn/new")
        assert (await client.post(f"/characters/{cid}/features/{key}/use", json={})).status_code == 200
        return await client.post(f"/characters/{cid}/target-effects", json={"combatant_id": target, "effect_key": key})

    async def resolve(target, passed):
        as_user(GM_ID)
        live = (await client.get(f"/sessions/{sid}/live")).json()["encounter"]
        save = next(c for c in live["combatants"] if c["id"] == target)["pending_saves"][0]
        r = await client.post(f"/sessions/{sid}/encounter/pending-saves/{save['id']}/resolve", json={"passed": passed})
        assert r.status_code == 200, r.text
        as_user(PLAYER_ID)

    assert (await read(g1)).json()["pending_save_id"] is not None
    await resolve(g1, passed=False)
    assert [s["key"] for s in await _states(client, cid)] == ["read_thoughts"]  # il TS fallito lo lascia
    assert (await read(g2)).json()["pending_save_id"] is not None
    await resolve(g2, passed=True)
    assert await _states(client, cid) == []  # il TS superato: niente lettura, niente lancio gratuito


# --- I4: Manto di Ombre ------------------------------------------------------------------------------------------------

async def test_cloak_of_shadows_makes_you_invisible_and_any_attack_or_cast_ends_it_on_the_server(client):
    cid = await _cleric(client, 6, "trickery", strength=14)
    sword = await _weapon(client, cid, "Mazza", damage_dice="1d6")
    assert (await _use(client, cid, "cleric.cloak_of_shadows")).status_code == 200
    assert (await _full(client, cid))["conditions"].get("invisible") is True
    r = await client.post(f"/characters/{cid}/items/{sword}/attack", json={"die": 10})  # senza alcuna opzione
    assert r.status_code == 200, r.text
    assert await _states(client, cid) == [] and not (await _full(client, cid))["conditions"].get("invisible")

    await client.post(f"/characters/{cid}/turn/new")
    await _use(client, cid, "cleric.cloak_of_shadows")
    spell = await _spell(client, cid, "Dardo", "force", 1, "1d4")
    assert (await client.post(f"/characters/{cid}/spells/{spell}/use", json={"slot_level": 1})).status_code == 200
    assert await _states(client, cid) == [] and not (await _full(client, cid))["conditions"].get("invisible")


async def test_cloak_of_shadows_leaves_the_invisibility_of_another_source_alone(client):
    cid = await _cleric(client, 6, "trickery")
    assert (await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"invisible": True}})).status_code == 200
    await _use(client, cid, "cleric.cloak_of_shadows")
    for _ in range(2):  # i 2 round passano: lo stato finisce
        await client.post(f"/characters/{cid}/rounds/tick")
    assert await _states(client, cid) == []
    assert (await _full(client, cid))["conditions"].get("invisible") is True


async def test_cloak_of_shadows_expiring_removes_the_invisibility(client):
    cid = await _cleric(client, 6, "trickery")
    await _use(client, cid, "cleric.cloak_of_shadows")
    for _ in range(2):
        await client.post(f"/characters/{cid}/rounds/tick")
    assert await _states(client, cid) == [] and not (await _full(client, cid))["conditions"].get("invisible")


# --- M9: incapacitated non viene dalla scheda né dal manuale ----------------------------------------------------------

@pytest.mark.parametrize("key,domain,level", [("cleric.cloak_of_shadows", "trickery", 6), ("cleric.read_thoughts", "knowledge", 6),
                                              ("cleric.corona_of_light", "light", 17)])
async def test_being_incapacitated_does_not_end_these_states(client, key, domain, level):
    cid = await _cleric(client, level, domain, wisdom=16)
    assert (await _use(client, cid, key)).status_code == 200
    assert (await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"stunned": True}})).status_code == 200
    assert [s["key"] for s in await _states(client, cid)] == [key.split(".")[1]]


# --- I10: la concentrazione presa da un privilegio rilascia gli effetti dell'incantesimo precedente ------------------------

async def test_a_feature_taking_the_concentration_releases_the_effects_of_the_previous_spell(client, test_session_factory):
    cid = await _cleric(client, 6, "trickery", wisdom=16)
    sp = {s["srd_index"]: s for s in (await _full(client, cid))["spells"]}
    r = await client.post(f"/characters/{cid}/spells/{sp['pass-without-trace']['id']}/use", json={"slot_level": 2})
    assert r.status_code == 200, r.text
    async with test_session_factory() as s:
        other = Character(user_id=9, name="Bersaglio")
        s.add(other)
        await s.flush()
        s.add(ConditionEffect(character_id=other.id, slug="restrained", source_character_id=cid, ends_with_concentration=True,
                              source_spell_id=sp["pass-without-trace"]["id"], created_at="2026-01-01"))
        await s.commit()
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _use(client, cid, "cleric.invoke_duplicity")).status_code == 200
    async with test_session_factory() as s:
        assert (await s.execute(select(ConditionEffect))).scalars().all() == []


# --- M2 e M3 ---------------------------------------------------------------------------------------------------------------

async def test_blessing_of_the_trickster_on_an_ally_closes_the_earlier_note(client, test_session_factory):
    sid, cleric, hero = await _table(client, test_session_factory, 6, "trickery")
    as_user(GM_ID)
    key = "cleric.blessing_of_the_trickster"
    assert (await _use(client, cleric, key)).status_code == 200
    assert [s["key"] for s in await _states(client, cleric)] == ["trickster_blessing_note"]
    await client.post(f"/characters/{cleric}/turn/new")
    r = await client.post(f"/characters/{cleric}/features/{key}/use", json={"params": {"target_character_id": hero}})
    assert r.status_code == 200, r.text
    assert await _states(client, cleric) == []  # la nota cade: lo stato sta sull'alleato


async def test_the_wrath_state_says_maximized_only_when_the_server_maximised(client):
    cid = await _cleric(client, 1, "tempest", wisdom=16)
    r = await _use(client, cid, "cleric.wrath_of_the_storm", params={"damage_type": "thunder", "destructive": True})
    assert r.status_code == 200, r.text
    assert r.json()["state"]["data"]["maximized"] is False  # a 1° livello Collera Distruttiva non c'è: nessuna spesa


def test_the_concentration_of_a_closed_state_ends_with_it_but_not_that_of_a_spell():
    from api.services.rules_states import end_states_on_rest
    held = _char(_state("invoke_duplicity", 10))
    held.settings = {"concentration_item_spell": {"feature_key": "x", "name": "Duplicato"}, "concentration_rounds_left": 5}
    end_states_on_rest(held, "short")
    assert held.settings == {}
    spell = _char()
    spell.settings, spell.concentrating_spell_id = {"concentration_rounds_left": 5}, 3
    end_states_on_rest(spell, "short")
    assert spell.concentrating_spell_id == 3 and spell.settings == {"concentration_rounds_left": 5}
