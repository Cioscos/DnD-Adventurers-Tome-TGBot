"""Viewer-redacted response builder for the combat tracker.

Shared by api/routers/encounters.py (mutation responses) and
api/routers/sessions.py (the `encounter` block in /live).
"""

from __future__ import annotations

from api.schemas.encounter import CombatantLive, EncounterLive
from core.db.models import Combatant, Encounter
from core.utils.session_view import hp_bucket_from_ratio


def combatant_payload(c: Combatant, *, mode: str, viewer_is_gm: bool) -> CombatantLive:
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
        conditions=c.conditions or {},
        current_hp=c.current_hp if (show_hp and viewer_is_gm) else None,
        max_hp=c.max_hp if (show_hp and viewer_is_gm) else None,
        ac=c.ac if (show_hp and viewer_is_gm) else None,
        hp_bucket=bucket,
    )


def build_encounter_block(enc: Encounter, *, viewer_is_gm: bool) -> EncounterLive:
    combs = list(enc.combatants)
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
            combatant_payload(c, mode=enc.mode, viewer_is_gm=viewer_is_gm) for c in combs
        ],
    )
