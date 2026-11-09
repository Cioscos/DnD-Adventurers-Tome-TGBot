"""Edizione delle regole seguita da un personaggio."""
from __future__ import annotations

from typing import Any

from core.data.spell_slots import normalize_class_name
from core.rules.types import Edition

EDITIONS: tuple[Edition, ...] = ("2014", "2024")


def character_edition(char: Any) -> Edition:
    """Edizione del personaggio; `None` e valori ignoti valgono 2014."""
    value = getattr(char, "rules_edition", None)
    return value if value in EDITIONS else "2014"


CLASS_KEYS: tuple[str, ...] = (
    "barbarian", "bard", "cleric", "druid", "fighter", "monk",
    "paladin", "ranger", "rogue", "sorcerer", "warlock", "wizard",
)


def class_key(char_class: Any) -> str | None:
    """Chiave inglese della classe (`Mago`/`wizard`/`Wizard` -> `wizard`); `None` se custom."""
    return normalize_class_name(getattr(char_class, "class_name", None))
