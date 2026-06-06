"""Integration tests for consumable structured effects + the /use endpoint."""
from __future__ import annotations

import pytest


async def _create_character(client) -> int:
    r = await client.post("/characters", json={"name": "Use Test"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _find_item(char_full: dict, name: str) -> dict:
    return next(i for i in char_full["items"] if i["name"] == name)


@pytest.mark.asyncio
async def test_create_consumable_with_valid_effects(client):
    cid = await _create_character(client)
    r = await client.post(f"/characters/{cid}/items", json={
        "name": "Pozione di cura",
        "item_type": "consumable",
        "quantity": 1,
        "item_metadata": {
            "subtype": "potion",
            "effects": [{"kind": "heal", "amount": "2d4+2"}],
        },
    })
    assert r.status_code == 201, r.text
    item = _find_item(r.json(), "Pozione di cura")
    assert item["item_metadata"]["effects"][0]["kind"] == "heal"
    assert item["item_metadata"]["subtype"] == "potion"


@pytest.mark.asyncio
async def test_create_consumable_with_invalid_effect_kind_rejected(client):
    cid = await _create_character(client)
    r = await client.post(f"/characters/{cid}/items", json={
        "name": "Bad",
        "item_type": "consumable",
        "quantity": 1,
        "item_metadata": {"effects": [{"kind": "teleport"}]},
    })
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_create_consumable_with_invalid_condition_rejected(client):
    cid = await _create_character(client)
    r = await client.post(f"/characters/{cid}/items", json={
        "name": "Bad",
        "item_type": "consumable",
        "quantity": 1,
        "item_metadata": {"effects": [{"kind": "add_condition", "condition": "happy"}]},
    })
    assert r.status_code == 422, r.text
