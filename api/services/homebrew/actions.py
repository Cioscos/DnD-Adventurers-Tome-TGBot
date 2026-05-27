"""Action implementations. Each function follows signature:

    def execute_<action>(payload, ctx, rfr, session, char, **kwargs) -> None
"""
from __future__ import annotations

import random
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from api.services.homebrew.dsl import Filter, RuleDSL
from api.services.homebrew.exceptions import ActionExecutionError
from api.services.homebrew.filters import evaluate_filter
from api.services.homebrew.path_resolver import resolve_path
from api.services.homebrew.types import ExecutionContext, Notification, RuleFiringResult


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


def execute_match(action, ctx, rfr, session, char, **kw):
    val = _resolve_or_value(action["value"], ctx)
    branch = action["cases"].get(str(val))
    if branch is None:
        return  # no matching case = no-op
    for sub_action in branch:
        execute_action(sub_action, ctx, rfr, session, char, **kw)


def execute_if(action, ctx, rfr, session, char, **kw):
    cond = Filter.model_validate(action["cond"])
    if evaluate_filter(cond, ctx.to_dict()):
        branch = action.get("then", [])
    else:
        branch = action.get("else", [])
    for sub_action in branch:
        execute_action(sub_action, ctx, rfr, session, char, **kw)


# Placeholder — populated in subsequent tasks.
_ACTION_HANDLERS = {
    "roll_dice": execute_roll_dice,
    "lookup_table": execute_lookup_table,
    "match": execute_match,
    "if": execute_if,
}


def execute_action(action, ctx, rfr, session, char, **kw):
    """Dispatch a single action by its 'action' field."""
    handler = _ACTION_HANDLERS.get(action["action"])
    if handler is None:
        raise ActionExecutionError(f"No handler for action: {action['action']}")
    handler(action, ctx, rfr, session, char, **kw)
