"""Shared helpers for router logic (avoid circular imports)."""
import random

from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.common import ConcentrationSaveResult
from core.db.models import Character, CharacterHistory
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


def _append_concentration_history(
    session: AsyncSession,
    char_id: int,
    damage: int,
    dc: int,
    die: int,
    con_mod: int,
    total: int,
    success: bool,
    lost_concentration: bool,
) -> None:
    """Local history helper (avoids depending on router's private _add_history)."""
    outcome = "SUCCESSO" if success else "FALLIMENTO"
    desc = (
        f"TS Concentrazione (danno {damage}, DC {dc}): "
        f"d20={die}+{con_mod}={total} — {outcome}"
        + (" → concentrazione persa" if lost_concentration else "")
    )
    session.add(CharacterHistory(
        character_id=char_id,
        event_type="concentration_save",
        description=desc,
    ))


def roll_concentration_save(
    char: Character,
    damage: int,
    session: AsyncSession,
) -> ConcentrationSaveResult:
    """Roll a CON save vs DC=max(10, damage//2). Nat20 auto-pass, nat1 auto-fail.

    Side effects:
    - Clears char.concentrating_spell_id on failure (if it was set).
    - Appends a history entry describing the roll.

    Returns a ConcentrationSaveResult with die, bonus, total, is_critical,
    is_fumble, description, dc, success, lost_concentration.
    """
    dc = max(10, damage // 2)

    # Raw CON modifier (equipped-item bonuses intentionally ignored here to
    # preserve the pre-existing /concentration/save behavior). Swap to
    # effective_con_mod(char) if item bonuses should apply.
    con_score = next((s for s in char.ability_scores if s.name == "constitution"), None)
    con_mod = con_score.modifier if con_score else 0

    die = random.randint(1, 20)
    total = die + con_mod
    is_crit = die == 20
    is_fumble = die == 1

    if is_crit:
        success = True
    elif is_fumble:
        success = False
    else:
        success = total >= dc

    lost_concentration = not success and char.concentrating_spell_id is not None
    if lost_concentration:
        char.concentrating_spell_id = None

    _append_concentration_history(
        session, char.id, damage, dc, die, con_mod, total, success, lost_concentration,
    )

    return ConcentrationSaveResult(
        die=die,
        bonus=con_mod,
        total=total,
        is_critical=is_crit,
        is_fumble=is_fumble,
        description=f"DC {dc}",
        dc=dc,
        success=success,
        lost_concentration=lost_concentration,
    )
