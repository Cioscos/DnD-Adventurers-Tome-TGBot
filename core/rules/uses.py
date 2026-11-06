"""Usi massimi di un privilegio a catalogo."""
from __future__ import annotations

from core.game.stats import effective_ability_mod
from core.rules.types import FeatureSpec, RuleContext


def max_uses(spec: FeatureSpec, ctx: RuleContext) -> int | None:
    """Usi massimi al livello di classe di `ctx`; `None` significa illimitato o senza contatore, 0 non ancora disponibile.
    Una riserva condivisa (``shared_pool``) la tiene la sola classe che ne dà di più: per le altre vale 0."""
    own = _own_max(spec, ctx)
    if not own or not spec.shared_pool or ctx.class_row is None:
        return own
    from core.rules.catalog import active_features  # import locale: il catalogo importa i tipi, non questo modulo
    for other, row in active_features(ctx.char):
        if other.shared_pool != spec.shared_pool or row.id == ctx.class_row.id:
            continue
        theirs = _own_max(other, RuleContext(char=ctx.char, edition=ctx.edition, class_row=row, class_level=row.level))
        if theirs and (theirs > own or (theirs == own and row.id < ctx.class_row.id)):
            return 0
    return own


def pool_key(char, key: str) -> str:
    """La chiave della riga che tiene gli usi di ``key``: la stessa, o quella della classe che tiene la riserva condivisa."""
    from core.rules.catalog import active_features  # import locale
    specs = [s for s, _row in active_features(char)]
    shared = next((s.shared_pool for s in specs if s.key == key), None)
    if not shared:
        return key
    held = {a.feature_key for a in char.abilities}
    return next((s.key for s in specs if s.shared_pool == shared and s.key in held), key)


def _own_max(spec: FeatureSpec, ctx: RuleContext) -> int | None:
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
