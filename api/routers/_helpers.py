"""Shared helpers for router logic (avoid circular imports)."""
import logging
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.common import ConcentrationSaveResult, RollMode
from api.services.d20 import d20_history_label, d20_records, resolve_d20
from api.services.dice_stats import record_dice
from api.services.homebrew.passive import get_passive_modifiers
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


def effective_ability_mod(char, ability: str) -> int:
    """Effective modifier for `ability` (base score + modifiers from equipped
    items), the same value the character sheet shows."""
    row = next((a for a in char.ability_scores if a.name == ability), None)
    if row is None:
        return 0
    eq_items = [i for i in char.items if i.is_equipped]
    effective, _ = effective_ability_score(ability, row.value, eq_items)
    return (effective - 10) // 2


async def saving_throw_bonus(session: AsyncSession, char: Character, ability: str) -> int:
    """Saving throw bonus as the sheet shows it: effective modifier,
    proficiency and homebrew passive modifiers."""
    proficient = bool((char.saving_throws or {}).get(ability, False))
    return (
        effective_ability_mod(char, ability)
        + (char.proficiency_bonus if proficient else 0)
        + await get_passive_modifiers(session, char, f"character.saving_throw.{ability}")
    )


def effective_con_mod(char) -> int:
    """Effective CON modifier (base CON + modifiers from equipped items)."""
    return effective_ability_mod(char, "constitution")


def _append_concentration_history(
    session: AsyncSession,
    char_id: int,
    damage: int,
    dc: int,
    label: str,
    con_mod: int,
    total: int,
    success: bool,
    lost_concentration: bool,
) -> None:
    """Local history helper (avoids depending on router's private _add_history)."""
    outcome = "SUCCESSO" if success else "FALLIMENTO"
    desc = (
        f"TS Concentrazione (danno {damage}, DC {dc}): "
        f"{label}+{con_mod}={total}: {outcome}"
        + (" → concentrazione persa" if lost_concentration else "")
    )
    session.add(CharacterHistory(
        character_id=char_id,
        timestamp=datetime.utcnow().isoformat(timespec="seconds"),
        event_type="concentration_save",
        description=desc,
    ))


async def roll_concentration_save(
    char: Character,
    damage: int,
    session: AsyncSession,
    mode: RollMode = "normal",
    dice: list[int] | None = None,
) -> ConcentrationSaveResult:
    """Roll a CON save vs DC=max(10, damage//2). RAW: natural 20 and 1 have
    no special effect on saving throws, only the total counts.

    Side effects:
    - Clears char.concentrating_spell_id on failure (if it was set).
    - Appends a history entry describing the roll.

    Returns a ConcentrationSaveResult with die, bonus, total, is_critical,
    is_fumble, description, dc, success, lost_concentration.
    """
    dc = max(10, damage // 2)
    con_mod = await saving_throw_bonus(session, char, "constitution")

    outcome = resolve_d20(mode, dice, None)
    die = outcome.kept
    record_dice(char, d20_records(outcome))
    total = die + con_mod
    is_crit = die == 20
    is_fumble = die == 1
    success = total >= dc

    lost_concentration = not success and char.concentrating_spell_id is not None
    if lost_concentration:
        char.concentrating_spell_id = None

    _append_concentration_history(
        session, char.id, damage, dc, d20_history_label(outcome), con_mod, total, success, lost_concentration,
    )

    return ConcentrationSaveResult(
        die=die,
        dice=outcome.dice,
        mode=outcome.mode,
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
