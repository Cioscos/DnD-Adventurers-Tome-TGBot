"""PATCH /characters/{id}/xp — XP set/add and single-class level sync.

D&D 5e SRD thresholds (core.data.xp_thresholds): 300 → L2, 900 → L3.
For a SINGLE-class character the class level tracks the XP-derived level and,
with ``hp_auto_calc`` on, each gained level adds ``hit_die//2 + 1 + con_mod`` HP
(the fixed method; level 1 was granted at creation). Level-DOWN syncs the class
level but never *removes* HP. Multiclass characters do NOT auto-sync (the user
distributes levels manually via /classes/distribute).

Contract: ``CharacterFull`` with experience_points / classes[].level /
hit_points / current_hit_points / hp_gained (api.stats.updateXP, Experience.tsx).
"""
from __future__ import annotations


async def _fighter(client) -> int:
    r = await client.post(
        "/characters",
        json={"name": "XP", "initial_class": {"class_name": "Guerriero", "level": 1, "hit_die": 10}},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["hit_points"] == 10 and body["classes"][0]["level"] == 1
    return body["id"]


async def _add_rogue(client, cid: int) -> None:
    r = await client.post(f"/characters/{cid}/classes",
                          json={"class_name": "Ladro", "level": 1, "hit_die": 8})
    assert r.status_code == 201, r.text


async def test_set_xp_levels_up_single_class_and_adds_hp(client):
    cid = await _fighter(client)
    r = await client.patch(f"/characters/{cid}/xp", json={"set": 900})  # → level 3
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["experience_points"] == 900
    assert body["classes"][0]["level"] == 3
    # Levels 2 and 3, fixed method d10 CON 0: 6 + 6 = 12.
    assert body["hp_gained"] == 12
    assert body["hit_points"] == 22
    assert body["current_hit_points"] == 22


async def test_add_xp_levels_up_by_one(client):
    cid = await _fighter(client)
    r = await client.patch(f"/characters/{cid}/xp", json={"add": 300})  # 0 → 300 → level 2
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["experience_points"] == 300
    assert body["classes"][0]["level"] == 2
    assert body["hp_gained"] == 6
    assert body["hit_points"] == 16


async def test_level_down_syncs_level_but_keeps_hp(client):
    cid = await _fighter(client)
    await client.patch(f"/characters/{cid}/xp", json={"set": 900})       # L3, 22 HP
    r = await client.patch(f"/characters/{cid}/xp", json={"set": 0})     # back to L1
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["classes"][0]["level"] == 1
    assert body["hit_points"] == 22          # XP loss never strips HP
    assert body["hp_gained"] is None


async def test_negative_xp_clamps_to_zero(client):
    cid = await _fighter(client)
    r = await client.patch(f"/characters/{cid}/xp", json={"set": -100})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["experience_points"] == 0
    assert body["classes"][0]["level"] == 1


async def test_multiclass_does_not_auto_sync_levels(client):
    cid = await _fighter(client)
    await _add_rogue(client, cid)
    r = await client.patch(f"/characters/{cid}/xp", json={"set": 900})  # XP level 3
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["experience_points"] == 900
    # Two classes → no automatic level sync; both stay at 1.
    assert sorted(c["level"] for c in body["classes"]) == [1, 1]
    assert body["hp_gained"] is None
    assert body["hit_points"] == 10
