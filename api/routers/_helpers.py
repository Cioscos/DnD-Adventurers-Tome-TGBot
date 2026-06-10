"""Shared helpers for router logic (avoid circular imports)."""
import logging
import random
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.common import ConcentrationSaveResult
from api.services.dice_stats import record_dice
from core.db.models import Character, CharacterHistory
from core.game.stats import effective_ability_score

logger = logging.getLogger(__name__)


def _settings_value(char: Character, key: str, default):
    settings = (char.settings if isinstance(char.settings, dict) else None) or {}
    return settings.get(key, default)


async def prune_history(session: AsyncSession, char: Character) -> int:
    """Trim a character's history per `settings.history_retention_*`.

    Modes:
      - "off" (default): no-op.
      - "events": keep at most `history_retention_events` rows
        (default 100), deleting the oldest by `timestamp`.
      - "days": delete rows whose `timestamp` is older than
        `history_retention_days` (default 30).

    Returns the number of rows deleted (for logging/telemetry).
    Best-effort: errors are swallowed and logged to avoid breaking the
    primary action that triggered the prune.
    """
    mode = _settings_value(char, "history_retention_mode", "off")
    if mode not in ("events", "days"):
        return 0

    try:
        if mode == "events":
            keep = int(_settings_value(char, "history_retention_events", 100) or 100)
            keep = max(1, keep)
            # IDs to keep: the most recent N
            keep_subq = (
                select(CharacterHistory.id)
                .where(CharacterHistory.character_id == char.id)
                .order_by(CharacterHistory.timestamp.desc())
                .limit(keep)
                .subquery()
            )
            # Only prune when there are more rows than the cap to avoid the
            # cost of running the delete every insert on small histories.
            count_q = select(func.count(CharacterHistory.id)).where(
                CharacterHistory.character_id == char.id
            )
            total = (await session.execute(count_q)).scalar() or 0
            if total <= keep:
                return 0
            result = await session.execute(
                delete(CharacterHistory).where(
                    CharacterHistory.character_id == char.id,
                    ~CharacterHistory.id.in_(select(keep_subq.c.id)),
                )
            )
            return result.rowcount or 0
        else:  # "days"
            days = int(_settings_value(char, "history_retention_days", 30) or 30)
            days = max(1, days)
            cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat(timespec="seconds")
            result = await session.execute(
                delete(CharacterHistory).where(
                    CharacterHistory.character_id == char.id,
                    CharacterHistory.timestamp < cutoff,
                )
            )
            return result.rowcount or 0
    except Exception as exc:
        logger.warning("prune_history failed for char %s: %s", char.id, exc)
        return 0


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
        f"d20={die}+{con_mod}={total}: {outcome}"
        + (" → concentrazione persa" if lost_concentration else "")
    )
    session.add(CharacterHistory(
        character_id=char_id,
        timestamp=datetime.utcnow().isoformat(timespec="seconds"),
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
    record_dice(char, [("d20", die)])
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


def collect_homebrew_notifications(firing_results) -> list[dict]:
    """Flatten a list of RuleFiringResult into the dict shape exposed by responses."""
    return [
        {
            "severity": n.severity,
            "message": n.message,
            "rule_id": n.rule_id,
            "rule_name": n.rule_name,
        }
        for rfr in firing_results
        for n in rfr.notifications
    ]
