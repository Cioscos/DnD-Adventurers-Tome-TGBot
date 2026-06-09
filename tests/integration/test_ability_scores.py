"""PATCH /characters/{id}/ability_scores/{ability_name}.

D&D 5e ripple rules exercised end-to-end:
- value must be 1–30 (else 400);
- CONSTITUTION change retroactively adjusts max HP and current HP by
  ``delta_con_mod * total_level`` (with ``hp_auto_calc`` on, the default);
- STRENGTH change recomputes carry capacity (STR x 15) unless overridden.

Contract: response is a ``CharacterFull`` (api.stats.updateAbilityScore in
client.ts reads hit_points / current_hit_points / carry_capacity /
ability_scores[].{value,base_value,modifier}).
"""
from __future__ import annotations


async def _fighter(client) -> int:
    """Level-1 d10 fighter, CON 10 (mod 0) → 10 HP."""
    r = await client.post(
        "/characters",
        json={"name": "Stat", "initial_class": {"class_name": "Guerriero", "level": 1, "hit_die": 10}},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["hit_points"] == 10 and body["current_hit_points"] == 10
    return body["id"]


async def _patch(client, cid: int, ability: str, value: int):
    return await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})


def _score(body: dict, name: str) -> dict:
    return next(s for s in body["ability_scores"] if s["name"] == name)


async def test_value_below_one_is_400(client):
    cid = await _fighter(client)
    r = await _patch(client, cid, "strength", 0)
    assert r.status_code == 400, r.text


async def test_value_above_thirty_is_400(client):
    cid = await _fighter(client)
    r = await _patch(client, cid, "strength", 31)
    assert r.status_code == 400, r.text


async def test_constitution_increase_raises_max_and_current_hp(client):
    cid = await _fighter(client)
    # CON 10 → 14: mod 0 → +2, delta +2 over total_level 1 → +2 HP.
    r = await _patch(client, cid, "constitution", 14)
    assert r.status_code == 200, r.text
    body = r.json()
    assert _score(body, "constitution")["value"] == 14
    assert _score(body, "constitution")["modifier"] == 2
    assert body["hit_points"] == 12
    assert body["current_hit_points"] == 12


async def test_constitution_decrease_lowers_hp_symmetrically(client):
    cid = await _fighter(client)
    await _patch(client, cid, "constitution", 14)   # → 12/12
    r = await _patch(client, cid, "constitution", 10)  # back to mod 0
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["hit_points"] == 10
    assert body["current_hit_points"] == 10


async def test_strength_change_recomputes_carry_capacity(client):
    cid = await _fighter(client)
    r = await _patch(client, cid, "strength", 16)
    assert r.status_code == 200, r.text
    body = r.json()
    assert _score(body, "strength")["value"] == 16
    assert body["carry_capacity"] == 16 * 15      # 240


async def test_non_constitution_change_does_not_touch_hp(client):
    cid = await _fighter(client)
    r = await _patch(client, cid, "dexterity", 18)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["hit_points"] == 10
    assert body["current_hit_points"] == 10
    assert _score(body, "dexterity")["modifier"] == 4
