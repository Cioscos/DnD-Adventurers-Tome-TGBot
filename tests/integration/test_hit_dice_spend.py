"""POST /characters/{id}/hit_dice/spend — short-rest hit-die healing.

D&D 5e rule under test: each spent hit die heals ``roll + CON modifier`` with a
floor of 1 per die, and the total recovery is clamped to the character's maximum
HP. A freshly created character has CON 10 (modifier 0), so each die heals
exactly its face value (≥ 1). Error paths: an unknown ``class_id`` ⇒ 404, a
``count`` below 1 ⇒ 400.

The roll is RNG-backed, so the assertions key off the values the endpoint reports
back (``rolls`` / ``con_bonus``) rather than hard-coding a single outcome.
"""
from __future__ import annotations


async def _create_character(client) -> int:
    r = await client.post("/characters", json={"name": "HitDice Test"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _add_class(client, cid: int, *, name: str = "fighter", hit_die: int = 10):
    r = await client.post(
        f"/characters/{cid}/classes",
        json={"class_name": name, "level": 1, "hit_die": hit_die},
    )
    assert r.status_code == 201, r.text
    cls = next(c for c in r.json()["classes"] if c["class_name"] == name)
    return cls["id"], (cls["hit_die"] or 8)


async def _set_hp(client, cid: int, maximum: int, current: int):
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": maximum})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": current})


async def test_spending_dice_heals_within_die_range(client):
    cid = await _create_character(client)
    class_id, die = await _add_class(client, cid, hit_die=10)
    await _set_hp(client, cid, 100, 1)  # plenty of headroom so nothing is clamped

    r = await client.post(
        f"/characters/{cid}/hit_dice/spend", json={"class_id": class_id, "count": 2}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["rolls"]) == 2
    assert all(1 <= roll <= die for roll in body["rolls"])
    assert body["con_bonus"] == 0  # CON 10 ⇒ modifier 0
    expected = sum(max(1, roll + body["con_bonus"]) for roll in body["rolls"])
    assert body["healed"] == expected
    assert body["new_current_hp"] == 1 + expected


async def test_heal_is_clamped_to_maximum(client):
    cid = await _create_character(client)
    class_id, _die = await _add_class(client, cid, hit_die=12)
    await _set_hp(client, cid, 5, 4)  # only 1 HP of headroom

    r = await client.post(
        f"/characters/{cid}/hit_dice/spend", json={"class_id": class_id, "count": 1}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["new_current_hp"] == 5   # never exceeds max
    assert body["healed"] == 1           # 4 → 5, regardless of the roll


async def test_unknown_class_is_404(client):
    cid = await _create_character(client)
    r = await client.post(
        f"/characters/{cid}/hit_dice/spend", json={"class_id": 99999, "count": 1}
    )
    assert r.status_code == 404, r.text


async def test_count_below_one_is_400(client):
    cid = await _create_character(client)
    class_id, _die = await _add_class(client, cid)
    r = await client.post(
        f"/characters/{cid}/hit_dice/spend", json={"class_id": class_id, "count": 0}
    )
    assert r.status_code == 400, r.text
