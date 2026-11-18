"""Notazione dei dadi «2d6+2»: riconoscimento e tiro, condivisi dai router."""
from __future__ import annotations

import random
import re

# Tetti (999 dadi, 9999 facce, facce >= 1): la stringa arriva dall'utente e i dadi si tirano uno a uno nel processo dell'API.
DICE_RE = re.compile(r"^(\d{1,3})d([1-9]\d{0,3})([+-]\d+)?$", re.IGNORECASE)


def roll_dice(notation: str) -> tuple[list[int], int]:
    """Roll dice from notation like '1d8' or '2d6+2'. Returns (rolls, bonus)."""
    m = DICE_RE.match(notation.strip())
    if not m:
        return [0], 0
    count = int(m.group(1))
    sides = int(m.group(2))
    bonus = int(m.group(3)) if m.group(3) else 0
    rolls = [random.randint(1, sides) for _ in range(count)]
    return rolls, bonus
