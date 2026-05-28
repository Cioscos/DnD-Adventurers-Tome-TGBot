"""Pydantic strict validation of the homebrew API-facing schemas."""
import pytest
from pydantic import ValidationError
from api.schemas.homebrew import (
    HomebrewRuleCreate, HomebrewRuleRead, HomebrewRuleUpdate,
    HomebrewResourceRead, TemplateRead,
)


def test_rule_create_requires_name_and_dsl():
    body = HomebrewRuleCreate(
        name="My Rule",
        description="Test",
        dsl={"version": 1, "subject": {"type": "character"},
             "triggers": [{"event": "manual_trigger", "filters": [], "effects": []}]},
        enabled=True,
    )
    assert body.name == "My Rule"


def test_rule_create_invalid_dsl_rejected():
    with pytest.raises(ValidationError):
        HomebrewRuleCreate(name="x", dsl={"version": 99}, enabled=True)


def test_template_read_minimal_fields():
    t = TemplateRead(id="quality_wear", name="Qualità & Usura",
                     description="...", icon="⚒️")
    assert t.id == "quality_wear"
