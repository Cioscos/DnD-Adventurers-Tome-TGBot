"""Registro degli effetti degli incantesimi, per ``srd_index`` o nome (it/en normalizzato)."""
from __future__ import annotations

import re
import unicodedata
from typing import Any

from core.rules.catalog.spells import basics, damage, defenses, dice, hitpoints, marks, movement, texts, weapons
from core.rules.edition import character_edition
from core.rules.spell_effects import SPELL_STATE_PREFIX, SpellEffect, SpellVariant

SPELL_EFFECTS: dict[str, SpellEffect] = {e.key: e for e in (*basics.SPELLS, *dice.SPELLS, *defenses.SPELLS, *hitpoints.SPELLS, *movement.SPELLS, *damage.SPELLS, *marks.SPELLS, *weapons.SPELLS, *texts.SPELLS)}

_BY_INDEX = {i: e for e in SPELL_EFFECTS.values() for i in e.srd_index}


def _norm(name: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower())


_BY_NAME = {_norm(n): e for e in SPELL_EFFECTS.values() for n in e.names}


def spell_effect(edition: str, srd_index: str | None, name: str | None = None) -> tuple[SpellEffect, SpellVariant] | None:
    # nome intero («Ingrandire/Ridurre»), poi bilingue «Desiderio / Wish» (Intervento Divino): vale ciascuna metà
    effect = _BY_INDEX.get(srd_index or "") or next((e for p in (name or "", *(name or "").split("/")) if (e := _BY_NAME.get(_norm(p)))), None)
    variant = effect and effect.variants.get(edition)
    return (effect, variant) if variant else None


def hurled_lit(char: Any, srd_index: str | None, name: str | None) -> bool | None:
    """Incantesimo che attacca dal suo stato (Produrre Fiamma 2024, Lama Infuocata): se è acceso; ``None`` per ogni altro."""
    found = spell_effect(character_edition(char), srd_index, name)
    if found is None or not found[1].hurled:
        return None
    return any(s.get("key") == f"{SPELL_STATE_PREFIX}{found[0].key}" for s in char.active_states or [])
