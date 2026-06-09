"""PATCH /characters/{id}/classes/distribute — atomic class-level redistribution.

Validations:
- the body must cover exactly the character's class ids → else 400 classes_mismatch.
- ``sum(level)`` must not exceed the XP-derived level → else 400 sum_exceeds_target.

On success (multiclass, so PATCH /xp does NOT auto-sync a single class level):
- each class level is updated;
- with ``hp_auto_calc`` on, max HP is recomputed from the new class mix and
  current HP is scaled by the old ``current/old_max`` ratio;
- ``hp_gained`` reports the positive max-HP delta.

A level-1 d10 character starts at 10 HP (CON 10 → mod 0). After distributing to
Guerriero L2 + Ladro L1 the fixed-HP formula yields 10 + 6 + 5 = 21
(``total_base_hp``: first level uses the max die, later levels ``die//2 + 1``).

Contract: response is a ``CharacterFull`` (classes / hit_points /
current_hit_points / hp_gained) consumed by api.classes.distribute in client.ts.
"""
from __future__ import annotations


async def _create_fighter(client) -> tuple[int, int]:
    """Level-1 d10 fighter → 10 HP. Returns (char_id, fighter_class_id)."""
    r = await client.post(
        "/characters",
        json={"name": "Multi",
              "initial_class": {"class_name": "Guerriero", "level": 1, "hit_die": 10}},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["hit_points"] == 10
    return body["id"], body["classes"][0]["id"]


async def _add_rogue(client, cid: int) -> int:
    r = await client.post(
        f"/characters/{cid}/classes",
        json={"class_name": "Ladro", "level": 1, "hit_die": 8},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    return next(c["id"] for c in body["classes"] if c["class_name"] == "Ladro")


async def _set_xp(client, cid: int, xp: int) -> None:
    r = await client.patch(f"/characters/{cid}/xp", json={"set": xp})
    assert r.status_code == 200, r.text


def _level_of(body: dict, class_id: int) -> int:
    return next(c["level"] for c in body["classes"] if c["id"] == class_id)


async def test_distribute_updates_levels_and_scales_full_hp(client):
    cid, gid = await _create_fighter(client)
    lid = await _add_rogue(client, cid)
    await _set_xp(client, cid, 900)  # level 3; multiclass → no single-class auto-sync

    r = await client.patch(
        f"/characters/{cid}/classes/distribute",
        json={"classes": [{"class_id": gid, "level": 2}, {"class_id": lid, "level": 1}]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert _level_of(body, gid) == 2
    assert _level_of(body, lid) == 1
    assert body["hit_points"] == 21                 # 10 + 6 + 5
    # current was full (10/10) → ratio 1.0 → current tracks the new max.
    assert body["current_hit_points"] == 21
    assert body["hp_gained"] == 11                  # 21 - 10


async def test_distribute_scales_current_hp_by_ratio(client):
    cid, gid = await _create_fighter(client)
    lid = await _add_rogue(client, cid)
    await _set_xp(client, cid, 900)
    # Halve current HP first → ratio 0.5 against old max 10.
    rh = await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 5})
    assert rh.status_code == 200, rh.text

    r = await client.patch(
        f"/characters/{cid}/classes/distribute",
        json={"classes": [{"class_id": gid, "level": 2}, {"class_id": lid, "level": 1}]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    new_max = body["hit_points"]
    assert new_max == 21
    assert body["current_hit_points"] == round(0.5 * new_max)  # round(10.5) → 10


async def test_sum_exceeding_xp_level_is_400(client):
    cid, gid = await _create_fighter(client)  # XP 0 → target level 1
    r = await client.patch(
        f"/characters/{cid}/classes/distribute",
        json={"classes": [{"class_id": gid, "level": 2}]},
    )
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "sum_exceeds_target"


async def test_unknown_class_id_is_mismatch_400(client):
    cid, _gid = await _create_fighter(client)
    r = await client.patch(
        f"/characters/{cid}/classes/distribute",
        json={"classes": [{"class_id": 999999, "level": 1}]},
    )
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "classes_mismatch"


async def test_body_missing_a_class_is_mismatch_400(client):
    cid, gid = await _create_fighter(client)
    await _add_rogue(client, cid)
    await _set_xp(client, cid, 900)
    # Body omits the rogue → does not cover every class id.
    r = await client.patch(
        f"/characters/{cid}/classes/distribute",
        json={"classes": [{"class_id": gid, "level": 2}]},
    )
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "classes_mismatch"
