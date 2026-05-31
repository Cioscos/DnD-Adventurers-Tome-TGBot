"""Integration test: unarmed strike endpoint (base + Monk Martial Arts)."""
from __future__ import annotations

import pytest


async def _add_monk(client, char_id: int, level: int) -> None:
    r = await client.post(
        f"/characters/{char_id}/classes",
        json={"class_name": "Monaco", "level": level, "hit_die": 8},
    )
    assert r.status_code == 201, r.text


@pytest.mark.asyncio
async def test_monk_unarmed_uses_martial_arts_die(client, char_id, patch_random_roll):
    """Monk lvl5: damage die 1d6; to-hit = mod + proficiency (pb +3 at total level 5)."""
    await _add_monk(client, char_id, 5)
    patch_random_roll([15, 4])  # [15] to-hit die (no crit/fumble), [4] damage die roll

    r = await client.post(f"/characters/{char_id}/attack/unarmed")
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["weapon_name"] == "Attacco a mano libera"
    assert body["damage_dice"] == "1d6"
    assert body["to_hit_die"] == 15
    assert body["is_critical"] is False
    assert body["is_fumble"] is False
    assert body["to_hit_bonus"] == 3   # mod 0 + pb 3
    assert body["to_hit_total"] == 18
    assert body["damage_rolls"] == [4]
    assert body["damage_total"] == 4   # 1d6 roll(4) + mod 0


@pytest.mark.asyncio
async def test_non_monk_unarmed_is_flat_one(client, char_id, patch_random_roll):
    """No class -> flat 1 + STR mod (0 by default), bludgeoning, no die roll."""
    patch_random_roll([12])  # to-hit die only
    r = await client.post(f"/characters/{char_id}/attack/unarmed")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["damage_dice"] == "1"
    assert body["damage_rolls"] == [1]
    assert body["damage_total"] == 1   # 1 + 0
    assert body["is_critical"] is False
