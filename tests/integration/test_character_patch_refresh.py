"""Regression tests for the ``_resolve_abilities`` column-drop bug.

Background
----------
``CharacterFull._resolve_abilities`` (in ``api/schemas/character.py``) is a
``model_validator(mode="before")`` that builds a dict from ORM attributes. For
each attribute returned by ``dir(data)`` it does ``getattr(data, k)`` wrapped
in ``try/except Exception: continue``. On PATCH endpoints that mutate
``char.*`` and add side-effect rows (e.g. ``CharacterHistory``), SQLAlchemy
auto-expires some attributes by serialization time. The lazy-load triggered by
``getattr`` then fails in sync context (``greenlet_spawn`` unavailable), the
exception is swallowed, and required columns (``id``, ``name``,
``shield_armor_class``, ``magic_armor``, ``ac`` ...) silently drop out of the
dict — the final ``CharacterFull.model_validate`` returns **422 Field
required**.

These tests exercise PATCH ``/conditions`` and PATCH ``/skills`` against a
character created via the real ``POST /characters`` endpoint (so its
``ability_scores`` + ``currency`` rows exist). The fix is to ``await
session.flush()`` + ``session.refresh(char, attribute_names=[...])`` before
returning the ORM object — see ``api/routers/items.py`` and
``api/routers/classes.py`` for the canonical pattern.
"""
from __future__ import annotations

import pytest


async def _create_full_character(client) -> int:
    """POST /characters so the row has ability_scores + currency populated.

    The bare ``Character(...)`` fixture used by homebrew tests skips these
    side-rows; ``CharacterFull`` is happy either way (relations default to
    ``[]``), but using the real endpoint exercises the same code path the
    webapp does and gives us a realistic baseline state.
    """
    r = await client.post("/characters", json={"name": "Refresh Test"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.mark.asyncio
async def test_patch_conditions_returns_full_character_after_history_side_effect(client):
    """PATCH /conditions writes a CharacterHistory row → autoflush expires
    char column attrs → fix must refresh before serialization.

    Pre-fix: response is 422 because ``_resolve_abilities`` swallows the
    MissingGreenlet exception from the lazy-load, dropping ``id``, ``name``,
    ``shield_armor_class``, ``magic_armor``, ``ac`` from the dict.
    """
    char_id = await _create_full_character(client)

    r = await client.patch(
        f"/characters/{char_id}/conditions",
        json={"conditions": {"poisoned": True}},
    )
    assert r.status_code == 200, r.text

    body = r.json()
    # Required columns must round-trip through the validator
    assert body["id"] == char_id
    assert body["name"] == "Refresh Test"
    # AC component columns — the ones that silently dropped in the bug
    assert "shield_armor_class" in body
    assert "magic_armor" in body
    assert "ac" in body
    assert "base_armor_class" in body
    # The mutation was actually persisted
    assert body["conditions"]["poisoned"] is True


@pytest.mark.asyncio
async def test_patch_skills_returns_full_character(client):
    """PATCH /skills also mutates ``char.*`` and returns ``CharacterFull``.

    No history side-effect here, but autoflush on the dirty char during
    serialization can still expire columns once the validator is upstream of
    a flush. Same fix pattern, so we lock it in with a regression test.
    """
    char_id = await _create_full_character(client)

    r = await client.patch(
        f"/characters/{char_id}/skills",
        json={"skills": {"perception": True}},
    )
    assert r.status_code == 200, r.text

    body = r.json()
    assert body["id"] == char_id
    assert "shield_armor_class" in body
    assert "magic_armor" in body
    assert "ac" in body
    assert body["skills"]["perception"] is True


@pytest.mark.asyncio
async def test_patch_conditions_exhaustion_logged_to_history(client):
    """Exhaustion level changes also write to CharacterHistory — same code
    path that triggers the autoflush in the original bug.
    """
    char_id = await _create_full_character(client)

    r = await client.patch(
        f"/characters/{char_id}/conditions",
        json={"conditions": {"exhaustion": 2}},
    )
    assert r.status_code == 200, r.text

    body = r.json()
    assert body["id"] == char_id
    assert body["conditions"]["exhaustion"] == 2
    # All ability score relations should still be present (length == 6 from
    # POST /characters seed)
    assert len(body["ability_scores"]) == 6
