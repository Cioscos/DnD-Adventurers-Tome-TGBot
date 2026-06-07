"""Le feature di classe (is_class_feature) hanno struttura protetta (409)."""
from __future__ import annotations

import pytest_asyncio

from core.db.models import Character, CharacterClass, Ability
from tests.integration.conftest import TEST_USER_ID


@pytest_asyncio.fixture
async def feature_ids(test_session_factory):
    """Crea un personaggio con un'Ability feature di classe; ritorna (char_id, ability_id)."""
    async with test_session_factory() as s:
        char = Character(user_id=TEST_USER_ID, name="Prot")
        s.add(char)
        await s.flush()
        cls = CharacterClass(character_id=char.id, class_name="Monaco", level=2)
        s.add(cls)
        await s.flush()
        ab = Ability(
            character_id=char.id, name="Punti Ki", max_uses=2, uses=2,
            is_active=True, is_class_feature=True, feature_key="monk.ki",
            source_class_id=cls.id, restoration_type="short_rest",
        )
        s.add(ab)
        await s.flush()
        ids = (char.id, ab.id)
        await s.commit()
    return ids


async def test_patch_uses_allowed(client, feature_ids):
    char_id, ab_id = feature_ids
    r = await client.patch(f"/characters/{char_id}/abilities/{ab_id}", json={"uses": 1})
    assert r.status_code == 200
    assert r.json()["uses"] == 1


async def test_patch_description_allowed(client, feature_ids):
    char_id, ab_id = feature_ids
    r = await client.patch(
        f"/characters/{char_id}/abilities/{ab_id}", json={"description": "Nota mia"}
    )
    assert r.status_code == 200
    assert r.json()["description"] == "Nota mia"


async def test_patch_name_blocked(client, feature_ids):
    char_id, ab_id = feature_ids
    r = await client.patch(f"/characters/{char_id}/abilities/{ab_id}", json={"name": "Hack"})
    assert r.status_code == 409


async def test_patch_max_uses_blocked(client, feature_ids):
    char_id, ab_id = feature_ids
    r = await client.patch(f"/characters/{char_id}/abilities/{ab_id}", json={"max_uses": 99})
    assert r.status_code == 409


async def test_delete_blocked(client, feature_ids):
    char_id, ab_id = feature_ids
    r = await client.delete(f"/characters/{char_id}/abilities/{ab_id}")
    assert r.status_code == 409
