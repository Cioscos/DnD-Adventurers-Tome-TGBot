"""Sintonia: non con due copie dello stesso oggetto (PHB 2024 p.232), 409 attunement_duplicate."""
from __future__ import annotations

import json

from core.db.models import Item


async def _char(client) -> int:
    r = await client.post("/characters", json={"name": "Sintonizzato"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _ring(client, cid, name="Anello", attuned=False, **meta):
    return await client.post(f"/characters/{cid}/items", json={
        "name": name, "item_type": "magic_item",
        "item_metadata": {"requires_attunement": True, "attuned": attuned, **meta}})


async def _attune(client, cid, iid, **extra):
    return await client.patch(f"/characters/{cid}/items/{iid}", json={
        "item_metadata": {"requires_attunement": True, "attuned": True, **extra}})


def _last_id(r) -> int:
    return max(i["id"] for i in r.json()["items"])


async def test_attune_second_copy_same_srd_index_409(client):
    cid = await _char(client)
    assert (await _ring(client, cid, "Anello A", attuned=True, srd_index="ring-of-x")).status_code == 201
    iid = _last_id(await _ring(client, cid, "Anello B", srd_index="ring-of-x"))
    r = await _attune(client, cid, iid, srd_index="ring-of-x")
    assert r.status_code == 409 and r.json()["detail"] == "attunement_duplicate"


async def test_attune_second_copy_same_name_409(client):
    cid = await _char(client)
    await _ring(client, cid, "Anello della Fortuna", attuned=True)
    iid = _last_id(await _ring(client, cid, "ANELLO DELLA FORTUNA"))
    r = await _attune(client, cid, iid)
    assert r.status_code == 409 and r.json()["detail"] == "attunement_duplicate"


async def test_attune_different_items_ok(client):
    cid = await _char(client)
    await _ring(client, cid, "Anello A", attuned=True, srd_index="ring-a")
    iid = _last_id(await _ring(client, cid, "Anello B", srd_index="ring-b"))
    assert (await _attune(client, cid, iid, srd_index="ring-b")).status_code == 200


async def test_create_item_already_attuned_duplicate_409(client):
    cid = await _char(client)
    await _ring(client, cid, "Mantello", attuned=True)
    r = await _ring(client, cid, "mantello", attuned=True)
    assert r.status_code == 409 and r.json()["detail"] == "attunement_duplicate"


async def test_existing_duplicates_untouched(client, test_session_factory):
    cid = await _char(client)
    async with test_session_factory() as s:
        for _ in range(2):
            s.add(Item(character_id=cid, name="Anello", item_type="magic_item", quantity=1, weight=0,
                       item_metadata=json.dumps({"requires_attunement": True, "attuned": True})))
        await s.commit()
    items = (await client.get(f"/characters/{cid}")).json()["items"]
    r = await client.patch(f"/characters/{cid}/items/{items[0]['id']}", json={"name": "Anello rinominato"})
    assert r.status_code == 200, r.text
    meta = {"requires_attunement": True, "attuned": True}  # già in sintonia: non è una sintonia nuova
    r = await client.patch(f"/characters/{cid}/items/{items[1]['id']}", json={"item_metadata": meta})
    assert r.status_code == 200, r.text


async def test_null_metadata_ignored(client, test_session_factory):
    cid = await _char(client)
    async with test_session_factory() as s:
        s.add(Item(character_id=cid, name="Sasso", item_type="generic", quantity=1, weight=0, item_metadata=None))
        await s.commit()
    r = await _ring(client, cid, "Anello", attuned=True)
    assert r.status_code == 201, r.text
