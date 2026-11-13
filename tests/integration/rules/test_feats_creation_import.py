"""Talento d'Origine alla creazione, stato dei talenti nella risposta e talenti da D&D Beyond (PR 1 talenti, Task 7)."""
from __future__ import annotations

from api.services.ddb_import import convert

BASE = {"name": "Nuova", "rules_edition": "2024", "initial_class": {"class_name": "fighter", "level": 1}}


def _feat(body, key):
    return next((a for a in body["abilities"] if a["feature_key"] == f"feat.{key}"), None)


async def test_create_2024_with_origin_feat(client):
    plain = (await client.post("/characters", json=BASE)).json()
    r = await client.post("/characters", json={**BASE, "origin_feat": "2024_tough"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert _feat(body, "2024_tough")["feat_status"] == "active"
    assert body["computed"]["hp_max_effective"] == plain["computed"]["hp_max_effective"] + 2
    assert body["current_hit_points"] == body["computed"]["hp_max_effective"]  # nasce a PF pieni


async def test_create_with_general_feat_rejected(client):
    r = await client.post("/characters", json={**BASE, "origin_feat": "2024_actor"})
    assert r.status_code == 422


async def test_create_2014_with_origin_feat_rejected(client):
    r = await client.post("/characters", json={**BASE, "rules_edition": "2014", "origin_feat": "2024_alert"})
    assert r.status_code == 422


async def test_feat_status_in_response(client):
    body = (await client.post("/characters", json={**BASE, "origin_feat": "2024_skilled"})).json()
    assert _feat(body, "2024_skilled")["feat_status"] == "incomplete"
    r = await client.patch(f"/characters/{body['id']}", json={"rules_edition": "2014"})
    assert r.status_code == 200, r.text
    body = (await client.get(f"/characters/{body['id']}")).json()
    assert _feat(body, "2024_skilled")["feat_status"] == "other_edition"


def _ddb(feats: list[str], edition_2024=True) -> dict:
    return {"name": "Beyond", "stats": [{"id": i, "value": 10} for i in range(1, 7)], "classes": [
        {"level": 1, "definition": {"name": "Fighter", "hitDice": 10}, "isStartingClass": True}],
        "feats": [{"definition": {"name": n, "description": "x"}} for n in feats],
        "preferences": {"useOriginFeats": edition_2024}, "race": {"fullName": "Human", "racialTraits": []}}


def test_ddb_feat_mapped():
    export, _report, _uses = convert(_ddb(["Alert", "Some Homebrew Feat"]), "it", "2024")
    keys = {a.name: a.feature_key for a in export.abilities}
    assert keys["Allerta"] == "feat.2024_alert"
    assert keys["Some Homebrew Feat"] is None
    export14, _r, _u = convert(_ddb(["Alert"]), "en", "2014")
    assert {a.name: a.feature_key for a in export14.abilities}["Alert"] == "feat.alert"
