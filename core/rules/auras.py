"""Aure che un personaggio proietta sugli alleati seduti alla sua stessa serata (Paladino 2014).

``projected_auras(ally)`` le calcola per chi le proietta; ``party_auras(char)`` legge quelle che i compagni proiettano su
``char``, messe lì dal server prima di un tiro (``api.services.session_allies.attach_party_auras``): un attributo
transitorio, mai salvato."""
from __future__ import annotations

from typing import Any

from core.rules.catalog import active_features
from core.rules.edition import character_edition
from core.rules.states import is_conscious
from core.rules.types import RuleContext


def projected_auras(char: Any) -> list[dict]:
    """Le aure che ``char`` proietta adesso: ``{kind, source, bonus, range_ft}``."""
    out: list[dict] = []
    for spec, row in active_features(char):
        aura = spec.aura
        if aura is None or (aura.needs_conscious and not is_conscious(char)):
            continue
        ctx = RuleContext(char=char, edition=character_edition(char), class_row=row, class_level=row.level)
        out.append({"kind": aura.kind, "source": char.name, "bonus": aura.bonus(ctx), "range_ft": aura.range_ft(ctx),
                    "edition": ctx.edition})
    return out


def party_auras(char: Any, kind: str | None = None) -> list[dict]:
    return [a for a in getattr(char, "party_auras", None) or [] if kind is None or a["kind"] == kind]


def has_own_aura(char: Any, kind: str) -> bool:
    """Chi ha già l'aura non ne somma una uguale di un compagno: vale la sua."""
    return any(spec.aura is not None and spec.aura.kind == kind for spec, _row in active_features(char))
