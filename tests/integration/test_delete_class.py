"""DELETE /characters/{id}/classes/{class_id} — remove a class, rescale HP.

Mirrors PATCH /classes/distribute: removing a class lowers total_level, so max
HP is recomputed from the remaining classes via ``total_base_hp`` and current HP
is scaled by the old ``current/old_max`` ratio (finding #3 — previously only
spell slots were recalculated, leaving "ghost" HP). With no classes left,
``total_base_hp`` returns 0 → HP 0/0.

``total_base_hp`` (CON 10 → mod 0): the lowest-id class owns the level-1 slot
(full die); every other class-level uses ``die // 2 + 1``. So:
- [Guerriero L2 d10, Ladro L1 d8] = 10 + 6 + 5 = 21
- [Guerriero L2 d10]              = 10 + 6      = 16

Contract: the response is a ``CharacterFull`` (classes / hit_points /
current_hit_points).
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
    return next(c["id"] for c in r.json()["classes"] if c["class_name"] == "Ladro")


async def _multiclass_21hp(client) -> tuple[int, int, int]:
    """Guerriero L2 + Ladro L1 = 21 HP. Returns (char_id, fighter_id, rogue_id)."""
    cid, gid = await _create_fighter(client)
    lid = await _add_rogue(client, cid)
    r = await client.patch(f"/characters/{cid}/xp", json={"set": 900})  # multiclass: no auto-sync
    assert r.status_code == 200, r.text
    r = await client.patch(
        f"/characters/{cid}/classes/distribute",
        json={"classes": [{"class_id": gid, "level": 2}, {"class_id": lid, "level": 1}]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["hit_points"] == 21
    return cid, gid, lid


async def test_delete_class_lowers_max_and_scales_full_current(client):
    cid, _gid, lid = await _multiclass_21hp(client)  # 21/21

    r = await client.delete(f"/characters/{cid}/classes/{lid}")
    assert r.status_code == 200, r.text
    body = r.json()
    # Remaining [Guerriero L2] → total_base_hp = 16. current was full → tracks new max.
    assert body["hit_points"] == 16
    assert body["current_hit_points"] == 16
    assert len(body["classes"]) == 1
    assert body["classes"][0]["class_name"] == "Guerriero"


async def test_delete_class_scales_current_by_ratio(client):
    cid, _gid, lid = await _multiclass_21hp(client)
    rh = await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 7})
    assert rh.status_code == 200, rh.text  # 7/21

    r = await client.delete(f"/characters/{cid}/classes/{lid}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["hit_points"] == 16
    # ratio 7/21 against new max 16 → round(5.333) = 5
    assert body["current_hit_points"] == round(7 / 21 * 16)
    assert body["current_hit_points"] == 5


async def test_delete_last_remaining_class_zeroes_hp(client):
    cid, gid = await _create_fighter(client)  # 10/10, single class

    r = await client.delete(f"/characters/{cid}/classes/{gid}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["classes"] == []
    assert body["hit_points"] == 0
    assert body["current_hit_points"] == 0


async def test_delete_unknown_class_is_404(client):
    cid, _gid = await _create_fighter(client)
    r = await client.delete(f"/characters/{cid}/classes/999999")
    assert r.status_code == 404, r.text
