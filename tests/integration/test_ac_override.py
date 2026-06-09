"""PATCH /characters/{id}/ac and POST /characters/{id}/ac/reset-override.

PATCH pins a manual AC component and locks it: ``base`` → base_armor_class +
base_armor_class_override=True; ``shield`` → shield_armor_class +
shield_armor_class_override=True; ``magic`` → magic_armor (no override flag).
All components clamp to >= 0.

reset-override clears the base/shield override flags and recomputes both from the
currently equipped items (with no armor → base 10, with no shield → shield 0);
``magic`` is left untouched (it has no override flag and the reset never reads it).

Contract: the response is a ``CharacterFull`` whose ``ac_breakdown``
{base, shield, magic} and ``ac = base + shield + magic`` are read by
api.characters.updateAC / resetACOverride in client.ts.
"""
from __future__ import annotations


async def _create_character(client) -> int:
    """Bare character: no class, no armor → base AC 10, shield 0, magic 0."""
    r = await client.post("/characters", json={"name": "Armored"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_patch_base_sets_override_and_ac(client):
    cid = await _create_character(client)
    r = await client.patch(f"/characters/{cid}/ac", json={"base": 18})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ac_breakdown"]["base"] == 18
    assert body["base_armor_class_override"] is True
    assert body["ac"] == 18  # no shield / magic


async def test_patch_shield_and_magic(client):
    cid = await _create_character(client)
    r = await client.patch(f"/characters/{cid}/ac", json={"shield": 2, "magic": 1})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ac_breakdown"]["shield"] == 2
    assert body["ac_breakdown"]["magic"] == 1
    assert body["shield_armor_class_override"] is True
    assert body["ac"] == 13  # base 10 + shield 2 + magic 1


async def test_patch_clamps_negative_base(client):
    cid = await _create_character(client)
    r = await client.patch(f"/characters/{cid}/ac", json={"base": -5})
    assert r.status_code == 200, r.text
    assert r.json()["ac_breakdown"]["base"] == 0


async def test_reset_override_recomputes_base_shield_and_clears_flags(client):
    cid = await _create_character(client)
    # Pin base + shield manually (sets both override flags).
    r = await client.patch(f"/characters/{cid}/ac", json={"base": 99, "shield": 5})
    assert r.status_code == 200, r.text
    assert r.json()["base_armor_class_override"] is True
    assert r.json()["shield_armor_class_override"] is True

    r = await client.post(f"/characters/{cid}/ac/reset-override")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["base_armor_class_override"] is False
    assert body["shield_armor_class_override"] is False
    assert body["ac_breakdown"]["base"] == 10  # no armor equipped → 10
    assert body["ac_breakdown"]["shield"] == 0  # no shield equipped → 0
    assert body["ac"] == 10


async def test_reset_override_leaves_magic_untouched(client):
    cid = await _create_character(client)
    r = await client.patch(f"/characters/{cid}/ac", json={"base": 99, "magic": 3})
    assert r.status_code == 200, r.text
    assert r.json()["ac_breakdown"]["magic"] == 3

    r = await client.post(f"/characters/{cid}/ac/reset-override")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ac_breakdown"]["base"] == 10
    assert body["ac_breakdown"]["magic"] == 3  # reset only touches base/shield
    assert body["ac"] == 13  # 10 + 0 + 3
