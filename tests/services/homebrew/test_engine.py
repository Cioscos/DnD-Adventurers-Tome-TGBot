"""RuleEngine.execute_trigger tests."""
import json
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from core.db.models import Base, Character, HomebrewRule, Item
from api.services.homebrew.engine import RuleEngine
from api.services.homebrew.types import ExecutionContext


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    SM = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with SM() as s:
        yield s


@pytest.mark.asyncio
async def test_engine_skips_when_filters_dont_match(db_session):
    char = Character(user_id=1, name="T")
    db_session.add(char)
    await db_session.flush()
    dsl = {
        "version": 1, "subject": {"type": "item"},
        "triggers": [{
            "event": "attack_rolled",
            "filters": [{"path": "$event.is_fumble", "op": "eq", "value": True}],
            "effects": [{"action": "notify", "severity": "info", "message": "x"}],
        }],
    }
    rule = HomebrewRule(
        character_id=char.id, name="r", dsl=dsl,
        created_at="x", updated_at="x",
    )
    db_session.add(rule)
    await db_session.flush()

    ctx = ExecutionContext.new("attack_rolled", {"is_fumble": False}, {}, {"id": char.id})
    engine = RuleEngine()
    result = await engine.execute_trigger(rule, rule.dsl["triggers"][0], ctx, db_session, char)
    assert result is None


@pytest.mark.asyncio
async def test_engine_runs_effects_when_filters_match(db_session, monkeypatch):
    monkeypatch.setattr("api.services.homebrew.actions.random.randint", lambda lo, hi: 7)
    char = Character(user_id=1, name="T")
    db_session.add(char)
    await db_session.flush()
    dsl = {
        "version": 1, "subject": {"type": "item"},
        "triggers": [{
            "event": "attack_rolled",
            "filters": [{"path": "$event.is_fumble", "op": "eq", "value": True}],
            "effects": [
                {"action": "roll_dice", "notation": "1d20", "store_as": "r"},
                {"action": "notify", "severity": "warning", "message": "got $r"},
            ],
        }],
    }
    rule = HomebrewRule(
        character_id=char.id, name="r", dsl=dsl,
        created_at="x", updated_at="x",
    )
    db_session.add(rule)
    await db_session.flush()

    ctx = ExecutionContext.new("attack_rolled", {"is_fumble": True}, {}, {"id": char.id})
    engine = RuleEngine()
    result = await engine.execute_trigger(rule, rule.dsl["triggers"][0], ctx, db_session, char)
    assert result is not None
    assert len(result.notifications) == 1
    assert "got 7" in result.notifications[0].message


@pytest.mark.asyncio
async def test_engine_continues_on_action_error(db_session):
    char = Character(user_id=1, name="T")
    db_session.add(char)
    await db_session.flush()
    # First effect references a missing table — ActionExecutionError.
    # Second effect is a plain notify and should still run.
    dsl = {
        "version": 1, "subject": {"type": "item"},
        "triggers": [{
            "event": "attack_rolled",
            "filters": [],
            "effects": [
                {"action": "lookup_table", "table": "missing",
                 "row": "$subject.quality", "col": "$wear_roll", "store_as": "x"},
                {"action": "notify", "severity": "warning", "message": "second"},
            ],
        }],
    }
    rule = HomebrewRule(
        character_id=char.id, name="r", dsl=dsl,
        created_at="x", updated_at="x",
    )
    db_session.add(rule)
    await db_session.flush()

    ctx = ExecutionContext.new("attack_rolled", {"is_fumble": True},
                                 {"_kind": "item", "metadata": {"hb_quality": "pessima"}},
                                 {"id": char.id})
    ctx.set_var("wear_roll", 5)
    engine = RuleEngine()
    result = await engine.execute_trigger(rule, rule.dsl["triggers"][0], ctx, db_session, char)
    assert result is not None
    assert len(result.errors) == 1
    assert "missing" in result.errors[0]
    # The second effect ran despite the first failing.
    assert len(result.notifications) == 1
    assert result.notifications[0].message == "second"


