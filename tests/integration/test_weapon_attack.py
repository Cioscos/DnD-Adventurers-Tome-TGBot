"""POST /characters/{id}/items/{item_id}/attack — weapon to-hit + damage (RNG pinned).

D&D 5e rules encoded (``random.randint`` is monkeypatched to a deterministic
sequence: the first call is the d20 to-hit, subsequent calls are damage dice):
- ``to_hit_total = d20 + ability_mod + proficiency_bonus``.
- nat 20 = critical → damage dice rolled twice (doubled count).
- nat 1 = fumble → damage zeroed (rolls ``[0]``, bonus 0, total 0).
- ability mod selection: melee→STR, ranged→DEX, finesse→max(STR, DEX).
- ``with_inspiration`` consumes the heroic-inspiration token; 409 when absent.

A freshly created character has all abilities at 10 (mod 0) and proficiency
bonus +2 (level 0). DEX is bumped where the test needs STR ≠ DEX.

Contract: response matches the FE ``WeaponAttackResult`` type consumed by
api.items.attack in client.ts.
"""
from __future__ import annotations

import random


def _patch_sequence(monkeypatch, values: list[int]) -> None:
    """Make random.randint yield `values` in order (then repeat the last)."""
    seq = iter(list(values))
    state = {"last": values[-1]}

    def fake(a, b):
        try:
            state["last"] = next(seq)
        except StopIteration:
            pass
        return state["last"]

    monkeypatch.setattr(random, "randint", fake)


async def _create_character(client) -> int:
    r = await client.post("/characters", json={"name": "Fighter"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _add_weapon(client, cid: int, *, name="Spada", damage_dice="1d8",
                      weapon_type="melee", properties=None) -> int:
    meta = {"damage_dice": damage_dice, "weapon_type": weapon_type,
            "properties": properties or []}
    r = await client.post(
        f"/characters/{cid}/items",
        json={"name": name, "item_type": "weapon", "item_metadata": meta},
    )
    assert r.status_code == 201, r.text
    items = (await client.get(f"/characters/{cid}/items")).json()
    return next(i["id"] for i in items if i["name"] == name)


async def _set_dex(client, cid: int, value: int) -> None:
    r = await client.patch(f"/characters/{cid}/ability_scores/dexterity", json={"value": value})
    assert r.status_code == 200, r.text


async def test_normal_hit_math(client, monkeypatch):
    cid = await _create_character(client)
    wid = await _add_weapon(client, cid, damage_dice="1d8")
    _patch_sequence(monkeypatch, [10, 6])  # d20=10, damage 1d8=6
    r = await client.post(f"/characters/{cid}/items/{wid}/attack")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["to_hit_die"] == 10
    assert body["to_hit_bonus"] == 2   # str mod 0 + pb 2
    assert body["to_hit_total"] == 12
    assert body["is_critical"] is False
    assert body["is_fumble"] is False
    assert body["damage_rolls"] == [6]
    assert body["damage_bonus"] == 0   # str mod 0
    assert body["damage_total"] == 6


async def test_critical_doubles_damage_dice(client, monkeypatch):
    cid = await _create_character(client)
    wid = await _add_weapon(client, cid, damage_dice="1d8")
    _patch_sequence(monkeypatch, [20, 7, 3])  # crit: base [7] + extra [3]
    r = await client.post(f"/characters/{cid}/items/{wid}/attack")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_critical"] is True
    assert body["damage_rolls"] == [7, 3]
    assert body["damage_total"] == 10  # 7 + 3 + 0


async def test_fumble_zeroes_damage(client, monkeypatch):
    cid = await _create_character(client)
    wid = await _add_weapon(client, cid, damage_dice="1d8")
    _patch_sequence(monkeypatch, [1, 5])  # nat 1; the damage roll is discarded
    r = await client.post(f"/characters/{cid}/items/{wid}/attack")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_fumble"] is True
    assert body["damage_rolls"] == [0]
    assert body["damage_bonus"] == 0
    assert body["damage_total"] == 0


async def test_ranged_uses_dexterity(client, monkeypatch):
    cid = await _create_character(client)
    await _set_dex(client, cid, 16)  # DEX mod +3
    wid = await _add_weapon(client, cid, name="Arco", damage_dice="1d6", weapon_type="ranged")
    _patch_sequence(monkeypatch, [10, 4])
    r = await client.post(f"/characters/{cid}/items/{wid}/attack")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["to_hit_bonus"] == 5   # dex 3 + pb 2
    assert body["damage_bonus"] == 3   # dex mod flows into damage


async def test_finesse_picks_best_of_str_dex(client, monkeypatch):
    cid = await _create_character(client)
    await _set_dex(client, cid, 16)  # DEX +3 beats STR 0
    wid = await _add_weapon(client, cid, name="Stiletto", damage_dice="1d4",
                            properties=["Finesse"])
    _patch_sequence(monkeypatch, [10, 2])
    r = await client.post(f"/characters/{cid}/items/{wid}/attack")
    assert r.status_code == 200, r.text
    assert r.json()["to_hit_bonus"] == 5  # max(0, 3) + pb 2


async def test_attack_consumes_inspiration(client, monkeypatch):
    cid = await _create_character(client)
    wid = await _add_weapon(client, cid)
    ri = await client.patch(f"/characters/{cid}/inspiration", json={"heroic_inspiration": True})
    assert ri.status_code == 200, ri.text
    _patch_sequence(monkeypatch, [10, 4])
    r = await client.post(f"/characters/{cid}/items/{wid}/attack", json={"with_inspiration": True})
    assert r.status_code == 200, r.text
    g = await client.get(f"/characters/{cid}")
    assert g.json()["heroic_inspiration"] is False


async def test_inspiration_without_token_is_409(client):
    cid = await _create_character(client)
    wid = await _add_weapon(client, cid)
    r = await client.post(f"/characters/{cid}/items/{wid}/attack", json={"with_inspiration": True})
    assert r.status_code == 409, r.text


async def test_non_weapon_is_400(client):
    cid = await _create_character(client)
    r = await client.post(f"/characters/{cid}/items", json={"name": "Mela", "item_type": "generic"})
    assert r.status_code == 201, r.text
    items = (await client.get(f"/characters/{cid}/items")).json()
    iid = next(i["id"] for i in items if i["name"] == "Mela")
    r2 = await client.post(f"/characters/{cid}/items/{iid}/attack")
    assert r2.status_code == 400, r2.text


async def test_unknown_item_is_404(client):
    cid = await _create_character(client)
    r = await client.post(f"/characters/{cid}/items/999999/attack")
    assert r.status_code == 404, r.text
