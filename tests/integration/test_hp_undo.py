"""POST /characters/{id}/hp/undo — annullamento dell'ultima operazione PF.

Lo snapshot ``before``/``after`` vive sul server (``Character.hp_undo``): il
client manda solo l'``op_id`` ricevuto da ``PATCH /hp`` e l'annullamento è
rifiutato (409) se lo stato è cambiato nel frattempo.
"""
from __future__ import annotations

import random

from sqlalchemy import select

from core.db.models import Character

TEST_USER_ID = 1234  # mirrors tests/integration/conftest.py


def _force_d20(monkeypatch, value: int) -> None:
    monkeypatch.setattr(random, "randint", lambda a, b: value)


async def _hp(client, cid: int, op: str, value: int, **extra) -> dict:
    r = await client.patch(f"/characters/{cid}/hp", json={"op": op, "value": value, **extra})
    assert r.status_code == 200, r.text
    return r.json()


async def _make_char(client, max_hp: int = 20, current: int | None = None) -> int:
    r = await client.post("/characters", json={"name": "Hero"})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    await _hp(client, cid, "set_max", max_hp)
    await _hp(client, cid, "set_current", max_hp if current is None else current)
    return cid


async def _undo(client, cid: int, op_id: str):
    return await client.post(f"/characters/{cid}/hp/undo", json={"op_id": op_id})


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


async def test_undo_damage_restores_temp_hp(client):
    cid = await _make_char(client, 20)
    await _hp(client, cid, "set_temp", 5)
    dmg = await _hp(client, cid, "damage", 8)
    assert dmg["current_hit_points"] == 17 and dmg["temp_hp"] == 0
    r = await _undo(client, cid, dmg["hp_undo_id"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["current_hit_points"] == 20
    assert body["temp_hp"] == 5
    assert body["hp_undo_id"] is None


async def test_undo_restores_lost_concentration(client, monkeypatch):
    cid = await _make_char(client, 20)
    spell_id = await _start_concentration(client, cid)
    _force_d20(monkeypatch, 1)
    dmg = await _hp(client, cid, "damage", 5)
    assert dmg["concentrating_spell_id"] is None
    r = await _undo(client, cid, dmg["hp_undo_id"])
    assert r.status_code == 200, r.text
    assert r.json()["concentrating_spell_id"] == spell_id


async def test_undo_massive_damage_revives(client):
    cid = await _make_char(client, 20)
    dmg = await _hp(client, cid, "damage", 40)
    assert dmg["is_dead"] is True
    r = await _undo(client, cid, dmg["hp_undo_id"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_dead"] is False
    assert body["current_hit_points"] == 20


async def test_undo_damage_at_zero_restores_death_saves(client):
    cid = await _make_char(client, 20, current=0)
    dmg = await _hp(client, cid, "damage", 1)
    assert dmg["death_saves"]["failures"] == 1
    r = await _undo(client, cid, dmg["hp_undo_id"])
    assert r.status_code == 200, r.text
    # lo stato precedente può essere il default vuoto {}
    assert r.json()["death_saves"].get("failures", 0) == 0


async def test_undo_set_max_and_set_temp(client):
    cid = await _make_char(client, 20)
    temp = await _hp(client, cid, "set_temp", 7)
    r = await _undo(client, cid, temp["hp_undo_id"])
    assert r.status_code == 200, r.text
    assert r.json()["temp_hp"] == 0

    mx = await _hp(client, cid, "set_max", 10)
    assert mx["hit_points"] == 10 and mx["current_hit_points"] == 10
    r = await _undo(client, cid, mx["hp_undo_id"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["hit_points"] == 20
    assert body["current_hit_points"] == 20


async def test_undo_current_above_base_max(client, test_session_factory):
    cid = await _make_char(client, 20)
    async with test_session_factory() as s:
        char = (await s.execute(select(Character).where(Character.id == cid))).scalar_one()
        char.current_hit_points = 30
        await s.commit()
    dmg = await _hp(client, cid, "damage", 5)
    assert dmg["current_hit_points"] == 25
    r = await _undo(client, cid, dmg["hp_undo_id"])
    assert r.status_code == 200, r.text
    assert r.json()["current_hit_points"] == 30


async def test_undo_twice_is_409(client):
    cid = await _make_char(client, 20)
    dmg = await _hp(client, cid, "damage", 5)
    assert (await _undo(client, cid, dmg["hp_undo_id"])).status_code == 200
    r = await _undo(client, cid, dmg["hp_undo_id"])
    assert r.status_code == 409
    g = (await client.get(f"/characters/{cid}")).json()
    assert g["current_hit_points"] == 20


async def test_undo_wrong_op_id_is_409(client):
    cid = await _make_char(client, 20)
    first = await _hp(client, cid, "damage", 1)
    await _hp(client, cid, "damage", 5)
    r = await _undo(client, cid, first["hp_undo_id"])
    assert r.status_code == 409
    g = (await client.get(f"/characters/{cid}")).json()
    assert g["current_hit_points"] == 14


async def test_undo_after_rest_is_409(client):
    cid = await _make_char(client, 20)
    dmg = await _hp(client, cid, "damage", 5)
    rr = await client.post(f"/characters/{cid}/rest", json={"rest_type": "long"})
    assert rr.status_code == 200, rr.text
    r = await _undo(client, cid, dmg["hp_undo_id"])
    assert r.status_code == 409
    g = (await client.get(f"/characters/{cid}")).json()
    assert g["current_hit_points"] == 20


async def test_undo_without_snapshot_is_409(client):
    r = await client.post("/characters", json={"name": "Fresh"})
    cid = r.json()["id"]
    assert (await _undo(client, cid, "nope")).status_code == 409


async def test_undo_foreign_character_is_403(client, test_session_factory):
    async with test_session_factory() as s:
        other = Character(user_id=TEST_USER_ID + 1, name="NotMine")
        s.add(other)
        await s.commit()
        other_id = other.id
    assert (await _undo(client, other_id, "x")).status_code == 403


async def test_dead_character_patch_returns_no_undo_id(client):
    cid = await _make_char(client, 20)
    await _hp(client, cid, "damage", 40)  # morte istantanea
    body = await _hp(client, cid, "damage", 1)
    assert body["is_dead"] is True
    assert body["hp_undo_id"] is None


async def test_undo_with_deleted_concentration_spell_clears_it(client, monkeypatch):
    cid = await _make_char(client, 20)
    spell_id = await _start_concentration(client, cid)
    _force_d20(monkeypatch, 1)
    dmg = await _hp(client, cid, "damage", 5)
    assert dmg["concentrating_spell_id"] is None
    rd = await client.delete(f"/characters/{cid}/spells/{spell_id}")
    assert rd.status_code == 204, rd.text
    r = await _undo(client, cid, dmg["hp_undo_id"])
    assert r.status_code == 200, r.text
    assert r.json()["concentrating_spell_id"] is None
