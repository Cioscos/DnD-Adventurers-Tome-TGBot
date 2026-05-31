"""Pure D&D 5e attack-profile helpers (no DB, no I/O).

Currently covers the unarmed strike, including the Monk's Martial Arts die.
"""
from __future__ import annotations


def martial_arts_die(monk_level: int) -> str:
    """Return the Monk Martial Arts damage die for a given Monk level.

    1d4 (1-4), 1d6 (5-10), 1d8 (11-16), 1d10 (17-20). Empty string for level 0
    (not a Monk).
    """
    if monk_level <= 0:
        return ""
    if monk_level < 5:
        return "1d4"
    if monk_level < 11:
        return "1d6"
    if monk_level < 17:
        return "1d8"
    return "1d10"


def unarmed_strike_profile(
    str_mod: int, dex_mod: int, monk_level: int
) -> tuple[int, str]:
    """Return (ability_mod, damage_dice) for an unarmed strike.

    - Non-Monk: STR mod, flat ``"1"`` damage (bludgeoning, +mod).
    - Monk: best of STR/DEX, Martial Arts die for the level (always >= flat 1).
    """
    if monk_level > 0:
        return max(str_mod, dex_mod), martial_arts_die(monk_level)
    return str_mod, "1"
