"""POST /characters/{id}/spells/{spell_id}/use — spend a slot, maybe start concentration.

D&D 5e rules encoded:
- Casting from a slot decrements that level's availability (``used += 1``).
- A concentration spell sets ``concentrating_spell_id``; a non-concentration one
  leaves it ``None``.
- No slot configured at the requested level → 400.
- All slots at that level already spent → 400.
- Unknown spell id → 404.

Contract: the response is a ``CharacterFull`` whose ``spell_slots`` match the FE
``SpellSlot`` shape (``available = total - used``) and whose
``concentrating_spell_id`` mirrors the cast (api.spells.use in client.ts).
"""
from __future__ import annotations


async def _create_character(client) -> int:
    r = await client.post("/characters", json={"name": "Caster"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _add_slot(client, cid: int, level: int, total: int, used: int = 0):
    r = await client.post(
        f"/characters/{cid}/spell_slots",
        json={"level": level, "total": total, "used": used},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _add_spell(client, cid: int, *, name="Test Spell", level=1, is_concentration=False) -> int:
    r = await client.post(
        f"/characters/{cid}/spells",
        json={"name": name, "level": level, "is_concentration": is_concentration},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _slot_at(body: dict, level: int) -> dict:
    return next(s for s in body["spell_slots"] if s["level"] == level)


async def test_use_spell_consumes_a_slot(client):
    cid = await _create_character(client)
    await _add_slot(client, cid, level=1, total=2)
    spell_id = await _add_spell(client, cid, level=1)

    r = await client.post(f"/characters/{cid}/spells/{spell_id}/use", json={"slot_level": 1})
    assert r.status_code == 200, r.text
    slot = _slot_at(r.json(), 1)
    assert slot["used"] == 1
    assert slot["available"] == 1


async def test_concentration_spell_sets_tracking(client):
    cid = await _create_character(client)
    await _add_slot(client, cid, level=1, total=1)
    spell_id = await _add_spell(client, cid, level=1, is_concentration=True)

    r = await client.post(f"/characters/{cid}/spells/{spell_id}/use", json={"slot_level": 1})
    assert r.status_code == 200, r.text
    assert r.json()["concentrating_spell_id"] == spell_id


async def test_non_concentration_spell_leaves_tracking_none(client):
    cid = await _create_character(client)
    await _add_slot(client, cid, level=1, total=1)
    spell_id = await _add_spell(client, cid, level=1, is_concentration=False)

    r = await client.post(f"/characters/{cid}/spells/{spell_id}/use", json={"slot_level": 1})
    assert r.status_code == 200, r.text
    assert r.json()["concentrating_spell_id"] is None


async def test_no_slot_configured_is_400(client):
    cid = await _create_character(client)
    spell_id = await _add_spell(client, cid, level=3)
    # No slots configured at all → level 3 has no slot.
    r = await client.post(f"/characters/{cid}/spells/{spell_id}/use", json={"slot_level": 3})
    assert r.status_code == 400, r.text


async def test_no_slots_available_is_400(client):
    cid = await _create_character(client)
    await _add_slot(client, cid, level=1, total=1)
    spell_id = await _add_spell(client, cid, level=1)

    r1 = await client.post(f"/characters/{cid}/spells/{spell_id}/use", json={"slot_level": 1})
    assert r1.status_code == 200, r1.text  # spends the only slot
    r2 = await client.post(f"/characters/{cid}/spells/{spell_id}/use", json={"slot_level": 1})
    assert r2.status_code == 400, r2.text


async def test_unknown_spell_is_404(client):
    cid = await _create_character(client)
    await _add_slot(client, cid, level=1, total=1)
    r = await client.post(f"/characters/{cid}/spells/999999/use", json={"slot_level": 1})
    assert r.status_code == 404, r.text
