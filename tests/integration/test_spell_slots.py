"""Spell slot endpoints — api/routers/spell_slots.py.

Covers the manual slot lifecycle the webapp drives via ``api.spellSlots.*``:

- ``POST /spell_slots`` seeds a slot and reports ``available = total - used``.
- ``PATCH /spell_slots/{id}`` casts (``used`` up) or refunds (``used`` down). The
  ``spell_cast`` homebrew event only fires on an increment; with no rules
  installed the response carries no ``homebrew_notifications``.
- ``POST /spell_slots/reset`` zeroes every slot's ``used`` (long-rest parity) and
  returns the full character.
- A missing slot id is a 404.

Contract: the create/patch responses match the FE ``SpellSlot`` type
(``{id, level, total, used, available, is_pact}``) read in webapp/src/types.
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


async def test_add_slot_reports_available(client):
    cid = await _create_character(client)
    slot = await _add_slot(client, cid, level=1, total=3)
    assert slot["level"] == 1
    assert slot["total"] == 3
    assert slot["used"] == 0
    assert slot["available"] == 3
    assert slot["is_pact"] is False


async def test_patch_used_increment_casts_a_slot(client):
    cid = await _create_character(client)
    slot = await _add_slot(client, cid, level=1, total=3)

    r = await client.patch(
        f"/characters/{cid}/spell_slots/{slot['id']}", json={"used": 2}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["used"] == 2
    assert body["available"] == 1
    # No homebrew rules installed → no notifications surfaced on the cast.
    assert not body.get("homebrew_notifications")


async def test_patch_used_refund_decrements(client):
    cid = await _create_character(client)
    slot = await _add_slot(client, cid, level=1, total=3, used=2)

    r = await client.patch(
        f"/characters/{cid}/spell_slots/{slot['id']}", json={"used": 1}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["used"] == 1
    assert body["available"] == 2


async def test_patch_total_only_leaves_used_untouched(client):
    cid = await _create_character(client)
    slot = await _add_slot(client, cid, level=2, total=2, used=1)

    r = await client.patch(
        f"/characters/{cid}/spell_slots/{slot['id']}", json={"total": 4}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 4
    assert body["used"] == 1
    assert body["available"] == 3


async def test_patch_missing_slot_is_404(client):
    cid = await _create_character(client)
    r = await client.patch(
        f"/characters/{cid}/spell_slots/999999", json={"used": 1}
    )
    assert r.status_code == 404, r.text


async def test_reset_zeroes_every_slot(client):
    cid = await _create_character(client)
    await _add_slot(client, cid, level=1, total=3, used=2)
    await _add_slot(client, cid, level=2, total=2, used=1)

    r = await client.post(f"/characters/{cid}/spell_slots/reset")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["spell_slots"]) == 2
    assert all(s["used"] == 0 for s in body["spell_slots"])
    assert all(s["available"] == s["total"] for s in body["spell_slots"])


async def test_delete_slot_returns_204(client):
    cid = await _create_character(client)
    slot = await _add_slot(client, cid, level=1, total=1)
    r = await client.delete(f"/characters/{cid}/spell_slots/{slot['id']}")
    assert r.status_code == 204, r.text
