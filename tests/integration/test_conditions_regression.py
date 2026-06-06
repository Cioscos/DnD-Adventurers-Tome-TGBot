"""Regression guard for the apply_conditions extraction."""
from __future__ import annotations

import pytest


async def _create_character(client) -> int:
    r = await client.post("/characters", json={"name": "Cond Test"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.mark.asyncio
async def test_set_and_clear_condition(client):
    cid = await _create_character(client)

    r = await client.patch(f"/characters/{cid}/conditions",
                           json={"conditions": {"poisoned": True}})
    assert r.status_code == 200, r.text
    assert r.json()["conditions"].get("poisoned") is True

    r = await client.patch(f"/characters/{cid}/conditions",
                           json={"conditions": {"poisoned": False}})
    assert r.status_code == 200, r.text
    assert r.json()["conditions"].get("poisoned") is False


@pytest.mark.asyncio
async def test_exhaustion_is_integer(client):
    cid = await _create_character(client)
    r = await client.patch(f"/characters/{cid}/conditions",
                           json={"conditions": {"exhaustion": 2}})
    assert r.status_code == 200, r.text
    assert r.json()["conditions"].get("exhaustion") == 2
