"""Registro degli effetti degli incantesimi, per ``srd_index`` o nome (it/en normalizzato)."""
from __future__ import annotations

import re
import unicodedata

from core.rules.catalog.spells import basics, damage, defenses, dice, hitpoints, marks, movement
from core.rules.spell_effects import SpellEffect, SpellVariant

SPELL_EFFECTS: dict[str, SpellEffect] = {e.key: e for e in (*basics.SPELLS, *dice.SPELLS, *defenses.SPELLS, *hitpoints.SPELLS, *movement.SPELLS, *damage.SPELLS, *marks.SPELLS)}

_BY_INDEX = {i: e for e in SPELL_EFFECTS.values() for i in e.srd_index}


def _norm(name: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower())


_BY_NAME = {_norm(n): e for e in SPELL_EFFECTS.values() for n in e.names}


def spell_effect(edition: str, srd_index: str | None, name: str | None = None) -> tuple[SpellEffect, SpellVariant] | None:
    effect = _BY_INDEX.get(srd_index or "") or _BY_NAME.get(_norm(name))
    variant = effect and effect.variants.get(edition)
    return (effect, variant) if variant else None
