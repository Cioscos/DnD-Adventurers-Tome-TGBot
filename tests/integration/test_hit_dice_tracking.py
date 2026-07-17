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


async def test_spend_increments_used_and_respects_pool(client):
    cid = await _create_character(client)
    class_id = await _add_class(client, cid, level=3)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 50})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 1})

    r = await client.post(f"/characters/{cid}/hit_dice/spend", json={"class_id": class_id, "count": 2})
    assert r.status_code == 200, r.text

    r = await client.get(f"/characters/{cid}")
    assert r.json()["classes"][0]["hit_dice_used"] == 2


async def test_overspend_returns_409(client):
    cid = await _create_character(client)
    class_id = await _add_class(client, cid, level=2)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 50})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 1})

    r = await client.post(f"/characters/{cid}/hit_dice/spend", json={"class_id": class_id, "count": 3})
    assert r.status_code == 409
    assert r.json()["detail"] == "hit_dice_exhausted"
    # nulla è cambiato
    r = await client.get(f"/characters/{cid}")
    assert r.json()["classes"][0]["hit_dice_used"] == 0


async def test_long_rest_restores_half_biggest_die_first(client):
    cid = await _create_character(client)
    fighter = await _add_class(client, cid, name="fighter", level=6, hit_die=10)
    wizard = await _add_class(client, cid, name="wizard", level=4, hit_die=6)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 200})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 1})
    # spendi 4 dadi fighter e 3 wizard
    await client.post(f"/characters/{cid}/hit_dice/spend", json={"class_id": fighter, "count": 4})
    await client.post(f"/characters/{cid}/hit_dice/spend", json={"class_id": wizard, "count": 3})

    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "long"})
    assert r.status_code == 200, r.text
    classes = {c["class_name"]: c for c in r.json()["classes"]}
    # budget = max(1, 10 // 2) = 5, prima il d10: fighter 4-4=0, poi wizard 3-1=2
    assert classes["fighter"]["hit_dice_used"] == 0
    assert classes["wizard"]["hit_dice_used"] == 2


async def test_short_rest_does_not_restore_hit_dice(client):
    cid = await _create_character(client)
    class_id = await _add_class(client, cid, level=4)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 50})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 1})
    await client.post(f"/characters/{cid}/hit_dice/spend", json={"class_id": class_id, "count": 2})

    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})
    assert r.status_code == 200
    assert r.json()["classes"][0]["hit_dice_used"] == 2
