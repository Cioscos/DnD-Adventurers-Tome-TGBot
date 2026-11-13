"""Usi e riposi dei talenti dal motore: il sync ricalcola il massimo dal livello totale e conserva gli usi spesi."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from core.db.models import Ability
from core.rules.catalog import feats as feat_module
from core.rules.catalog.feats import feat
from core.rules.types import Uses


@pytest.fixture
def counted_feat(monkeypatch):
    spec = feat("test_points", "2024", "Punti", "Points", "x", "x", uses=Uses(proficiency=True, minimum=0),
                restoration="long_rest")
    monkeypatch.setitem(feat_module.FEAT_FEATURES, spec.key, spec)
    return spec


async def _row(factory, cid):
    async with factory() as s:
        return (await s.execute(select(Ability).where(Ability.character_id == cid,
                                                     Ability.feature_key == "feat.test_points"))).scalar_one()


async def test_feat_uses_follow_total_level(client, test_session_factory, counted_feat):
    r = await client.post("/characters", json={"name": "Contatrice", "rules_edition": "2024",
                                               "initial_class": {"class_name": "fighter", "level": 4}})
    assert r.status_code == 201, r.text
    cid, class_id = r.json()["id"], r.json()["classes"][0]["id"]
    async with test_session_factory() as s:
        s.add(Ability(character_id=cid, name="Punti", is_passive=False, feature_key="feat.test_points"))
        await s.commit()

    r = await client.patch(f"/characters/{cid}/classes/{class_id}", json={"level": 3})  # il sync parte col cambio di livello
    assert r.status_code == 200, r.text
    row = await _row(test_session_factory, cid)
    assert (row.max_uses, row.uses, row.restoration_type.value) == (2, 2, "long_rest")

    async with test_session_factory() as s:
        (await s.get(Ability, row.id)).uses = 1
        await s.commit()
    r = await client.patch(f"/characters/{cid}/classes/{class_id}", json={"level": 5, "hp_rolls": [5, 5]})
    assert r.status_code == 200, r.text
    row = await _row(test_session_factory, cid)
    assert (row.max_uses, row.uses) == (3, 2)
