"""PATCH /hp DAMAGE con nota di resistenza/vulnerabilità e guardia danno zero."""
from __future__ import annotations


async def _hp(client, cid: int, op: str, value: int, **extra) -> dict:
    r = await client.patch(f"/characters/{cid}/hp", json={"op": op, "value": value, **extra})
    assert r.status_code == 200, r.text
    return r.json()


async def _make_char(client, max_hp: int = 20) -> int:
    r = await client.post("/characters", json={"name": "Hero"})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    await _hp(client, cid, "set_max", max_hp)
    await _hp(client, cid, "set_current", max_hp)
    return cid


async def _start_concentration(client, cid: int) -> int:
    rs = await client.post(f"/characters/{cid}/spell_slots", json={"level": 1, "total": 1})
    assert rs.status_code == 201, rs.text
    rsp = await client.post(
        f"/characters/{cid}/spells",
        json={"name": "Bless", "level": 1, "is_concentration": True},
    )
    assert rsp.status_code == 201, rsp.text
    spell_id = rsp.json()["id"]
    ru = await client.post(f"/characters/{cid}/spells/{spell_id}/use", json={"slot_level": 1})
    assert ru.status_code == 200, ru.text
    return spell_id


async def _descriptions(client, cid: int) -> list[str]:
    return [e["description"] for e in (await client.get(f"/characters/{cid}/history")).json()]


async def test_half_damage_history_note(client):
    cid = await _make_char(client, 20)
    body = await _hp(client, cid, "damage", 4, damage_modifier="half", raw_value=8)
    assert body["current_hit_points"] == 16
    assert "Danni: -4 HP (8 dimezzati) (20 → 16)" in await _descriptions(client, cid)


async def test_double_damage_history_note(client):
    cid = await _make_char(client, 20)
    body = await _hp(client, cid, "damage", 16, damage_modifier="double", raw_value=8)
    assert body["current_hit_points"] == 4
    assert "Danni: -16 HP (8 raddoppiati) (20 → 4)" in await _descriptions(client, cid)


async def test_zero_damage_skips_concentration_save(client):
    cid = await _make_char(client, 20)
    await _start_concentration(client, cid)
    await _hp(client, cid, "set_temp", 3)
    body = await _hp(client, cid, "damage", 0, damage_modifier="half", raw_value=1)
    assert body.get("concentration_save") is None
    assert body["current_hit_points"] == 20
    assert body["temp_hp"] == 3


async def test_hp_undo_after_modified_damage(client):
    cid = await _make_char(client, 20)
    dmg = await _hp(client, cid, "damage", 5, damage_modifier="half", raw_value=10)
    assert dmg["current_hit_points"] == 15
    r = await client.post(f"/characters/{cid}/hp/undo", json={"op_id": dmg["hp_undo_id"]})
    assert r.status_code == 200, r.text
    assert r.json()["current_hit_points"] == 20
