"""POST /characters/{id}/hp/recalc — recompute max HP from the D&D 5e fixed formula.

``recalc_hp`` sets ``hit_points`` to ``total_base_hp(classes, effective_con_mod)``
and reconciles ``current_hit_points``:

- new_max > old_max → current grows by the delta (a level/CON bump adds HP).
- new_max < old_max → current is clamped down to the new max.
- no classes → formula yields 0 (HP 0/0).

Setup is deterministic: a single class with ``hit_die=10`` at level 1 and the
default CON 10 (mod 0) gives ``hit_points_for_level(10, 0, 1) == 10``. We capture
that value from the create response so the assertions don't hardcode the formula.
"""
from __future__ import annotations


async def _create_with_fighter(client) -> tuple[int, int]:
    """Create a level-1 d10 class character. Returns (char_id, formula_max_hp)."""
    r = await client.post(
        "/characters",
        json={"name": "Recalc", "initial_class": {"class_name": "Guerriero", "level": 1, "hit_die": 10}},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    return body["id"], body["hit_points"]


async def _patch_hp(client, cid: int, op: str, value: int):
    r = await client.patch(f"/characters/{cid}/hp", json={"op": op, "value": value})
    assert r.status_code == 200, r.text
    return r.json()


async def _recalc(client, cid: int):
    r = await client.post(f"/characters/{cid}/hp/recalc")
    assert r.status_code == 200, r.text
    return r.json()


async def test_recalc_clamps_current_down_when_max_shrinks(client):
    cid, formula_hp = await _create_with_fighter(client)
    assert formula_hp == 10  # d10 + CON 0 at level 1

    # Inflate max + current well above the formula value.
    await _patch_hp(client, cid, "set_max", 30)
    await _patch_hp(client, cid, "set_current", 30)

    body = await _recalc(client, cid)
    assert body["hit_points"] == formula_hp           # back to formula
    assert body["current_hit_points"] == formula_hp   # clamped down from 30


async def test_recalc_grows_current_by_delta_when_max_increases(client):
    cid, formula_hp = await _create_with_fighter(client)

    # Shrink max below the formula; current follows the clamp.
    await _patch_hp(client, cid, "set_max", 2)
    body = await _recalc(client, cid)

    assert body["hit_points"] == formula_hp
    # current was 2; grows by (formula_hp - 2) → exactly formula_hp.
    assert body["current_hit_points"] == formula_hp


async def test_recalc_with_no_classes_yields_zero(client):
    r = await client.post("/characters", json={"name": "Classless"})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]

    await _patch_hp(client, cid, "set_max", 8)
    await _patch_hp(client, cid, "set_current", 5)

    body = await _recalc(client, cid)
    assert body["hit_points"] == 0
    assert body["current_hit_points"] == 0


async def test_recalc_returns_full_character_shape(client):
    """Contract: the endpoint returns a CharacterFull with the AC breakdown populated."""
    cid, _ = await _create_with_fighter(client)
    body = await _recalc(client, cid)

    for key in ("id", "hit_points", "current_hit_points", "ac", "ac_breakdown"):
        assert key in body, f"missing {key} in recalc response"
    assert set(body["ac_breakdown"]) == {"base", "shield", "magic", "homebrew"}
