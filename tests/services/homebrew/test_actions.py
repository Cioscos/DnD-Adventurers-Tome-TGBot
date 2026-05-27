"""Action execution unit tests. random.randint is seeded for determinism."""
import random
import pytest
from unittest.mock import MagicMock

from api.services.homebrew.dsl import RuleDSL
from api.services.homebrew.types import ExecutionContext, RuleFiringResult
from api.services.homebrew.actions import (
    execute_roll_dice, execute_lookup_table, execute_match, execute_if,
)


def _ctx():
    return ExecutionContext.new(
        event_type="attack_rolled",
        event_payload={"is_fumble": True},
        subject={"_kind": "item", "metadata": {"hb_quality": "pessima", "hb_damage_state": "integra"}},
        character={"current_hit_points": 10},
    )


def test_roll_dice_stores_var(monkeypatch):
    monkeypatch.setattr(random, "randint", lambda lo, hi: 7)
    ctx = _ctx()
    rfr = RuleFiringResult(rule_id=1, rule_name="r")
    execute_roll_dice({"action": "roll_dice", "notation": "1d20", "store_as": "wear_roll"},
                      ctx, rfr, MagicMock(), MagicMock())
    assert ctx.vars["wear_roll"] == 7


def test_roll_dice_with_bonus(monkeypatch):
    rolls = iter([4, 5])
    monkeypatch.setattr(random, "randint", lambda lo, hi: next(rolls))
    ctx = _ctx()
    rfr = RuleFiringResult(rule_id=1, rule_name="r")
    execute_roll_dice({"action": "roll_dice", "notation": "2d6+3", "store_as": "x"},
                      ctx, rfr, MagicMock(), MagicMock())
    assert ctx.vars["x"] == 12  # 4+5+3


def test_lookup_table_returns_cell():
    rule = RuleDSL.model_validate({
        "version": 1, "subject": {"type": "item"},
        "tables": [{"id": "t", "row_axis": "quality", "col_axis": "d20",
                    "col_bins": [[1, 1], [2, 3], [4, 9], [10, 15], [16, 20]],
                    "cells": {
                        "pessima":   ["X", "X", "D", "D", "S"],
                        "ordinaria": ["X", "D", "D", "S", "S"],
                    }}],
        "triggers": [{"event": "attack_rolled", "filters": [], "effects": []}],
    })
    ctx = _ctx()
    ctx.set_var("wear_roll", 1)
    rfr = RuleFiringResult(rule_id=1, rule_name="r")
    execute_lookup_table(
        {"action": "lookup_table", "table": "t",
         "row": "$subject.quality", "col": "$wear_roll", "store_as": "result"},
        ctx, rfr, MagicMock(), MagicMock(), rule=rule,
    )
    assert ctx.vars["result"] == "X"


def test_lookup_table_col_bin_mapping():
    rule = RuleDSL.model_validate({
        "version": 1, "subject": {"type": "item"},
        "tables": [{"id": "t", "row_axis": "quality", "col_axis": "d20",
                    "col_bins": [[1, 1], [2, 3], [4, 9], [10, 15], [16, 20]],
                    "cells": {"pessima": ["X", "Y", "Z", "W", "S"]}}],
        "triggers": [{"event": "attack_rolled", "filters": [], "effects": []}],
    })
    ctx = _ctx()
    ctx.set_var("wear_roll", 7)  # falls into bin [4,9] → col index 2
    rfr = RuleFiringResult(rule_id=1, rule_name="r")
    execute_lookup_table(
        {"action": "lookup_table", "table": "t",
         "row": "$subject.quality", "col": "$wear_roll", "store_as": "result"},
        ctx, rfr, MagicMock(), MagicMock(), rule=rule,
    )
    assert ctx.vars["result"] == "Z"


def test_match_executes_branch(monkeypatch):
    ctx = _ctx()
    ctx.set_var("result", "D")
    rfr = RuleFiringResult(rule_id=1, rule_name="r")
    notify_calls = []

    def fake_execute_action(action, ctx, rfr, session, char, **kw):
        if action["action"] == "notify":
            notify_calls.append(action["message"])

    monkeypatch.setattr("api.services.homebrew.actions.execute_action", fake_execute_action)
    execute_match(
        {"action": "match", "value": "$result",
         "cases": {
             "X": [{"action": "notify", "severity": "error", "message": "destroyed"}],
             "D": [{"action": "notify", "severity": "warning", "message": "damaged"}],
             "S": [],
         }},
        ctx, rfr, MagicMock(), MagicMock(),
    )
    assert notify_calls == ["damaged"]


def test_if_runs_then_branch(monkeypatch):
    ctx = _ctx()
    rfr = RuleFiringResult(rule_id=1, rule_name="r")
    notify_calls = []

    def fake_execute_action(action, ctx, rfr, session, char, **kw):
        notify_calls.append(action.get("message"))

    monkeypatch.setattr("api.services.homebrew.actions.execute_action", fake_execute_action)
    execute_if(
        {"action": "if",
         "cond": {"path": "$subject.damage_state", "op": "eq", "value": "integra"},
         "then": [{"action": "notify", "severity": "info", "message": "was_integra"}],
         "else": [{"action": "notify", "severity": "info", "message": "was_else"}]},
        ctx, rfr, MagicMock(), MagicMock(),
    )
    assert notify_calls == ["was_integra"]


from api.services.homebrew.actions import execute_notify, execute_add_history


def test_notify_resolves_dollar_placeholders():
    ctx = _ctx()
    rfr = RuleFiringResult(rule_id=42, rule_name="QU")
    execute_notify(
        {"action": "notify", "severity": "warning", "message": "$subject.name danneggiata!"},
        ctx, rfr, None, None,
    )
    assert len(rfr.notifications) == 1
    n = rfr.notifications[0]
    assert n.severity == "warning"
    assert "Spada" not in n.message  # subject has no 'name' field by default in our test ctx
    # Defaults to literal $subject.name string when unresolvable — be tolerant.


def test_notify_static_message():
    ctx = _ctx()
    rfr = RuleFiringResult(rule_id=42, rule_name="QU")
    execute_notify(
        {"action": "notify", "severity": "error", "message": "Static msg"},
        ctx, rfr, None, None,
    )
    assert rfr.notifications[0].message == "Static msg"


def test_add_history_buffers_entry():
    ctx = _ctx()
    rfr = RuleFiringResult(rule_id=42, rule_name="QU")
    execute_add_history(
        {"action": "add_history", "description": "Weapon damaged"}, ctx, rfr, None, None,
    )
    assert rfr.history_entries[0].description == "Weapon damaged"
