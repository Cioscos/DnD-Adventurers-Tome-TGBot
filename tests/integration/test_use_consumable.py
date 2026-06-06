"""Integration tests for consumable structured effects + the /use endpoint."""
from __future__ import annotations

import pytest


async def _create_character(client) -> int:
    r = await client.post("/characters", json={"name": "Use Test"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _find_item(char_full: dict, name: str) -> dict:
    item = next((i for i in char_full["items"] if i["name"] == name), None)
    assert item is not None, f"item {name!r} not found in {[i['name'] for i in char_full['items']]}"
    return item


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
    assert item["item_metadata"]["effects"][0]["amount"] == "2d4+2"


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


async def _add_consumable(client, cid: int, name: str, effects: list[dict],
                          quantity: int = 1) -> int:
    r = await client.post(f"/characters/{cid}/items", json={
        "name": name,
        "item_type": "consumable",
        "quantity": quantity,
        "item_metadata": {"subtype": "potion", "effects": effects},
    })
    assert r.status_code == 201, r.text
    return _find_item(r.json(), name)["id"]


async def test_create_consumable_with_invalid_subtype_rejected(client):
    cid = await _create_character(client)
    r = await client.post(f"/characters/{cid}/items", json={
        "name": "Bad", "item_type": "consumable", "quantity": 1,
        "item_metadata": {"subtype": "bomb", "effects": [{"kind": "heal", "amount": "1"}]},
    })
    assert r.status_code == 422, r.text


async def test_use_heal_applies_fixed_amount(client):
    cid = await _create_character(client)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 20})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 5})
    iid = await _add_consumable(client, cid, "Cura", [{"kind": "heal", "amount": "5"}], quantity=2)

    r = await client.post(f"/characters/{cid}/items/{iid}/use")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["current_hit_points"] == 10
    assert body["consumable_use"]["total_healed"] == 5
    assert _find_item(body, "Cura")["quantity"] == 1


async def test_use_heal_dice_in_range(client):
    cid = await _create_character(client)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 50})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 1})
    iid = await _add_consumable(client, cid, "Cura grande", [{"kind": "heal", "amount": "2d4+2"}])

    r = await client.post(f"/characters/{cid}/items/{iid}/use")
    assert r.status_code == 200, r.text
    healed = r.json()["consumable_use"]["total_healed"]
    assert 4 <= healed <= 10  # 2d4+2


async def test_use_remove_and_add_condition(client):
    cid = await _create_character(client)
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"poisoned": True}})
    iid = await _add_consumable(client, cid, "Antidoto", [
        {"kind": "remove_condition", "condition": "poisoned"},
        {"kind": "add_condition", "condition": "invisible"},
    ])

    r = await client.post(f"/characters/{cid}/items/{iid}/use")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["conditions"].get("poisoned") is False
    assert body["conditions"].get("invisible") is True
    assert "poisoned" in body["consumable_use"]["conditions_removed"]
    assert "invisible" in body["consumable_use"]["conditions_added"]


async def test_use_decrements_to_zero_without_delete_then_409(client):
    cid = await _create_character(client)
    iid = await _add_consumable(client, cid, "Una sola", [{"kind": "heal", "amount": "1"}], quantity=1)

    r1 = await client.post(f"/characters/{cid}/items/{iid}/use")
    assert r1.status_code == 200
    assert _find_item(r1.json(), "Una sola")["quantity"] == 0

    r2 = await client.post(f"/characters/{cid}/items/{iid}/use")
    assert r2.status_code == 409, r2.text


async def test_use_non_consumable_rejected(client):
    cid = await _create_character(client)
    r = await client.post(f"/characters/{cid}/items", json={
        "name": "Spada", "item_type": "weapon", "quantity": 1,
        "item_metadata": {"damage_dice": "1d8"},
    })
    iid = _find_item(r.json(), "Spada")["id"]
    r = await client.post(f"/characters/{cid}/items/{iid}/use")
    assert r.status_code == 400, r.text


async def test_use_consumable_without_effects_rejected(client):
    cid = await _create_character(client)
    r = await client.post(f"/characters/{cid}/items", json={
        "name": "Razione", "item_type": "consumable", "quantity": 1,
        "item_metadata": {"subtype": "food"},
    })
    iid = _find_item(r.json(), "Razione")["id"]
    r = await client.post(f"/characters/{cid}/items/{iid}/use")
    assert r.status_code == 400, r.text


async def test_use_is_inert_when_dead(client):
    cid = await _create_character(client)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 10})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 10})
    # Massive damage => instant death (overflow >= max).
    await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 100})
    iid = await _add_consumable(client, cid, "Cura", [{"kind": "heal", "amount": "5"}])

    r = await client.post(f"/characters/{cid}/items/{iid}/use")
    assert r.status_code == 200, r.text
    assert r.json()["current_hit_points"] == 0
    assert _find_item(r.json(), "Cura")["quantity"] == 1
