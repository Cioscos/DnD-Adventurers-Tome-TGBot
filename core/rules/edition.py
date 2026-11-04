"""Edizione delle regole seguita da un personaggio."""
from __future__ import annotations

from typing import Any

from core.rules.types import Edition

EDITIONS: tuple[Edition, ...] = ("2014", "2024")


def character_edition(char: Any) -> Edition:
    """Edizione del personaggio; `None` e valori ignoti valgono 2014."""
    value = getattr(char, "rules_edition", None)
    return value if value in EDITIONS else "2014"
