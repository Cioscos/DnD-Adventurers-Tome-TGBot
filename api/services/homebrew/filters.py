"""Filter operator evaluation."""
from __future__ import annotations

from collections.abc import Iterable

from api.services.homebrew.dsl import Filter, FilterOp
from api.services.homebrew.path_resolver import resolve_path


def evaluate_filter(f: Filter, ctx: dict) -> bool:
    """Evaluate a single Filter against the execution context."""
    if f.op == FilterOp.HAS_PROPERTY:
        # value is the property KEY; path resolves to the subject dict
        target = resolve_path(f.path, ctx)
        if not isinstance(target, dict):
            return False
        if target.get("_kind") == "item":
            md = target.get("metadata") or {}
            return f"hb_{f.value}" in md
        return f.value in target

    lhs = resolve_path(f.path, ctx)
    rhs = f.value

    if f.op == FilterOp.EQ:
        return lhs == rhs
    if f.op == FilterOp.NEQ:
        return lhs != rhs
    if f.op == FilterOp.LT:
        return lhs < rhs
    if f.op == FilterOp.LTE:
        return lhs <= rhs
    if f.op == FilterOp.GT:
        return lhs > rhs
    if f.op == FilterOp.GTE:
        return lhs >= rhs
    if f.op == FilterOp.IN:
        if not isinstance(rhs, Iterable):
            return False
        return lhs in rhs
    raise ValueError(f"Unhandled filter op: {f.op}")


def evaluate_filters(filters: list[Filter], ctx: dict) -> bool:
    """AND across all filters. Short-circuits on first False."""
    return all(evaluate_filter(f, ctx) for f in filters)
