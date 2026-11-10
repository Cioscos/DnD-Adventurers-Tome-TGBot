"""Danno delle opzioni di tiro sul danno di un attacco, condiviso da armi, incantesimi e compagni."""
from __future__ import annotations

from api.services.rules_options import roll_option_dice
from core.db.models import Character
from core.rules.roll_options import AppliedOptions, scale_damage


def option_damage(char: Character, opts: AppliedOptions, is_critical: bool, damage: int) -> tuple[list[int], int, int]:
    """Dadi delle opzioni al danno: (valori, loro totale, danno finale)."""
    rolls, total = roll_option_dice(char, opts, is_critical)
    opts.damage_unscaled = damage + total
    return rolls, total, scale_damage(damage + total, opts.multiplier)
