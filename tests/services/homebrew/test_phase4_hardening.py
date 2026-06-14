"""Fase 4 — schema hardening: reject malformed DSL at create, not at runtime."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from api.services.homebrew.dsl import (
    ActionApplyModifierOnce, ActionChangeResource, ActionIf, ActionMatch,
    ActionRollDice, PassiveModifier, Property, RuleDSL, Subject, Table,
)
from api.services.homebrew.actions import execute_lookup_table
from api.services.homebrew.types import ExecutionContext, RuleFiringResult
from core.db.models import Base, Character, HomebrewRule, Item


# ─── F4-16 (D2): apply_modifier_once target restricted ───────────────────────
def test_apply_modifier_once_rejects_unsupported_target():
    with pytest.raises(ValidationError):
        ActionApplyModifierOnce(action="apply_modifier_once", target="character.ac",
                                delta=1, label="x")
    # Supported stored fields + N*level delta are accepted.
    ActionApplyModifierOnce(action="apply_modifier_once",
                            target="character.hit_points_max", delta="2*level", label="x")
    ActionApplyModifierOnce(action="apply_modifier_once",
                            target="character.speed", delta=5, label="x")


# ─── F4-21: change/restore_resource key must be snake_case ───────────────────
def test_change_resource_key_must_be_snake_case():
    with pytest.raises(ValidationError):
        ActionChangeResource(action="change_resource", key="Bad Key", delta=-1)
    ActionChangeResource(action="change_resource", key="luck_points", delta=-1)


# ─── F4-23: dice notation rejects M=0 and caps count/sides ───────────────────
def test_dice_notation_rejects_zero_sides_and_caps():
    with pytest.raises(ValidationError):
        ActionRollDice(action="roll_dice", notation="1d0", store_as="x")
    with pytest.raises(ValidationError):
        ActionRollDice(action="roll_dice", notation="9999d6", store_as="x")
    ActionRollDice(action="roll_dice", notation="2d6+1", store_as="x")


# ─── F4-15: nested match/if actions validated recursively ────────────────────
def test_match_validates_nested_actions():
    with pytest.raises(ValidationError):
        ActionMatch(action="match", value="$x", cases={"a": [{"action": "nope"}]})
    ActionMatch(action="match", value="$x",
                cases={"a": [{"action": "add_history", "description": "ok"}]})


def test_if_validates_nested_branch_actions():
    with pytest.raises(ValidationError):
        ActionIf(action="if", cond={"path": "$x", "op": "eq", "value": 1},
                 then=[{"action": "nope"}])
    ActionIf(action="if", cond={"path": "$x", "op": "eq", "value": 1},
             then=[{"action": "add_history", "description": "ok"}])


# ─── F4-24: Property.value_labels_i18n consistency ───────────────────────────
def test_property_value_labels_must_match_values_and_languages():
    with pytest.raises(ValidationError):
        Property(key="q", type="enum", values=["a", "b"], default="a",
                 label_i18n={"it": "Q", "en": "Q"},
                 value_labels_i18n={"zzz": {"it": "X", "en": "X"}})  # key not in values
    with pytest.raises(ValidationError):
        Property(key="q", type="enum", values=["a"], default="a",
                 label_i18n={"it": "Q", "en": "Q"},
                 value_labels_i18n={"a": {"it": "X"}})  # missing 'en'
    Property(key="q", type="enum", values=["a"], default="a",
             label_i18n={"it": "Q", "en": "Q"},
             value_labels_i18n={"a": {"it": "X", "en": "X"}})


# ─── F4-27: PassiveModifier.value int-only ───────────────────────────────────
def test_passive_value_rejects_dice_string():
    with pytest.raises(ValidationError):
        PassiveModifier(when={"path": "$x", "op": "eq", "value": True},
                        target="character.ac", value="1d4",
                        label_i18n={"it": "X", "en": "X"})
    PassiveModifier(when={"path": "$x", "op": "eq", "value": True},
                    target="character.ac", value=2, label_i18n={"it": "X", "en": "X"})


# ─── F4-26: passive skill/save slug restricted to supported ones ─────────────
def test_passive_target_rejects_unknown_slug():
    with pytest.raises(ValidationError):
        PassiveModifier(when={"path": "$x", "op": "eq", "value": True},
                        target="character.skill.lockpicking", value=1,
                        label_i18n={"it": "X", "en": "X"})
    PassiveModifier(when={"path": "$x", "op": "eq", "value": True},
                    target="character.skill.stealth", value=1,
                    label_i18n={"it": "X", "en": "X"})


# ─── F4-19: subject 'ability' removed ────────────────────────────────────────
def test_subject_type_ability_rejected():
    with pytest.raises(ValidationError):
        Subject(type="ability")
    Subject(type="character")
    Subject(type="item")


# ─── F4-25: table bins non-empty and non-overlapping ─────────────────────────
def test_table_rejects_overlapping_and_empty_bins():
    with pytest.raises(ValidationError):
        Table(id="t", row_axis="q", col_axis="d", col_bins=[[1, 5], [3, 8]],
              cells={"q": ["a", "b"]})  # overlap
    with pytest.raises(ValidationError):
        Table(id="t", row_axis="q", col_axis="d", col_bins=[], cells={})  # empty
    Table(id="t", row_axis="q", col_axis="d", col_bins=[[1, 1], [2, 3]],
          cells={"q": ["a", "b"]})


# ─── F4-22: lookup_table.table must reference a declared table ───────────────
def test_lookup_table_must_reference_declared_table():
    with pytest.raises(ValidationError):
        RuleDSL.model_validate({
            "version": 1, "subject": {"type": "character"},
            "tables": [],
            "triggers": [{"event": "manual_trigger", "filters": [], "effects": [
                {"action": "lookup_table", "table": "ghost", "row": "$r",
                 "col": "$c", "store_as": "x"}]}],
        })


# ─── F4-20 (D4): lookup_table accepts a literal numeric col ──────────────────
def test_lookup_table_accepts_literal_numeric_col():
    rule = RuleDSL.model_validate({
        "version": 1, "subject": {"type": "item"},
        "tables": [{"id": "t", "row_axis": "quality", "col_axis": "d20",
                    "col_bins": [[1, 1], [2, 3], [4, 9], [10, 15], [16, 20]],
                    "cells": {"pessima": ["X", "X", "D", "D", "S"]}}],
        "triggers": [{"event": "attack_rolled", "filters": [], "effects": []}],
    })
    ctx = ExecutionContext.new(
        event_type="attack_rolled", event_payload={},
        subject={"_kind": "item", "metadata": {"hb_quality": "pessima"}},
        character={"current_hit_points": 10},
    )
    rfr = RuleFiringResult(rule_id=1, rule_name="r")
    # Literal "5" (no $var) is coerced to 5 → bin [4,9] (index 2) → cells[..][2] = "D".
    execute_lookup_table(
        {"action": "lookup_table", "table": "t", "row": "$subject.quality",
         "col": "5", "store_as": "out"},
        ctx, rfr, MagicMock(), MagicMock(), rule=rule,
    )
    assert ctx.vars["out"] == "D"


# ─── F4-18: passive scoping honors subject.name_contains ─────────────────────
@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sm() as s:
        yield s


@pytest.mark.asyncio
async def test_passive_modifier_respects_name_contains(db_session):
    char = Character(user_id=1, name="T")
    db_session.add(char)
    await db_session.flush()
    db_session.add_all([
        Item(character_id=char.id, name="Spada Sacra", item_type="weapon",
             is_equipped=True, item_metadata="{}"),
        Item(character_id=char.id, name="Spada", item_type="weapon",
             is_equipped=True, item_metadata="{}"),
    ])
    await db_session.flush()
    rule = HomebrewRule(
        character_id=char.id, name="HolyAC", dsl={
            "version": 1,
            "subject": {"type": "item", "filter": {"name_contains": "Sacra"}},
            "passive_modifiers": [
                {"when": {"path": "$subject.is_equipped", "op": "eq", "value": True},
                 "target": "character.ac", "value": 2,
                 "label_i18n": {"it": "Sacra", "en": "Holy"}},
            ],
            "triggers": [],
        }, created_at="x", updated_at="x",
    )
    db_session.add(rule)
    await db_session.flush()

    from api.services.homebrew.passive import get_passive_modifiers
    total = await get_passive_modifiers(db_session, char, "character.ac")
    # Only "Spada Sacra" matches name_contains → +2 once (not +4 for both swords).
    assert total == 2
