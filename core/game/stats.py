"""Pure compute functions for D&D 5e character mechanics.

No side effects, no database access. Safe to unit-test in isolation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal


ABILITY_NAMES = (
    "strength",
    "dexterity",
    "constitution",
    "intelligence",
    "wisdom",
    "charisma",
)

ModifierKind = Literal["absolute", "relative"]


@dataclass(frozen=True)
class AppliedModifier:
    """A single ability modifier applied from an equipped item.

    Used for response breakdown on the frontend (Stats page).
    """
    source: str          # item name
    ability: str         # one of ABILITY_NAMES
    kind: ModifierKind
    value: int
    item_id: int


def hit_points_for_level(hit_die: int, con_mod: int, level: int) -> int:
    """HP gained for a single level-up event.

    Level 1: ``hit_die + con_mod`` (PHB max die value).
    Level 2+: ``(hit_die // 2 + 1) + con_mod`` (fixed method).

    The result is always clamped to a minimum of 1 (PHB rule:
    a level gives at least 1 HP even with very negative CON).
    """
    if level < 1:
        raise ValueError(f"level must be >= 1, got {level}")
    if hit_die <= 0:
        raise ValueError(f"hit_die must be > 0, got {hit_die}")

    if level == 1:
        raw = hit_die + con_mod
    else:
        raw = (hit_die // 2 + 1) + con_mod

    return max(1, raw)


def total_base_hp(
    classes: "Iterable[_ClassLike]",
    con_mod: int,
) -> int:
    """Sum of HP across every level of every class.

    The 'first class' (lowest id, i.e. DB insertion order) owns the
    character's level-1 slot and uses the level-1 formula.
    All other levels (including level 1 of any additional multiclass)
    use the level 2+ formula.

    Returns 0 if classes is empty.
    """
    sorted_classes = sorted(classes, key=lambda c: c.id)
    if not sorted_classes:
        return 0

    total = 0
    first_level_consumed = False

    for cls in sorted_classes:
        for level_within_class in range(1, cls.level + 1):
            if not first_level_consumed:
                total += hit_points_for_level(cls.hit_die, con_mod, 1)
                first_level_consumed = True
            else:
                total += hit_points_for_level(cls.hit_die, con_mod, 2)

    return total


def effective_ability_score(
    ability_name: str,
    base_value: int,
    equipped_items: "Iterable[_ItemLike]",
) -> tuple[int, list[AppliedModifier]]:
    """Compute the effective ability score after equipped-item modifiers.

    Stacking rule:
      - Sum of all *relative* modifiers for this ability
      - Max of all *absolute* modifiers for this ability (if any)
      - Final = max(base + sum(rel), max(abs)) if any absolute exists,
                else base + sum(rel)

    No cap applied (homebrew-friendly).

    Returns (effective_value, list_of_applied_modifiers_for_breakdown).
    """
    if ability_name not in ABILITY_NAMES:
        raise ValueError(f"unknown ability: {ability_name}")

    applied: list[AppliedModifier] = []
    relative_sum = 0
    absolutes: list[int] = []

    for item in equipped_items:
        mods = _extract_ability_modifiers(item)
        for mod in mods:
            if mod.get("ability") != ability_name:
                continue
            kind = mod.get("kind")
            value = mod.get("value")
            if not isinstance(value, int):
                continue
            if kind == "relative":
                relative_sum += value
                applied.append(AppliedModifier(
                    source=item.name,
                    ability=ability_name,
                    kind="relative",
                    value=value,
                    item_id=item.id,
                ))
            elif kind == "absolute":
                absolutes.append(value)
                applied.append(AppliedModifier(
                    source=item.name,
                    ability=ability_name,
                    kind="absolute",
                    value=value,
                    item_id=item.id,
                ))

    base_plus_rel = base_value + relative_sum
    if absolutes:
        effective = max(base_plus_rel, max(absolutes))
    else:
        effective = base_plus_rel

    return effective, applied


def _extract_ability_modifiers(item: "_ItemLike") -> list[dict]:
    """Read `ability_modifiers` from an item's metadata (parsed JSON).

    Defensive: returns empty list on any parse / structure error.
    """
    import json as _json

    raw = item.item_metadata
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            parsed = _json.loads(raw)
        except (ValueError, TypeError):
            return []
    else:
        parsed = raw

    if not isinstance(parsed, dict):
        return []
    mods = parsed.get("ability_modifiers")
    if not isinstance(mods, list):
        return []
    return [m for m in mods if isinstance(m, dict)]


# --- Structural typing (Protocol-like) ----------------------------------
# We intentionally avoid `Protocol` here so the module stays dependency-free
# and does not require importing SQLAlchemy models. Callers pass in anything
# with matching attribute shape.

class _ClassLike:
    id: int
    level: int
    hit_die: int


class _ItemLike:
    id: int
    name: str
    item_metadata: str | dict | None
