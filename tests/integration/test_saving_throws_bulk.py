"""PATCH /characters/{id}/saving_throws (SavingThrowsUpdate, bulk).

The webapp's SavingThrows page toggles a single proficiency at a time but sends
the *whole* map (``api.characters.updateSavingThrows(id, Record<str,bool>)`` →
``{saving_throws}``). The endpoint MERGES the payload into the existing map
(``current.update(body.saving_throws)``) — it never replaces it — so unsent
keys survive. A starting Guerriero is seeded proficient in STR & CON saves
(PHB), which gives us pre-existing keys to assert the merge against.

Contract: response is ``CharacterFull`` (``saving_throws`` dict the FE reads).
"""
from __future__ import annotations


async def _fighter(client) -> int:
    r = await client.post(
        "/characters",
        json={"name": "Bulk", "initial_class": {"class_name": "Guerriero", "level": 1, "hit_die": 10}},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["saving_throws"]["strength"] is True
    assert body["saving_throws"]["constitution"] is True
    return body["id"]


async def _patch(client, cid: int, saving_throws: dict):
    return await client.patch(f"/characters/{cid}/saving_throws", json={"saving_throws": saving_throws})


async def test_bulk_merges_new_key_keeping_existing(client):
    cid = await _fighter(client)
    r = await _patch(client, cid, {"dexterity": True})
    assert r.status_code == 200, r.text
    saves = r.json()["saving_throws"]
    assert saves["dexterity"] is True          # newly added
    assert saves["strength"] is True           # class-seeded, untouched by merge
    assert saves["constitution"] is True


async def test_bulk_can_flip_a_proficiency_off(client):
    cid = await _fighter(client)
    r = await _patch(client, cid, {"strength": False})
    assert r.status_code == 200, r.text
    saves = r.json()["saving_throws"]
    assert saves["strength"] is False
    assert saves["constitution"] is True       # not in the payload → preserved


async def test_partial_update_leaves_unsent_keys_untouched(client):
    cid = await _fighter(client)
    r = await _patch(client, cid, {"charisma": True})
    assert r.status_code == 200, r.text
    saves = r.json()["saving_throws"]
    assert saves["charisma"] is True
    assert saves["strength"] is True and saves["constitution"] is True


async def test_response_shape_is_character_full(client):
    cid = await _fighter(client)
    body = (await _patch(client, cid, {"wisdom": True})).json()
    assert body["id"] == cid
    assert isinstance(body["saving_throws"], dict)


async def test_patch_unknown_character_is_404(client):
    r = await _patch(client, 999_999, {"wisdom": True})
    assert r.status_code == 404, r.text
