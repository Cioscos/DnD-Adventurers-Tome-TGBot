"""Regression guard for the apply_heal extraction: the /hp HEAL op must keep
clamping to max and resetting death saves when HP rises from 0."""
from __future__ import annotations

import pytest


async def _create_character(client) -> int:
    r = await client.post("/characters", json={"name": "Heal Test"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.mark.asyncio
async def test_heal_clamps_to_max(client):
    cid = await _create_character(client)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 20})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 5})

    r = await client.patch(f"/characters/{cid}/hp", json={"op": "heal", "value": 100})
    assert r.status_code == 200, r.text
    assert r.json()["current_hit_points"] == 20


@pytest.mark.asyncio
async def test_heal_from_zero_resets_death_saves(client):
    cid = await _create_character(client)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 10})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 3})
    # Drop to 0, then take damage at 0 to accrue a failure.
    await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 3})
    await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 1})

    r = await client.patch(f"/characters/{cid}/hp", json={"op": "heal", "value": 5})
    assert r.status_code == 200, r.text
    assert r.json()["current_hit_points"] == 5
    ds = r.json()["death_saves"]
    assert ds["successes"] == 0 and ds["failures"] == 0 and ds.get("stable") is False
