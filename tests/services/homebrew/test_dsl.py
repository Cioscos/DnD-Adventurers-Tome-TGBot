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
