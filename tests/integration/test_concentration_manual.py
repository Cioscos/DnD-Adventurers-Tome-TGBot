"""PATCH /characters/{id}/concentration — manually set or drop concentration.

Distinct from the automatic tracking in POST /spells/{id}/use: this endpoint
lets the UI pin ``concentrating_spell_id`` directly (e.g. when toggling a
concentration spell on) or clear it (``spell_id: null`` / omitted).

Contract: the response is a ``CharacterFull`` whose ``concentrating_spell_id``
mirrors the body (api.spells.setConcentration in client.ts; ``ConcentrationUpdate``
has a single optional ``spell_id``).
"""
from __future__ import annotations


async def _create_character(client) -> int:
    r = await client.post("/characters", json={"name": "Concentrator"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _add_spell(client, cid: int) -> int:
    r = await client.post(
        f"/characters/{cid}/spells",
        json={"name": "Benedizione", "level": 1, "is_concentration": True},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_set_concentration_manually(client):
    cid = await _create_character(client)
    spell_id = await _add_spell(client, cid)

    r = await client.patch(f"/characters/{cid}/concentration", json={"spell_id": spell_id})
    assert r.status_code == 200, r.text
    assert r.json()["concentrating_spell_id"] == spell_id


async def test_clear_concentration_with_null(client):
    cid = await _create_character(client)
    spell_id = await _add_spell(client, cid)
    await client.patch(f"/characters/{cid}/concentration", json={"spell_id": spell_id})

    r = await client.patch(f"/characters/{cid}/concentration", json={"spell_id": None})
    assert r.status_code == 200, r.text
    assert r.json()["concentrating_spell_id"] is None


async def test_empty_body_clears_concentration(client):
    cid = await _create_character(client)
    spell_id = await _add_spell(client, cid)
    await client.patch(f"/characters/{cid}/concentration", json={"spell_id": spell_id})

    # spell_id is optional → omitting it defaults to None, dropping concentration.
    r = await client.patch(f"/characters/{cid}/concentration", json={})
    assert r.status_code == 200, r.text
    assert r.json()["concentrating_spell_id"] is None
