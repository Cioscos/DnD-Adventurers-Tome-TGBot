"""Predicati e costruttori comuni ai cataloghi di classe (foglia: nessun import da ``core.rules.modifiers``)."""
from __future__ import annotations

from typing import Any

from core.rules.states import has_state
from core.rules.types import FeatureSpec, RuleContext
from core.utils.session_view import armor_category

INCAPACITATING = ("incapacitated", "paralyzed", "petrified", "stunned", "unconscious")


def heavy_armor(char: Any) -> bool:
    return armor_category(char) == "heavy"


def state_on(ctx: RuleContext, key: str) -> bool:
    return has_state(ctx.char, key)


def cannot_perceive_or_act(char: Any) -> bool:
    """Accecato, assordato o incapacitato (Percezione del Pericolo non funziona)."""
    conditions = char.conditions or {}
    return any(conditions.get(c) for c in ("blinded", "deafened", *INCAPACITATING))


def once_used(char: Any, key: str) -> bool:
    return key in ((getattr(char, "turn_state", None) or {}).get("once_per_turn") or [])


def attacks_made(ctx: RuleContext) -> int:
    return int((ctx.turn or {}).get("attacks_made") or 0)


def feature(key: str, class_key: str, edition: str, level: int, title: str, name: tuple[str, str],
            summary: tuple[str, str], action_type: str | None = None, **kw: Any) -> FeatureSpec:
    """Scorciatoia per le righe del catalogo: ``name`` e ``summary`` sono coppie (it, en)."""
    kw.setdefault("passive", action_type is None and kw.get("on_use") is None)
    return FeatureSpec(
        key=f"{class_key}.{key}", class_key=class_key, edition=edition, level=level, source_title=title,
        name={"it": name[0], "en": name[1]}, summary={"it": summary[0], "en": summary[1]},
        action_type=action_type, **kw)
