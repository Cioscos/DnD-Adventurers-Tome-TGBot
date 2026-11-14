"""GEN-14: tornare in vita con livelli di Esaurimento (2024 Glossario, «Dead», p.365)."""
from __future__ import annotations

import pytest


async def _dead_with_exhaustion(client, edition: str, level: int) -> int:
    cid = (await client.post("/characters", json={"name": "Prova"})).json()["id"]
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 1, "hit_die": 10})
    assert r.status_code == 201, r.text
    if edition != "2014":
        assert (await client.patch(f"/characters/{cid}", json={"rules_edition": edition})).status_code == 200
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"exhaustion": level}})
    assert r.status_code == 200, r.text
    for _ in range(3):
        await client.patch(f"/characters/{cid}/death_saves", json={"action": "failure"})
    return cid


@pytest.mark.parametrize("edition,expected", [("2024", 2), ("2014", 3)])
async def test_revive_exhaustion_by_edition(client, edition, expected):
    cid = await _dead_with_exhaustion(client, edition, 3)
    r = await client.post(f"/characters/{cid}/revive")
    body = r.json()
    assert body["is_dead"] is False
    assert body["conditions"]["exhaustion"] == expected  # 2024 p.365: un livello in meno al ritorno in vita
