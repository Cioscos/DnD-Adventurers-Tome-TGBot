"""Dadi 3D letti dal client per attacchi e dadi vita.

Come per tiri salvezza, abilità e danni degli incantesimi, il client può inviare
la faccia uscita dalla fisica; il server la valida. Senza valore tira il server.
I danni dell'attacco restano sempre tirati dal server.
"""
from __future__ import annotations

import random


async def _make_char(client) -> int:
    r = await client.post("/characters", json={"name": "Dadi Client"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _add_weapon(client, cid: int) -> int:
    meta = {"damage_dice": "1d8", "weapon_type": "melee", "properties": []}
    r = await client.post(
        f"/characters/{cid}/items",
        json={"name": "Spada", "item_type": "weapon", "item_metadata": meta},
    )
    assert r.status_code == 201, r.text
    items = (await client.get(f"/characters/{cid}/items")).json()
    return next(i["id"] for i in items if i["name"] == "Spada")


async def _add_class(client, cid: int, *, level: int = 2, hit_die: int = 10) -> int:
    r = await client.post(
        f"/characters/{cid}/classes",
        json={"class_name": "fighter", "level": level, "hit_die": hit_die},
    )
    assert r.status_code == 201, r.text
    return next(c for c in r.json()["classes"] if c["class_name"] == "fighter")["id"]


async def _set_hp(client, cid: int, maximum: int, current: int) -> None:
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": maximum})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": current})


async def test_weapon_attack_uses_the_client_die(client):
    cid = await _make_char(client)
    item_id = await _add_weapon(client, cid)
    r = await client.post(f"/characters/{cid}/items/{item_id}/attack", json={"die": 17})
    assert r.status_code == 200, r.text
    assert r.json()["to_hit_die"] == 17


async def test_weapon_attack_client_20_is_a_critical_with_doubled_damage_dice(client):
    cid = await _make_char(client)
    item_id = await _add_weapon(client, cid)
    r = await client.post(f"/characters/{cid}/items/{item_id}/attack", json={"die": 20})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_critical"] is True
    assert len(body["damage_rolls"]) == 2


async def test_weapon_attack_client_1_is_a_fumble(client):
    cid = await _make_char(client)
    item_id = await _add_weapon(client, cid)
    r = await client.post(f"/characters/{cid}/items/{item_id}/attack", json={"die": 1})
    assert r.status_code == 200, r.text
    assert r.json()["is_fumble"] is True
    assert r.json()["damage_total"] == 0


async def test_weapon_reroll_spends_inspiration_and_keeps_the_client_die(client):
    cid = await _make_char(client)
    item_id = await _add_weapon(client, cid)
    await client.patch(f"/characters/{cid}/inspiration", json={"heroic_inspiration": True})
    r = await client.post(
        f"/characters/{cid}/items/{item_id}/attack",
        json={"die": 9, "with_inspiration": True},
    )
    assert r.status_code == 200, r.text
    assert r.json()["to_hit_die"] == 9


async def test_weapon_attack_rejects_a_die_out_of_range(client):
    cid = await _make_char(client)
    item_id = await _add_weapon(client, cid)
    for bad in (0, 21):
        r = await client.post(f"/characters/{cid}/items/{item_id}/attack", json={"die": bad})
        assert r.status_code == 422, r.text


async def test_weapon_attack_without_die_still_rolls_on_the_server(client, monkeypatch):
    cid = await _make_char(client)
    item_id = await _add_weapon(client, cid)
    monkeypatch.setattr(random, "randint", lambda a, b: 13)
    r = await client.post(f"/characters/{cid}/items/{item_id}/attack")
    assert r.status_code == 200, r.text
    assert r.json()["to_hit_die"] == 13


async def test_unarmed_attack_uses_the_client_die(client):
    cid = await _make_char(client)
    r = await client.post(f"/characters/{cid}/attack/unarmed", json={"die": 4})
    assert r.status_code == 200, r.text
    assert r.json()["to_hit_die"] == 4


async def test_hit_dice_use_the_client_rolls(client):
    cid = await _make_char(client)
    class_id = await _add_class(client, cid, level=2, hit_die=10)
    await _set_hp(client, cid, 100, 1)
    r = await client.post(
        f"/characters/{cid}/hit_dice/spend",
        json={"class_id": class_id, "count": 2, "rolls": [7, 3]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rolls"] == [7, 3]
    assert body["healed"] == 10


async def test_hit_dice_reject_the_wrong_number_of_rolls(client):
    cid = await _make_char(client)
    class_id = await _add_class(client, cid, level=2, hit_die=10)
    r = await client.post(
        f"/characters/{cid}/hit_dice/spend",
        json={"class_id": class_id, "count": 2, "rolls": [7]},
    )
    assert r.status_code == 400, r.text


async def test_hit_dice_reject_a_face_the_die_does_not_have(client):
    cid = await _make_char(client)
    class_id = await _add_class(client, cid, level=2, hit_die=6)
    for bad in (0, 7):
        r = await client.post(
            f"/characters/{cid}/hit_dice/spend",
            json={"class_id": class_id, "count": 1, "rolls": [bad]},
        )
        assert r.status_code == 400, r.text


async def test_rejected_hit_dice_rolls_do_not_spend_the_die(client):
    cid = await _make_char(client)
    class_id = await _add_class(client, cid, level=1, hit_die=6)
    bad = await client.post(
        f"/characters/{cid}/hit_dice/spend",
        json={"class_id": class_id, "count": 1, "rolls": [9]},
    )
    assert bad.status_code == 400, bad.text
    good = await client.post(
        f"/characters/{cid}/hit_dice/spend",
        json={"class_id": class_id, "count": 1, "rolls": [2]},
    )
    assert good.status_code == 200, good.text
