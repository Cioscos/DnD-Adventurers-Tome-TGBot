"""Audit EQ: sintonia (PHB 2024 p.232): senza sintonia si ottengono solo i benefici non magici.

Un'arma magica che richiede sintonia e non e' sintonizzata non somma il suo bonus magico (+N) a colpire e ai danni.
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


async def _attack(client, monkeypatch, meta: dict) -> dict:
    cid = (await client.post("/characters", json={"name": "Hero"})).json()["id"]
    meta = {"damage_dice": "1d8", "weapon_type": "melee", "properties": [], "magic_bonus": 1, **meta}
    r = await client.post(f"/characters/{cid}/items", json={"name": "Spada", "item_type": "weapon", "item_metadata": meta})
    assert r.status_code == 201, r.text
    wid = next(i["id"] for i in (await client.get(f"/characters/{cid}/items")).json() if i["name"] == "Spada")
    _patch_sequence(monkeypatch, [10, 4])
    r = await client.post(f"/characters/{cid}/items/{wid}/attack")
    assert r.status_code == 200, r.text
    return r.json()


async def test_unattuned_magic_weapon_gives_no_magic_bonus(client, monkeypatch):
    body = await _attack(client, monkeypatch, {"requires_attunement": True})
    assert body["to_hit_bonus"] == 2  # solo competenza
    assert body["damage_total"] == 4


async def test_attuned_magic_weapon_gives_its_bonus(client, monkeypatch):
    body = await _attack(client, monkeypatch, {"requires_attunement": True, "attuned": True})
    assert body["to_hit_bonus"] == 3
    assert body["damage_total"] == 5


async def test_magic_weapon_without_attunement_requirement_keeps_its_bonus(client, monkeypatch):
    body = await _attack(client, monkeypatch, {})
    assert body["to_hit_bonus"] == 3
