"""B8 (playtest 2026-11-16): la cura di un incantesimo arriva a un PG seduto alla stessa serata attiva, verificato dal server."""
from __future__ import annotations

from core.db.models import Character
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session
from tests.integration.rules.test_2014_bard_inspiration import _seat


async def _healer(client, factory, srd="healing-word", name="Parola Guaritrice", level=1) -> tuple[int, int]:
    as_user(GM_ID)
    cid = (await client.post("/characters", json={"name": "Ilse"})).json()["id"]
    r = await client.post(f"/characters/{cid}/spells", json={"name": name, "srd_index": srd, "level": level})
    assert r.status_code == 201, r.text
    await _seat(factory, cid, GM_ID)
    return cid, r.json()["id"]


async def _down(factory, cid) -> None:
    async with factory() as s:
        brann = await s.get(Character, cid)
        brann.hit_points, brann.current_hit_points = 30, 0
        brann.death_saves = {"successes": 1, "failures": 2, "stable": False}
        await s.commit()


async def test_healing_word_brings_a_downed_ally_back_and_clears_his_death_saves(client, test_session_factory):
    _, brann = await seed_session(test_session_factory)
    ilse, spell = await _healer(client, test_session_factory)
    await _down(test_session_factory, brann)
    as_user(GM_ID)
    r = await client.post(f"/characters/{ilse}/spells/{spell}/roll_healing", json={"casting_level": 1, "target_character_ids": [brann]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["healed"] == 0 and body["healed_allies"] == [{"id": brann, "name": "Eroe", "healed": body["total"]}]
    async with test_session_factory() as s:
        row = await s.get(Character, brann)
        assert row.current_hit_points == body["total"] > 0
        assert row.death_saves == {"successes": 0, "failures": 0, "stable": False}


async def test_the_target_must_sit_at_the_same_evening_and_a_single_target_spell_heals_one(client, test_session_factory):
    _, brann = await seed_session(test_session_factory)
    ilse, spell = await _healer(client, test_session_factory)
    as_user(PLAYER_ID)
    stranger = (await client.post("/characters", json={"name": "Altrove"})).json()["id"]
    as_user(GM_ID)
    url = f"/characters/{ilse}/spells/{spell}/roll_healing"
    r = await client.post(url, json={"target_character_ids": [stranger]})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_target"
    r = await client.post(url, json={"target_character_ids": [brann], "apply_to_self": True})  # Parola Guaritrice: una creatura
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_target"


async def test_mass_healing_word_heals_the_caster_and_the_ally_of_the_same_total(client, test_session_factory):
    _, brann = await seed_session(test_session_factory)
    ilse, spell = await _healer(client, test_session_factory, "mass-healing-word", "Parola Guaritrice di Massa", 3)
    await _down(test_session_factory, brann)
    as_user(GM_ID)
    r = await client.post(f"/characters/{ilse}/spells/{spell}/roll_healing",
                          json={"casting_level": 3, "target_character_ids": [brann], "apply_to_self": True})
    assert r.status_code == 200, r.text
    assert r.json()["healed_allies"][0]["healed"] == r.json()["total"]
