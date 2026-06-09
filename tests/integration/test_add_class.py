"""POST /characters/{id}/classes — add a (multi)class.

Behaviours pinned here:
- The FIRST class on a 0-HP character bootstraps max HP via the level-1 formula
  (``hit_die + con_mod``) and seeds the starting class's two saving-throw
  proficiencies (D&D 5e PHB).
- Adding a SUBSEQUENT class does NOT change HP (max HP is only recomputed by
  /classes/distribute, /xp or a class-level edit) and does NOT grant extra
  saving-throw proficiencies (PHB multiclass rule).
- A predefined class name (CLASS_HIT_DIE / CLASS_SPELLCASTING) defaults its
  hit die and spellcasting ability when the body omits them.

Contract: ``CharacterFull`` (api.classes.add → classes[]/hit_points/saving_throws).
"""
from __future__ import annotations


async def _empty_character(client) -> int:
    """Character with no class → 0 HP, ability scores all 10."""
    r = await client.post("/characters", json={"name": "Empty"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["hit_points"] == 0 and body["classes"] == []
    return body["id"]


async def _fighter(client) -> int:
    r = await client.post(
        "/characters",
        json={"name": "Multi", "initial_class": {"class_name": "Guerriero", "level": 1, "hit_die": 10}},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_first_class_bootstraps_hp_and_saves(client):
    cid = await _empty_character(client)
    r = await client.post(f"/characters/{cid}/classes",
                          json={"class_name": "Guerriero", "level": 1, "hit_die": 10})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["hit_points"] == 10          # d10 + CON mod 0
    assert body["current_hit_points"] == 10
    cls = body["classes"][0]
    assert cls["class_name"] == "Guerriero" and cls["level"] == 1 and cls["hit_die"] == 10
    # Guerriero seeds STR + CON saving-throw proficiencies.
    assert body["saving_throws"]["strength"] is True
    assert body["saving_throws"]["constitution"] is True


async def test_second_class_keeps_hp_and_grants_no_saves(client):
    cid = await _fighter(client)            # 10 HP, STR/CON saves
    r = await client.post(f"/characters/{cid}/classes",
                          json={"class_name": "Ladro", "level": 1, "hit_die": 8})
    assert r.status_code == 201, r.text
    body = r.json()
    assert len(body["classes"]) == 2
    assert body["hit_points"] == 10          # second class does not bootstrap HP
    # Rogue saves (DEX/INT) are NOT granted by multiclassing.
    assert not body["saving_throws"].get("dexterity")
    assert not body["saving_throws"].get("intelligence")


async def test_predefined_class_defaults_hit_die_and_spellcasting(client):
    cid = await _empty_character(client)
    # Mago: hit_die omitted → defaults to 6, spellcasting → intelligence.
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "Mago"})
    assert r.status_code == 201, r.text
    body = r.json()
    cls = body["classes"][0]
    assert cls["hit_die"] == 6
    assert cls["spellcasting_ability"] == "intelligence"
    assert body["hit_points"] == 6           # first-class bootstrap d6 + 0


async def test_add_class_to_missing_character_is_404(client):
    r = await client.post("/characters/999999/classes",
                          json={"class_name": "Guerriero", "level": 1, "hit_die": 10})
    assert r.status_code == 404, r.text
