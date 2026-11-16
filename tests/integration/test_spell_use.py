"""POST /characters/{id}/spells/{spell_id}/use — spend a slot, maybe start concentration.

D&D 5e rules encoded:
- Casting from a slot decrements that level's availability (``used += 1``).
- A concentration spell sets ``concentrating_spell_id``; a non-concentration one
  leaves it ``None``.
- No slot configured at the requested level → 400.
- All slots at that level already spent → 400.
- Unknown spell id → 404.

Contract: the response is a ``CharacterFull`` whose ``spell_slots`` match the FE
``SpellSlot`` shape (``available = total - used``) and whose
``concentrating_spell_id`` mirrors the cast (api.spells.use in client.ts).
"""
from __future__ import annotations


async def _create_character(client) -> int:
    r = await client.post("/characters", json={"name": "Caster"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _add_slot(client, cid: int, level: int, total: int, used: int = 0):
    r = await client.post(
        f"/characters/{cid}/spell_slots",
        json={"level": level, "total": total, "used": used},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _add_spell(client, cid: int, *, name="Test Spell", level=1, is_concentration=False) -> int:
    r = await client.post(
        f"/characters/{cid}/spells",
        json={"name": name, "level": level, "is_concentration": is_concentration},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _slot_at(body: dict, level: int) -> dict:
    return next(s for s in body["spell_slots"] if s["level"] == level)


async def test_use_spell_consumes_a_slot(client):
    cid = await _create_character(client)
    await _add_slot(client, cid, level=1, total=2)
    spell_id = await _add_spell(client, cid, level=1)

    r = await client.post(f"/characters/{cid}/spells/{spell_id}/use", json={"slot_level": 1})
    assert r.status_code == 200, r.text
    slot = _slot_at(r.json(), 1)
    assert slot["used"] == 1
    assert slot["available"] == 1


async def test_concentration_spell_sets_tracking(client):
    cid = await _create_character(client)
    await _add_slot(client, cid, level=1, total=1)
    spell_id = await _add_spell(client, cid, level=1, is_concentration=True)

    r = await client.post(f"/characters/{cid}/spells/{spell_id}/use", json={"slot_level": 1})
    assert r.status_code == 200, r.text
    assert r.json()["concentrating_spell_id"] == spell_id


async def test_non_concentration_spell_leaves_tracking_none(client):
    cid = await _create_character(client)
    await _add_slot(client, cid, level=1, total=1)
    spell_id = await _add_spell(client, cid, level=1, is_concentration=False)

    r = await client.post(f"/characters/{cid}/spells/{spell_id}/use", json={"slot_level": 1})
    assert r.status_code == 200, r.text
    assert r.json()["concentrating_spell_id"] is None


async def test_no_slot_configured_is_400(client):
    cid = await _create_character(client)
    spell_id = await _add_spell(client, cid, level=3)
    # No slots configured at all → level 3 has no slot.
    r = await client.post(f"/characters/{cid}/spells/{spell_id}/use", json={"slot_level": 3})
    assert r.status_code == 400, r.text


async def test_no_slots_available_is_400(client):
    cid = await _create_character(client)
    await _add_slot(client, cid, level=1, total=1)
    spell_id = await _add_spell(client, cid, level=1)

    r1 = await client.post(f"/characters/{cid}/spells/{spell_id}/use", json={"slot_level": 1})
    assert r1.status_code == 200, r1.text  # spends the only slot
    r2 = await client.post(f"/characters/{cid}/spells/{spell_id}/use", json={"slot_level": 1})
    assert r2.status_code == 400, r2.text


async def test_unknown_spell_is_404(client):
    cid = await _create_character(client)
    await _add_slot(client, cid, level=1, total=1)
    r = await client.post(f"/characters/{cid}/spells/999999/use", json={"slot_level": 1})
    assert r.status_code == 404, r.text


async def _turn(client, cid: int) -> dict:
    return (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]


async def _spell_with_time(client, cid: int, name: str, level: int, casting_time: str | None) -> int:
    r = await client.post(f"/characters/{cid}/spells", json={"name": name, "level": level, "casting_time": casting_time})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_casting_marks_the_turn_slot_of_its_casting_time(client):
    """B4 (playtest 2026-11-16): Palla di Fuoco segna l'azione, Scudo la reazione, Parola Guaritrice l'azione bonus;
    un secondo lancio con lo slot già segnato non viene rifiutato."""
    cid = await _create_character(client)
    await _add_slot(client, cid, level=3, total=1)
    fireball = await _spell_with_time(client, cid, "Palla di Fuoco", 3, "1 azione")
    assert (await client.post(f"/characters/{cid}/spells/{fireball}/use", json={"slot_level": 3})).status_code == 200
    turn = await _turn(client, cid)
    assert turn["action_used"] and not turn["bonus_used"] and not turn["reaction_used"]
    other = await _create_character(client)
    await _add_slot(client, other, level=1, total=4)
    shield = await _spell_with_time(client, other, "Scudo", 1, "1 reazione")
    word = await _spell_with_time(client, other, "Parola Guaritrice", 1, "1 azione bonus")
    assert (await client.post(f"/characters/{other}/spells/{word}/use", json={"slot_level": 1})).status_code == 200
    assert (await client.post(f"/characters/{other}/spells/{shield}/use", json={"slot_level": 1})).status_code == 200
    turn = await _turn(client, other)
    assert turn["reaction_used"] and turn["bonus_used"] and not turn["action_used"]
    again = await client.post(f"/characters/{other}/spells/{shield}/use", json={"slot_level": 1})
    assert again.status_code == 200, again.text


async def test_cantrip_marks_the_action_and_long_or_ritual_casts_do_not(client):
    cid = await _create_character(client)
    await _add_slot(client, cid, level=1, total=1)
    cantrip = await _spell_with_time(client, cid, "Fiamma Sacra", 0, "1 azione")
    assert (await client.post(f"/characters/{cid}/spells/{cantrip}/use", json={})).status_code == 200
    assert (await _turn(client, cid))["action_used"]
    other = await _create_character(client)
    await _add_slot(client, other, level=1, total=1)
    long_cast = await _spell_with_time(client, other, "Allarme", 1, "1 minuto")
    assert (await client.post(f"/characters/{other}/spells/{long_cast}/use", json={"slot_level": 1})).status_code == 200
    turn = await _turn(client, other)
    assert not (turn["action_used"] or turn["bonus_used"] or turn["reaction_used"])


async def _encounter_caster(client, test_session_factory, monkeypatch) -> tuple[int, int]:
    """Un PG combattente in uno scontro attivo, con il turno in mano (primo nell'ordine)."""
    from tests.integration.rules.test_2014_barbarian_round1 import _in_encounter
    sid, cid = await _in_encounter(client, test_session_factory, monkeypatch)
    await _add_slot(client, cid, level=1, total=4)
    return sid, cid


async def _next_turns(client, sid: int, times: int) -> None:
    from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user
    as_user(GM_ID)
    for _ in range(times):
        assert (await client.post(f"/sessions/{sid}/encounter/next-turn")).status_code == 200
    as_user(PLAYER_ID)


async def test_in_an_encounter_a_cast_with_the_slot_already_used_is_refused_and_spends_nothing(client, test_session_factory, monkeypatch):
    sid, cid = await _encounter_caster(client, test_session_factory, monkeypatch)
    bolt = await _spell_with_time(client, cid, "Dardo", 1, "1 azione")
    shield = await _spell_with_time(client, cid, "Scudo", 1, "1 reazione")
    assert (await client.post(f"/characters/{cid}/spells/{bolt}/use", json={"slot_level": 1})).status_code == 200
    again = await client.post(f"/characters/{cid}/spells/{bolt}/use", json={"slot_level": 1})
    assert again.status_code == 409 and again.json()["detail"]["code"] == "turn_slot_used"
    full = (await client.get(f"/characters/{cid}")).json()
    assert _slot_at(full, 1)["used"] == 1  # il rifiuto annulla anche lo slot
    assert (await client.post(f"/characters/{cid}/spells/{shield}/use", json={"slot_level": 1})).status_code == 200
    assert (await client.post(f"/characters/{cid}/spells/{shield}/use", json={"slot_level": 1})).status_code == 409
    await _next_turns(client, sid, 3)  # i due goblin e di nuovo il PG: azione e reazione tornano
    turn = await _turn(client, cid)
    assert not turn["action_used"] and not turn["reaction_used"]
    assert (await client.post(f"/characters/{cid}/spells/{shield}/use", json={"slot_level": 1})).status_code == 200


async def test_action_surge_lets_a_second_action_spell_through_in_an_encounter(client, test_session_factory, monkeypatch):
    sid, cid = await _encounter_caster(client, test_session_factory, monkeypatch)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 2, "hit_die": 10})
    assert r.status_code == 201, r.text
    full = (await client.get(f"/characters/{cid}")).json()
    if not any(x["level"] == 1 for x in full["spell_slots"]):  # la classe nuova può aver rifatto gli slot
        await _add_slot(client, cid, level=1, total=4)
    bolt = await _spell_with_time(client, cid, "Dardo", 1, "1 azione")
    first = await client.post(f"/characters/{cid}/spells/{bolt}/use", json={"slot_level": 1})
    assert first.status_code == 200, first.text
    surge = await client.post(f"/characters/{cid}/features/fighter.action_surge/use", json={})
    assert surge.status_code == 200, surge.text
    second = await client.post(f"/characters/{cid}/spells/{bolt}/use", json={"slot_level": 1})
    assert second.status_code == 200, second.text
    assert (await _turn(client, cid))["extra_actions"] == 0
