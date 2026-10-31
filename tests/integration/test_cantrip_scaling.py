"""I trucchetti scalano con il livello totale del personaggio, gli incantesimi no."""
from __future__ import annotations

import pytest

from core.game.stats import cantrip_dice_multiplier


@pytest.mark.parametrize(
    "level,mult", [(1, 1), (4, 1), (5, 2), (10, 2), (11, 3), (16, 3), (17, 4), (20, 4)]
)
def test_multiplier_table(level, mult):
    assert cantrip_dice_multiplier(level) == mult


async def _roll(client, level, spell_level, rolls):
    r = await client.post("/characters", json={"name": "Mago"})
    cid = r.json()["id"]
    r = await client.post(
        f"/characters/{cid}/classes",
        json={"class_name": "wizard", "level": level, "hit_die": 6},
    )
    assert r.status_code == 201, r.text
    r = await client.post(
        f"/characters/{cid}/spells",
        json={"name": "Dardo di fuoco", "level": spell_level, "damage_dice": "1d10",
              "damage_type": "fire"},
    )
    sid = r.json()["id"]
    return await client.post(
        f"/characters/{cid}/spells/{sid}/roll_damage",
        json={"casting_level": spell_level, "main_rolls": rolls},
    )


async def test_cantrip_dice_scale_at_5_11_17(client):
    r = await _roll(client, 5, 0, [3, 4])
    assert r.status_code == 200, r.text
    assert r.json()["scaled_dice"] == "2d10"
    assert r.json()["total"] == 7
    r = await _roll(client, 17, 0, [1, 2, 3, 4])
    assert r.json()["scaled_dice"] == "4d10"


async def test_leveled_spell_not_scaled(client):
    r = await _roll(client, 17, 1, [5])
    assert r.status_code == 200, r.text
    assert r.json()["scaled_dice"] == "1d10"
