"""Pure helpers computing redacted session-view properties for a Character.

These helpers are consumed by the FastAPI session endpoints when serving the
privacy-redacted live snapshot to non-GM, non-owner viewers. They live in
core/utils/ so they can be shared by future bot/webapp code without a
FastAPI or Pydantic dependency.
"""

from __future__ import annotations

import json
from typing import Literal

from core.db.models import Character

HpBucket = Literal["healthy", "lightly_wounded", "badly_wounded", "dying", "dead"]
ArmorCategory = Literal["unarmored", "light", "medium", "heavy"]


def hp_bucket(char: Character) -> HpBucket:
    """Return the bucket label that summarises the character's HP."""
    death_saves = char.death_saves or {}
    if int(death_saves.get("failures", 0) or 0) >= 3:
        return "dead"
    current = int(char.current_hit_points or 0)
    if current <= 0:
        # A stabilized character (3 successful death saves) is down but no
        # longer actively dying — communicate that as badly_wounded.
        if bool(death_saves.get("stable")):
            return "badly_wounded"
        return "dying"
    total = int(char.hit_points or 0)
    if total <= 0:
        return "healthy"
    pct = (current / total) * 100
    if pct >= 76:
        return "healthy"
    if pct >= 51:
        return "lightly_wounded"
    return "badly_wounded"


def armor_category(char: Character) -> ArmorCategory:
    """Return the category of the currently equipped armor, or 'unarmored'."""
    for item in char.items or []:
        if item.item_type != "armor" or not item.is_equipped:
            continue
        raw = item.item_metadata or ""
        if not raw:
            continue
        try:
            meta = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        category = meta.get("armor_type")
        if category in ("light", "medium", "heavy"):
            return category
        return "unarmored"
    return "unarmored"
