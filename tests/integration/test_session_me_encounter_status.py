"""GET /sessions/me espone lo stato dell'incontro aperto (per il banner della scheda)."""
from __future__ import annotations

from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session
from tests.integration.test_encounters_turns import (
    install_fake_telegram,
    setup_full_encounter,
)


async def _status(client):
    r = await client.get("/sessions/me")
    assert r.status_code == 200, r.text
    return r.json()["encounter_status"]


async def test_me_without_encounter_has_null_status(client, test_session_factory):
    await seed_session(test_session_factory)
    assert await _status(client) is None


async def test_me_reports_setup_then_active_then_none(client, test_session_factory, monkeypatch):
    install_fake_telegram(monkeypatch)
    sid, _ = await setup_full_encounter(client, test_session_factory)
    assert await _status(client) == "setup"
    await client.post(f"/sessions/{sid}/encounter/start", json={})
    assert await _status(client) == "active"
    as_user(PLAYER_ID)
    assert await _status(client) == "active"
    as_user(GM_ID)
    await client.post(f"/sessions/{sid}/encounter/end")
    assert await _status(client) is None


async def test_me_participants_include_character_name(client, test_session_factory):
    await seed_session(test_session_factory)
    r = await client.get("/sessions/me")
    parts = {p["user_id"]: p for p in r.json()["participants"]}
    assert parts[PLAYER_ID]["character_name"] == "Eroe"
    assert parts[GM_ID]["character_name"] is None
