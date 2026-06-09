"""PATCH /characters/{id}/items/{item_id} — slot-aware equip and AC bookkeeping.

This is the end-to-end AC loop the paper-doll relies on:

- Equipping body armor sets ``base_armor_class`` from the item's ``ac_value``;
  unequipping it reverts the base to 10.
- Equipping a shield sets ``shield_armor_class`` from ``ac_bonus``.
- Equipping a second item into an occupied slot displaces the prior occupant
  (``swap_slot_occupant``) AND resets the displaced item's AC contribution.
- A slot incompatible with the item type is rejected with 422.

AC is asserted through ``ac_breakdown`` / ``ac`` (``ac == base + shield + magic``,
per core/db/models.py Character.ac), which build_character_response populates.
"""
from __future__ import annotations


async def _create_character(client) -> int:
    r = await client.post("/characters", json={"name": "Equipper"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _add_item(client, cid: int, **fields) -> int:
    """POST an item; return its id (located by unique name in the response)."""
    r = await client.post(f"/characters/{cid}/items", json=fields)
    assert r.status_code == 201, r.text
    items = r.json()["items"]
    match = next(i for i in items if i["name"] == fields["name"])
    return match["id"]


async def _patch_item(client, cid: int, item_id: int, **fields):
    r = await client.patch(f"/characters/{cid}/items/{item_id}", json=fields)
    return r


def _item(items: list[dict], item_id: int) -> dict:
    return next(i for i in items if i["id"] == item_id)


async def test_equip_armor_sets_base_ac_from_ac_value(client):
    cid = await _create_character(client)
    armor = await _add_item(
        client, cid, name="Plate", item_type="armor",
        item_metadata={"ac_value": 18}, is_equipped=False,
    )

    r = await _patch_item(client, cid, armor, is_equipped=True, equipment_slot="body")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ac_breakdown"]["base"] == 18
    assert body["ac"] == 18  # base 18 + shield 0 + magic 0
    equipped = _item(body["items"], armor)
    assert equipped["is_equipped"] is True
    assert equipped["equipment_slot"] == "body"


async def test_unequip_armor_reverts_base_to_ten(client):
    cid = await _create_character(client)
    armor = await _add_item(
        client, cid, name="Plate", item_type="armor",
        item_metadata={"ac_value": 18}, is_equipped=False,
    )
    await _patch_item(client, cid, armor, is_equipped=True, equipment_slot="body")

    r = await _patch_item(client, cid, armor, is_equipped=False)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ac_breakdown"]["base"] == 10
    assert _item(body["items"], armor)["equipment_slot"] is None


async def test_equip_shield_sets_shield_bonus(client):
    cid = await _create_character(client)
    shield = await _add_item(
        client, cid, name="Heater Shield", item_type="shield",
        item_metadata={"ac_bonus": 2}, is_equipped=False,
    )

    r = await _patch_item(client, cid, shield, is_equipped=True, equipment_slot="off_hand")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ac_breakdown"]["shield"] == 2
    assert body["ac"] == 12  # base 10 + shield 2


async def test_slot_displacement_resets_displaced_armor_ac(client):
    cid = await _create_character(client)
    plate = await _add_item(
        client, cid, name="Plate", item_type="armor",
        item_metadata={"ac_value": 18}, is_equipped=False,
    )
    chain = await _add_item(
        client, cid, name="Chainmail", item_type="armor",
        item_metadata={"ac_value": 16}, is_equipped=False,
    )

    await _patch_item(client, cid, plate, is_equipped=True, equipment_slot="body")
    # Equipping a second armor into the body slot displaces the plate.
    r = await _patch_item(client, cid, chain, is_equipped=True, equipment_slot="body")
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["ac_breakdown"]["base"] == 16  # chainmail now owns the base
    displaced = _item(body["items"], plate)
    assert displaced["is_equipped"] is False
    assert displaced["equipment_slot"] is None


async def test_incompatible_slot_is_rejected(client):
    cid = await _create_character(client)
    armor = await _add_item(
        client, cid, name="Plate", item_type="armor",
        item_metadata={"ac_value": 18}, is_equipped=False,
    )
    # Armor is only allowed in the body slot; 'head' is gear-only.
    r = await _patch_item(client, cid, armor, is_equipped=True, equipment_slot="head")
    assert r.status_code == 422, r.text
