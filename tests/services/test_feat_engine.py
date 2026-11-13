"""Talenti nel motore delle regole: un talento posseduto è un privilegio attivo (PR 1 talenti, Task 2)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.rules.catalog import active_features
from core.rules.catalog import feats as feat_module
from core.rules.catalog.feats import FeatSource, feat, feat_status
from core.rules.modifiers import modifiers_for
from core.rules.types import Modifier


def _char(edition="2024", abilities=(), levels=(3,)):
    return SimpleNamespace(
        rules_edition=edition, conditions={}, items=[], settings={}, general_proficiencies={}, active_states=[],
        hit_points=20, damage_modifiers={}, proficiency_bonus=2, skills={}, saving_throws={}, shield_armor_class=0,
        classes=[SimpleNamespace(level=lv, class_name="Homebrew", subclass_key=None, options={}, id=i + 1)
                 for i, lv in enumerate(levels)],
        abilities=list(abilities))


def _row(key="feat.test", options=None):
    return SimpleNamespace(feature_key=key, options=options, id=99)


@pytest.fixture
def test_feat(monkeypatch):
    spec = feat("test", "2024", "Prova", "Test", "x", "x", modifiers=(Modifier("initiative", 3),))
    monkeypatch.setitem(feat_module.FEAT_FEATURES, spec.key, spec)
    return spec


def test_owned_feat_is_an_active_feature(test_feat):
    char = _char(abilities=[_row()], levels=())  # nessuna classe: il talento d'Origine viene prima
    pairs = [(s, r) for s, r in active_features(char) if s is test_feat]
    assert len(pairs) == 1
    source = pairs[0][1]
    assert isinstance(source, FeatSource) and source.id is None and source.level == 1


def test_feat_level_is_total_level(test_feat):
    char = _char(abilities=[_row()], levels=(3, 2))
    assert next(r for s, r in active_features(char) if s is test_feat).level == 5


def test_feat_of_other_edition_is_inert(test_feat):
    char = _char(edition="2014", abilities=[_row()])
    assert not any(s is test_feat for s, _ in active_features(char))
    assert feat_status(char, char.abilities[0]) == "other_edition"


def test_feat_with_missing_options_is_incomplete(test_feat, monkeypatch):
    monkeypatch.setitem(feat_module.FEAT_NEEDS, test_feat.key, ("picks",))
    row = _row()
    char = _char(abilities=[row])
    assert feat_status(char, row) == "incomplete"
    assert not any(s is test_feat for s, _ in active_features(char))
    row.options = {"picks": ["stealth"]}
    assert feat_status(char, row) == "active"
    assert any(s is test_feat for s, _ in active_features(char))


def test_feat_modifier_reaches_rolls(test_feat):
    char = _char(abilities=[_row()])
    assert modifiers_for(char, "initiative").flat == 3


def test_not_a_feat_row_has_no_status():
    assert feat_status(_char(), _row("fighter.second_wind")) is None
