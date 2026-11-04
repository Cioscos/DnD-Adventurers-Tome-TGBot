"""Usi massimi dei privilegi a catalogo."""
from __future__ import annotations

from core.db.models import AbilityScore, Character, CharacterClass, Item
from core.rules.types import FeatureSpec, RuleContext, Uses
from core.rules.uses import max_uses


def _spec(key="fighter.action_surge", uses=None, **kw) -> FeatureSpec:
    return FeatureSpec(key=key, class_key=key.split(".")[0], edition="2014", level=kw.pop("level", 1),
                       source_title=key, name={"it": key, "en": key}, summary={"it": "s", "en": "s"},
                       action_type="special", uses=uses, **kw)


def _ctx(level: int, cha: int = 10, items=()) -> RuleContext:
    char = Character(user_id=1, name="x")
    char.ability_scores = [AbilityScore(name="charisma", value=cha)]
    char.items = list(items)
    row = CharacterClass(class_name="bard", level=level)
    char.classes = [row]
    return RuleContext(char=char, edition="2014", class_row=row, class_level=level)


SURGE = _spec(uses=Uses(table={2: 1, 17: 2}))
WILD_SHAPE = _spec("druid.wild_shape", Uses(table={2: 2}, unlimited_from=20))
RAGE = _spec("barbarian.rage", Uses(table={1: 2, 3: 3, 6: 4, 12: 5, 17: 6}, unlimited_from=20))
INSPIRATION = _spec("bard.bardic_inspiration", Uses(ability="charisma"))


def test_action_surge_2014_max_is_two():
    assert max_uses(SURGE, _ctx(20)) == 2
    assert max_uses(SURGE, _ctx(16)) == 1


def test_table_below_first_level_gives_zero():
    assert max_uses(SURGE, _ctx(1)) == 0


def test_wild_shape_2014_unlimited_at_20():
    assert max_uses(WILD_SHAPE, _ctx(19)) == 2
    assert max_uses(WILD_SHAPE, _ctx(20)) is None


def test_rage_2014_unlimited_at_20():
    assert max_uses(RAGE, _ctx(17)) == 6
    assert max_uses(RAGE, _ctx(20)) is None


def test_bardic_inspiration_follows_effective_charisma():
    assert max_uses(INSPIRATION, _ctx(1, cha=16)) == 3
    assert max_uses(INSPIRATION, _ctx(1, cha=6)) == 1  # minimo 1
    headband = Item(name="Fascia", is_equipped=True, item_metadata='{"ability_modifiers": '
                    '[{"ability": "charisma", "kind": "absolute", "value": 20}]}')
    assert max_uses(INSPIRATION, _ctx(1, cha=10, items=[headband])) == 5
    headband.is_equipped = False
    assert max_uses(INSPIRATION, _ctx(1, cha=10, items=[headband])) == 1


def test_per_level_and_proficiency():
    assert max_uses(_spec(uses=Uses(per_level=5)), _ctx(4)) == 20
    assert max_uses(_spec(uses=Uses(proficiency=True)), _ctx(5)) == 3  # bonus di competenza al livello 5


def test_no_uses_means_no_counter():
    assert max_uses(_spec(), _ctx(5)) is None
