"""GET/DELETE /characters/{id}/dice/stats — lettura raw e reset dei contatori."""
from __future__ import annotations

from core.db.models import Character
from tests.integration.conftest import TEST_USER_ID


async def _make_char(client) -> int:
    r = await client.post("/characters", json={"name": "Statistico"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _seed_stats(test_session_factory, char_id: int, stats: dict) -> None:
    async with test_session_factory() as s:
        char = await s.get(Character, char_id)
        char.dice_stats = stats
        await s.commit()


async def test_get_empty_stats(client):
    cid = await _make_char(client)
    r = await client.get(f"/characters/{cid}/dice/stats")
    assert r.status_code == 200, r.text
    assert r.json() == {"stats": {}}


async def test_get_returns_seeded_stats(client, test_session_factory):
    cid = await _make_char(client)
    await _seed_stats(test_session_factory, cid, {"d20": {"20": 2, "1": 1}})
    r = await client.get(f"/characters/{cid}/dice/stats")
    assert r.status_code == 200, r.text
    assert r.json() == {"stats": {"d20": {"20": 2, "1": 1}}}


async def test_delete_resets_stats(client, test_session_factory):
    cid = await _make_char(client)
    await _seed_stats(test_session_factory, cid, {"d6": {"3": 7}})
    r = await client.delete(f"/characters/{cid}/dice/stats")
    assert r.status_code == 204, r.text
    r = await client.get(f"/characters/{cid}/dice/stats")
    assert r.json() == {"stats": {}}


async def test_unknown_character_is_404(client):
    assert (await client.get("/characters/999999/dice/stats")).status_code == 404
    assert (await client.delete("/characters/999999/dice/stats")).status_code == 404


async def test_foreign_character_is_403(client, test_session_factory):
    async with test_session_factory() as s:
        other = Character(user_id=TEST_USER_ID + 1, name="NotMine")
        s.add(other)
        await s.commit()
        other_id = other.id
    assert (await client.get(f"/characters/{other_id}/dice/stats")).status_code == 403
    assert (await client.delete(f"/characters/{other_id}/dice/stats")).status_code == 403
