"""Item create / delete — api/routers/items.py.

Covers the inventory CRUD the webapp drives via ``api.items.create`` /
``api.items.delete`` (equip/AC is in test_item_equip_ac; /use in
test_use_consumable):

- ``POST /items`` stores an ``ItemCreate`` and returns the full character (201).
  Generic items dedup by name (quantity merges instead of a second row).
  An ``equipment_slot`` incompatible with ``item_type`` is rejected (422).
- ``DELETE /items/{id}`` removes the row and returns the character without it; a
  missing id → 404.

Contract: ``ItemRead`` (id / name / quantity / weight / item_type / is_equipped /
equipment_slot) inside ``CharacterFull.items`` matches the FE ``Item`` type.
"""
from __future__ import annotations


async def _create_character(client) -> int:
    r = await client.post("/characters", json={"name": "Hoarder"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _find_item(char: dict, item_id: int) -> dict | None:
    return next((i for i in char["items"] if i["id"] == item_id), None)


async def test_create_generic_item_returns_201_and_full_shape(client):
    cid = await _create_character(client)
    r = await client.post(
        f"/characters/{cid}/items",
        json={"name": "Torcia", "quantity": 2, "weight": 1.0},
    )
    assert r.status_code == 201, r.text
    char = r.json()
    item = next(i for i in char["items"] if i["name"] == "Torcia")
    assert item["quantity"] == 2
    assert item["weight"] == 1.0
    assert item["item_type"] == "generic"
    assert item["is_equipped"] is False
    assert item["equipment_slot"] is None


async def test_create_weapon_with_explicit_fields(client):
    cid = await _create_character(client)
    r = await client.post(
        f"/characters/{cid}/items",
        json={
            "name": "Spada lunga",
            "item_type": "weapon",
            "is_equipped": True,
            "equipment_slot": "main_hand",
        },
    )
    assert r.status_code == 201, r.text
    item = next(i for i in r.json()["items"] if i["name"] == "Spada lunga")
    assert item["item_type"] == "weapon"
    assert item["is_equipped"] is True
    assert item["equipment_slot"] == "main_hand"


async def test_generic_items_dedup_by_name(client):
    cid = await _create_character(client)
    r1 = await client.post(f"/characters/{cid}/items", json={"name": "Freccia", "quantity": 5})
    assert r1.status_code == 201, r1.text
    r2 = await client.post(f"/characters/{cid}/items", json={"name": "Freccia", "quantity": 3})
    assert r2.status_code == 201, r2.text

    arrows = [i for i in r2.json()["items"] if i["name"] == "Freccia"]
    assert len(arrows) == 1
    assert arrows[0]["quantity"] == 8


async def test_create_item_incompatible_slot_is_422(client):
    cid = await _create_character(client)
    # A generic item allows no equipment slot at all → validation rejects it.
    r = await client.post(
        f"/characters/{cid}/items",
        json={"name": "Cappello", "item_type": "generic", "equipment_slot": "head"},
    )
    assert r.status_code == 422, r.text


async def test_delete_item_returns_character_without_it(client):
    cid = await _create_character(client)
    rc = await client.post(f"/characters/{cid}/items", json={"name": "Corda"})
    item_id = next(i for i in rc.json()["items"] if i["name"] == "Corda")["id"]

    r = await client.delete(f"/characters/{cid}/items/{item_id}")
    assert r.status_code == 200, r.text
    assert _find_item(r.json(), item_id) is None


async def test_delete_unknown_item_is_404(client):
    cid = await _create_character(client)
    r = await client.delete(f"/characters/{cid}/items/999999")
    assert r.status_code == 404, r.text
