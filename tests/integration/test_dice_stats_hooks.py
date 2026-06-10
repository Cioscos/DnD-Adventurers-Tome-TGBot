"""Accumulo dice_stats in tutti i punti d'ingresso dei tiri.

Ogni flusso passa per UN solo funnel (verificato in spec), quindi niente doppi
conteggi. Dove il server tira, ``random.randint`` è pinnato in sequenza (primo
valore = d20, successivi = dadi danno) — stesso pattern di test_weapon_attack.
"""
from __future__ import annotations

import random


def _patch_sequence(monkeypatch, values: list[int]) -> None:
    seq = iter(list(values))
    state = {"last": values[-1]}

    def fake(a, b):
        try:
            state["last"] = next(seq)
        except StopIteration:
            pass
        return state["last"]

    monkeypatch.setattr(random, "randint", fake)


async def _make_char(client, name: str = "Tiratore") -> int:
    r = await client.post("/characters", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _stats(client, cid: int) -> dict:
    r = await client.get(f"/characters/{cid}/dice/stats")
    assert r.status_code == 200, r.text
    return r.json()["stats"]


async def test_dice_result_records_explicit_kinds(client):
    cid = await _make_char(client)
    r = await client.post(f"/characters/{cid}/dice/result", json={
        "rolls": [{"kind": "d20", "value": 20},
                  {"kind": "d6", "value": 3},
                  {"kind": "d6", "value": 3}],
    })
    assert r.status_code == 200, r.text
    assert await _stats(client, cid) == {"d20": {"20": 1}, "d6": {"3": 2}}


async def test_skill_roll_records_d20(client):
    cid = await _make_char(client)
    r = await client.post(f"/characters/{cid}/skills/athletics/roll", json={"die": 20})
    assert r.status_code == 200, r.text
    assert (await _stats(client, cid))["d20"] == {"20": 1}


async def test_saving_throw_records_d20(client):
    cid = await _make_char(client)
    r = await client.post(f"/characters/{cid}/saving_throws/strength/roll", json={"die": 1})
    assert r.status_code == 200, r.text
    assert (await _stats(client, cid))["d20"] == {"1": 1}


async def test_death_save_roll_records_d20(client):
    cid = await _make_char(client)
    r = await client.post(f"/characters/{cid}/death_saves/roll", json={"die": 7})
    assert r.status_code == 200, r.text
    assert (await _stats(client, cid))["d20"] == {"7": 1}


async def test_hit_dice_spend_records_hit_die(client):
    cid = await _make_char(client)
    r = await client.post(f"/characters/{cid}/classes",
                          json={"class_name": "fighter", "level": 1, "hit_die": 10})
    assert r.status_code in (200, 201), r.text
    cls = next(c for c in r.json()["classes"] if c["class_name"] == "fighter")
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 10})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 5})
    r = await client.post(f"/characters/{cid}/hit_dice/spend",
                          json={"class_id": cls["id"], "count": 1})
    assert r.status_code == 200, r.text
    d10 = (await _stats(client, cid)).get("d10", {})
    assert sum(d10.values()) == 1


async def test_spell_damage_records_main_dice(client):
    cid = await _make_char(client)
    r = await client.post(f"/characters/{cid}/spells",
                          json={"name": "Fuoco", "level": 1, "damage_dice": "2d8"})
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    r = await client.post(f"/characters/{cid}/spells/{sid}/roll_damage",
                          json={"main_rolls": [8, 1]})
    assert r.status_code == 200, r.text
    assert (await _stats(client, cid))["d8"] == {"8": 1, "1": 1}


async def _add_weapon(client, cid: int) -> int:
    meta = {"damage_dice": "1d8", "weapon_type": "melee", "properties": []}
    r = await client.post(
        f"/characters/{cid}/items",
        json={"name": "Spada", "item_type": "weapon", "item_metadata": meta},
    )
    assert r.status_code == 201, r.text
    items = (await client.get(f"/characters/{cid}/items")).json()
    return next(i["id"] for i in items if i["name"] == "Spada")


async def test_weapon_attack_records_to_hit_and_damage(client, monkeypatch):
    cid = await _make_char(client)
    item_id = await _add_weapon(client, cid)
    _patch_sequence(monkeypatch, [10, 5])  # d20=10, 1d8=5
    r = await client.post(f"/characters/{cid}/items/{item_id}/attack")
    assert r.status_code == 200, r.text
    stats = await _stats(client, cid)
    assert stats["d20"] == {"10": 1}
    assert stats["d8"] == {"5": 1}


async def test_weapon_attack_fumble_records_only_d20(client, monkeypatch):
    cid = await _make_char(client)
    item_id = await _add_weapon(client, cid)
    _patch_sequence(monkeypatch, [1])  # fumble: danno azzerato, niente dadi danno
    r = await client.post(f"/characters/{cid}/items/{item_id}/attack")
    assert r.status_code == 200, r.text
    stats = await _stats(client, cid)
    assert stats["d20"] == {"1": 1}
    assert "d8" not in stats


async def test_unarmed_attack_records_d20(client, monkeypatch):
    cid = await _make_char(client)
    _patch_sequence(monkeypatch, [12])
    r = await client.post(f"/characters/{cid}/attack/unarmed")
    assert r.status_code == 200, r.text
    assert (await _stats(client, cid))["d20"] == {"12": 1}


async def test_concentration_save_records_d20(client, monkeypatch):
    cid = await _make_char(client)
    _patch_sequence(monkeypatch, [15])
    r = await client.post(f"/characters/{cid}/concentration/save", json={"damage": 10})
    assert r.status_code == 200, r.text
    assert (await _stats(client, cid))["d20"] == {"15": 1}
