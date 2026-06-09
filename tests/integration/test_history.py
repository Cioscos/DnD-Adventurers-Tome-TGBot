"""History (audit log) endpoints — routers/history.py.

  - GET    /characters/{id}/history                    → newest-first, capped at 200
  - GET    /characters/{id}/history/retention-preview  → purge-count preview
  - DELETE /characters/{id}/history                     → wipe

History rows are normally written as side-effects of many mutations, but the
retention-preview "days" branch needs rows with *old* timestamps (the API only
ever writes `now`). So we seed `CharacterHistory` directly through the test
session factory (same SQLite file the overridden `get_db` reads). `timestamp`
is stored as an ISO string and compared lexicographically by the router.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import delete

from core.db.models import Character, CharacterHistory

TEST_USER_ID = 1234  # mirrors tests/integration/conftest.py


async def _make_char(client) -> int:
    r = await client.post("/characters", json={"name": "Hist"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _seed(factory, char_id: int, rows: list[tuple[str, str, str]]) -> None:
    """rows = [(timestamp_iso, event_type, description), ...]. Resets first."""
    async with factory() as s:
        await s.execute(delete(CharacterHistory).where(CharacterHistory.character_id == char_id))
        for ts, et, desc in rows:
            s.add(CharacterHistory(character_id=char_id, timestamp=ts, event_type=et, description=desc))
        await s.commit()


# --- GET /history -----------------------------------------------------------

async def test_get_history_returns_newest_first(client, test_session_factory):
    cid = await _make_char(client)
    await _seed(test_session_factory, cid, [
        ("2026-01-01T00:00:00", "hp", "oldest"),
        ("2026-03-01T00:00:00", "ac", "middle"),
        ("2026-06-01T00:00:00", "xp", "newest"),
    ])
    entries = (await client.get(f"/characters/{cid}/history")).json()
    assert [e["description"] for e in entries] == ["newest", "middle", "oldest"]


async def test_get_history_entry_shape_excludes_meta(client, test_session_factory):
    cid = await _make_char(client)
    await _seed(test_session_factory, cid, [("2026-06-01T00:00:00", "hp", "took 5 damage")])
    entry = (await client.get(f"/characters/{cid}/history")).json()[0]
    assert set(entry) == {"id", "timestamp", "event_type", "description"}
    assert "meta" not in entry  # HistoryEntryRead omits the JSON meta column


async def test_get_history_unknown_character_is_404(client):
    r = await client.get("/characters/999999/history")
    assert r.status_code == 404, r.text


async def test_get_history_other_owner_is_403(client, test_session_factory):
    async with test_session_factory() as s:
        other = Character(user_id=TEST_USER_ID + 1, name="NotMine")
        s.add(other)
        await s.commit()
        other_id = other.id
    r = await client.get(f"/characters/{other_id}/history")
    assert r.status_code == 403, r.text


# --- GET /history/retention-preview -----------------------------------------

async def test_retention_preview_events_count(client, test_session_factory):
    cid = await _make_char(client)
    await _seed(test_session_factory, cid, [
        (f"2026-06-0{i}T00:00:00", "hp", f"e{i}") for i in range(1, 6)  # 5 rows
    ])
    body = (await client.get(f"/characters/{cid}/history/retention-preview", params={"events": 2})).json()
    assert body["total"] == 5
    assert body["events_keep"] == 2
    assert body["would_purge_events"] == 3  # max(0, 5 - 2)


async def test_retention_preview_days_count(client, test_session_factory):
    cid = await _make_char(client)
    now = datetime.utcnow()
    old = (now - timedelta(days=100)).isoformat(timespec="seconds")
    recent = now.isoformat(timespec="seconds")
    await _seed(test_session_factory, cid, [
        (old, "hp", "old-1"),
        (old, "hp", "old-2"),
        (recent, "hp", "fresh"),
    ])
    body = (await client.get(f"/characters/{cid}/history/retention-preview", params={"days": 30})).json()
    assert body["days_window"] == 30
    assert body["would_purge_days"] == 2  # only the two 100-day-old rows are past the cutoff


async def test_retention_preview_validates_query_bounds(client):
    cid = await _make_char(client)
    assert (await client.get(f"/characters/{cid}/history/retention-preview", params={"events": 0})).status_code == 422
    assert (await client.get(f"/characters/{cid}/history/retention-preview", params={"days": 0})).status_code == 422


# --- DELETE /history --------------------------------------------------------

async def test_delete_history_wipes_all_rows(client, test_session_factory):
    cid = await _make_char(client)
    await _seed(test_session_factory, cid, [
        ("2026-06-01T00:00:00", "hp", "a"),
        ("2026-06-02T00:00:00", "ac", "b"),
    ])
    assert (await client.get(f"/characters/{cid}/history")).json()  # non-empty before
    r = await client.delete(f"/characters/{cid}/history")
    assert r.status_code == 204, r.text
    assert (await client.get(f"/characters/{cid}/history")).json() == []


async def test_delete_history_unknown_character_is_404(client):
    r = await client.delete("/characters/999999/history")
    assert r.status_code == 404, r.text
