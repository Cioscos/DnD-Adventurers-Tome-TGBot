"""Action implementations. Each function follows signature:

    def execute_<action>(payload, ctx, rfr, session, char, **kwargs) -> None

Some handlers (the DB-mutating ones) are async; the rest are sync.
`execute_action` is async and dispatches to either kind transparently.
"""
from __future__ import annotations

import asyncio
import json as _json
import random
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from api.services.homebrew.dsl import Filter, RuleDSL
from api.services.homebrew.exceptions import ActionExecutionError
from api.services.homebrew.filters import evaluate_filter
from api.services.homebrew.path_resolver import resolve_path
from api.services.homebrew.types import ExecutionContext, Notification, RuleFiringResult
from core.db.models import Character, HomebrewResource, Item


_DICE_RE = re.compile(r"^(\d+)d(\d+)([+-]\d+)?$", re.IGNORECASE)


def _roll(notation: str) -> int:
    m = _DICE_RE.match(notation.strip())
    if not m:
        raise ActionExecutionError(f"Invalid dice notation: {notation}")
    count, sides = int(m.group(1)), int(m.group(2))
    bonus = int(m.group(3) or 0)
    return sum(random.randint(1, sides) for _ in range(count)) + bonus


def _resolve_or_value(v: Any, ctx: ExecutionContext) -> Any:
    if isinstance(v, str):
        return resolve_path(v, ctx.to_dict())
    return v


def execute_roll_dice(action, ctx, rfr, session, char, **kw):
    total = _roll(action["notation"])
    ctx.set_var(action["store_as"], total)


def execute_lookup_table(action, ctx, rfr, session, char, *, rule: RuleDSL, **kw):
    table_id = action["table"]
    table = next((t for t in rule.tables if t.id == table_id), None)
    if table is None:
        raise ActionExecutionError(f"Table '{table_id}' not found in rule")

    row_value = _resolve_or_value(action["row"], ctx)
    col_value = _resolve_or_value(action["col"], ctx)

    # Map numeric col to its bin index
    col_index = None
    if isinstance(col_value, (int, float)):
        for i, (lo, hi) in enumerate(table.col_bins):
            if lo <= col_value <= hi:
                col_index = i
                break
        if col_index is None:
            raise ActionExecutionError(
                f"Col value {col_value} doesn't fall into any bin {table.col_bins}"
            )
    else:
        # Treat as string column key — not supported in MVP (col_bins are numeric)
        raise ActionExecutionError(
            f"Non-numeric col '{col_value}' for table '{table_id}'"
        )

    row = table.cells.get(str(row_value))
    if row is None:
        raise ActionExecutionError(
            f"Row '{row_value}' not in table '{table_id}' (rows: {list(table.cells.keys())})"
        )
    if col_index >= len(row):
        raise ActionExecutionError(
            f"Col index {col_index} out of range for row '{row_value}' (len={len(row)})"
        )
    ctx.set_var(action["store_as"], row[col_index])


async def execute_match(action, ctx, rfr, session, char, **kw):
    val = _resolve_or_value(action["value"], ctx)
    branch = action["cases"].get(str(val))
    if branch is None:
        return  # no matching case = no-op
    for sub_action in branch:
        await execute_action(sub_action, ctx, rfr, session, char, **kw)


async def execute_if(action, ctx, rfr, session, char, **kw):
    cond = Filter.model_validate(action["cond"])
    if evaluate_filter(cond, ctx.to_dict()):
        branch = action.get("then", [])
    else:
        branch = action.get("else", [])
    for sub_action in branch:
        await execute_action(sub_action, ctx, rfr, session, char, **kw)


_PLACEHOLDER_RE = re.compile(r"\$[\w.]+")
_BRACE_PLACEHOLDER_RE = re.compile(r"\{([\w.]+)\}")


