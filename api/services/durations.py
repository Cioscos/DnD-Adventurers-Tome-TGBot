"""Round-based durations for conditions (condition_effects) and concentration (settings JSON):
turn edges inside an active encounter, manual ticks outside it."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.data.labels import condition_label
from core.db.models import Character, Combatant, ConditionEffect, Encounter, PendingSave
from api.services.condition_effects import (
    UndoLog, clear_effects_for, effect_snapshot, effects_for_character,
)
from api.services.effects import _add_history, apply_conditions


def is_concentrating(char: Character) -> bool:
    return char.concentrating_spell_id is not None or bool(
        (char.settings or {}).get("concentration_item_spell"))


def end_concentration(char: Character) -> None:
    """Single place that drops concentration (spell id, item spell, round counter)."""
    char.concentrating_spell_id = None
    s = dict(char.settings or {})
    if any([s.pop("concentration_rounds_left", None) is not None,
            s.pop("concentration_item_spell", None) is not None]):
        char.settings = s


def start_concentration(char: Character, spell_id: int | None, rounds: int | None,
                        item_spell: dict | None = None) -> None:
    """Begin concentrating, properly ending any previous one first."""
    end_concentration(char)
    char.concentrating_spell_id = spell_id
    s = dict(char.settings or {})
    if item_spell is not None:
        s["concentration_item_spell"] = item_spell
    if rounds is not None:
        s["concentration_rounds_left"] = rounds
    char.settings = s


def set_concentration_rounds(char: Character, rounds: int | None) -> None:
    s = dict(char.settings or {})
    if rounds is None:
        s.pop("concentration_rounds_left", None)
    else:
        s["concentration_rounds_left"] = rounds
    char.settings = s


def _is_int(v: object) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _tick_concentration(session: AsyncSession, char: Character) -> tuple[dict | None, bool]:
    """One round off ``concentration_rounds_left``. Returns (undo entry or None, ended)."""
    s = dict(char.settings or {})
    conc = s.get("concentration_rounds_left")
    if conc is None:
        return None, False
    entry = {"char_id": char.id, "prev_rounds": conc,
             "prev_spell_id": char.concentrating_spell_id,
             "prev_item_spell": s.get("concentration_item_spell"), "released_effects": []}
    ended = False
    if not _is_int(conc):
        s.pop("concentration_rounds_left")
    elif conc - 1 > 0:
        s["concentration_rounds_left"] = conc - 1
    else:
        s.pop("concentration_rounds_left")
        s.pop("concentration_item_spell", None)
        ended = True
    char.settings = s
    if ended:
        char.concentrating_spell_id = None
        _add_history(session, char.id, "concentration",
                     "Concentrazione terminata: durata scaduta")
    return entry, ended


async def _expire_effect(session: AsyncSession, eff: ConditionEffect, undo: UndoLog | None) -> str:
    """Switch the condition off on its target (dropping the effect row); returns its label."""
    label = condition_label(eff.slug)
    snapshot = effect_snapshot(eff)
    if eff.character_id is not None:
        target = ("character", eff.character_id)
        char = await session.get(Character, eff.character_id)
        prev = (char.conditions or {}).get(eff.slug)
        _add_history(session, char.id, "condition_change", f"Durata scaduta: {label}")
        await apply_conditions(session, char, {eff.slug: False})
    else:
        target = ("combatant", eff.combatant_id)
        comb = await session.get(Combatant, eff.combatant_id)
        conds = dict(comb.conditions or {})
        prev = conds.pop(eff.slug, None)
        comb.conditions = conds
        await clear_effects_for(session, target, [eff.slug])
    if undo is not None:
        undo.expired.append({"target": list(target), "slug": eff.slug,
                             "prev_value": prev, "effect_snapshot": snapshot})
    return label


async def tick_rounds(session: AsyncSession, char: Character) -> list[str]:
    """Manual "end of round": every expiry on the PC -1 (any anchor/edge), concentration
    -1. No repeated saves (out of combat there are no turns)."""
    expired: list[str] = []
    for eff in await effects_for_character(session, char.id):
        if eff.expiry_count is None:
            continue
        if eff.expiry_count - 1 > 0:
            eff.expiry_count -= 1
        else:
            expired.append(await _expire_effect(session, eff, None))
    _, ended = _tick_concentration(session, char)
    if ended:
        expired.append("Concentrazione")
    return expired


async def process_edge(db: AsyncSession, enc: Encounter, combatant: Combatant,
                       edge: Literal["start", "end"], undo: UndoLog) -> list[str]:
    """One turn edge (spec §2): expiries anchored on ``combatant`` first, then the
    PC's concentration (start only), then repeated saves for effects on it."""
    char = (await db.get(Character, combatant.character_id)
            if combatant.kind == "pc" and combatant.character_id else None)
    on_x = (ConditionEffect.character_id == char.id if char is not None
            else ConditionEffect.combatant_id == combatant.id)

    async def anchored_here(eff: ConditionEffect) -> bool:
        if eff.expiry_anchor == "source" and eff.source_combatant_id:
            src = await db.get(Combatant, eff.source_combatant_id)
            if src is not None and src.encounter_id == enc.id and not src.is_dead:
                return src.id == combatant.id
        # owner, or a source that left the fight: falls back to the target's own turn
        return (eff.character_id == char.id) if char is not None else eff.combatant_id == combatant.id

    expired: list[str] = []
    rows = (await db.execute(select(ConditionEffect).where(
        ConditionEffect.expiry_edge == edge, ConditionEffect.expiry_count.is_not(None),
        or_(on_x, ConditionEffect.source_combatant_id == combatant.id),
    ).order_by(ConditionEffect.id))).scalars().all()
    for eff in rows:
        if not await anchored_here(eff):
            continue
        if eff.expiry_count - 1 > 0:
            undo.decremented.append({"effect_id": eff.id, "prev_count": eff.expiry_count})
            eff.expiry_count -= 1
        else:
            expired.append(await _expire_effect(db, eff, undo))

    if char is not None and edge == "start":
        entry, ended = _tick_concentration(db, char)
        if entry is not None:
            undo.concentration = entry
        if ended:
            expired.append("Concentrazione")

    saves = (await db.execute(select(ConditionEffect).where(
        on_x, ConditionEffect.save_edge == edge, ConditionEffect.save_ability.is_not(None),
    ).order_by(ConditionEffect.id))).scalars().all()
    for eff in saves:
        if eff.save_skip_once:
            eff.save_skip_once = False
            undo.skip_cleared.append(eff.id)
            continue
        if (await db.execute(select(PendingSave.id).where(
                PendingSave.effect_id == eff.id, PendingSave.status == "pending",
        ).limit(1))).first():
            continue
        ps = PendingSave(effect_id=eff.id, character_id=eff.character_id,
                         combatant_id=eff.combatant_id, ability=eff.save_ability,
                         dc=eff.save_dc, status="pending",
                         created_at=datetime.utcnow().isoformat(timespec="seconds"))
        db.add(ps)
        await db.flush()
        undo.created_saves.append(ps.id)
    return expired
