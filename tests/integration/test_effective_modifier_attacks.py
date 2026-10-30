"""Gli attacchi usano il modificatore effettivo della scheda (bonus degli oggetti equipaggiati inclusi)."""
from __future__ import annotations


async def _setup(client) -> tuple[int, int]:
    """Personaggio con FOR 14 (+2), livello 2 (PB +2), spada 1d8 e anello FOR +4 equipaggiato."""
    r = await client.post("/characters", json={"name": "Forzuto"})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    r = await client.post(
        f"/characters/{cid}/classes",
        json={"class_name": "fighter", "level": 2, "hit_die": 10},
    )
    assert r.status_code == 201, r.text
    r = await client.patch(f"/characters/{cid}/ability_scores/strength", json={"value": 14})
    assert r.status_code == 200, r.text

    meta = {"damage_dice": "1d8", "weapon_type": "melee", "properties": []}
    r = await client.post(
        f"/characters/{cid}/items",
        json={"name": "Spada", "item_type": "weapon", "item_metadata": meta},
    )
    assert r.status_code == 201, r.text
    ring_meta = {"ability_modifiers": [{"ability": "strength", "kind": "relative", "value": 4}]}
    r = await client.post(
        f"/characters/{cid}/items",
        json={"name": "Guanti", "item_type": "accessory", "item_metadata": ring_meta},
    )
    assert r.status_code == 201, r.text
    items = (await client.get(f"/characters/{cid}/items")).json()
    wid = next(i["id"] for i in items if i["name"] == "Spada")
    gid = next(i["id"] for i in items if i["name"] == "Guanti")
    r = await client.patch(f"/characters/{cid}/items/{gid}", json={"is_equipped": True})
    assert r.status_code == 200, r.text
    return cid, wid


async def test_weapon_attack_uses_item_bonus(client):
    cid, wid = await _setup(client)
    r = await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 10})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["to_hit_bonus"] == 6  # +4 FOR effettiva (18), +2 PB
    assert body["damage_bonus"] == 4


async def test_unarmed_attack_uses_item_bonus(client):
    cid, _ = await _setup(client)
    r = await client.post(f"/characters/{cid}/attack/unarmed", json={"die": 10})
    assert r.status_code == 200, r.text
    assert r.json()["to_hit_bonus"] == 6
