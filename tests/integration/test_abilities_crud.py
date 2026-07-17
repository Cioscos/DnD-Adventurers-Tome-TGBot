"""CRUD for free-form abilities — api/routers/abilities.py.

Covers the create/update/delete lifecycle the webapp drives via ``api.abilities.*``
for **non** class-feature abilities (the class-feature *lock* — name/max_uses/
restoration_type frozen, delete blocked — is the subject of
``test_ability_protection.py``; this file exercises the unlocked paths):

- ``POST /abilities`` stores an ``AbilityCreate`` (only ``name`` required) → 201.
- ``PATCH /abilities/{id}`` is an ``exclude_unset`` partial. Decrementing ``uses``
  ("using" the ability) fires the ``ability_used`` homebrew event; with no rules
  installed the response carries no ``homebrew_notifications``. Restoring ``uses``
  (increment) must *not* be treated as a use.
- A non class-feature ability may freely edit name / max_uses (no 409).
- ``DELETE /abilities/{id}`` → 204; a missing id → 404 on patch/delete.

Contract: ``AbilityRead`` (id / name / uses / max_uses / is_class_feature /
restoration_type / homebrew_notifications) is consumed by api.abilities.* in
client.ts.
"""
from __future__ import annotations


async def _create_character(client) -> int:
    r = await client.post("/characters", json={"name": "Tracker"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _add_ability(client, cid: int, **fields) -> dict:
    body = {"name": "Talento"}
    body.update(fields)
    r = await client.post(f"/characters/{cid}/abilities", json=body)
    assert r.status_code == 201, r.text
    return r.json()


async def test_create_ability_returns_201_and_full_shape(client):
    cid = await _create_character(client)
    body = await _add_ability(
        client, cid,
        name="Furia",
        description="Vantaggio agli attacchi in mischia",
        max_uses=3,
        uses=3,
        is_active=True,
        restoration_type="long_rest",
    )
    assert isinstance(body["id"], int)
    assert body["name"] == "Furia"
    assert body["max_uses"] == 3
    assert body["uses"] == 3
    assert body["is_active"] is True
    assert body["restoration_type"] == "long_rest"
    # A user-created ability is never a protected class feature.
    assert body["is_class_feature"] is False
    assert not body.get("homebrew_notifications")


async def test_create_minimal_defaults(client):
    cid = await _create_character(client)
    body = await _add_ability(client, cid, name="Occhio di falco")
    assert body["is_passive"] is False
    assert body["is_active"] is False
    assert body["restoration_type"] == "none"
    assert body["max_uses"] is None
    assert body["uses"] is None


async def test_created_ability_is_listed(client):
    cid = await _create_character(client)
    ab = await _add_ability(client, cid, name="Ispirazione bardica", max_uses=2, uses=2)
    r = await client.get(f"/characters/{cid}/abilities")
    assert r.status_code == 200, r.text
    assert any(a["id"] == ab["id"] and a["name"] == "Ispirazione bardica" for a in r.json())


async def test_patch_uses_decrement_is_a_use(client):
    cid = await _create_character(client)
    ab = await _add_ability(client, cid, name="Punti Ki", max_uses=5, uses=5)

    r = await client.patch(f"/characters/{cid}/abilities/{ab['id']}", json={"uses": 4})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["uses"] == 4
    # No homebrew rules installed → the ability_used event surfaces nothing.
    assert not body.get("homebrew_notifications")


async def test_patch_uses_increment_restores_without_firing(client):
    cid = await _create_character(client)
    ab = await _add_ability(client, cid, name="Secondo Respiro", max_uses=1, uses=0)

    r = await client.patch(f"/characters/{cid}/abilities/{ab['id']}", json={"uses": 1})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["uses"] == 1
    assert not body.get("homebrew_notifications")


async def test_patch_non_class_feature_name_and_max_uses_allowed(client):
    """The structure lock only applies to class features — a free-form ability
    may rename and re-scale freely (contrast with test_ability_protection)."""
    cid = await _create_character(client)
    ab = await _add_ability(client, cid, name="Vecchio nome", max_uses=2, uses=2)

    r = await client.patch(
        f"/characters/{cid}/abilities/{ab['id']}",
        json={"name": "Nuovo nome", "max_uses": 9},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "Nuovo nome"
    assert body["max_uses"] == 9


async def test_patch_unknown_ability_is_404(client):
    cid = await _create_character(client)
    r = await client.patch(f"/characters/{cid}/abilities/999999", json={"uses": 1})
    assert r.status_code == 404, r.text


async def test_delete_non_class_feature_returns_204(client):
    cid = await _create_character(client)
    ab = await _add_ability(client, cid, name="Da rimuovere")

    r = await client.delete(f"/characters/{cid}/abilities/{ab['id']}")
    assert r.status_code == 204, r.text

    rl = await client.get(f"/characters/{cid}/abilities")
    assert all(a["id"] != ab["id"] for a in rl.json())


async def test_delete_unknown_ability_is_404(client):
    cid = await _create_character(client)
    r = await client.delete(f"/characters/{cid}/abilities/999999")
    assert r.status_code == 404, r.text


async def test_patch_uses_is_clamped_to_max(client):
    r = await client.post("/characters", json={"name": "Clamp Uses"})
    cid = r.json()["id"]
    r = await client.post(
        f"/characters/{cid}/abilities",
        json={"name": "Sanità", "max_uses": 200, "uses": 200, "is_active": True,
              "restoration_type": "manual"},
    )
    aid = r.json()["id"]

    r = await client.patch(f"/characters/{cid}/abilities/{aid}", json={"uses": 999})
    assert r.status_code == 200
    assert r.json()["uses"] == 200

    r = await client.patch(f"/characters/{cid}/abilities/{aid}", json={"uses": -3})
    assert r.status_code == 200
    assert r.json()["uses"] == 0


async def test_lowering_max_uses_clamps_uses_without_firing_use(client):
    r = await client.post("/characters", json={"name": "Clamp MaxUses"})
    cid = r.json()["id"]
    r = await client.post(
        f"/characters/{cid}/abilities",
        json={"name": "Sanità", "max_uses": 200, "uses": 200, "is_active": True,
              "restoration_type": "manual"},
    )
    aid = r.json()["id"]

    # Abbassare solo max_uses clampa uses al nuovo tetto…
    r = await client.patch(f"/characters/{cid}/abilities/{aid}", json={"max_uses": 5})
    assert r.status_code == 200
    assert r.json()["max_uses"] == 5
    assert r.json()["uses"] == 5
    # …senza segnalare un falso "uso" (nessuna notifica homebrew nel payload).
    assert r.json().get("homebrew_notifications") in (None, [])
