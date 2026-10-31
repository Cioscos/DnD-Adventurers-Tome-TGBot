"""Economia d'azione: parser di tempi di lancio / durate e attacchi per azione (5e 2014)."""
from __future__ import annotations

import re
from typing import Iterable, Literal

from core.data.classes import EXTRA_ATTACK_LEVELS
from core.data.spell_slots import normalize_class_name

ActionType = Literal["action", "bonus_action", "reaction", "free", "special"]

# Bonus prima di azione: "1 azione bonus" inizia con "1 azione".
_CASTING_TIME = re.compile(r"^1\s+(?:(azione bonus|bonus action)|(azione|action)|(reazione|reaction))\b")


def parse_casting_time(text: str | None) -> ActionType | None:
    """Tempo di lancio -> tipo di azione; il testo dopo la virgola è ignorato."""
    m = _CASTING_TIME.match((text or "").split(",")[0].strip().lower())
    if not m:
        return None
    return "bonus_action" if m.group(1) else "action" if m.group(2) else "reaction"


_DURATION = re.compile(r"(\d+)\s*(rounds?|minut\w*|hours?|ore|ora)\b")
_ROUNDS_PER_UNIT = {"round": 1, "minut": 10, "hour": 600, "or": 600}


def parse_duration_rounds(text: str | None) -> int | None:
    """Durata -> round (1 minuto = 10 round); istantanea, speciale, giorni e altro -> None."""
    m = _DURATION.search((text or "").lower())
    if not m:
        return None
    unit = next(v for k, v in _ROUNDS_PER_UNIT.items() if m.group(2).startswith(k))
    return int(m.group(1)) * unit


def attacks_per_action(classes: Iterable) -> int:
    """Attacchi per azione Attacco: massimo fra le classi (Extra Attack non si somma)."""
    best = 1
    for c in classes:
        levels = EXTRA_ATTACK_LEVELS.get(normalize_class_name(c.class_name), ())
        best = max(best, 1 + sum(c.level >= lv for lv in levels))
    return best
