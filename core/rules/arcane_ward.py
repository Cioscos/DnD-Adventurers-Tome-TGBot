"""Interdizione Arcana (Mago 2014, Scuola di Abiurazione): lo stato che assorbe i danni prima dei PF.

Funzioni pure su ``Character.active_states``. L'interdizione è una sola finché non si completa un riposo lungo (lo stato
finisce lì): a 0 PF resta, non assorbe, e ogni abiurazione la ricarica.
"""
from __future__ import annotations

from typing import Any

from core.rules.states import get_states

KEY = "arcane_ward"


def ward_state(char: Any) -> dict | None:
    return next((s for s in get_states(char) if s.get("key") == KEY), None)


def ward_max(char: Any, row: Any) -> int:
    """2 x livello da mago + modificatore di Intelligenza."""
    from core.game.stats import effective_ability_mod  # import locale: stats usa il catalogo
    return max(0, 2 * row.level + effective_ability_mod(char, "intelligence"))


def _set_hp(char: Any, hp: int, maximum: int) -> None:
    char.active_states = [{**s, "data": {**(s.get("data") or {}), "hp": hp, "max": maximum}} if s.get("key") == KEY else s
                          for s in get_states(char)]


def on_abjuration(char: Any, row: Any, spell_level: int, begin) -> None:
    """Si è lanciata un'abiurazione di 1° livello o superiore: crea l'interdizione piena, o ricarica quella che c'è di
    2 x il livello dell'incantesimo, mai oltre il massimo. ``begin(state_key, hp, maximum)`` avvia lo stato."""
    maximum = ward_max(char, row)
    current = ward_state(char)
    if current is None:
        begin(maximum, maximum)
        return
    hp = int((current.get("data") or {}).get("hp") or 0)
    _set_hp(char, min(maximum, hp + 2 * spell_level), maximum)


def absorb(char: Any, damage: int) -> int:
    """L'interdizione prende il danno al posto del mago, fino ai suoi PF. Restituisce quanto ha assorbito."""
    ward = ward_state(char)
    hp = int(((ward or {}).get("data") or {}).get("hp") or 0)
    taken = min(hp, max(0, damage))
    if taken:
        _set_hp(char, hp - taken, int((ward["data"]).get("max") or hp))
    return taken
