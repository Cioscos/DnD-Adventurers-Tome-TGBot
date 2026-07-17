"""Tracking dei dadi vita residui (spec 2026-07-17).

Residui per classe = level - hit_dice_used. La colonna parte a 0 (tutti
disponibili), /hit_dice/spend la incrementa e va in 409 oltre i residui,
il riposo lungo ne recupera max(1, total_level // 2) dal dado più grande.
"""
from __future__ import annotations


async def _create_character(client) -> int:
    r = await client.post("/characters", json={"name": "HD Tracking"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _add_class(client, cid: int, *, name: str = "fighter", level: int = 5, hit_die: int = 10) -> int:
    r = await client.post(
        f"/characters/{cid}/classes",
        json={"class_name": name, "level": level, "hit_die": hit_die},
    )
    assert r.status_code == 201, r.text
    return next(c["id"] for c in r.json()["classes"] if c["class_name"] == name)


async def test_new_class_exposes_hit_dice_used_zero(client):
    cid = await _create_character(client)
    await _add_class(client, cid, level=3)
    r = await client.get(f"/characters/{cid}")
    cls = r.json()["classes"][0]
    assert cls["hit_dice_used"] == 0
