"""Lanci che un privilegio del Warlock paga con un suo uso: Arcanum Mistico e le suppliche «una volta con uno slot di Patto».

Funzioni pure sul personaggio, senza scrivere nulla: chi lancia (``api/routers/spells.py``) controlla e spende.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from core.rules.catalog import active_features
from core.rules.feature_sync import GRANTED_SPELL_KEYS  # settings, scritto dal sync: gli incantesimi che un privilegio ha concesso


@dataclass(frozen=True)
class PactCast:
    """``arcanum``: si lancia senza slot, al livello dell'incantesimo. ``invocation``: serve uno slot di Patto (``pact_only``).
    ``feature_key``: la riga i cui usi si spendono; ``uses_left``: gli usi rimasti (``None`` se la riga non c'è)."""
    kind: Literal["arcanum", "invocation"]
    feature_key: str
    pact_only: bool
    uses_left: int | None
    also_slot: bool = False  # si lancia anche con uno slot normale (Incantesimi Personali, Mutaforma del Mago)
    ability_id: int | None = None  # la riga precisa che spende (un talento ripetibile ha una riga per istanza)


def _uses(char: Any, feature_key: str, class_id: int) -> int | None:
    row = next((a for a in char.abilities if a.feature_key == feature_key and a.source_class_id == class_id), None)
    return None if row is None else (row.uses or 0)


def pact_cast(char: Any, spell: Any) -> PactCast | None:
    """Come ``spell`` si lancia grazie a un privilegio del Warlock che ne spende un uso, o ``None``."""
    index = getattr(spell, "srd_index", None)
    name = getattr(spell, "name", None)
    granted = (getattr(char, "settings", None) or {}).get(GRANTED_SPELL_KEYS) or []
    for spec, row in active_features(char):
        if spec.arcanum_group and ((index or name) in ((row.options or {}).get(spec.arcanum_group) or [])
                                   or (name in ((row.options or {}).get(spec.arcanum_group) or []))):
            if spec.class_key == "feat":  # Iniziato alla magia: gli usi sono della riga del talento, anche con uno slot
                return PactCast("arcanum", spec.key, False, row.ability.uses or 0, also_slot=True, ability_id=row.ability.id)
            return PactCast("arcanum", spec.key, False, _uses(char, spec.key, row.id), also_slot=spec.class_key == "wizard")
        if spec.free_spell and index == spec.free_spell:  # Mutaforma: senza slot, spende l'uso come un Arcanum
            return PactCast("arcanum", spec.key, False, _uses(char, spec.key, row.id), also_slot=True)
        if spec.pact_spell and index == spec.pact_spell and index in granted:
            return PactCast("invocation", spec.key, True, _uses(char, spec.key, row.id))
    return None
