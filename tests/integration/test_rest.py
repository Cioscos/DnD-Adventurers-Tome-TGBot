"""Rest mechanics (POST /characters/{id}/rest).

D&D 5e rules under test:
- A long rest restores HP to (effective) maximum and resets death saves.
- A short rest only heals by the hit dice spent, clamped to maximum.
- An invalid rest_type is rejected with HTTP 400.
"""
from __future__ import annotations


async def _create_character(client) -> int:
    r = await client.post("/characters", json={"name": "Rest Test"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _set_hp(client, cid: int, *, maximum: int, current: int) -> None:
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": maximum})
    assert r.status_code == 200, r.text
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": current})
    assert r.status_code == 200, r.text


async def test_long_rest_restores_full_hp_and_resets_death_saves(client):
    cid = await _create_character(client)
    await _set_hp(client, cid, maximum=20, current=3)
    # Drop to 0 and take a hit at 0 to accrue a death-save failure.
    await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 3})
    await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 1})

    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "long"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["current_hit_points"] == 20
    ds = body["death_saves"]
    assert ds["successes"] == 0 and ds["failures"] == 0 and ds.get("stable") is False


async def test_short_rest_heals_by_hit_dice_spent(client):
    cid = await _create_character(client)
    await _set_hp(client, cid, maximum=20, current=5)

    r = await client.post(
        f"/characters/{cid}/rest", json={"rest_type": "short", "hit_dice_used": 10}
    )
    assert r.status_code == 200, r.text
    # 5 + 10 = 15, not a full heal to 20.
    assert r.json()["current_hit_points"] == 15


async def test_short_rest_heal_is_clamped_to_maximum(client):
    cid = await _create_character(client)
    await _set_hp(client, cid, maximum=20, current=5)

    r = await client.post(
        f"/characters/{cid}/rest", json={"rest_type": "short", "hit_dice_used": 100}
    )
    assert r.status_code == 200, r.text
    assert r.json()["current_hit_points"] == 20


async def test_invalid_rest_type_is_rejected(client):
    cid = await _create_character(client)
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "bogus"})
    assert r.status_code == 400, r.text
