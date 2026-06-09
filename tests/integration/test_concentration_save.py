"""POST /characters/{id}/concentration/save — CON save vs DC = max(10, damage // 2).

Exercises ``api/routers/_helpers.py::roll_concentration_save`` through the
endpoint. D&D 5e rules encoded (the shared d20 is pinned via monkeypatch):
- DC is ``max(10, damage // 2)``.
- A natural 20 always succeeds and a natural 1 always fails, regardless of DC.
- A normal roll succeeds iff ``die + CON mod >= DC``.
- On failure while concentrating, ``concentrating_spell_id`` is cleared and
  ``lost_concentration`` is True.

A freshly created character has CON 10 → modifier 0, so ``total == die``.

Contract: response matches the FE ``ConcentrationSaveResult`` type
(die / bonus / total / is_critical / is_fumble / dc / success / lost_concentration)
consumed by api.spells.concentrationSave in client.ts.
"""
from __future__ import annotations

import random


def _force_d20(monkeypatch, value: int) -> None:
    """Pin random.randint to a fixed value (the only RNG call is the d20)."""
    monkeypatch.setattr(random, "randint", lambda a, b: value)


async def _create_character(client) -> int:
    r = await client.post("/characters", json={"name": "Concentrator"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _start_concentration(client, cid: int) -> int:
    """Cast a concentration spell from a slot so concentrating_spell_id is set."""
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
    assert ru.json()["concentrating_spell_id"] == spell_id
    return spell_id


async def test_nat20_always_succeeds(client, monkeypatch):
    cid = await _create_character(client)
    _force_d20(monkeypatch, 20)
    # Huge damage → DC 50, but a nat 20 passes anyway.
    r = await client.post(f"/characters/{cid}/concentration/save", json={"damage": 100})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["die"] == 20
    assert body["is_critical"] is True
    assert body["dc"] == 50
    assert body["success"] is True


async def test_nat1_always_fails(client, monkeypatch):
    cid = await _create_character(client)
    _force_d20(monkeypatch, 1)
    # Trivial damage → DC 10, but a nat 1 fails anyway.
    r = await client.post(f"/characters/{cid}/concentration/save", json={"damage": 2})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["die"] == 1
    assert body["is_fumble"] is True
    assert body["dc"] == 10
    assert body["success"] is False


async def test_dc_floor_is_10(client, monkeypatch):
    cid = await _create_character(client)
    _force_d20(monkeypatch, 10)
    r = await client.post(f"/characters/{cid}/concentration/save", json={"damage": 4})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["dc"] == 10        # max(10, 4//2 = 2) → 10
    assert body["bonus"] == 0      # default CON 10
    assert body["total"] == 10
    assert body["success"] is True  # 10 >= 10


async def test_dc_scales_with_damage(client, monkeypatch):
    cid = await _create_character(client)
    _force_d20(monkeypatch, 15)
    r = await client.post(f"/characters/{cid}/concentration/save", json={"damage": 40})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["dc"] == 20         # 40 // 2
    assert body["total"] == 15
    assert body["success"] is False  # 15 < 20


async def test_failed_save_drops_concentration(client, monkeypatch):
    cid = await _create_character(client)
    await _start_concentration(client, cid)

    _force_d20(monkeypatch, 5)  # low roll vs DC 20 → fail
    r = await client.post(f"/characters/{cid}/concentration/save", json={"damage": 40})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is False
    assert body["lost_concentration"] is True

    # The tracking column was cleared as a side effect.
    g = await client.get(f"/characters/{cid}")
    assert g.status_code == 200, g.text
    assert g.json()["concentrating_spell_id"] is None


async def test_successful_save_keeps_concentration(client, monkeypatch):
    cid = await _create_character(client)
    spell_id = await _start_concentration(client, cid)

    _force_d20(monkeypatch, 20)  # nat 20 → success even vs DC 20
    r = await client.post(f"/characters/{cid}/concentration/save", json={"damage": 40})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    assert body["lost_concentration"] is False

    g = await client.get(f"/characters/{cid}")
    assert g.json()["concentrating_spell_id"] == spell_id
