"""Integration tests for the carry-capacity manual override.

Mirrors the AC override pattern: PATCH sets a manual value and locks it
(carry_capacity_override=True) so subsequent Strength changes do NOT clobber
it; POST .../reset-override clears the flag and recomputes STR x 15.
"""
from __future__ import annotations

import pytest


async def _create_character(client) -> int:
    r = await client.post("/characters", json={"name": "Carry Test"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.mark.asyncio
async def test_carry_capacity_auto_tracks_strength(client):
    """Baseline: with no override, carry_capacity follows STR x 15."""
    char_id = await _create_character(client)

    r = await client.patch(
        f"/characters/{char_id}/ability_scores/strength", json={"value": 15}
    )
    assert r.status_code == 200, r.text
    assert r.json()["carry_capacity"] == 225
    assert r.json()["carry_capacity_override"] is False


@pytest.mark.asyncio
async def test_patch_carry_capacity_sets_override(client):
    """PATCH /carry-capacity stores the value and flips the override flag."""
    char_id = await _create_character(client)

    r = await client.patch(
        f"/characters/{char_id}/carry-capacity", json={"value": 300}
    )
    assert r.status_code == 200, r.text
    assert r.json()["carry_capacity"] == 300
    assert r.json()["carry_capacity_override"] is True


@pytest.mark.asyncio
async def test_carry_capacity_clamps_negative(client):
    """Negative manual values clamp to 0 (mirrors max(0, ...) on AC)."""
    char_id = await _create_character(client)

    r = await client.patch(
        f"/characters/{char_id}/carry-capacity", json={"value": -50}
    )
    assert r.status_code == 200, r.text
    assert r.json()["carry_capacity"] == 0


@pytest.mark.asyncio
async def test_strength_change_does_not_clobber_override(client):
    """With the override active, a Strength change must NOT recompute capacity."""
    char_id = await _create_character(client)

    await client.patch(f"/characters/{char_id}/carry-capacity", json={"value": 300})
    r = await client.patch(
        f"/characters/{char_id}/ability_scores/strength", json={"value": 8}
    )
    assert r.status_code == 200, r.text
    # 8 x 15 = 120, but the override must hold at 300.
    assert r.json()["carry_capacity"] == 300
    assert r.json()["carry_capacity_override"] is True


@pytest.mark.asyncio
async def test_reset_override_recomputes_from_strength(client):
    """POST /carry-capacity/reset-override clears the flag and recomputes."""
    char_id = await _create_character(client)

    await client.patch(
        f"/characters/{char_id}/ability_scores/strength", json={"value": 8}
    )
    await client.patch(f"/characters/{char_id}/carry-capacity", json={"value": 300})

    r = await client.post(f"/characters/{char_id}/carry-capacity/reset-override")
    assert r.status_code == 200, r.text
    # Back to STR(8) x 15 = 120.
    assert r.json()["carry_capacity"] == 120
    assert r.json()["carry_capacity_override"] is False
