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

from api.services.homebrew.dsl import Filter, RuleDSL
from api.services.homebrew.exceptions import ActionExecutionError
from api.services.homebrew.filters import evaluate_filter
from api.services.homebrew.path_resolver import resolve_path
from api.services.homebrew.types import ExecutionContext, Notification, RuleFiringResult
from core.db.models import Character, Item


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


def _format_message(template: str, ctx: ExecutionContext) -> str:
    """Substitute $path placeholders in a message template."""
    def _replace(m):
        path = m.group(0)
        try:
            v = resolve_path(path, ctx.to_dict())
            return str(v)
        except Exception:
            return path  # leave as-is if unresolvable
    return _PLACEHOLDER_RE.sub(_replace, template)


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


async def execute_inc_property(action, ctx, rfr, session, char, **kw):
    delta = action["delta"]
    if isinstance(delta, str):
        delta = _roll(delta)

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
