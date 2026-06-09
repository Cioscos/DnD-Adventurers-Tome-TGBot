"""POST /characters/{id}/attack/unarmed — unarmed strike (RNG pinned).

D&D 5e rules encoded (``random.randint`` monkeypatched to a deterministic
sequence: first call = d20 to-hit, subsequent = damage dice):
- Non-Monk: flat ``"1"`` bludgeoning + STR mod; a crit does NOT double the flat
  1 (crit doubles dice, and there are none).
- Monk: best of STR/DEX + the Martial Arts die for the level (1d6 at level 5),
  and a crit DOES double those dice.
- ``with_inspiration`` consumes the heroic-inspiration token; 409 when absent.

Defaults: abilities 10 (mod 0); proficiency bonus +2 (level 0) / +3 (level 5).

Contract: response matches the FE ``WeaponAttackResult`` type consumed by
api.items.attackUnarmed in client.ts. The Monk path mirrors
``core/game/attacks.py::unarmed_strike_profile`` (tested as a pure unit in
``webapp/tests/unit/lib/unarmedStrike.test.ts``).
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


async def _create_plain(client) -> int:
    r = await client.post("/characters", json={"name": "Brawler"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _create_monk(client, level: int = 5) -> int:
    r = await client.post(
        "/characters",
        json={"name": "Monk", "initial_class": {"class_name": "Monaco", "level": level}},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _set_dex(client, cid: int, value: int) -> None:
    r = await client.patch(f"/characters/{cid}/ability_scores/dexterity", json={"value": value})
    assert r.status_code == 200, r.text


async def test_non_monk_flat_one(client, monkeypatch):
    cid = await _create_plain(client)
    _patch_sequence(monkeypatch, [12])  # only the d20 to-hit is rolled
    r = await client.post(f"/characters/{cid}/attack/unarmed")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["damage_dice"] == "1"
    assert body["damage_rolls"] == [1]
    assert body["to_hit_bonus"] == 2   # str mod 0 + pb 2
    assert body["damage_total"] == 1   # 1 + str mod 0


async def test_non_monk_crit_does_not_double_flat_one(client, monkeypatch):
    cid = await _create_plain(client)
    _patch_sequence(monkeypatch, [20])
    r = await client.post(f"/characters/{cid}/attack/unarmed")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_critical"] is True
    assert body["damage_rolls"] == [1]  # flat 1 is NOT doubled
    assert body["damage_total"] == 1


async def test_monk_uses_martial_arts_die(client, monkeypatch):
    cid = await _create_monk(client, level=5)
    await _set_dex(client, cid, 16)       # DEX +3 beats STR 0
    _patch_sequence(monkeypatch, [10, 4])  # d20=10, martial-arts 1d6=4
    r = await client.post(f"/characters/{cid}/attack/unarmed")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["damage_dice"] == "1d6"  # martial arts die at level 5
    assert body["damage_rolls"] == [4]
    assert body["to_hit_bonus"] == 6     # max(0, 3) + pb 3 (monk level 5)
    assert body["damage_bonus"] == 3
    assert body["damage_total"] == 7     # 4 + 3


async def test_monk_crit_doubles_martial_arts_dice(client, monkeypatch):
    cid = await _create_monk(client, level=5)
    _patch_sequence(monkeypatch, [20, 4, 5])  # crit: base [4] + extra [5]
    r = await client.post(f"/characters/{cid}/attack/unarmed")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_critical"] is True
    assert body["damage_rolls"] == [4, 5]


async def test_unarmed_consumes_inspiration(client, monkeypatch):
    cid = await _create_plain(client)
    ri = await client.patch(f"/characters/{cid}/inspiration", json={"heroic_inspiration": True})
    assert ri.status_code == 200, ri.text
    _patch_sequence(monkeypatch, [10])
    r = await client.post(f"/characters/{cid}/attack/unarmed", json={"with_inspiration": True})
    assert r.status_code == 200, r.text
    g = await client.get(f"/characters/{cid}")
    assert g.json()["heroic_inspiration"] is False


async def test_unarmed_inspiration_without_token_is_409(client):
    cid = await _create_plain(client)
    r = await client.post(f"/characters/{cid}/attack/unarmed", json={"with_inspiration": True})
    assert r.status_code == 409, r.text
