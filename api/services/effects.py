"""Shared, endpoint-agnostic effect appliers.

Extracted so the HP/conditions endpoints AND the consumable "use" endpoint
apply identical D&D 5e rules (heal clamp to effective max, death-save reset on
rising from 0, condition history logging) without duplicating logic.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import Character, CharacterHistory
from core.data.labels import condition_label
from api.services.homebrew.passive import get_passive_modifiers
from api.services.homebrew.dispatcher import dispatch


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _add_history(session, char_id: int, event_type: str, description: str,
                 meta: dict | None = None) -> None:
    session.add(CharacterHistory(
        character_id=char_id,
        timestamp=_now(),
        event_type=event_type,
        description=description,
        meta=meta,
    ))


async def apply_heal(session: AsyncSession, char: Character, amount: int) -> dict:
    """Heal `char` by `amount` HP, clamped to effective max (base + passive
    homebrew bonus). Resets death saves if HP rises from 0. Logs history and
    dispatches the `hp_healed` homebrew event.

    Returns {"old", "new", "healed", "firing"}; the caller collects
    notifications from "firing" via collect_homebrew_notifications.
    """
    was_at_zero = char.current_hit_points == 0
    old = char.current_hit_points
    hb_hp_bonus = await get_passive_modifiers(session, char, "character.hit_points_max")
    effective_max = char.hit_points + hb_hp_bonus
    char.current_hit_points = min(effective_max, char.current_hit_points + amount)
    healed = char.current_hit_points - old
    _add_history(session, char.id, "hp_change",
                 f"Cura: +{amount} HP ({old} → {char.current_hit_points})",
                 meta={"op": "HEAL"})
    firing = await dispatch(session, char, "hp_healed", {
        "amount": amount,
        "current_hp_before": old,
        "current_hp_after": char.current_hit_points,
    })
    if was_at_zero and char.current_hit_points > 0:
        ds = dict(char.death_saves or {})
        if ds.get("successes", 0) > 0 or ds.get("failures", 0) > 0 or ds.get("stable", False):
            char.death_saves = {"successes": 0, "failures": 0, "stable": False}
            _add_history(session, char.id, "death_save",
                         "Tiri salvezza morte azzerati (HP risaliti sopra 0)")
    return {"old": old, "new": char.current_hit_points, "healed": healed, "firing": firing}


async def apply_conditions(session: AsyncSession, char: Character,
                           changes: dict[str, bool | int]) -> dict:
    """Set/clear conditions on `char` (merging into the existing dict). Logs one
    history row per actual change. `exhaustion` is treated as an integer level;
    all other conditions are booleans. Returns {"changed": bool}.
    """
    old_conditions = dict(char.conditions or {})
    current = dict(old_conditions)
    current.update(changes)
    char.conditions = current

    changed = False
    for cond, new_val in changes.items():
        is_exhaustion = cond == "exhaustion"
        default = 0 if is_exhaustion else False
        old_val = old_conditions.get(cond, default)
        if is_exhaustion:
            old_val = int(old_val) if isinstance(old_val, (int, bool)) and old_val is not None else 0
            new_disp = int(new_val) if isinstance(new_val, (int, bool)) and new_val is not None else 0
        else:
            new_disp = new_val
        if new_disp != old_val:
            changed = True
            if is_exhaustion:
                _add_history(session, char.id, "condition_change",
                             f"Spossatezza: livello {old_val} → {new_disp}")
            elif new_val:
                _add_history(session, char.id, "condition_change",
                             f"Condizione attivata: {condition_label(cond)}")
            else:
                _add_history(session, char.id, "condition_change",
                             f"Condizione rimossa: {condition_label(cond)}")
    return {"changed": changed}
