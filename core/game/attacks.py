"""Pure D&D 5e attack-profile helpers (no DB, no I/O).

Currently covers the unarmed strike, including the Monk's Martial Arts die.
"""
from __future__ import annotations


def martial_arts_die(monk_level: int, edition: str = "2014") -> str:
    """Return the Monk Martial Arts damage die for a given Monk level.

    Thresholds 1/5/11/17: 2014 d4, d6, d8, d10; 2024 d6, d8, d10, d12.
    Empty string for level 0 (not a Monk).
    """
    if monk_level <= 0:
        return ""
    step = (monk_level >= 5) + (monk_level >= 11) + (monk_level >= 17)
    return f"1d{(6 if edition == '2024' else 4) + 2 * step}"


def unarmed_strike_profile(
    str_mod: int, dex_mod: int, monk_level: int, edition: str = "2014"
) -> tuple[int, str]:
    """Return (ability_mod, damage_dice) for an unarmed strike.

    - Non-Monk: STR mod, flat ``"1"`` damage (bludgeoning, +mod).
    - Monk: best of STR/DEX, Martial Arts die for the level (always >= flat 1).
    """
    if monk_level > 0:
        return max(str_mod, dex_mod), martial_arts_die(monk_level, edition)
    return str_mod, "1"
