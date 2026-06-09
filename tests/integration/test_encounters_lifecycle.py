"""POST /sessions/{id}/encounter — creazione incontro (routers/encounters.py)."""
from __future__ import annotations

from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session


async def test_create_full_encounter_auto_adds_pcs(client, test_session_factory):
    sid, char_id = await seed_session(test_session_factory)
    r = await client.post(f"/sessions/{sid}/encounter", json={"mode": "full"})
    assert r.status_code == 201, r.text
    enc = r.json()
    assert enc["mode"] == "full"
    assert enc["status"] == "setup"
    assert enc["round"] == 1
    pcs = [c for c in enc["combatants"] if c["kind"] == "pc"]
    assert len(pcs) == 1
    assert pcs[0]["character_id"] == char_id
    assert pcs[0]["owner_user_id"] == PLAYER_ID
    assert pcs[0]["name"] == "Eroe"
    assert pcs[0]["initiative_mod"] == 3     # DEX 16 -> +3
    assert pcs[0]["initiative"] is None


async def test_create_requires_gm(client, test_session_factory):
    sid, _ = await seed_session(test_session_factory)
    as_user(PLAYER_ID)
    r = await client.post(f"/sessions/{sid}/encounter", json={"mode": "light"})
    assert r.status_code == 403, r.text


async def test_double_open_encounter_is_409(client, test_session_factory):
    sid, _ = await seed_session(test_session_factory)
    r1 = await client.post(f"/sessions/{sid}/encounter", json={"mode": "light"})
    assert r1.status_code == 201, r1.text
    r2 = await client.post(f"/sessions/{sid}/encounter", json={"mode": "full"})
    assert r2.status_code == 409, r2.text


async def test_invalid_mode_is_422(client, test_session_factory):
    sid, _ = await seed_session(test_session_factory)
    r = await client.post(f"/sessions/{sid}/encounter", json={"mode": "epic"})
    assert r.status_code == 422, r.text