@pytest.mark.asyncio
async def test_engine_raises_on_invalid_dsl(db_session):
    char = Character(user_id=1, name="T")
    db_session.add(char)
    await db_session.flush()
    # Invalid DSL: version is 99 (only 1 allowed)
    rule = HomebrewRule(
        character_id=char.id, name="r",
        dsl={"version": 99, "subject": {"type": "item"}, "triggers": []},
        created_at="x", updated_at="x",
    )
    db_session.add(rule)
    await db_session.flush()

    ctx = ExecutionContext.new("attack_rolled", {}, {}, {"id": char.id})
    engine = RuleEngine()
    from api.services.homebrew.exceptions import DSLValidationError
    with pytest.raises(DSLValidationError):
        await engine.execute_trigger(
            rule,
            {"event": "attack_rolled", "filters": [], "effects": []},
            ctx, db_session, char,
        )


@pytest.mark.asyncio
async def test_quality_wear_full_flow_fumble_pessima(db_session, monkeypatch):
    """Full integration: nat-1 attack with pessima weapon →
    roll d20 mocked to 7 → lookup tabella_usura → "D" → set damage_state=danneggiata + notify."""
    monkeypatch.setattr("api.services.homebrew.actions.random.randint", lambda lo, hi: 7)
    char = Character(user_id=1, name="T")
    db_session.add(char)
    await db_session.flush()
    item = Item(
        character_id=char.id, name="Spada", item_type="weapon", is_equipped=True,
        item_metadata=json.dumps({"hb_quality": "pessima", "hb_damage_state": "integra"}),
    )
    db_session.add(item)
    await db_session.flush()

    dsl = {
        "version": 1,
        "subject": {"type": "item", "filter": {"item_types": ["weapon"]}},
        "properties": [
            {"key": "quality", "type": "enum",
             "values": ["pessima", "ordinaria", "buona", "straordinaria"],
             "default": "ordinaria",
             "label_i18n": {"it": "Q", "en": "Q"}},
            {"key": "damage_state", "type": "enum",
             "values": ["integra", "danneggiata", "distrutta"],
             "default": "integra",
             "label_i18n": {"it": "S", "en": "S"}},
        ],
        "tables": [
            {"id": "tabella_usura", "row_axis": "quality", "col_axis": "d20",
             "col_bins": [[1, 1], [2, 3], [4, 9], [10, 15], [16, 20]],
             "cells": {"pessima": ["X", "X", "D", "D", "S"]}},
        ],
        "triggers": [{
            "event": "attack_rolled",
            "filters": [
                {"path": "$event.is_fumble", "op": "eq", "value": True},
                {"path": "$subject", "op": "has_property", "value": "quality"},
            ],
            "effects": [
                {"action": "roll_dice", "notation": "1d20", "store_as": "wear_roll"},
                {"action": "lookup_table", "table": "tabella_usura",
                 "row": "$subject.quality", "col": "$wear_roll", "store_as": "result"},
                {"action": "match", "value": "$result", "cases": {
                    "X": [{"action": "notify", "severity": "error", "message": "destroyed!"}],
                    "D": [
                        {"action": "set_property", "target": "subject",
                         "key": "damage_state", "value": "danneggiata"},
                        {"action": "notify", "severity": "warning", "message": "damaged"},
                    ],
                    "S": [],
                }},
            ],
        }],
    }
    rule = HomebrewRule(
        character_id=char.id, name="QU", dsl=dsl,
        created_at="x", updated_at="x",
    )
    db_session.add(rule)
    await db_session.flush()

    from api.services.homebrew.dispatcher import dispatch
    results = await dispatch(
        db_session, char, "attack_rolled",
        {"is_fumble": True, "is_critical": False, "to_hit_die": 1,
         "item_id": item.id, "damage_total": 0},
    )
    assert len(results) == 1
    rfr = results[0]
    assert any("damaged" in n.message for n in rfr.notifications)
    await db_session.refresh(item)
    md = json.loads(item.item_metadata)
    assert md["hb_damage_state"] == "danneggiata"
