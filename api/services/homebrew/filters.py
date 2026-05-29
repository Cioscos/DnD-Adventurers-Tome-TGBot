"""Filter operator evaluation."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Union

from api.services.homebrew.dsl import Filter, FilterOp
from api.services.homebrew.path_resolver import resolve_path


def _coerce_num(v: object) -> Union[int, float, None]:
    """Try to coerce *v* to a numeric type for ordered/equality comparisons.

    Booleans are intentionally excluded — ``True`` and ``False`` must never
    be treated as 1 and 0 in DSL filter comparisons.
    Returns ``None`` when coercion is not possible.
    """
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        s = v.strip()
        try:
            return int(s)
        except ValueError:
            try:
                return float(s)
            except ValueError:
                return None
    return None


def evaluate_filter(f: Filter, ctx: dict) -> bool:
    """Evaluate a single Filter against the execution context."""
    if f.op == FilterOp.HAS_PROPERTY:
        # value is the property KEY; path resolves to the subject dict
        target = resolve_path(f.path, ctx)
        if not isinstance(target, dict):
            return False
        if target.get("_kind") == "item":
            md = target.get("metadata") or {}
            if not isinstance(md, dict):
                return False
            return f"hb_{f.value}" in md
        return f.value in target

    lhs = resolve_path(f.path, ctx)
    rhs = f.value

    if f.op == FilterOp.EQ:
        # If at least one side is a number (non-bool), attempt numeric coercion
        # so that ``5 == "5"`` evaluates to True.
        if isinstance(lhs, (int, float)) and not isinstance(lhs, bool):
            rhs_num = _coerce_num(rhs)
            if rhs_num is not None:
                return lhs == rhs_num
        elif isinstance(rhs, (int, float)) and not isinstance(rhs, bool):
            lhs_num = _coerce_num(lhs)
            if lhs_num is not None:
                return lhs_num == rhs
        return lhs == rhs

    if f.op == FilterOp.NEQ:
        # Mirror of EQ coercion logic.
        if isinstance(lhs, (int, float)) and not isinstance(lhs, bool):
            rhs_num = _coerce_num(rhs)
            if rhs_num is not None:
                return lhs != rhs_num
        elif isinstance(rhs, (int, float)) and not isinstance(rhs, bool):
            lhs_num = _coerce_num(lhs)
            if lhs_num is not None:
                return lhs_num != rhs
        return lhs != rhs

    # Ordered comparisons: coerce both sides to numbers; if either is None
    # (non-numeric, None value, or bool), return False rather than crash.
    if f.op in (FilterOp.LT, FilterOp.LTE, FilterOp.GT, FilterOp.GTE):
        lhs_num = _coerce_num(lhs)
        rhs_num = _coerce_num(rhs)
        if lhs_num is None or rhs_num is None:
            return False
        try:
            if f.op == FilterOp.LT:
                return lhs_num < rhs_num
            if f.op == FilterOp.LTE:
                return lhs_num <= rhs_num
            if f.op == FilterOp.GT:
                return lhs_num > rhs_num
            if f.op == FilterOp.GTE:
                return lhs_num >= rhs_num
        except (TypeError, ValueError):
            return False

    if f.op == FilterOp.IN:
        # Reject strings explicitly: `lhs in "abc"` is substring matching, a footgun.
        if isinstance(rhs, str) or not isinstance(rhs, Iterable):
            return False
        return lhs in rhs
    raise ValueError(f"Unhandled filter op: {f.op}")


def evaluate_filters(filters: list[Filter], ctx: dict) -> bool:
    """AND across all filters. Short-circuits on first False."""
    return all(evaluate_filter(f, ctx) for f in filters)
