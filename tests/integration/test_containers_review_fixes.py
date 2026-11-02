"""Fix della review finale dei contenitori (C1, I2-I5, m10)."""
from __future__ import annotations

import json

import pytest

from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session
from tests.integration.test_attack_ammunition import _add as _add_typed, _bow, _qty, _quiver
from tests.integration.test_character_import import _import
from tests.integration.test_containers import _add, _bag, _char, _item, _move

pytestmark = pytest.mark.asyncio


async def test_move_full_stack_with_quantity_equal_to_stack(client):  # C1
    cid = await _char(client)
    bag = _item(await _add(client, cid, name="Zaino", item_metadata=_bag()), "Zaino")["id"]
    rid = _item(await _add(client, cid, name="Razioni", quantity=10), "Razioni")["id"]
    r = await _move(client, cid, [rid], bag, quantity=10)
    assert r.status_code == 200, r.text
    rows = [i for i in r.json()["items"] if i["name"] == "Razioni"]
    assert len(rows) == 1 and rows[0]["id"] == rid and rows[0]["quantity"] == 10 and rows[0]["container_id"] == bag


async def test_partial_move_keeps_staying_stack_equipped(client):  # I2
    cid = await _char(client)
    bag = _item(await _add(client, cid, name="Faretra", item_metadata=_bag()), "Faretra")["id"]
    aid = _item(await _add(client, cid, name="Frecce", item_type="ammunition", quantity=20), "Frecce")["id"]
    r = await client.patch(f"/characters/{cid}/items/{aid}", json={"is_equipped": True, "equipment_slot": "ammunition"})
    assert r.status_code == 200, r.text
    r = await _move(client, cid, [aid], bag, quantity=10)
    assert r.status_code == 200, r.text
    assert r.json()["unequipped_item_names"] == []
    rows = {i["container_id"]: i for i in r.json()["items"] if i["name"] == "Frecce"}
    assert rows[None]["quantity"] == 10 and rows[None]["is_equipped"] and rows[None]["equipment_slot"] == "ammunition"
    assert rows[bag]["quantity"] == 10 and not rows[bag]["is_equipped"] and rows[bag]["equipment_slot"] is None


async def test_two_ammo_stacks_in_quiver_use_first(client):  # I3
    cid = await _char(client)
    wid = await _bow(client, cid)
    qid = await _quiver(client, cid)
    a1 = await _put(client, cid, qid, 5)
    a2 = await _put(client, cid, qid, 7)
    r = await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 10})
    assert r.status_code == 200, r.text
    assert r.json()["ammo"]["item_id"] == a1 and r.json()["ammo_missing"] is False
    assert await _qty(client, cid, a1) == 4 and await _qty(client, cid, a2) == 7


async def test_two_different_ammo_names_still_ambiguous(client):  # I3
    cid = await _char(client)
    wid = await _bow(client, cid)
    qid = await _quiver(client, cid)
    await _put(client, cid, qid, 5)
    await _put(client, cid, qid, 5, name="Quadrelli")
    r = await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 10})
    assert r.json()["ammo_missing"] is True


async def test_quiver_stack_wins_over_loose_stack(client):  # I3
    cid = await _char(client)
    wid = await _bow(client, cid)
    qid = await _quiver(client, cid)
    inq = await _put(client, cid, qid, 5)
    loose = await _add_typed(client, cid, "Frecce lunghe", "ammunition", quantity=9)
    r = await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 10})
    assert r.json()["ammo"]["item_id"] == inq
    assert await _qty(client, cid, inq) == 4 and await _qty(client, cid, loose) == 9


async def _put(client, cid, container_id, quantity, name="Frecce") -> int:
    r = await client.post(
        f"/characters/{cid}/items",
        json={"name": name, "item_type": "ammunition", "quantity": quantity, "container_id": container_id},
    )
    assert r.status_code == 201, r.text
    return max(i["id"] for i in r.json()["items"] if i["name"] == name)


async def test_gm_grant_does_not_merge_into_containers(client, test_session_factory, monkeypatch):  # I4
    from tests.integration._telegram_stub import install_fake_telegram
    install_fake_telegram(monkeypatch)
    sid, cid = await seed_session(test_session_factory)
    as_user(PLAYER_ID)
    bag = _item(await _add(client, cid, name="Corda", item_metadata=_bag()), "Corda")["id"]
    await _add(client, cid, name="Torcia", container_id=bag)
    as_user(GM_ID)
    grant = lambda item: client.post(f"/sessions/{sid}/gm/grant_item", json={"recipient_user_ids": [PLAYER_ID], "item": item})
    assert (await grant({"name": "Corda", "quantity": 2, "item_type": "generic"})).status_code == 201
    assert (await grant({"name": "Torcia", "quantity": 3, "item_type": "generic"})).status_code == 201
    r = await grant({"name": "Torcia", "quantity": 1, "item_type": "generic", "item_metadata": _bag()})
    assert r.status_code == 201
    r = await grant({"name": "Zaino", "quantity": 2, "item_type": "generic", "item_metadata": _bag()})
    assert r.status_code == 422 and r.json()["detail"] == "container_quantity"
    as_user(PLAYER_ID)
    items = (await client.get(f"/characters/{cid}/items")).json()
    box = next(i for i in items if i["id"] == bag)
    assert box["quantity"] == 1
    assert sorted(((i["container_id"] or 0), i["quantity"]) for i in items if i["name"] == "Torcia" and "container" not in (i["item_metadata"] or {})) == [(0, 3), (bag, 1)]
    assert [i["quantity"] for i in items if i["name"] == "Corda" and i["id"] != bag] == [2]


async def test_homebrew_passive_ignores_items_in_containers(client):  # I5
    from tests.integration.homebrew.test_passive_modifiers import _ALWAYS_TRUE_CHAR, _build_passive_rule
    cid = await _char(client)
    rule = _build_passive_rule("+1 AC", {"type": "item", "filter": {"item_types": ["shield"]}}, "character.ac", 1, _ALWAYS_TRUE_CHAR)
    assert (await client.post(f"/characters/{cid}/homebrew/rules", json=rule)).status_code in (200, 201)
    bag = _item(await _add(client, cid, name="Zaino", item_metadata=_bag()), "Zaino")["id"]
    sh = _item(await _add(client, cid, name="Scudo", item_type="shield"), "Scudo")["id"]
    assert (await client.get(f"/characters/{cid}")).json()["ac_breakdown"]["homebrew"] == 1
    assert (await _move(client, cid, [sh], bag)).status_code == 200
    assert (await client.get(f"/characters/{cid}")).json()["ac_breakdown"]["homebrew"] == 0


async def test_import_container_with_quantity_not_one_keeps_meta_and_coins(client):  # m10
    d = {"exported_at": "x", "character": {"name": "Imp"}, "items": [
        {"name": "Zaino", "quantity": 3, "ref": 1, "item_metadata": _bag(capacity_lb=30, coins={"gold": 7})},
        {"name": "Corda", "ref": 2, "container_ref": 1},
    ]}
    r = await _import(client, d)
    assert r.status_code == 201, r.text
    items = (await client.get(f"/characters/{r.json()['id']}/items")).json()
    by = {i["name"]: i for i in items}
    assert by["Zaino"]["quantity"] == 1
    assert by["Zaino"]["item_metadata"]["container"]["coins"]["gold"] == 7
    assert by["Corda"]["container_id"] == by["Zaino"]["id"]
