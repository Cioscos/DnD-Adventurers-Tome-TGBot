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
    free_key: str | None = None  # un lancio gratuito per incantesimo: la chiave da segnare in ``FREE_CASTS`` spendendo


# ``Ability.options``: gli incantesimi che hanno usato il loro lancio gratuito (Toccato dalle fate / dall'ombra)
FREE_CASTS = "free_casts"


def spent_free_casts(ability: Any) -> list[str]:
    """Valgono solo gli ultimi ``max_uses - uses`` lanci segnati: il riposo che rende gli usi svuota il registro senza scriverlo."""
    gone = (ability.max_uses or 0) - (ability.uses or 0)
    return list(((ability.options or {}).get(FREE_CASTS) or [])[-gone:]) if gone > 0 else []


def _feat_cast(spec: Any, row: Any, key: str) -> PactCast:
    """Un talento che spende gli usi della sua riga, anche con uno slot (Iniziato alla magia). Con ``free_spell``
    (Toccato dalle fate / dall'ombra, PHB 2024 pag. 204 e 207) ognuno dei due incantesimi ha un solo lancio gratuito."""
    left = row.ability.uses or 0
    per_spell = spec.free_spell is not None
    if per_spell and key in spent_free_casts(row.ability):
        left = 0
    return PactCast("arcanum", spec.key, False, left, also_slot=True, ability_id=row.ability.id, free_key=key if per_spell else None)


def _uses(char: Any, feature_key: str, class_id: int) -> int | None:
    row = next((a for a in char.abilities if a.feature_key == feature_key and a.source_class_id == class_id), None)
    return None if row is None else (row.uses or 0)


def pact_cast(char: Any, spell: Any) -> PactCast | None:
    """Come ``spell`` si lancia grazie a un privilegio del Warlock che ne spende un uso, o ``None``."""
    index = getattr(spell, "srd_index", None)
    name = getattr(spell, "name", None)
    granted = (getattr(char, "settings", None) or {}).get(GRANTED_SPELL_KEYS) or []
    # due Iniziato alla magia con lo stesso incantesimo: prima la riga che ha ancora l'uso gratuito
    features = sorted(active_features(char), key=lambda f: f[0].class_key == "feat" and not f[1].ability.uses)
    for spec, row in features:
        if spec.arcanum_group and ((index or name) in ((row.options or {}).get(spec.arcanum_group) or [])
                                   or (name in ((row.options or {}).get(spec.arcanum_group) or []))):
            if spec.class_key == "feat":  # Iniziato alla magia: gli usi sono della riga del talento, anche con uno slot
                return _feat_cast(spec, row, index or name)
            return PactCast("arcanum", spec.key, False, _uses(char, spec.key, row.id), also_slot=spec.class_key == "wizard")
        if spec.free_spell and index == spec.free_spell and spec.class_key == "feat" and spec.arcanum_group:  # l'incantesimo fisso di Toccato dalle fate
            return _feat_cast(spec, row, index)
        if spec.free_spell and index == spec.free_spell:  # Mutaforma: senza slot, spende l'uso come un Arcanum
            return PactCast("arcanum", spec.key, False, _uses(char, spec.key, row.id), also_slot=True)
        if spec.pact_spell and index == spec.pact_spell and index in granted:
            return PactCast("invocation", spec.key, True, _uses(char, spec.key, row.id))
    return None
