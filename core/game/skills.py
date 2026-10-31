"""Pure skill math (proficiency, Jack of All Trades); totals with homebrew live in api.services.skills."""
from __future__ import annotations

from core.data.spell_slots import normalize_class_name
from core.db.models import Character

PASSIVE_SKILLS = ("perception", "insight", "investigation")


def has_jack_of_all_trades(char: Character) -> bool:
    """Bard level 2+ (computed, never stored)."""
    return any(
        normalize_class_name(c.class_name) == "bard" and c.level >= 2
        for c in char.classes
    )


def skill_proficiency_part(char: Character, skill: str) -> int:
    """PB x {expert 2, proficient 1}; Jack of All Trades adds floor(PB/2) when not proficient."""
    level = (char.skills or {}).get(skill)
    pb = char.proficiency_bonus
    if level == "expert":
        return 2 * pb
    if level is True or level == 1:
        return pb
    return pb // 2 if has_jack_of_all_trades(char) else 0
