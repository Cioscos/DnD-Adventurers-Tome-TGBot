"""Il colpo senz'armi riconosce il Monaco sia con il nome inglese sia con quello italiano."""
from __future__ import annotations

import pytest


@pytest.mark.parametrize("class_name", ["monk", "Monaco"])
async def test_monk_unarmed_uses_dex_and_martial_arts(client, class_name):
    r = await client.post(
        "/characters",
        json={"name": "Monaco", "initial_class": {"class_name": class_name, "level": 1, "hit_die": 8}},
    )
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    r = await client.patch(f"/characters/{cid}/ability_scores/dexterity", json={"value": 16})
    assert r.status_code == 200, r.text

    r = await client.post(f"/characters/{cid}/attack/unarmed", json={"die": 10})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["to_hit_bonus"] == 5  # DEX +3, competenza +2
    assert body["damage_dice"] == "1d4"
