"""Il danno finale di un attacco o di un incantesimo, tenuto da parte per i privilegi che ritirano i dadi dopo averli visti.

Un solo formato per arma, incantesimo e compagno (``turn_state["last_damage"]``):

- ``dice``: ``[lati, valore]`` di tutti i dadi ritirabili, nell'ordine in cui il client li mostra: prima quelli di base
  (``base`` dadi, critico compreso), poi quelli aggiunti dalle opzioni;
- ``mod``: il modificatore del danno di base, non tagliato; ``flat``: il resto (fisso delle opzioni, bonus);
- ``multiplier``: moltiplicatore finale, ``main``: quanti dei dadi di base sono del tiro principale (per gli incantesimi).
"""
from __future__ import annotations

from typing import Any

from core.rules.roll_options import scale_damage


def last_damage_total(values: list[int], last: dict[str, Any]) -> int:
    """Come il flusso dell'attacco: il danno di base non scende sotto 0, poi i dadi delle opzioni, il fisso e il moltiplicatore."""
    base = last.get("base", len(values))
    cut = max(0, sum(values[:base]) + last.get("mod", 0))
    return scale_damage(cut + sum(values[base:]) + last["flat"], last["multiplier"])


def pairs(rolled: list[tuple[int, int]] | list[list[int]]) -> list[list[int]]:
    return [[int(sides), int(value)] for sides, value in rolled]
