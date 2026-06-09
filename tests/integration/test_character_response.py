"""build_character_response — the canonical CharacterFull serializer.

Exercised end-to-end through GET /characters/{id} and POST /items (every router
returns through this builder). Asserts the contract the whole FE depends on:

- ``ac_breakdown`` is populated with {base, shield, magic, homebrew} and
  ``ac == base + shield + magic`` (homebrew is reported separately).
- the homebrew breakdown fields default cleanly with no rules installed
  (hp_max_homebrew_modifier 0, empty skills/saves modifier maps).
- ``has_custom_silhouette`` is False without an uploaded silhouette.
- ability scores are resolved to {base_value, value, modifier, modifiers_applied},
  and an equipped item's ability modifier flows through ``_resolve_ability_effective``
  into the effective value.
"""
from __future__ import annotations


async def _create_character(client) -> int:
    r = await client.post("/characters", json={"name": "Serialized"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_baseline_breakdown_and_defaults(client):
    cid = await _create_character(client)
    r = await client.get(f"/characters/{cid}")
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["ac_breakdown"] == {"base": 10, "shield": 0, "magic": 0, "homebrew": 0}
    assert body["ac"] == 10
    assert body["has_custom_silhouette"] is False
    assert body["hp_max_homebrew_modifier"] == 0
    assert body["speed_homebrew_modifier"] == 0
    assert body["skills_homebrew_modifiers"] == {}
    assert body["saves_homebrew_modifiers"] == {}


async def test_ability_scores_are_resolved(client):
    cid = await _create_character(client)
    body = (await client.get(f"/characters/{cid}")).json()

    assert len(body["ability_scores"]) == 6
    for score in body["ability_scores"]:
        assert set(score) >= {"name", "value", "base_value", "modifier", "modifiers_applied"}
        # Defaults: base 10 → effective 10 → modifier 0, no applied modifiers.
        assert score["base_value"] == 10
        assert score["value"] == 10
        assert score["modifier"] == 0
        assert score["modifiers_applied"] == []


async def test_equipped_item_ability_modifier_flows_into_effective_value(client):
    cid = await _create_character(client)
    r = await client.post(
        f"/characters/{cid}/items",
        json={
            "name": "Belt of Hill Giant Strength",
            "item_type": "accessory",
            "equipment_slot": "ring1",
            "is_equipped": True,
            "item_metadata": {
                "ability_modifiers": [
                    {"ability": "strength", "kind": "relative", "value": 2}
                ]
            },
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()

    strength = next(s for s in body["ability_scores"] if s["name"] == "strength")
    assert strength["base_value"] == 10
    assert strength["value"] == 12              # 10 + 2 relative
    assert strength["modifier"] == 1            # (12 - 10) // 2
    assert strength["modifiers_applied"], "expected the equipped modifier in the breakdown"
    applied = strength["modifiers_applied"][0]
    assert applied["ability"] == "strength"
    assert applied["kind"] == "relative"
    assert applied["value"] == 2


async def test_magic_armor_feeds_breakdown_and_total(client):
    cid = await _create_character(client)
    r = await client.patch(f"/characters/{cid}/ac", json={"magic": 3})
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["ac_breakdown"]["magic"] == 3
    assert body["ac"] == 13  # base 10 + shield 0 + magic 3
