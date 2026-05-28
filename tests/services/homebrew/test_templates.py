"""Templates are hardcoded immutable DSL documents."""
from api.services.homebrew.dsl import EventType, RuleDSL
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


def test_get_template_unknown_returns_none():
    assert get_template("does_not_exist") is None


# Task 3.8 — Bleeding template
def test_bleeding_template_exists():
    t = get_template("bleeding")
    assert t is not None
    assert t["name"] == "Sanguinamento"
    RuleDSL.model_validate(t["dsl"])


def test_bleeding_template_has_turn_started_trigger():
    t = get_template("bleeding")
    triggers = t["dsl"]["triggers"]
    assert len(triggers) == 1
    assert triggers[0]["event"] == "turn_started"
    # Filter checks `$character.conditions` has `custom:bleeding`
    filt = triggers[0]["filters"][0]
    assert filt["path"] == "$character.conditions"
    assert filt["op"] == "has_property"
    assert filt["value"] == "custom:bleeding"


def test_bleeding_template_uses_dollar_var_runtime():
    t = get_template("bleeding")
    effects = t["dsl"]["triggers"][0]["effects"]
    # First effect rolls 1d4 → store_as "blood"; second damages with $blood.
    assert effects[0]["action"] == "roll_dice"
    assert effects[0]["store_as"] == "blood"
    assert effects[1]["action"] == "damage_character"
    assert effects[1]["amount"] == "$blood"


# Task 3.9 — Enchanted Weapon +1d6 template
def test_enchanted_weapon_template_validates():
    template = get_template("enchanted_weapon")
    assert template is not None
    assert template["id"] == "enchanted_weapon"
    rule = RuleDSL.model_validate(template["dsl"])
    assert rule.subject.type == "item"
    assert rule.subject.filter.item_types == ["weapon"]
    assert len(rule.properties) == 1
    assert rule.properties[0].key == "enchanted"
    assert rule.properties[0].type == "boolean"
    assert len(rule.triggers) == 1
    assert rule.triggers[0].event == EventType.ATTACK_ROLLED
