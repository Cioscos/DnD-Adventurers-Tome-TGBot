"""Templates are hardcoded immutable DSL documents."""
import pytest
from api.services.homebrew.dsl import RuleDSL
from api.services.homebrew.templates import TEMPLATES, get_template


def test_quality_wear_template_exists():
    t = get_template("quality_wear")
    assert t is not None
    assert t["name"] == "Qualità & Usura"
    # DSL must validate
    RuleDSL.model_validate(t["dsl"])


def test_quality_wear_has_three_triggers():
    t = get_template("quality_wear")
    triggers = t["dsl"]["triggers"]
    events = {tr["event"] for tr in triggers}
    assert events == {"attack_rolled", "damage_taken", "dropped_to_zero"}


def test_list_templates_returns_at_least_one():
    assert len(TEMPLATES) >= 1
    assert any(t["id"] == "quality_wear" for t in TEMPLATES)
