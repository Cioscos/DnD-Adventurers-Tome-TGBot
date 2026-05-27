"""Path resolver for the homebrew DSL.

Resolves dollar-prefixed paths into values, given an execution context:
- $event.X      → ctx['event'][X]
- $subject      → ctx['subject'] (entire dict)
- $subject.X    → for items: ctx['subject']['metadata']['hb_X'] (falls back to top-level)
                  for character/ability: ctx['subject'][X]
- $character.X  → ctx['character'][X]
- $<var>        → ctx['vars'][<var>]

Literal values (non-strings, or strings not starting with $) are returned unchanged.
"""
from __future__ import annotations

from typing import Any


class PathResolutionError(LookupError):
    """Raised when a path cannot be resolved."""


def resolve_path(path: Any, ctx: dict) -> Any:
    if not isinstance(path, str) or not path.startswith("$"):
        return path

    bare = path[1:]  # strip leading $
    if "." not in bare:
        # $subject / $character / $event / $<var>
        if bare == "subject":
            return ctx.get("subject") or {}
        if bare == "character":
            return ctx.get("character") or {}
        if bare == "event":
            return ctx.get("event") or {}
        vars_ = ctx.get("vars") or {}
        if bare in vars_:
            return vars_[bare]
        raise PathResolutionError(f"Unknown variable: ${bare}")

    head, _, tail = bare.partition(".")
    if head == "event":
        d = ctx.get("event") or {}
        if tail not in d:
            raise PathResolutionError(f"Missing event field: $event.{tail}")
        return d[tail]
    if head == "character":
        d = ctx.get("character") or {}
        if tail not in d:
            raise PathResolutionError(f"Missing character field: $character.{tail}")
        return d[tail]
    if head == "subject":
        subject = ctx.get("subject") or {}
        kind = subject.get("_kind")
        # For items, lookup in metadata under hb_<key> prefix
        if kind == "item":
            md = subject.get("metadata") or {}
            hb_key = f"hb_{tail}"
            if hb_key in md:
                return md[hb_key]
            if tail in subject:
                return subject[tail]
            raise PathResolutionError(f"Missing subject property: $subject.{tail}")
        # For character/ability, lookup top-level
        if tail in subject:
            return subject[tail]
        raise PathResolutionError(f"Missing subject field: $subject.{tail}")

    raise PathResolutionError(f"Unknown path namespace: {path}")
