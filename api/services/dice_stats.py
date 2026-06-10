"""Contatori cumulativi dei tiri di dado (Character.dice_stats).

Struttura: ``{"d20": {"1": 3, "20": 2}, "d6": {"4": 10}}`` — solo conteggi per
faccia; media, totali e trofei sono derivati a lettura. I dict vengono
sostituiti (mai mutati in place) così il change tracking SQLAlchemy vede
sempre un'identità nuova, con ``flag_modified`` come cintura di sicurezza.
"""
from __future__ import annotations

from typing import Iterable

from sqlalchemy.orm.attributes import flag_modified

from core.db.models import Character


def record_dice(char: Character, rolls: Iterable[tuple[str, int]]) -> None:
    """Accumula i tiri (kind, valore) nelle statistiche del personaggio."""
    rolls = list(rolls)
    if not rolls:
        return
    stats: dict = dict(char.dice_stats or {})
    for kind, value in rolls:
        kind_stats = dict(stats.get(kind, {}))
        key = str(value)
        kind_stats[key] = int(kind_stats.get(key, 0)) + 1
        stats[kind] = kind_stats
    char.dice_stats = stats
    flag_modified(char, "dice_stats")
