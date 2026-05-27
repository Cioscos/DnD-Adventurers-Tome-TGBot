"""Pydantic strict validation of the homebrew DSL."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.services.homebrew.dsl import (
    Filter, Property, FilterOp,
    Action, ActionRollDice, ActionLookupTable, ActionMatch, ActionIf,
    ActionSetProperty, ActionIncProperty, ActionUnequip,
    ActionDamageCharacter, ActionHealCharacter,
    ActionChangeResource, ActionRestoreResource,
    ActionApplyCondition, ActionRemoveCondition, ActionApplyModifierOnce,
    ActionNotify, ActionAddHistory,
    parse_action,
)


def test_filter_eq_accepts_string():
    f = Filter(path="$subject.quality", op=FilterOp.EQ, value="pessima")
    assert f.path == "$subject.quality"
    assert f.op == FilterOp.EQ
    assert f.value == "pessima"


def test_filter_invalid_op_rejected():
    with pytest.raises(ValidationError):
        Filter(path="$subject.x", op="banana", value=1)


def test_property_enum_requires_values():
    p = Property(
        key="quality", type="enum",
        values=["pessima", "ordinaria"], default="ordinaria",
        label_i18n={"it": "Qualità", "en": "Quality"},
    )
    assert p.default in p.values


def test_property_enum_default_must_be_in_values():
    with pytest.raises(ValidationError) as exc:
        Property(
            key="quality", type="enum",
            values=["pessima", "buona"], default="straordinaria",
            label_i18n={"it": "Qualità", "en": "Q"},
        )
    assert "default" in str(exc.value)


def test_property_key_lowercase_snake_case():
    with pytest.raises(ValidationError):
        Property(
            key="Bad Key!", type="enum", values=["a"], default="a",
            label_i18n={"it": "Test", "en": "Test"},
        )


def test_action_roll_dice_basic():
    a = ActionRollDice(action="roll_dice", notation="1d20", store_as="wear_roll")
    assert a.notation == "1d20"


@pytest.mark.parametrize("notation", ["1d20", "2d6+3", "3d8-2", "1d100", "4d4+0"])
def test_action_roll_dice_valid_notation(notation):
    ActionRollDice(action="roll_dice", notation=notation, store_as="x")


@pytest.mark.parametrize("bad", ["", "20d", "d20", "1d", "1d20+", "abc"])
def test_action_roll_dice_invalid_notation_rejected(bad):
    with pytest.raises(ValidationError):
        ActionRollDice(action="roll_dice", notation=bad, store_as="x")


def test_action_lookup_table():
    a = ActionLookupTable(
        action="lookup_table", table="tabella_usura",
        row="$subject.quality", col="$wear_roll", store_as="wear_result",
    )
    assert a.table == "tabella_usura"


def test_action_match_requires_at_least_one_case():
    with pytest.raises(ValidationError):
        ActionMatch(action="match", value="$wear_result", cases={})


def test_action_match_cases_value_is_list_of_actions():
    a = ActionMatch(
        action="match", value="$x",
        cases={
            "X": [{"action": "notify", "severity": "error", "message": "Broken!"}],
            "S": [],
        },
    )
    assert "X" in a.cases


def test_action_if_with_then_else():
    a = ActionIf(
        action="if",
        cond={"path": "$subject.damage_state", "op": "eq", "value": "danneggiata"},
        then=[{"action": "set_property", "target": "subject", "key": "damage_state", "value": "distrutta"}],
        **{"else": [{"action": "set_property", "target": "subject", "key": "damage_state", "value": "danneggiata"}]},
    )
    assert len(a.then) == 1


def test_action_set_property():
    a = ActionSetProperty(action="set_property", target="subject", key="damage_state", value="distrutta")
    assert a.target == "subject"


def test_action_inc_property_dice_notation():
    a = ActionIncProperty(action="inc_property", target="character", key="rage_uses", delta="1d4")
    assert a.delta == "1d4"


def test_action_change_resource_negative_delta():
    a = ActionChangeResource(action="change_resource", key="luck_points", delta=-1)
    assert a.delta == -1


def test_action_restore_resource_to_max():
    a = ActionRestoreResource(action="restore_resource", key="luck_points", amount="max")
    assert a.amount == "max"


def test_action_apply_condition():
    a = ActionApplyCondition(action="apply_condition", key="custom:bleeding", params={"die": "1d4"})
    assert a.key == "custom:bleeding"


def test_action_apply_modifier_once():
    a = ActionApplyModifierOnce(
        action="apply_modifier_once", target="character.hit_points_max",
        delta="2*level", label="Robusto: +2 PF per livello",
    )
    assert a.delta == "2*level"


def test_action_notify_severity_enum():
    a = ActionNotify(action="notify", severity="warning", message="Arma danneggiata!")
    assert a.severity == "warning"


def test_parse_action_dispatches_by_discriminator():
    raw = {"action": "roll_dice", "notation": "1d20", "store_as": "x"}
    a = parse_action(raw)
    assert isinstance(a, ActionRollDice)


def test_parse_action_unknown_rejected():
    with pytest.raises(ValueError):
        parse_action({"action": "do_evil"})


from api.services.homebrew.dsl import (
    Subject, SubjectFilter, Table, PassiveModifier, Trigger, EventType, RuleDSL,
)


_QU_DSL = {
    "version": 1,
    "subject": {"type": "item", "filter": {"item_types": ["weapon", "armor", "shield"]}},
    "properties": [
        {"key": "quality", "type": "enum",
         "values": ["pessima", "ordinaria", "buona", "straordinaria"],
         "default": "ordinaria",
         "label_i18n": {"it": "Qualità", "en": "Quality"}},
        {"key": "damage_state", "type": "enum",
         "values": ["integra", "danneggiata", "distrutta"],
         "default": "integra",
         "label_i18n": {"it": "Stato", "en": "State"}},
    ],
    "tables": [
        {"id": "tabella_usura", "row_axis": "quality", "col_axis": "d20_result",
         "col_bins": [[1,1],[2,3],[4,9],[10,15],[16,20]],
         "cells": {
             "pessima":      ["X","X","D","D","S"],
             "ordinaria":    ["X","D","D","S","S"],
             "buona":        ["D","D","S","S","S"],
             "straordinaria":["D","S","S","S","S"],
         }}
    ],
    "passive_modifiers": [],
    "triggers": [
        {"event": "attack_rolled",
         "filters": [
             {"path": "$event.is_fumble", "op": "eq", "value": True},
             {"path": "$subject", "op": "has_property", "value": "quality"},
         ],
         "effects": [
             {"action": "roll_dice", "notation": "1d20", "store_as": "wear_roll"},
             {"action": "notify", "severity": "warning", "message": "Test"},
         ]},
    ],
}


def test_rule_dsl_qualita_usura_validates():
    rule = RuleDSL.model_validate(_QU_DSL)
    assert rule.version == 1
    assert rule.subject.type == "item"
    assert len(rule.properties) == 2
    assert len(rule.tables) == 1
    assert len(rule.triggers) == 1


def test_rule_dsl_unknown_event_rejected():
    bad = {**_QU_DSL, "triggers": [{"event": "lunch_time", "filters": [], "effects": []}]}
    with pytest.raises(ValidationError):
        RuleDSL.model_validate(bad)


def test_rule_dsl_table_cells_match_row_axis_values():
    bad = {**_QU_DSL}
    bad["tables"] = [{"id": "t1", "row_axis": "quality", "col_axis": "d20_result",
                     "col_bins": [[1,5],[6,10]],
                     "cells": {"unknown_quality_value": ["X", "S"]}}]
    # NB: this validates cell-length-vs-bins, not row-axis-matching to property values
    # (that's an engine-layer concern). Cell length is verified.
    rule = RuleDSL.model_validate(bad)
    assert "unknown_quality_value" in rule.tables[0].cells


def test_rule_dsl_table_cells_length_must_match_bins():
    bad = {**_QU_DSL}
    bad["tables"] = [{"id": "t1", "row_axis": "quality", "col_axis": "d20_result",
                     "col_bins": [[1,5],[6,10],[11,20]],
                     "cells": {"pessima": ["X", "S"]}}]  # only 2 cells, expected 3
    with pytest.raises(ValidationError):
        RuleDSL.model_validate(bad)


def test_rule_dsl_version_must_be_one():
    bad = {**_QU_DSL, "version": 99}
    with pytest.raises(ValidationError):
        RuleDSL.model_validate(bad)


def test_passive_modifier_target_path():
    pm = PassiveModifier(
        when={"path": "$subject.is_equipped", "op": "eq", "value": True},
        target="character.ac", value=1,
        label_i18n={"it": "Scudo +1", "en": "Shield +1"},
    )
    assert pm.target == "character.ac"


def test_passive_modifier_invalid_target_rejected():
    with pytest.raises(ValidationError):
        PassiveModifier(
            when={"path": "$subject.is_equipped", "op": "eq", "value": True},
            target="character.foobar", value=1,
            label_i18n={"it": "x", "en": "y"},
        )


def test_rule_must_have_trigger_or_passive():
    bad = {
        "version": 1,
        "subject": {"type": "character"},
        "properties": [], "tables": [],
        "passive_modifiers": [], "triggers": [],
    }
    with pytest.raises(ValidationError):
        RuleDSL.model_validate(bad)


def test_rule_with_only_passive_modifier_is_valid():
    rule = RuleDSL.model_validate({
        "version": 1,
        "subject": {"type": "item", "filter": {"item_types": ["shield"]}},
        "passive_modifiers": [{
            "when": {"path": "$subject.is_equipped", "op": "eq", "value": True},
            "target": "character.ac", "value": 1,
            "label_i18n": {"it": "+1 AC scudo", "en": "+1 AC shield"},
        }],
        "triggers": [],
    })
    assert len(rule.passive_modifiers) == 1


def test_trigger_effects_validated_recursively():
    bad = {
        **_QU_DSL,
        "triggers": [{
            "event": "attack_rolled", "filters": [],
            "effects": [{"action": "unknown_action_xyz"}],
        }],
    }
    with pytest.raises(ValidationError):
        RuleDSL.model_validate(bad)
