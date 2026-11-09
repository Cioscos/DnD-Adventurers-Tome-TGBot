"""Primi incantesimi con effetto sul bersaglio (Scudo della Fede, Aiuto, Passo Veloce)."""
from __future__ import annotations

from core.rules.spell_effects import SpellEffect, SpellTarget, SpellVariant
from core.rules.types import Modifier

_SHIELD = SpellVariant(modifiers=lambda d: (Modifier("ac", 2),), concentration=True, rounds=100)  # 10 minuti
# +5 PF massimi per il 2° livello e +5 per ogni livello oltre (uguale nelle due edizioni)
_AID = SpellVariant(modifiers=lambda d: (Modifier("hp_max", 5 * (max(d.get("slot_level", 2), 2) - 1)),), until_rest=True)
# +3 m = +10 ft di velocità, un'ora
_LONGSTRIDER = SpellVariant(modifiers=lambda d: (Modifier("speed", 10),), rounds=600)

SPELLS: tuple[SpellEffect, ...] = (
    SpellEffect("shield_of_faith", ("shield-of-faith",), ("Scudo della Fede", "Shield of Faith"), SpellTarget("ally"),
                {"2014": _SHIELD, "2024": _SHIELD}),
    SpellEffect("aid", ("aid",), ("Aiuto", "Aid"), SpellTarget("allies", lambda slot: 3), {"2014": _AID, "2024": _AID}),
    SpellEffect("longstrider", ("longstrider",), ("Passo Veloce", "Passo Lungo", "Longstrider"),
                SpellTarget("allies", lambda slot: max(slot, 1)), {"2014": _LONGSTRIDER, "2024": _LONGSTRIDER}),
)
