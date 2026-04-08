"""D&D 5e standard skills list and ability score associations.

Each entry is a tuple of (skill_slug, ability_name).  The list is ordered
alphabetically by slug for consistent display.  Use SKILL_ABILITY_MAP for
O(1) lookups by slug.
"""

from __future__ import annotations

# 18 standard D&D 5e skills — (slug, associated_ability_name)
SKILLS: list[tuple[str, str]] = [
    ("acrobatics",      "dexterity"),
    ("animal_handling", "wisdom"),
    ("arcana",          "intelligence"),
    ("athletics",       "strength"),
    ("deception",       "charisma"),
    ("history",         "intelligence"),
    ("insight",         "wisdom"),
    ("intimidation",    "charisma"),
    ("investigation",   "intelligence"),
    ("medicine",        "wisdom"),
    ("nature",          "intelligence"),
    ("perception",      "wisdom"),
    ("performance",     "charisma"),
    ("persuasion",      "charisma"),
    ("religion",        "intelligence"),
    ("sleight_of_hand", "dexterity"),
    ("stealth",         "dexterity"),
    ("survival",        "wisdom"),
]

# Dict version for O(1) lookup: slug → ability_name
SKILL_ABILITY_MAP: dict[str, str] = dict(SKILLS)
