"""Item charges: recharge planning (pure) and application on rest."""
from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass

from core.game.item_bonuses import item_meta

_DICE = re.compile(r"^(\d+)d(\d+)([+-]\d+)?$", re.IGNORECASE)
# A long rest also restores short-rest charges (same rule as abilities/resources).
_RECHARGES = {"long": ("long_rest", "dawn", "short_rest"), "short": ("short_rest",)}


@dataclass
class ItemRecharge:
    item: object
    before: int
    after: int | None  # None = dice amount not rolled (preview)
    formula: str


def _has_use_magic_device(char) -> bool:
    from core.rules.catalog import active_features  # import locale: il catalogo importa i servizi
    return any(spec.key == "rogue.use_magic_device" and spec.edition == "2024" for spec, _row in active_features(char))


def attunement_limit(char) -> int:
    """Oggetti con sintonia: 3, e 4 con Usare Dispositivi Magici (Furfante 2024, 13°)."""
    return 4 if _has_use_magic_device(char) else 3


def has_use_magic_device(char) -> bool:
    return _has_use_magic_device(char)


def charge_die(char) -> int | None:
    """Una spesa di cariche: con Usare Dispositivi Magici si tira 1d6 e con 6 non si spende nulla. ``None`` senza il privilegio."""
    return random.randint(1, 6) if _has_use_magic_device(char) else None


def charge_note(rolled: int | None) -> list[dict]:
    """L'esito del d6 come notifica della risposta (il client le mostra tutte): vuoto senza tiro."""
    if rolled is None:
        return []
    saved = rolled == 6
    return [{"severity": "success" if saved else "info", "rule_id": None, "rule_name": "Usare Dispositivi Magici",
             "message": f"d6 = {rolled}: " + ("nessuna carica spesa" if saved else "cariche spese")}]


def _roll_amount(formula: str) -> int:
    m = _DICE.match(formula)
    if not m:
        return 0
    n, sides, bonus = int(m[1]), int(m[2]), int(m[3] or 0)
    return sum(random.randint(1, sides) for _ in range(n)) + bonus


def plan_item_recharges(items, rest_type: str, roll: bool = True) -> list[ItemRecharge]:
    """Charges that would regain on this rest. `roll=False` is a non-random preview."""
    plan: list[ItemRecharge] = []
    for item in items:
        ch = item_meta(item).get("charges")
        if not isinstance(ch, dict) or ch.get("recharge") not in _RECHARGES[rest_type]:
            continue
        mx, cur = int(ch.get("max") or 0), int(ch.get("current") or 0)
        if cur >= mx:
            continue
        formula = str(ch.get("recharge_amount") or "all")
        if formula == "all":
            after: int | None = mx
        elif roll:
            after = min(mx, cur + max(0, _roll_amount(formula)))
        else:
            after = None
        plan.append(ItemRecharge(item, cur, after, formula))
    return plan


def set_item_charges(item, current: int) -> None:
    meta = dict(item_meta(item))
    meta["charges"] = {**meta["charges"], "current": current}
    item.item_metadata = json.dumps(meta)
