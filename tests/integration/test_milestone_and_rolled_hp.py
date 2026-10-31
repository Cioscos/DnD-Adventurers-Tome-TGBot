"""Milestone advancement + rolled HP at level-up (settings.advancement / hp_mode / hp_rolls)."""
from __future__ import annotations


async def _fighter(client, **settings) -> tuple[int, int]:
    r = await client.post(
        "/characters",
        json={"name": "M", "initial_class": {"class_name": "Guerriero", "level": 1, "hit_die": 10}},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    if settings:
        r = await client.patch(f"/characters/{body['id']}", json={"settings": settings})
        assert r.status_code == 200, r.text
    return body["id"], body["classes"][0]["id"]


async def _set_con(client, cid: int, value: int) -> None:
    r = await client.patch(f"/characters/{cid}/ability_scores/constitution", json={"value": value})
    assert r.status_code == 200, r.text


def _dist(cid_cls: int, level: int, **extra) -> dict:
    return {"classes": [{"class_id": cid_cls, "level": level}], **extra}


async def test_milestone_level_up_without_xp(client):
    cid, gid = await _fighter(client, advancement="milestone")
    r = await client.patch(f"/characters/{cid}/classes/distribute", json=_dist(gid, 4))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["classes"][0]["level"] == 4
    assert body["experience_points"] == 0
    assert body["hit_points"] == 10 + 3 * 6
    # ASI choices still created on the milestone path (Task 21)
    assert [c["level"] for c in body["pending_choices"]] == [4]


async def test_milestone_xp_does_not_change_level(client):
    cid, _ = await _fighter(client, advancement="milestone")
    r = await client.patch(f"/characters/{cid}/xp", json={"set": 900})
    assert r.status_code == 200, r.text
    assert r.json()["classes"][0]["level"] == 1


async def test_milestone_cap_is_20(client):
    cid, gid = await _fighter(client, advancement="milestone")
    r = await client.patch(f"/characters/{cid}/classes/distribute", json=_dist(gid, 20))
    assert r.status_code == 200, r.text
    r = await client.patch(f"/characters/{cid}/classes/distribute", json=_dist(gid, 21))
    assert r.status_code == 422


async def test_rolled_hp_uses_rolls_and_effective_con(client):
    cid, gid = await _fighter(client, hp_mode="rolled")
    await _set_con(client, cid, 14)  # +2
    r = await client.patch(f"/characters/{cid}/xp", json={"set": 900})
    assert r.status_code == 200
    # level already 3 via xp; reset to 1 then redistribute with rolls
    r = await client.patch(f"/characters/{cid}/classes/{gid}", json={"level": 1})
    assert r.status_code == 200, r.text
    r = await client.patch(f"/characters/{cid}/classes/distribute", json=_dist(gid, 3, hp_rolls=[4, 6]))
    assert r.status_code == 200, r.text
    assert r.json()["hit_points"] == 12 + (4 + 2) + (6 + 2)
    # CON change then recalc keeps the rolls (no silent revert to fixed values)
    await _set_con(client, cid, 16)  # +3
    r = await client.post(f"/characters/{cid}/hp/recalc")
    assert r.json()["hit_points"] == 13 + (4 + 3) + (6 + 3)


async def test_rolled_hp_minimum_one_per_level(client):
    cid, gid = await _fighter(client, advancement="milestone")
    await _set_con(client, cid, 3)  # -4
    r = await client.patch(f"/characters/{cid}/classes/distribute", json=_dist(gid, 2, hp_rolls=[2]))
    assert r.status_code == 200, r.text
    assert r.json()["hit_points"] == 6 + 1  # 10-4 at level 1, max(1, 2-4) at level 2


async def test_rolled_hp_out_of_range_422(client):
    cid, gid = await _fighter(client, advancement="milestone")
    for rolls in ([0], [11], [1, 2]):
        r = await client.patch(f"/characters/{cid}/classes/distribute", json=_dist(gid, 2, hp_rolls=rolls))
        assert r.status_code == 422, rolls
    r = await client.get(f"/characters/{cid}")
    assert r.json()["classes"][0]["level"] == 1


async def test_update_class_level_recalculates_hp(client):
    cid, gid = await _fighter(client)
    r = await client.patch(f"/characters/{cid}/classes/{gid}", json={"level": 3})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["hit_points"] == 10 + 6 + 6
    assert body["current_hit_points"] == 22
    r = await client.patch(f"/characters/{cid}/classes/{gid}", json={"level": 4, "hp_rolls": [9]})
    assert r.json()["hit_points"] == 22 + 9
    assert [c["level"] for c in r.json()["pending_choices"]] == [4]


async def test_xp_mode_unchanged(client):
    cid, gid = await _fighter(client)
    r = await client.patch(f"/characters/{cid}/xp", json={"set": 900})
    assert r.json()["classes"][0]["level"] == 3
    assert r.json()["hit_points"] == 22
    # XP cap still enforced by distribute
    r = await client.patch(f"/characters/{cid}/classes/distribute", json=_dist(gid, 4))
    assert r.status_code == 400


async def test_xp_rolls_applied_and_stored(client):
    cid, gid = await _fighter(client, hp_mode="rolled")
    await _set_con(client, cid, 14)  # +2
    r = await client.patch(f"/characters/{cid}/xp", json={"set": 900, "hp_rolls": [4, 6]})  # -> level 3
    assert r.status_code == 200, r.text
    assert r.json()["hit_points"] == 12 + (4 + 2) + (6 + 2)
    assert r.json()["hp_gained"] == 6 + 8
    await _set_con(client, cid, 16)
    r = await client.post(f"/characters/{cid}/hp/recalc")
    assert r.json()["hit_points"] == 13 + 7 + 9  # rolls survive the recalc


async def test_xp_rolls_invalid_422(client):
    cid, _ = await _fighter(client, hp_mode="rolled")
    for rolls in ([11, 3], [4], []):
        r = await client.patch(f"/characters/{cid}/xp", json={"set": 900, "hp_rolls": rolls})
        assert r.status_code == 422, rolls
    r = await client.get(f"/characters/{cid}")
    assert r.json()["experience_points"] == 0


async def test_xp_rolls_not_applicable_to_multiclass(client):
    cid, _ = await _fighter(client)
    await client.post(f"/characters/{cid}/classes", json={"class_name": "Ladro", "level": 1, "hit_die": 8})
    r = await client.patch(f"/characters/{cid}/xp", json={"set": 900, "hp_rolls": [3, 3]})
    assert r.status_code == 422
    assert r.json()["detail"] == "hp_rolls_not_applicable"


async def test_xp_without_rolls_in_rolled_mode_falls_back_to_fixed(client):
    cid, _ = await _fighter(client, hp_mode="rolled")
    r = await client.patch(f"/characters/{cid}/xp", json={"set": 900})
    assert r.json()["hit_points"] == 22


async def test_update_class_rolls_without_level_change_422(client):
    cid, gid = await _fighter(client)
    r = await client.patch(f"/characters/{cid}/classes/{gid}", json={"subclass": "x", "hp_rolls": [3]})
    assert r.status_code == 422


async def test_rolls_survive_export_import_and_duplicate(client):
    await _fighter(client)  # shifts class ids so the copy cannot match by accident
    cid, gid = await _fighter(client, hp_mode="rolled", advancement="milestone")
    r = await client.patch(f"/characters/{cid}/classes/distribute", json=_dist(gid, 3, hp_rolls=[9, 9]))
    assert r.json()["hit_points"] == 10 + 9 + 9
    exp = (await client.get(f"/characters/{cid}/export")).json()
    imp = await client.post("/characters/import", json=exp)
    assert imp.status_code == 201, imp.text
    dup = await client.post(f"/characters/{cid}/duplicate")
    assert dup.status_code == 201, dup.text
    for copy in (imp.json(), dup.json()):
        assert copy["classes"][0]["id"] != gid
        r = await client.post(f"/characters/{copy['id']}/hp/recalc")
        assert r.json()["hit_points"] == 28


async def test_import_ignores_malformed_hp_rolls(client):
    cid, _ = await _fighter(client)
    exp = (await client.get(f"/characters/{cid}/export")).json()
    for bad in ([], "x", {"zz": {"2": 5}, "c0": 3}):
        exp["character"]["settings"] = {"hp_rolls": bad}
        r = await client.post("/characters/import", json=exp)
        assert r.status_code == 201, (bad, r.text)


async def test_export_and_duplicate_tolerate_corrupt_stored_hp_rolls(client, test_session_factory):
    from sqlalchemy import update
    from core.db.models import Character
    cid, _ = await _fighter(client)
    for bad in ([], "x", {"abc": {"2": 5}}, {"1": 7}):
        async with test_session_factory() as s:
            await s.execute(update(Character).where(Character.id == cid).values(settings={"hp_rolls": bad}))
            await s.commit()
        assert (await client.get(f"/characters/{cid}/export")).status_code == 200, bad
        assert (await client.post(f"/characters/{cid}/duplicate")).status_code == 201, bad
