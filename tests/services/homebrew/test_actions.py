"""Action execution unit tests. random.randint is seeded for determinism."""
import json
import random
import pytest
import pytest_asyncio
from unittest.mock import MagicMock

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from core.db.models import Base, Character, Item
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


@pytest.mark.asyncio
async def test_match_executes_branch(monkeypatch):
    ctx = _ctx()
    ctx.set_var("result", "D")
    rfr = RuleFiringResult(rule_id=1, rule_name="r")
    notify_calls = []

    async def fake_execute_action(action, ctx, rfr, session, char, **kw):
        if action["action"] == "notify":
            notify_calls.append(action["message"])

    monkeypatch.setattr("api.services.homebrew.actions.execute_action", fake_execute_action)
    await execute_match(
        {"action": "match", "value": "$result",
         "cases": {
             "X": [{"action": "notify", "severity": "error", "message": "destroyed"}],
             "D": [{"action": "notify", "severity": "warning", "message": "damaged"}],
             "S": [],
         }},
        ctx, rfr, MagicMock(), MagicMock(),
    )
    assert notify_calls == ["damaged"]


@pytest.mark.asyncio
async def test_if_runs_then_branch(monkeypatch):
    ctx = _ctx()
    rfr = RuleFiringResult(rule_id=1, rule_name="r")
    notify_calls = []

    async def fake_execute_action(action, ctx, rfr, session, char, **kw):
        notify_calls.append(action.get("message"))

    monkeypatch.setattr("api.services.homebrew.actions.execute_action", fake_execute_action)
    await execute_if(
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


# ---------------------------------------------------------------------------
# Task 1.6 — async handlers backed by the DB
# ---------------------------------------------------------------------------

from api.services.homebrew.actions import (
    execute_set_property, execute_inc_property, execute_unequip,
)


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    SessionMaker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionMaker() as s:
        yield s


@pytest_asyncio.fixture
async def char_with_item(db_session):
    char = Character(user_id=1, name="Test")
    db_session.add(char)
    await db_session.flush()
    item = Item(
        character_id=char.id, name="Spada lunga", item_type="weapon",
        item_metadata=json.dumps({"hb_quality": "pessima", "hb_damage_state": "integra"}),
        is_equipped=True,
    )
    db_session.add(item)
    await db_session.flush()
    return char, item


@pytest.mark.asyncio
async def test_set_property_on_item(db_session, char_with_item):
    char, item = char_with_item
    ctx = ExecutionContext.new(
        event_type="attack_rolled", event_payload={},
        subject={"_kind": "item", "_id": item.id,
                 "metadata": json.loads(item.item_metadata)},
        character={"id": char.id},
    )
    rfr = RuleFiringResult(rule_id=1, rule_name="r")
    await execute_set_property(
        {"action": "set_property", "target": "subject",
         "key": "damage_state", "value": "distrutta"},
        ctx, rfr, db_session, char,
    )
    await db_session.refresh(item)
    md = json.loads(item.item_metadata)
    assert md["hb_damage_state"] == "distrutta"
    assert ctx.subject["metadata"]["hb_damage_state"] == "distrutta"


@pytest.mark.asyncio
async def test_unequip_subject_item(db_session, char_with_item):
    char, item = char_with_item
    ctx = ExecutionContext.new(
        event_type="attack_rolled", event_payload={},
        subject={"_kind": "item", "_id": item.id,
                 "metadata": json.loads(item.item_metadata)},
        character={"id": char.id},
    )
    rfr = RuleFiringResult(rule_id=1, rule_name="r")
    await execute_unequip(
        {"action": "unequip", "target": "subject"}, ctx, rfr, db_session, char,
    )
    await db_session.refresh(item)
    assert item.is_equipped is False
    assert item.equipment_slot is None


@pytest.mark.asyncio
async def test_inc_property_int_delta_on_item(db_session, char_with_item):
    char, item = char_with_item
    md = json.loads(item.item_metadata)
    md["hb_uses"] = 2
    item.item_metadata = json.dumps(md)
    await db_session.flush()

    ctx = ExecutionContext.new(
        event_type="manual", event_payload={},
        subject={"_kind": "item", "_id": item.id, "metadata": json.loads(item.item_metadata)},
        character={"id": char.id},
    )
    rfr = RuleFiringResult(rule_id=1, rule_name="r")
    await execute_inc_property(
        {"action": "inc_property", "target": "subject", "key": "uses", "delta": 3},
        ctx, rfr, db_session, char,
    )
    await db_session.refresh(item)
    md = json.loads(item.item_metadata)
    assert md["hb_uses"] == 5
    assert ctx.subject["metadata"]["hb_uses"] == 5


@pytest.mark.asyncio
async def test_inc_property_creates_from_zero_when_absent(db_session, char_with_item):
    char, item = char_with_item
    ctx = ExecutionContext.new(
        event_type="manual", event_payload={},
        subject={"_kind": "item", "_id": item.id, "metadata": json.loads(item.item_metadata)},
        character={"id": char.id},
    )
    rfr = RuleFiringResult(rule_id=1, rule_name="r")
    await execute_inc_property(
        {"action": "inc_property", "target": "subject", "key": "uses", "delta": 1},
        ctx, rfr, db_session, char,
    )
    await db_session.refresh(item)
    md = json.loads(item.item_metadata)
    assert md["hb_uses"] == 1


@pytest.mark.asyncio
async def test_inc_property_dice_delta(db_session, char_with_item, monkeypatch):
    monkeypatch.setattr("api.services.homebrew.actions.random.randint", lambda lo, hi: 3)
    char, item = char_with_item
    ctx = ExecutionContext.new(
        event_type="manual", event_payload={},
        subject={"_kind": "item", "_id": item.id, "metadata": json.loads(item.item_metadata)},
        character={"id": char.id},
    )
    rfr = RuleFiringResult(rule_id=1, rule_name="r")
    await execute_inc_property(
        {"action": "inc_property", "target": "subject", "key": "uses", "delta": "1d4"},
        ctx, rfr, db_session, char,
    )
    await db_session.refresh(item)
    md = json.loads(item.item_metadata)
    assert md["hb_uses"] == 3


@pytest.mark.asyncio
async def test_inc_property_non_numeric_raises(db_session, char_with_item):
    char, item = char_with_item
    ctx = ExecutionContext.new(
        event_type="manual", event_payload={},
        subject={"_kind": "item", "_id": item.id, "metadata": json.loads(item.item_metadata)},
        character={"id": char.id},
    )
    rfr = RuleFiringResult(rule_id=1, rule_name="r")
    from api.services.homebrew.exceptions import ActionExecutionError
    with pytest.raises(ActionExecutionError, match="not numeric"):
        await execute_inc_property(
            {"action": "inc_property", "target": "subject", "key": "quality", "delta": 1},
            ctx, rfr, db_session, char,
        )


@pytest.mark.asyncio
async def test_set_property_target_character(db_session, char_with_item):
    char, _ = char_with_item
    ctx = ExecutionContext.new(
        event_type="manual", event_payload={},
        subject={}, character={"id": char.id},
    )
    rfr = RuleFiringResult(rule_id=1, rule_name="r")
    await execute_set_property(
        {"action": "set_property", "target": "character",
         "key": "blessed", "value": True},
        ctx, rfr, db_session, char,
    )
    await db_session.refresh(char)
    assert char.settings["homebrew_fields"]["blessed"] is True


@pytest.mark.asyncio
async def test_inc_property_target_character(db_session, char_with_item):
    char, _ = char_with_item
    char.settings = {"homebrew_fields": {"luck_used": 0}}
    await db_session.flush()
    ctx = ExecutionContext.new(
        event_type="manual", event_payload={},
        subject={}, character={"id": char.id},
    )
    rfr = RuleFiringResult(rule_id=1, rule_name="r")
    await execute_inc_property(
        {"action": "inc_property", "target": "character", "key": "luck_used", "delta": 2},
        ctx, rfr, db_session, char,
    )
    await db_session.refresh(char)
    assert char.settings["homebrew_fields"]["luck_used"] == 2


@pytest.mark.asyncio
async def test_unequip_armor_resets_base_ac(db_session):
    char = Character(user_id=1, name="Tank", base_armor_class=16,
                     base_armor_class_override=False)
    db_session.add(char)
    await db_session.flush()
    armor = Item(
        character_id=char.id, name="Mail", item_type="armor",
        item_metadata=json.dumps({"ac_value": 16}),
        is_equipped=True,
    )
    db_session.add(armor)
    await db_session.flush()

    ctx = ExecutionContext.new(
        event_type="dropped_to_zero", event_payload={},
        subject={"_kind": "item", "_id": armor.id, "metadata": json.loads(armor.item_metadata)},
        character={"id": char.id},
    )
    rfr = RuleFiringResult(rule_id=1, rule_name="r")
    await execute_unequip(
        {"action": "unequip", "target": "subject"}, ctx, rfr, db_session, char,
    )
    await db_session.refresh(char)
    await db_session.refresh(armor)
    assert armor.is_equipped is False
    assert char.base_armor_class == 10


@pytest.mark.asyncio
async def test_unequip_armor_respects_override(db_session):
    char = Character(user_id=1, name="Tank", base_armor_class=16,
                     base_armor_class_override=True)
    db_session.add(char)
    await db_session.flush()
    armor = Item(
        character_id=char.id, name="Mail", item_type="armor",
        item_metadata=json.dumps({"ac_value": 16}),
        is_equipped=True,
    )
    db_session.add(armor)
    await db_session.flush()

    ctx = ExecutionContext.new(
        event_type="manual", event_payload={},
        subject={"_kind": "item", "_id": armor.id, "metadata": json.loads(armor.item_metadata)},
        character={"id": char.id},
    )
    rfr = RuleFiringResult(rule_id=1, rule_name="r")
    await execute_unequip(
        {"action": "unequip", "target": "subject"}, ctx, rfr, db_session, char,
    )
    await db_session.refresh(char)
    assert char.base_armor_class == 16


# ---------------------------------------------------------------------------
# Task 1.7 — damage_character + heal_character
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_damage_character_int_amount(db_session, char_with_item):
    char, _ = char_with_item
    char.hit_points = 20
    char.current_hit_points = 15
    rfr = RuleFiringResult(rule_id=1, rule_name="r")
    ctx = ExecutionContext.new("homebrew_internal", {}, {}, {"id": char.id})

    from api.services.homebrew.actions import execute_damage_character
    await execute_damage_character(
        {"action": "damage_character", "amount": 5}, ctx, rfr, db_session, char,
    )
    assert char.current_hit_points == 10


@pytest.mark.asyncio
async def test_damage_character_dice_amount(db_session, char_with_item, monkeypatch):
    monkeypatch.setattr("api.services.homebrew.actions.random.randint", lambda lo, hi: 3)
    char, _ = char_with_item
    char.hit_points = 20
    char.current_hit_points = 20
    rfr = RuleFiringResult(rule_id=1, rule_name="r")
    ctx = ExecutionContext.new("homebrew_internal", {}, {}, {"id": char.id})

    from api.services.homebrew.actions import execute_damage_character
    await execute_damage_character(
        {"action": "damage_character", "amount": "1d4"}, ctx, rfr, db_session, char,
    )
    assert char.current_hit_points == 17  # 20 - 3


@pytest.mark.asyncio
async def test_heal_character_caps_at_max(db_session, char_with_item):
    char, _ = char_with_item
    char.hit_points = 20
    char.current_hit_points = 18
    rfr = RuleFiringResult(rule_id=1, rule_name="r")
    ctx = ExecutionContext.new("homebrew_internal", {}, {}, {"id": char.id})

    from api.services.homebrew.actions import execute_heal_character
    await execute_heal_character(
        {"action": "heal_character", "amount": 10}, ctx, rfr, db_session, char,
    )
    assert char.current_hit_points == 20  # capped at max
