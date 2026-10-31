"""New passive targets: initiative, passive.<skill>, hit_points_max_per_level."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.services.homebrew.dsl import PassiveModifier

_WHEN = {"path": "$character.id", "op": "gt", "value": 0}
_LABEL = {"it": "x", "en": "x"}


@pytest.mark.parametrize("target", [
    "character.initiative", "character.passive.perception", "character.hit_points_max_per_level",
])
def test_new_targets_accepted(target):
    PassiveModifier.model_validate({"when": _WHEN, "target": target, "value": 2, "label_i18n": _LABEL})


def test_unknown_passive_slug_rejected():
    with pytest.raises(ValidationError):
        PassiveModifier.model_validate(
            {"when": _WHEN, "target": "character.passive.nope", "value": 2, "label_i18n": _LABEL})


async def test_new_targets_are_summed(client, test_session_factory):
    from api.services.homebrew.passive import get_passive_modifiers, passive_modifier
    from core.db.models import Character, HomebrewRule

    r = await client.post("/characters", json={
        "name": "P", "initial_class": {"class_name": "Guerriero", "level": 3, "hit_die": 10}})
    cid = r.json()["id"]
    base_init = r.json()["initiative_bonus"]

    def rule(target, value):
        return {"version": 1, "subject": {"type": "character"}, "triggers": [],
                "passive_modifiers": [{"when": _WHEN, "target": target, "value": value, "label_i18n": _LABEL}]}

    async with test_session_factory() as s:
        for i, (t, v) in enumerate([("character.initiative", 2), ("character.initiative", 3),
                                    ("character.passive.perception", 5),
                                    ("character.hit_points_max_per_level", 2)]):
            s.add(HomebrewRule(character_id=cid, name=f"r{i}", dsl=rule(t, v), created_at="x", updated_at="x"))
        await s.commit()
        char = await s.get(Character, cid)
        assert await get_passive_modifiers(s, char, "character.initiative") == 5
        assert await passive_modifier(s, char, "perception") == 5
        assert await get_passive_modifiers(s, char, "character.hit_points_max") == 6  # 2 x level 3
    body = (await client.get(f"/characters/{cid}")).json()
    assert body["initiative_bonus"] == base_init + 5
    assert body["hp_max_homebrew_modifier"] == 6
