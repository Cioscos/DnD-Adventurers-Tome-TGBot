"""Viewer-redacted response builder for the combat tracker.

Shared by api/routers/encounters.py (mutation responses) and
api/routers/sessions.py (the `encounter` block in /live).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.schemas.condition_effects import ConditionEffectRead, PendingSaveRead
from api.schemas.encounter import CombatantLive, EncounterLive, PublicState, PublicStateOther
from api.services.condition_effects import effect_reads, pending_read
from api.services.rules_states import state_name
from core.db.models import Character, Combatant, ConditionEffect, Encounter, PendingSave
from core.utils.session_view import hp_bucket_from_ratio


def public_states(char: Character) -> list[PublicState]:
    """Gli stati attivi che portano effetti su altri, col testo dei privilegi: gli altri sono privati del giocatore."""
    out: list[PublicState] = []
    for state in char.active_states or []:
        others = [
            PublicStateOther(key=a.feature_key, name=a.name or "", text=a.description or "")
            for key in (state.get("data") or {}).get("others") or []
            for a in char.abilities if a.feature_key == key
        ]
        if others:
            out.append(PublicState(key=state["key"], name=state_name(char, state),
                                   rounds_left=state.get("rounds_left"), others=others))
    return out


def combatant_payload(
    c: Combatant, *, mode: str, viewer_is_gm: bool,
    effects: list[ConditionEffectRead] = (), pending: list[PendingSaveRead] = (),
    states: list[PublicState] = (),
) -> CombatantLive:
    show_hp = c.kind == "monster" and mode == "full"
    bucket = None
    if show_hp and not viewer_is_gm:
        bucket = "dead" if c.is_dead else hp_bucket_from_ratio(c.current_hp, c.max_hp)
    return CombatantLive(
        id=c.id,
        kind=c.kind,
        character_id=c.character_id,
        owner_user_id=c.owner_user_id,
        name=c.name,
        initiative=c.initiative,
        initiative_die=c.initiative_die,
        initiative_mod=c.initiative_mod,
        sort_order=c.sort_order,
        is_dead=c.is_dead,
        surprised=c.surprised,
        conditions=c.conditions or {},
        current_hp=c.current_hp if (show_hp and viewer_is_gm) else None,
        max_hp=c.max_hp if (show_hp and viewer_is_gm) else None,
        ac=c.ac if (show_hp and viewer_is_gm) else None,
        hp_bucket=bucket,
        condition_effects=list(effects),
        pending_saves=list(pending) if viewer_is_gm else [],
        active_states=list(states),
    )


async def build_encounter_block(
    db: AsyncSession, enc: Encounter, *, viewer_is_gm: bool,
) -> EncounterLive:
    combs = list(enc.combatants)
    # Monster effects live on the combatant; PC effects are on the sheet (live_characters).
    mon_ids = [c.id for c in combs if c.kind == "monster"]
    all_rows = list((await db.execute(select(ConditionEffect).where(
        ConditionEffect.combatant_id.in_(mon_ids)).order_by(ConditionEffect.id))).scalars())
    rows = [r for r in all_rows if not r.pending]  # i pending non sono ancora sul mostro
    effects: dict[int, list[ConditionEffectRead]] = {}
    for row, read in zip(rows, await effect_reads(db, rows)):
        effects.setdefault(row.combatant_id, []).append(read)
    pending: dict[int, list[PendingSaveRead]] = {}
    slugs = {r.id: r.slug for r in all_rows}
    for p in (await db.execute(select(PendingSave).where(
            PendingSave.combatant_id.in_(mon_ids), PendingSave.character_id.is_(None),
            PendingSave.status == "pending").order_by(PendingSave.id))).scalars():
        pending.setdefault(p.combatant_id, []).append(pending_read(p, slugs.get(p.effect_id, "")))
    pc_ids = [c.character_id for c in combs if c.kind == "pc" and c.character_id]
    states: dict[int, list[PublicState]] = {}
    if pc_ids:
        for ch in (await db.execute(select(Character).options(selectinload(Character.abilities))
                                    .where(Character.id.in_(pc_ids)))).scalars():
            if ch.active_states:
                states[ch.id] = public_states(ch)
    if enc.status == "setup":
        combs.sort(key=lambda c: (c.created_at, c.id))
    else:
        combs.sort(key=lambda c: (c.sort_order is None, c.sort_order or 0, c.id))
    return EncounterLive(
        id=enc.id,
        mode=enc.mode,
        status=enc.status,
        round=enc.round,
        active_combatant_id=enc.active_combatant_id,
        created_at=enc.created_at,
        started_at=enc.started_at,
        ended_at=enc.ended_at,
        combatants=[
            combatant_payload(c, mode=enc.mode, viewer_is_gm=viewer_is_gm,
                              effects=effects.get(c.id, []), pending=pending.get(c.id, []),
                              states=states.get(c.character_id, []) if c.kind == "pc" else [])
            for c in combs
        ],
    )
