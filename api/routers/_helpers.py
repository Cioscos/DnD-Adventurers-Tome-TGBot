"""Shared helpers for router logic (avoid circular imports)."""
from core.game.stats import effective_ability_score


def effective_con_mod(char) -> int:
    """Compute effective CON modifier given character's current state
    (base CON + modifiers from equipped items)."""
    con_row = next((a for a in char.ability_scores if a.name == "constitution"), None)
    if con_row is None:
        return 0
    eq_items = [i for i in char.items if i.is_equipped]
    effective, _ = effective_ability_score("constitution", con_row.value, eq_items)
    return (effective - 10) // 2
