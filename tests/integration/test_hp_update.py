"""PATCH /characters/{id}/hp — HP operations and D&D 5e death-state rules.

Exercises the five ``HPOp`` branches plus the death-save accrual logic that
makes this endpoint the highest-risk piece of HP handling:

- ``DAMAGE`` absorbs temporary HP first, then clamps current HP at 0.
- A single drop to 0 just knocks the character unconscious (no failures); a hit
  taken while *already* at 0 accrues a death-save failure (two on a critical).
- Massive overflow damage (>= effective max past 0) is instant death (RAW).
- ``HEAL`` above 0 resets any accrued death saves.
- ``SET_MAX`` clamps current down; ``SET_CURRENT`` clamps into ``[0, max]``;
  ``SET_TEMP`` floors at 0.

All branches are driven deterministically through the public API (no RNG).
"""
from __future__ import annotations


async def _create_character(client) -> int:
    r = await client.post("/characters", json={"name": "HP Test"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _patch_hp(client, cid: int, op: str, value: int, *, critical: bool = False):
    r = await client.patch(
        f"/characters/{cid}/hp",
        json={"op": op, "value": value, "was_critical_hit": critical},
    )
    assert r.status_code == 200, r.text
    return r.json()


async def _set_hp(client, cid: int, maximum: int, current: int):
    await _patch_hp(client, cid, "set_max", maximum)
    return await _patch_hp(client, cid, "set_current", current)


async def test_damage_absorbs_temp_hp_before_current(client):
    cid = await _create_character(client)
    await _set_hp(client, cid, 20, 20)
    await _patch_hp(client, cid, "set_temp", 5)
    body = await _patch_hp(client, cid, "damage", 8)
    # 5 absorbed by temp HP, the remaining 3 hit current HP → 17/20, temp depleted.
    assert body["temp_hp"] == 0
    assert body["current_hit_points"] == 17


async def test_damage_clamps_at_zero_without_death(client):
    cid = await _create_character(client)
    await _set_hp(client, cid, 20, 5)
    body = await _patch_hp(client, cid, "damage", 5)
    assert body["current_hit_points"] == 0
    assert body["is_dead"] is False
    # Dropping to 0 from a positive value is unconsciousness, not a failed save.
    ds = body["death_saves"] or {}
    assert ds.get("failures", 0) == 0


async def test_damage_while_at_zero_accrues_one_failure(client):
    cid = await _create_character(client)
    await _set_hp(client, cid, 20, 5)
    await _patch_hp(client, cid, "damage", 5)        # → 0, unconscious
    body = await _patch_hp(client, cid, "damage", 1)  # taken at 0 → +1 failure
    assert body["current_hit_points"] == 0
    assert body["is_dead"] is False
    assert body["death_saves"]["failures"] == 1


async def test_critical_hit_at_zero_accrues_two_failures(client):
    cid = await _create_character(client)
    await _set_hp(client, cid, 20, 4)
    await _patch_hp(client, cid, "damage", 4)  # → 0
    body = await _patch_hp(client, cid, "damage", 1, critical=True)
    assert body["death_saves"]["failures"] == 2


async def test_massive_overflow_is_instant_death(client):
    cid = await _create_character(client)
    await _set_hp(client, cid, 20, 20)
    # 40 damage at 20/20: overflow past 0 is 20, which equals the max → instant death.
    body = await _patch_hp(client, cid, "damage", 40)
    assert body["is_dead"] is True
    assert body["current_hit_points"] == 0


async def test_heal_above_zero_resets_death_saves(client):
    cid = await _create_character(client)
    await _set_hp(client, cid, 20, 1)
    await _patch_hp(client, cid, "damage", 1)  # → 0, unconscious
    await _patch_hp(client, cid, "damage", 1)  # taken at 0 → 1 failure
    body = await _patch_hp(client, cid, "heal", 6)
    assert body["current_hit_points"] == 6
    ds = body["death_saves"] or {}
    assert ds.get("failures", 0) == 0 and ds.get("successes", 0) == 0


async def test_set_max_clamps_current_down(client):
    cid = await _create_character(client)
    await _set_hp(client, cid, 20, 20)
    body = await _patch_hp(client, cid, "set_max", 10)
    assert body["hit_points"] == 10
    assert body["current_hit_points"] == 10  # clamped from 20


async def test_set_current_clamps_into_range(client):
    cid = await _create_character(client)
    await _patch_hp(client, cid, "set_max", 20)
    over = await _patch_hp(client, cid, "set_current", 50)
    assert over["current_hit_points"] == 20  # clamped up-to max
    under = await _patch_hp(client, cid, "set_current", -5)
    assert under["current_hit_points"] == 0  # floored at 0


async def test_set_temp_floors_at_zero(client):
    cid = await _create_character(client)
    pos = await _patch_hp(client, cid, "set_temp", 7)
    assert pos["temp_hp"] == 7
    neg = await _patch_hp(client, cid, "set_temp", -3)
    assert neg["temp_hp"] == 0
