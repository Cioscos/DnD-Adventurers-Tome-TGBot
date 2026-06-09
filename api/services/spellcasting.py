"""Costruzione del blocco ``CharacterFull.spellcasting``.

Funzione sincrona e senza query: richiede ``char.classes``,
``char.ability_scores`` e ``char.spells`` già caricati — vero per ogni chiamante
di ``build_character_response`` (le stesse relazioni sono serializzate da
``CharacterFull.model_validate``).

Il tetto usa i modificatori BASE delle caratteristiche (non gli effective con
bonus da oggetti): approssimazione documentata, compensabile con l'override
manuale (``settings.prepared_cap_mode = 'manual'``).
"""

from __future__ import annotations

from api.schemas.character import SpellcastingInfo
from core.data.spellcasting import (
    compute_prepared_cap,
    has_preparing_class,
    has_ritual_caster,
    has_wizard,
)
from core.db.models import Character


def build_spellcasting_info(char: Character) -> SpellcastingInfo:
    classes = char.classes
    settings = char.settings or {}
    preparing = has_preparing_class(classes)
    cap_mode = settings.get("prepared_cap_mode") or "auto"

    cap: int | None = None
    if preparing:
        if cap_mode == "manual":
            cap = max(0, int(settings.get("prepared_cap_value") or 0))
        else:
            modifiers = {a.name: a.modifier for a in char.ability_scores}
            cap = compute_prepared_cap(classes, modifiers)

    count = sum(1 for s in char.spells if s.level >= 1 and s.is_prepared)

    return SpellcastingInfo(
        has_preparing_class=preparing,
        prepared_cap=cap,
        prepared_count=count,
        cap_mode=cap_mode if preparing else "auto",
        has_ritual_caster=has_ritual_caster(classes),
        has_wizard=has_wizard(classes),
    )
