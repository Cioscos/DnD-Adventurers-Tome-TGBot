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


_AMULET = {"requires_attunement": True, "attuned": True,
           "ability_modifiers": [{"ability": "constitution", "kind": "absolute", "value": 19}]}


async def _dead_attuned(client, edition: str):
    cid = await _dead_with_exhaustion(client, edition, 0)
    for name, meta in (("Amuleto", _AMULET), ("Anello", {"requires_attunement": True, "attuned": True})):
        r = await client.post(f"/characters/{cid}/items", json={"name": name, "item_type": "accessory", "item_metadata": meta, "is_equipped": name == "Amuleto"})
        assert r.status_code == 201, r.text
    return cid


async def test_revive_2024_drops_attunement(client):
    cid = await _dead_attuned(client, "2024")
    assert (await client.get(f"/characters/{cid}")).json()["hit_points"] == 14  # COS 19 dall'amuleto
    body = (await client.post(f"/characters/{cid}/revive")).json()
    assert body["is_dead"] is False
    assert not any((i["item_metadata"] or {}).get("attuned") for i in body["items"])  # 2024 p.365
    assert body["hit_points"] == 10 and body["current_hit_points"] == 1


async def test_revive_2014_keeps_attunement(client):
    cid = await _dead_attuned(client, "2014")
    body = (await client.post(f"/characters/{cid}/revive")).json()
    assert sum(bool((i["item_metadata"] or {}).get("attuned")) for i in body["items"]) == 2
    assert body["hit_points"] == 14
