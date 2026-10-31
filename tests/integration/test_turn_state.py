"""GET /characters/{id}/turn-state (routers/sessions.py)."""
from __future__ import annotations

from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session
from tests.integration.test_encounters_turns import setup_full_encounter


async def test_turn_state_not_in_session(client, test_session_factory):
    _, char_id = await seed_session(test_session_factory)
    as_user(PLAYER_ID)
    r = await client.get(f"/characters/{char_id}/turn-state")
    assert r.status_code == 200, r.text
    assert r.json() == {"in_encounter": False, "is_my_turn": False, "round": None, "session_id": None}


async def test_turn_state_my_turn_true(client, test_session_factory):
    sid, enc = await setup_full_encounter(client, test_session_factory)
    pc = next(c for c in enc["combatants"] if c["kind"] == "pc")
    as_user(GM_ID)
    r = await client.post(f"/sessions/{sid}/encounter/start", json={})
    assert r.status_code == 200, r.text
    as_user(PLAYER_ID)
    r = await client.get(f"/characters/{pc['character_id']}/turn-state")
    assert r.json() == {"in_encounter": True, "is_my_turn": True, "round": 1, "session_id": sid}
    # Dopo next-turn tocca a un goblin.
    as_user(GM_ID)
    await client.post(f"/sessions/{sid}/encounter/next-turn")
    as_user(PLAYER_ID)
    r = await client.get(f"/characters/{pc['character_id']}/turn-state")
    assert r.json()["in_encounter"] is True and r.json()["is_my_turn"] is False


async def test_turn_state_other_user_forbidden(client, test_session_factory):
    _, char_id = await seed_session(test_session_factory)
    r = await client.get(f"/characters/{char_id}/turn-state")  # GM_ID non è il proprietario
    assert r.status_code == 403
