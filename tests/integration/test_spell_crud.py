"""POST /characters/{id}/spells and PATCH /characters/{id}/spells/{spell_id}.

Create stores a Spell from ``SpellCreate`` (only ``name`` required; ``level``
defaults to 0 = cantrip) and returns ``SpellRead``. PATCH applies an
``exclude_unset`` partial update (omitted fields untouched) and 404s on an
unknown spell.

Contract: ``SpellRead`` (id / name / level / is_concentration / is_pinned /
damage_dice …) is consumed by api.spells.* in client.ts.
"""
from __future__ import annotations


async def _create_character(client) -> int:
    r = await client.post("/characters", json={"name": "Caster"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_create_spell_returns_201_and_full_shape(client):
    cid = await _create_character(client)
    r = await client.post(
        f"/characters/{cid}/spells",
        json={
            "name": "Palla di Fuoco",
            "level": 3,
            "is_concentration": False,
            "damage_dice": "8d6",
            "damage_type": "fuoco",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert isinstance(body["id"], int)
    assert body["name"] == "Palla di Fuoco"
    assert body["level"] == 3
    assert body["is_concentration"] is False
    assert body["damage_dice"] == "8d6"
    assert body["damage_type"] == "fuoco"
    # defaults
    assert body["is_ritual"] is False
    assert body["is_pinned"] is False


async def test_create_minimal_defaults_to_cantrip(client):
    cid = await _create_character(client)
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Luce"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["level"] == 0
    assert body["is_concentration"] is False


async def test_created_spell_is_listed(client):
    cid = await _create_character(client)
    rc = await client.post(f"/characters/{cid}/spells", json={"name": "Invisibilità", "level": 2})
    assert rc.status_code == 201, rc.text
    spell_id = rc.json()["id"]

    rl = await client.get(f"/characters/{cid}/spells")
    assert rl.status_code == 200, rl.text
    assert any(s["id"] == spell_id and s["name"] == "Invisibilità" for s in rl.json())


async def test_patch_updates_only_given_fields(client):
    cid = await _create_character(client)
    rc = await client.post(
        f"/characters/{cid}/spells",
        json={"name": "Velocità", "level": 3, "is_ritual": True},
    )
    spell_id = rc.json()["id"]

    r = await client.patch(
        f"/characters/{cid}/spells/{spell_id}",
        json={"is_concentration": True, "level": 4},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_concentration"] is True
    assert body["level"] == 4
    # untouched fields survive the partial update
    assert body["name"] == "Velocità"
    assert body["is_ritual"] is True


async def test_patch_unknown_spell_is_404(client):
    cid = await _create_character(client)
    r = await client.patch(f"/characters/{cid}/spells/999999", json={"level": 1})
    assert r.status_code == 404, r.text


async def test_delete_spell_returns_204_and_unlists_it(client):
    cid = await _create_character(client)
    rc = await client.post(f"/characters/{cid}/spells", json={"name": "Dardo Incantato", "level": 1})
    spell_id = rc.json()["id"]

    r = await client.delete(f"/characters/{cid}/spells/{spell_id}")
    assert r.status_code == 204, r.text

    rl = await client.get(f"/characters/{cid}/spells")
    assert all(s["id"] != spell_id for s in rl.json())


async def test_delete_unknown_spell_is_404(client):
    cid = await _create_character(client)
    r = await client.delete(f"/characters/{cid}/spells/999999")
    assert r.status_code == 404, r.text
