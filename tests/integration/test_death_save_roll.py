"""D&D 5e death-save roll rules (POST /characters/{id}/death_saves/roll).

The endpoint accepts an optional client-supplied ``die`` value (D20RollSubmission),
so every branch is exercised deterministically without RNG:

    nat 20 → revive with 1 HP, saves reset
    nat 1  → counts as 2 failures
    10+    → 1 success (3 successes ⇒ stable)
    2–9    → 1 failure  (3 failures ⇒ dead)
"""
from __future__ import annotations


async def _create_character(client) -> int:
    r = await client.post("/characters", json={"name": "Death Test"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _roll(client, cid: int, die: int):
    r = await client.post(f"/characters/{cid}/death_saves/roll", json={"die": die})
    assert r.status_code == 200, r.text
    return r.json()


async def test_nat20_revives_with_1_hp(client):
    cid = await _create_character(client)
    res = await _roll(client, cid, 20)
    assert res["outcome"] == "nat20"
    assert res["revived"] is True
    assert res["current_hp"] == 1
    assert res["successes"] == 0 and res["failures"] == 0
    assert res["stable"] is False


async def test_nat1_counts_as_two_failures(client):
    cid = await _create_character(client)
    res = await _roll(client, cid, 1)
    assert res["outcome"] == "nat1"
    assert res["failures"] == 2
    assert res["successes"] == 0
    assert res["revived"] is False


async def test_ten_or_more_is_a_success(client):
    cid = await _create_character(client)
    res = await _roll(client, cid, 10)
    assert res["outcome"] == "success"
    assert res["successes"] == 1
    res = await _roll(client, cid, 15)
    assert res["outcome"] == "success"
    assert res["successes"] == 2


async def test_two_to_nine_is_a_failure(client):
    cid = await _create_character(client)
    res = await _roll(client, cid, 9)
    assert res["outcome"] == "failure"
    assert res["failures"] == 1
    res = await _roll(client, cid, 2)
    assert res["failures"] == 2


async def test_three_successes_become_stable(client):
    cid = await _create_character(client)
    await _roll(client, cid, 10)
    await _roll(client, cid, 12)
    res = await _roll(client, cid, 19)  # 19 ⇒ success
    assert res["successes"] == 3
    assert res["stable"] is True


async def test_three_failures_kill_the_character(client):
    cid = await _create_character(client)
    res = await _roll(client, cid, 1)  # 2 failures
    assert res["failures"] == 2
    res = await _roll(client, cid, 5)  # +1 ⇒ 3 failures, dead
    assert res["failures"] == 3
    # Once dead, the endpoint short-circuits and returns die=0 (no further rolling).
    res = await _roll(client, cid, 20)
    assert res["die"] == 0
    assert res["revived"] is False