def _format_message(template: str, ctx: ExecutionContext) -> str:
    """Substitute $path and {var}/{vars.x} placeholders in a message template."""
    data = ctx.to_dict()

    def _replace_dollar(m):
        path = m.group(0)
        try:
            v = resolve_path(path, data)
            return str(v)
        except Exception:
            return path  # leave as-is if unresolvable

    def _replace_brace(m):
        name = m.group(1)
        try:
            v = resolve_path("$" + name, data)
            return str(v)
        except Exception:
            return m.group(0)  # leave {...} as-is if unresolvable

    result = _PLACEHOLDER_RE.sub(_replace_dollar, template)
    return _BRACE_PLACEHOLDER_RE.sub(_replace_brace, result)


def execute_notify(action, ctx, rfr, session, char, **kw):
    msg = _format_message(action["message"], ctx)
    rfr.add_notification(Notification(severity=action["severity"], message=msg))


def execute_add_history(action, ctx, rfr, session, char, **kw):
    msg = _format_message(action["description"], ctx)
    rfr.add_history_entry(msg, meta=action.get("meta"))


# ---------------------------------------------------------------------------
# Async DB-mutating handlers (Task 1.6)
# ---------------------------------------------------------------------------

async def _load_item(session: AsyncSession, item_id: int) -> Item:
    res = await session.execute(select(Item).where(Item.id == item_id))
    item = res.scalar_one_or_none()
    if item is None:
        raise ActionExecutionError(f"Item {item_id} not found")
    return item


async def execute_set_property(action, ctx, rfr, session, char, **kw):
    target = action["target"]
    key = action["key"]
    value = action["value"]

    if target == "subject":
        subject = ctx.subject
        if subject.get("_kind") == "item":
            item = await _load_item(session, subject["_id"])
            md = _json.loads(item.item_metadata or "{}")
            md[f"hb_{key}"] = value
            item.item_metadata = _json.dumps(md)
            # Mirror in ctx so later steps see the new value.
            subject["metadata"] = md
        else:
            raise ActionExecutionError(
                f"set_property on subject kind '{subject.get('_kind')}' not supported in MVP"
            )
    elif target == "character":
        # Custom fields go into character.settings JSON (no schema change).
        settings = dict(char.settings or {})
        homebrew = dict(settings.get("homebrew_fields", {}))
        homebrew[key] = value
        settings["homebrew_fields"] = homebrew
        char.settings = settings
    else:
        raise ActionExecutionError(f"set_property target '{target}' not supported")

    await session.flush()


def _resolve_amount(amount, ctx: ExecutionContext, *, field: str):
    """Resolve an amount/delta that may be int, dice notation, or a `$var` path.

    Raises ActionExecutionError if the value cannot be coerced to an integer
    (e.g. missing `$var` in ctx, non-numeric resolved value).
    """
    if isinstance(amount, str):
        if amount.startswith("$"):
            try:
                amount = resolve_path(amount, ctx.to_dict())
            except Exception as e:
                raise ActionExecutionError(
                    f"{field}: could not resolve '{amount}' ({e})"
                )
        else:
            amount = _roll(amount)
    try:
        return int(amount)
    except (TypeError, ValueError):
        raise ActionExecutionError(
            f"{field}: resolved value not numeric (got {amount!r})"
        )


async def execute_inc_property(action, ctx, rfr, session, char, **kw):
    delta = _resolve_amount(action["delta"], ctx, field="inc_property.delta")

    target = action["target"]
    key = action["key"]
    if target == "subject" and ctx.subject.get("_kind") == "item":
        item = await _load_item(session, ctx.subject["_id"])
        md = _json.loads(item.item_metadata or "{}")
        current = md.get(f"hb_{key}", 0)
        try:
            md[f"hb_{key}"] = int(current) + delta
        except (TypeError, ValueError):
            raise ActionExecutionError(
                f"inc_property '{key}' not numeric (current value: {current!r})"
            )
        item.item_metadata = _json.dumps(md)
        ctx.subject["metadata"] = md
    elif target == "character":
        settings = dict(char.settings or {})
        homebrew = dict(settings.get("homebrew_fields", {}))
        current = homebrew.get(key, 0)
        try:
            homebrew[key] = int(current) + delta
        except (TypeError, ValueError):
            raise ActionExecutionError(
                f"inc_property '{key}' not numeric (current value: {current!r})"
            )
        settings["homebrew_fields"] = homebrew
        char.settings = settings
    else:
        raise ActionExecutionError(f"inc_property target '{target}' not supported")

    await session.flush()


