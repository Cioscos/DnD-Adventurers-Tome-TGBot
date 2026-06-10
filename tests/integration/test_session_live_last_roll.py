"""Filtro joined_at su last_roll nel live di sessione (routers/sessions.py).

I tiri fatti PRIMA di entrare in sessione non devono comparire nella riga
del giocatore; quelli senza timestamp (legacy) sono trattati come pre-sessione.
"""
from __future__ import annotations

from sqlalchemy import select

from core.db.models import Character
from tests.integration._encounter_helpers import NOW, seed_session

BEFORE_JOIN = "2026-06-09T09:59:00"   # < NOW ("2026-06-09T10:00:00")
AFTER_JOIN = "2026-06-09T10:05:00"


async def _set_rolls_history(test_session_factory, char_id: int, history: list) -> None:
    async with test_session_factory() as s:
        char = (await s.execute(select(Character).where(Character.id == char_id))).scalar_one()
        char.rolls_history = history
        await s.commit()


async def _hero_snapshot(client, sid: int) -> dict:
    r = await client.get(f"/sessions/{sid}/live")
    assert r.status_code == 200, r.text
    return next(c for c in r.json()["live_characters"] if c["name"] == "Eroe")


async def test_pre_session_roll_is_hidden(client, test_session_factory):
    sid, char_id = await seed_session(test_session_factory)
    await _set_rolls_history(test_session_factory, char_id, [
        {"notation": "d20", "rolls": [4], "total": 4, "timestamp": BEFORE_JOIN},
    ])
    assert (await _hero_snapshot(client, sid))["last_roll"] is None


async def test_in_session_roll_is_shown(client, test_session_factory):
    sid, char_id = await seed_session(test_session_factory)
    await _set_rolls_history(test_session_factory, char_id, [
        {"notation": "d20", "rolls": [4], "total": 4, "timestamp": BEFORE_JOIN},
        {"notation": "d8", "rolls": [7], "total": 7, "timestamp": AFTER_JOIN},
    ])
    last = (await _hero_snapshot(client, sid))["last_roll"]
    assert last is not None
    assert last["notation"] == "d8" and last["total"] == 7


async def test_legacy_roll_without_timestamp_is_hidden(client, test_session_factory):
    sid, char_id = await seed_session(test_session_factory)
    await _set_rolls_history(test_session_factory, char_id, [
        {"notation": "d20", "rolls": [12], "total": 12},
    ])
    assert (await _hero_snapshot(client, sid))["last_roll"] is None
