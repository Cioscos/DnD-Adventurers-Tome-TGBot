"""PATCH /characters/{id}: blank names and negative speeds never reach the sheet."""
from __future__ import annotations

import pytest


async def _create_character(client) -> int:
    r = await client.post("/characters", json={"name": "Eroe"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.mark.parametrize("name", ["", "   "])
async def test_blank_name_is_rejected(client, name):
    char_id = await _create_character(client)
    r = await client.patch(f"/characters/{char_id}", json={"name": name})
    assert r.status_code == 422
    assert (await client.get(f"/characters/{char_id}")).json()["name"] == "Eroe"


async def test_name_is_trimmed(client):
    char_id = await _create_character(client)
    r = await client.patch(f"/characters/{char_id}", json={"name": "  Kael  "})
    assert r.status_code == 200
    assert r.json()["name"] == "Kael"


async def test_negative_speed_is_rejected(client):
    char_id = await _create_character(client)
    r = await client.patch(f"/characters/{char_id}", json={"speed": -5})
    assert r.status_code == 422


async def test_speed_zero_is_allowed(client):
    char_id = await _create_character(client)
    r = await client.patch(f"/characters/{char_id}", json={"speed": 0})
    assert r.status_code == 200
    assert r.json()["speed"] == 0