async def execute_unequip(action, ctx, rfr, session, char, **kw):
    subject = ctx.subject
    if subject.get("_kind") != "item":
        raise ActionExecutionError("unequip requires subject=item")
    item = await _load_item(session, subject["_id"])
    item.is_equipped = False
    item.equipment_slot = None
    if item.item_type == "armor" and not char.base_armor_class_override:
        char.base_armor_class = 10
    elif item.item_type == "shield" and not char.shield_armor_class_override:
        char.shield_armor_class = 0
    await session.flush()


async def execute_damage_character(action, ctx, rfr, session, char, **kw):
    amount = _resolve_amount(action["amount"], ctx, field="damage_character.amount")

    # Absorb temp HP first (mirror hp.py:update_hp semantics)
    if char.temp_hp > 0:
        absorbed = min(char.temp_hp, amount)
        char.temp_hp -= absorbed
        amount -= absorbed

    before = char.current_hit_points
    char.current_hit_points = max(0, char.current_hit_points - amount)
    await session.flush()

    # Re-emit events with depth+1; existing stack + this rule's id.
    # Late import to avoid circular dependency (dispatcher → engine → actions).
    from api.services.homebrew.dispatcher import dispatch
    depth = kw.get("_depth", 0) + 1
    base_stack = kw.get("_stack", ())
    stack = base_stack + (rfr.rule_id,) if rfr.rule_id else base_stack
    await dispatch(
        session, char, "damage_taken",
        {"amount": amount, "was_critical_hit": False,
         "current_hp_before": before,
         "current_hp_after": char.current_hit_points},
        depth=depth, triggered_rule_stack=stack,
    )
    if before > 0 and char.current_hit_points == 0:
        await dispatch(
            session, char, "dropped_to_zero",
            {"damage_amount": amount, "from_critical": False},
            depth=depth, triggered_rule_stack=stack,
        )


async def execute_heal_character(action, ctx, rfr, session, char, **kw):
    amount = _resolve_amount(action["amount"], ctx, field="heal_character.amount")
    before = char.current_hit_points
    char.current_hit_points = min(char.hit_points, char.current_hit_points + amount)
    actual = char.current_hit_points - before

    # D&D 5e rule: HP above 0 resets death saves (per CLAUDE.md "HEAL/SET_CURRENT
    # automatically clears death saves when HP crosses from 0 to positive").
    if before == 0 and char.current_hit_points > 0:
        char.death_save_successes = 0
        char.death_save_failures = 0

    await session.flush()

    # Re-emit hp_healed (mirror damage_character's depth/stack threading).
    from api.services.homebrew.dispatcher import dispatch
    depth = kw.get("_depth", 0) + 1
    base_stack = kw.get("_stack", ())
    stack = base_stack + (rfr.rule_id,) if rfr.rule_id else base_stack
    await dispatch(
        session, char, "hp_healed",
        {"amount": actual,
         "current_hp_before": before,
         "current_hp_after": char.current_hit_points},
        depth=depth, triggered_rule_stack=stack,
    )


async def _load_resource(session: AsyncSession, char_id: int, key: str) -> HomebrewResource:
    res = await session.execute(
        select(HomebrewResource).where(
            HomebrewResource.character_id == char_id,
            HomebrewResource.key == key,
        )
    )
    obj = res.scalar_one_or_none()
    if obj is None:
        raise ActionExecutionError(f"Resource '{key}' not found for character")
    return obj


async def execute_change_resource(action, ctx, rfr, session, char, **kw):
    delta = _resolve_amount(action["delta"], ctx, field="change_resource.delta")
    resource = await _load_resource(session, char.id, action["key"])
    new = resource.current + delta
    new = max(0, min(resource.max, new))
    resource.current = new
    await session.flush()


