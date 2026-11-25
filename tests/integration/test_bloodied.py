"""GEN-107: Sanguinante (2024 p.27 e Glossario p.362) — a metà dei PF massimi o meno."""
from __future__ import annotations

import pytest


async def _fighter(client, edition: str) -> int:
    cid = (await client.post("/characters", json={"name": "Prova"})).json()["id"]
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 1, "hit_die": 10})
    assert r.status_code == 201, r.text
    if edition != "2014":
        assert (await client.patch(f"/characters/{cid}", json={"rules_edition": edition})).status_code == 200
    return cid


async def _set_hp(client, cid: int, value: int) -> dict:
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": value})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("edition,hp,expected", [
    ("2024", 5, True),    # metà esatta di 10
    ("2024", 6, False),
    ("2024", 0, True),    # 2024 Glossario p.362: «a metà PF o meno», lo 0 compreso
    ("2014", 5, False),   # il 2014 non ha la condizione
])
async def test_bloodied_flag(client, edition, hp, expected):
    cid = await _fighter(client, edition)
    full = (await client.get(f"/characters/{cid}")).json()
    assert full["computed"]["hp_max_effective"] == 10
    assert (await _set_hp(client, cid, hp))["computed"]["bloodied"] is expected
