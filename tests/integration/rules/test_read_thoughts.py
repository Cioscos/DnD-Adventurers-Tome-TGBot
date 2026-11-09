"""Lettura del Pensiero (R43): uno stato attivo autorizza il lancio di suggestione senza slot."""
from __future__ import annotations

from tests.integration.rules.test_2014_bard import _ability, _full, _spells, _states, _use
from tests.integration.rules.test_2014_barbarian import _turn
from tests.integration.rules.test_2014_cleric import POOL, _cleric

KEY = "cleric.read_thoughts"


async def _suggestion(client, cid) -> dict:
    return next(s for s in (await _spells(client, cid)).values() if s["srd_index"] == "suggestion")


async def _slots(client, cid) -> dict:
    return {s["level"]: s["available"] for s in (await _full(client, cid))["spell_slots"]}


async def _free(client, cid, spell, **body):
    return await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={"free_cast": True, **body})


async def test_read_thoughts_starts_a_state_with_dc_duration_and_the_free_cast(client):
    cid = await _cleric(client, 6, "knowledge", wisdom=16)  # competenza +3, Saggezza +3
    r = await _use(client, cid, KEY)
    assert r.status_code == 200, r.text
    state = r.json()["state"]
    assert state["rounds_left"] == 10 and state["data"]["dc"] == 14 and state["data"]["free_cast"] == "suggestion"
    assert r.json()["targets"] == [KEY]  # il TS del bersaglio lo gestisce l'incontro (D1)
    assert (await _ability(client, cid, POOL))["uses"] == 1 and (await _turn(client, cid))["action_used"] is True


async def test_without_the_state_a_free_cast_is_refused_and_nothing_is_spent(client):
    cid = await _cleric(client, 6, "knowledge")
    spell, slots = await _suggestion(client, cid), await _slots(client, cid)
    r = await _free(client, cid, spell)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "free_cast_unavailable"
    assert await _slots(client, cid) == slots and (await _turn(client, cid))["action_used"] is False


async def test_with_the_state_the_cast_costs_the_action_not_a_slot_and_closes_the_state(client):
    cid = await _cleric(client, 6, "knowledge")
    spell, slots = await _suggestion(client, cid), await _slots(client, cid)
    await _use(client, cid, KEY)
    await client.post(f"/characters/{cid}/turn/new")
    r = await _free(client, cid, spell)
    assert r.status_code == 200, r.text
    assert await _slots(client, cid) == slots
    assert (await _turn(client, cid))["action_used"] is True
    assert [s["key"] for s in await _states(client, cid)] == []
    assert (await _full(client, cid))["concentrating_spell_id"] == spell["id"]  # suggestione è a concentrazione
    again = await _free(client, cid, spell)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "free_cast_unavailable"


async def test_the_state_does_not_authorise_another_spell(client):
    cid = await _cleric(client, 6, "knowledge")
    other = next(s for s in (await _spells(client, cid)).values() if s["srd_index"] == "identify")
    await _use(client, cid, KEY)
    await client.post(f"/characters/{cid}/turn/new")
    r = await _free(client, cid, other)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "free_cast_unavailable"
    assert len(await _states(client, cid)) == 1


async def test_a_spent_action_refuses_the_free_cast_and_keeps_the_state(client):
    cid = await _cleric(client, 6, "knowledge")
    spell = await _suggestion(client, cid)
    await _use(client, cid, KEY)  # l'azione è spesa dall'uso stesso
    r = await _free(client, cid, spell)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "turn_slot_used"
    assert len(await _states(client, cid)) == 1


async def test_a_normal_cast_with_a_slot_is_untouched_by_the_state(client):
    cid = await _cleric(client, 6, "knowledge")
    spell, slots = await _suggestion(client, cid), await _slots(client, cid)
    await _use(client, cid, KEY)
    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={"slot_level": 2})
    assert r.status_code == 200 and (await _slots(client, cid))[2] == slots[2] - 1
    assert len(await _states(client, cid)) == 1  # senza free_cast lo stato resta


async def test_read_thoughts_needs_level_6_and_the_knowledge_domain(client):
    assert (await _use(client, await _cleric(client, 5, "knowledge"), KEY)).status_code == 404
    assert (await _use(client, await _cleric(client, 6, "war"), KEY)).status_code == 404