async def execute_restore_resource(action, ctx, rfr, session, char, **kw):
    amount = action["amount"]
    resource = await _load_resource(session, char.id, action["key"])
    if amount == "max":
        resource.current = resource.max
        await session.flush()
        return
    amount = _resolve_amount(amount, ctx, field="restore_resource.amount")
    resource.current = min(resource.max, resource.current + amount)
    await session.flush()


# ---------------------------------------------------------------------------
# Custom conditions (Task 1.9)
# ---------------------------------------------------------------------------


async def execute_apply_condition(action, ctx, rfr, session, char, **kw):
    conditions = dict(char.conditions or {})
    conditions[action["key"]] = {
        "rule_id": rfr.rule_id,
        "params": action.get("params") or {},
    }
    char.conditions = conditions
    flag_modified(char, "conditions")
    await session.flush()


async def execute_remove_condition(action, ctx, rfr, session, char, **kw):
    conditions = dict(char.conditions or {})
    conditions.pop(action["key"], None)
    char.conditions = conditions
    flag_modified(char, "conditions")
    await session.flush()


# ---------------------------------------------------------------------------
# Retroactive permanent modifiers (Task 1.10)
# ---------------------------------------------------------------------------


def _eval_delta(delta, char) -> int:
    if isinstance(delta, int):
        return delta
    if isinstance(delta, str):
        # Support "N*level" syntax — extract N
        s = delta.strip().lower()
        if s.endswith("*level"):
            try:
                n = int(s[:-len("*level")].strip())
            except ValueError:
                raise ActionExecutionError(f"Invalid expression: {delta}")
            return n * char.total_level
        # Otherwise treat as dice notation
        return _roll(delta)
    raise ActionExecutionError(f"Unsupported delta type: {type(delta)}")


async def execute_apply_modifier_once(action, ctx, rfr, session, char, **kw):
    target = action["target"]
    delta = _eval_delta(action["delta"], char)
    label = action["label"]

    if target == "character.hit_points_max":
        char.hit_points = max(0, char.hit_points + delta)
        # Clamp current HP to new max
        char.current_hit_points = min(char.current_hit_points, char.hit_points)
    elif target == "character.speed":
        char.speed = max(0, char.speed + delta)
    else:
        raise ActionExecutionError(
            f"apply_modifier_once target '{target}' not supported (MVP: hit_points_max, speed)"
        )

    rfr.add_history_entry(f"{label}: {target} {'+' if delta >= 0 else ''}{delta}")
    await session.flush()


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_ACTION_HANDLERS = {
    "roll_dice": execute_roll_dice,
    "lookup_table": execute_lookup_table,
    "match": execute_match,
    "if": execute_if,
    "notify": execute_notify,
    "add_history": execute_add_history,
}

# Async DB-mutating handlers — must be awaited.
_ASYNC_HANDLERS = {
    "set_property": execute_set_property,
    "inc_property": execute_inc_property,
    "unequip": execute_unequip,
    "damage_character": execute_damage_character,
    "heal_character": execute_heal_character,
    "change_resource": execute_change_resource,
    "restore_resource": execute_restore_resource,
    "apply_condition": execute_apply_condition,
    "remove_condition": execute_remove_condition,
    "apply_modifier_once": execute_apply_modifier_once,
}


async def execute_action(action, ctx, rfr, session, char, **kw):
    """Dispatch a single action. Handles both sync and async handlers."""
    name = action["action"]
    if name in _ASYNC_HANDLERS:
        await _ASYNC_HANDLERS[name](action, ctx, rfr, session, char, **kw)
        return
    if name in _ACTION_HANDLERS:
        result = _ACTION_HANDLERS[name](action, ctx, rfr, session, char, **kw)
        if asyncio.iscoroutine(result):
            await result
        return
    raise ActionExecutionError(f"No handler for action: {name}")
