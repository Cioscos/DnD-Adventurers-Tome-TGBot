"""PATCH /characters/{id}/classes/{class_id} — raw single-class edit.

Unlike PATCH /xp and /classes/distribute, this endpoint edits class fields
(level / subclass / hit_die) WITHOUT recomputing max HP — it is the manual
"fix my sheet" path. A level INCREASE still re-syncs predefined class-feature
abilities (e.g. a Monk gaining Ki points at level 2) and feeds spell-slot recalc.

Contract: ``CharacterFull`` (api.classes.update → classes[]/proficiency_bonus/
abilities[]).
"""
from __future__ import annotations


async def _fighter(client) -> tuple[int, int]:
    r = await client.post(
        "/characters",
        json={"name": "Edit", "initial_class": {"class_name": "Guerriero", "level": 1, "hit_die": 10}},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    return body["id"], body["classes"][0]["id"]


async def _monk(client) -> tuple[int, int]:
    r = await client.post(
        "/characters",
        json={"name": "Monk", "initial_class": {"class_name": "Monaco", "level": 1, "hit_die": 8}},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    return body["id"], body["classes"][0]["id"]


async def test_level_edit_does_not_ripple_hp(client):
    cid, gid = await _fighter(client)
    r = await client.patch(f"/characters/{cid}/classes/{gid}", json={"level": 5})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["classes"][0]["level"] == 5
    assert body["hit_points"] == 10              # raw edit leaves HP untouched
    assert body["proficiency_bonus"] == 3        # total level 5 → +3


async def test_update_subclass(client):
    cid, gid = await _fighter(client)
    r = await client.patch(f"/characters/{cid}/classes/{gid}", json={"subclass": "Campione"})
    assert r.status_code == 200, r.text
    assert r.json()["classes"][0]["subclass"] == "Campione"


async def test_update_hit_die(client):
    cid, gid = await _fighter(client)
    r = await client.patch(f"/characters/{cid}/classes/{gid}", json={"hit_die": 12})
    assert r.status_code == 200, r.text
    assert r.json()["classes"][0]["hit_die"] == 12


async def test_unknown_class_id_is_404(client):
    cid, _gid = await _fighter(client)
    r = await client.patch(f"/characters/{cid}/classes/999999", json={"level": 2})
    assert r.status_code == 404, r.text


async def test_levelup_syncs_class_feature_abilities(client):
    cid, mid = await _monk(client)
    # Monk Ki points appear at level 2 (formula lv >= 2 → lv uses).
    r = await client.patch(f"/characters/{cid}/classes/{mid}", json={"level": 2})
    assert r.status_code == 200, r.text
    abilities = r.json()["abilities"]
    ki = next((a for a in abilities if a.get("feature_key") == "monk.ki"), None)
    assert ki is not None
    assert ki["max_uses"] == 2
