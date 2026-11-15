"""Arma a due mani e mano secondaria occupata: il server rifiuta con 422 hands_conflict."""
from __future__ import annotations

import json

from core.db.models import EquipmentSlot, Item


async def _char(client) -> int:
    r = await client.post("/characters", json={"name": "Armigero"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _add(client, cid, name, item_type, **meta) -> int:
    r = await client.post(f"/characters/{cid}/items", json={"name": name, "item_type": item_type, "item_metadata": meta})
    assert r.status_code == 201, r.text
    return next(i["id"] for i in r.json()["items"] if i["name"] == name)


async def _equip(client, cid, iid, slot):
    return await client.patch(f"/characters/{cid}/items/{iid}", json={"is_equipped": True, "equipment_slot": slot})


async def _greatsword(client, cid, prop="prop_two_handed") -> int:
    return await _add(client, cid, "Spadone", "weapon", damage_dice="2d6", properties=[prop])


async def _shield(client, cid) -> int:
    return await _add(client, cid, "Scudo", "shield", ac_bonus=2)


async def _slots(client, cid) -> dict:
    items = (await client.get(f"/characters/{cid}")).json()["items"]
    return {i["name"]: (i["is_equipped"], i["equipment_slot"]) for i in items}


async def test_equip_two_handed_with_off_hand_occupied_422(client):
    cid = await _char(client)
    sid, gid = await _shield(client, cid), await _greatsword(client, cid)
    assert (await _equip(client, cid, sid, "off_hand")).status_code == 200
    r = await _equip(client, cid, gid, "main_hand")
    assert r.status_code == 422 and r.json()["detail"] == "hands_conflict"
    assert await _slots(client, cid) == {"Scudo": (True, "off_hand"), "Spadone": (False, None)}


async def test_equip_off_hand_with_two_handed_main_422(client):
    cid = await _char(client)
    sid, gid = await _shield(client, cid), await _greatsword(client, cid)
    assert (await _equip(client, cid, gid, "main_hand")).status_code == 200
    r = await _equip(client, cid, sid, "off_hand")
    assert r.status_code == 422 and r.json()["detail"] == "hands_conflict"
    assert (await _slots(client, cid))["Scudo"] == (False, None)


async def test_ddb_two_handed_name_422(client):
    cid = await _char(client)
    sid, gid = await _shield(client, cid), await _greatsword(client, cid, prop="Two-Handed")
    await _equip(client, cid, sid, "off_hand")
    assert (await _equip(client, cid, gid, "main_hand")).json()["detail"] == "hands_conflict"


async def test_create_equipped_two_handed_with_off_hand_422(client):
    cid = await _char(client)
    await _equip(client, cid, await _shield(client, cid), "off_hand")
    r = await client.post(f"/characters/{cid}/items", json={
        "name": "Spadone", "item_type": "weapon", "is_equipped": True, "equipment_slot": "main_hand",
        "item_metadata": {"properties": ["prop_two_handed"]}})
    assert r.status_code == 422 and r.json()["detail"] == "hands_conflict"


async def test_versatile_with_shield_ok(client):
    cid = await _char(client)
    sid = await _shield(client, cid)
    vid = await _add(client, cid, "Spada lunga", "weapon", damage_dice="1d8", properties=["prop_versatile"])
    await _equip(client, cid, sid, "off_hand")
    assert (await _equip(client, cid, vid, "main_hand")).status_code == 200


async def test_unequip_then_equip_ok(client):
    cid = await _char(client)
    sid, gid = await _shield(client, cid), await _greatsword(client, cid)
    await _equip(client, cid, sid, "off_hand")
    r = await client.patch(f"/characters/{cid}/items/{sid}", json={"is_equipped": False, "equipment_slot": None})
    assert r.status_code == 200, r.text
    assert (await _equip(client, cid, gid, "main_hand")).status_code == 200


async def test_existing_conflict_allows_other_edits(client, test_session_factory):
    cid = await _char(client)
    sid, gid = await _shield(client, cid), await _greatsword(client, cid)
    async with test_session_factory() as s:
        for iid, slot in ((sid, EquipmentSlot.OFF_HAND), (gid, EquipmentSlot.MAIN_HAND)):
            item = await s.get(Item, iid)
            item.is_equipped, item.equipment_slot = True, slot
        await s.commit()
    assert (await client.patch(f"/characters/{cid}/items/{gid}", json={"name": "Spadone nuovo"})).status_code == 200
    r = await client.patch(f"/characters/{cid}/items/{sid}", json={"is_equipped": False, "equipment_slot": None})
    assert r.status_code == 200, r.text


async def test_legacy_equipped_without_slot_ignored(client, test_session_factory):
    cid = await _char(client)
    sid, gid = await _shield(client, cid), await _greatsword(client, cid)
    async with test_session_factory() as s:
        (await s.get(Item, sid)).is_equipped = True  # legacy: equipaggiato, slot nullo
        await s.commit()
    assert (await _equip(client, cid, gid, "main_hand")).status_code == 200
