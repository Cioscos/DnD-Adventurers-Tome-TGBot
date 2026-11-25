"""Danno delle opzioni di tiro sul danno di un attacco, condiviso da armi, incantesimi e compagni."""
from __future__ import annotations

import random

from api.services.rules_options import roll_option_dice
from core.db.models import Character
from core.rules.roll_options import AppliedOptions, scale_damage


def option_damage(
    char: Character, opts: AppliedOptions, is_critical: bool, damage: int, reroll: int = 0, floor: int = 0,
) -> tuple[list[int], int, int]:
    """Dadi delle opzioni al danno: (valori, loro totale, danno finale).

    ``reroll``: i dadi che mostrano al più questo valore si ritirano una volta, come quelli dell'arma (Combattere con
    Armi Possenti 2014, pag. 72: «un dado dei danni» dell'attacco, anche il dado di superiorità o la punizione).
    ``floor``: i dadi che mostrano meno contano questo valore (Combattere con Armi a Due Mani 2024, pag. 209)."""
    rolls, total = roll_option_dice(char, opts, is_critical)
    for i, (sides, value) in enumerate(opts.rolled_dice):
        # una volta sola: il nuovo risultato vale anche se è ancora basso
        new = max(floor, random.randint(1, sides) if value <= reroll else value)
        if new != value:
            opts.rolled_dice[i], rolls[i], total = (sides, new), new, total + new - value
    opts.damage_unscaled = damage + total
    return rolls, total, scale_damage(damage + total, opts.multiplier)
