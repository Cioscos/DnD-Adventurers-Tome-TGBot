"""Scelta dei talenti 2024: Stili di Combattimento come talento e prerequisiti di addestramento (PR 2 talenti, Task 1)."""
from __future__ import annotations

from tests.integration.rules.test_feats_take_complete import SCORES, _feat_rows, _take
from tests.integration.test_rules_choices import _resolve


async def _char(client, class_name: str, level: int = 4, **scores) -> dict:
    r = await client.post("/characters", json={
        "name": "Stile", "rules_edition": "2024", "ability_scores": {**SCORES, "strength": 14, **scores},
        "initial_class": {"class_name": class_name, "level": level}})
    assert r.status_code == 201, r.text
    return r.json()


async def test_fighting_style_feat_needs_the_feature(client):
    wizard = await _char(client, "wizard")
    r = await _take(client, wizard["id"], "2024_fs_defense")
    assert r.status_code == 422 and "feat_prerequisite_style" in r.text
    fighter = await _char(client, "fighter")
    assert (await _take(client, fighter["id"], "2024_fs_defense")).status_code == 201


async def test_fighting_style_feat_not_twice(client):
    fighter = await _char(client, "fighter")
    r = await _resolve(client, fighter, "class_option", {"options": ["archery"]})
    assert r.status_code == 200, r.text
    r = await _take(client, fighter["id"], "2024_fs_archery")
    assert r.status_code == 422 and "feat_style_taken" in r.text


async def test_heavily_armored_needs_medium_training(client):
    wizard = await _char(client, "wizard")
    r = await _take(client, wizard["id"], "2024_heavily_armored", "strength")
    assert r.status_code == 422 and "feat_prerequisite_armor" in r.text
    cleric = await _char(client, "cleric")
    assert (await _take(client, cleric["id"], "2024_heavily_armored", "strength")).status_code == 201


async def test_elemental_adept_repeatable(client):
    wizard = await _char(client, "wizard", intelligence=14)
    assert (await _take(client, wizard["id"], "2024_elemental_adept", "intelligence")).status_code == 201
    r = await _take(client, wizard["id"], "2024_elemental_adept", "intelligence")
    assert r.status_code == 201, r.text
    assert len(_feat_rows(r.json(), "2024_elemental_adept")) == 2


async def test_style_feats_in_level_choice(client):
    fighter = await _char(client, "fighter")
    r = await _resolve(client, fighter, "asi", {"kind": "feat", "feat_key": "2024_fs_defense"})
    assert r.status_code == 200, r.text
    assert _feat_rows(r.json(), "2024_fs_defense")
