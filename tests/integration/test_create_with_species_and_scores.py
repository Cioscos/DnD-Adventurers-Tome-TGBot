"""POST /characters with species + ability_scores + skills (creation wizard)."""
from __future__ import annotations

HILL_DWARF = {
    "name": "Nano delle colline",
    "speed_ft": 25,
    "senses": [{"type": "darkvision", "range_ft": 60}],
    "languages": ["Comune", "Nanico"],
    "ability_bonuses": {"con": 2, "wis": 1},
    "roll_notes": {"save.constitution": "Vantaggio contro il veleno"},
    "traits": [{"name": "Scurovisione", "description": "Vedi al buio."}],
}


def _score(body: dict, name: str) -> int:
    return next(s for s in body["ability_scores"] if s["name"] == name)["value"]


async def test_create_applies_species(client):
    r = await client.post("/characters", json={
        "name": "Thorin",
        "ability_scores": {"strength": 15, "dexterity": 8, "constitution": 14,
                           "intelligence": 8, "wisdom": 10, "charisma": 12},
        "species": HILL_DWARF,
        "identity": {"languages": ["Elfico"]},
    })
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["race"] == "Nano delle colline"
    assert b["speed"] == 25
    assert b["settings"]["senses"] == [{"type": "darkvision", "range_ft": 60}]
    assert b["settings"]["roll_notes"] == {"save.constitution": "Vantaggio contro il veleno"}
    assert _score(b, "constitution") == 16 and _score(b, "wisdom") == 11
    assert _score(b, "strength") == 15
    assert set(b["languages"]) == {"Elfico", "Comune", "Nanico"}
    passive = [a for a in b["abilities"] if a["name"] == "Scurovisione"]
    assert passive and passive[0]["is_passive"] is True


async def test_create_scores_out_of_range_422(client):
    r = await client.post("/characters", json={
        "name": "X", "ability_scores": {"strength": 2}})
    assert r.status_code == 422
    r = await client.post("/characters", json={
        "name": "X", "ability_scores": {"strength": 19}, "species": {"name": "Umano", "ability_bonuses": {"str": 2}}})
    assert r.status_code == 422  # 21 after bonuses
    r = await client.post("/characters", json={
        "name": "X", "ability_scores": {"luck": 10}})
    assert r.status_code == 422


async def test_create_without_new_fields_unchanged(client):
    r = await client.post("/characters", json={"name": "Plain"})
    assert r.status_code == 201
    b = r.json()
    assert all(s["value"] == 10 for s in b["ability_scores"])
    assert b["speed"] == 30 and b["race"] in (None, "")
    assert "senses" not in (b["settings"] or {})
    assert b["abilities"] == []


async def test_create_skills_applied_and_validated(client):
    r = await client.post("/characters", json={"name": "S", "skills": {"insight": True, "religion": True}})
    assert r.status_code == 201
    assert r.json()["skills"]["insight"] is True
    r = await client.post("/characters", json={"name": "S", "skills": {"bogus": True}})
    assert r.status_code == 422


async def test_con_score_feeds_class_hp(client):
    r = await client.post("/characters", json={
        "name": "Tank", "ability_scores": {"constitution": 14},
        "initial_class": {"class_name": "Guerriero", "level": 1, "hit_die": 10}})
    assert r.status_code == 201
    assert r.json()["hit_points"] == 12  # 10 + CON mod 2
