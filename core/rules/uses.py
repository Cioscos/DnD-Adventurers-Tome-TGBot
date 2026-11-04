"""Usi massimi di un privilegio a catalogo."""
from __future__ import annotations

from core.game.stats import effective_ability_mod
from core.rules.types import FeatureSpec, RuleContext


def max_uses(spec: FeatureSpec, ctx: RuleContext) -> int | None:
    """Usi massimi al livello di classe di `ctx`; `None` significa illimitato o senza contatore, 0 non ancora disponibile."""
    uses = spec.uses
    if uses is None:
        return None
    level = ctx.class_level
    if uses.unlimited_from is not None and level >= uses.unlimited_from:
        return None
    total = uses.per_level * level
    if uses.table:
        reached = [lv for lv in uses.table if lv <= level]
        if not reached:
            return 0
        total += uses.table[max(reached)]
    if uses.ability:
        total += effective_ability_mod(ctx.char, uses.ability)
    if uses.proficiency:
        total += ctx.char.proficiency_bonus
    return max(uses.minimum, total)
