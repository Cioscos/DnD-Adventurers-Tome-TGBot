"""Condition effects: expiry / repeated-save / source metadata for an active condition.

The ``conditions`` map stays the source of truth for "is it on"; an effect exists only
while the condition is on. Exactly one of character_id / combatant_id is set (no DB
constraint: guaranteed here via ``Target``).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.condition_effects import ConditionEffectRead, PendingSaveRead
from core.db.models import (
    Character, Combatant, ConditionEffect, Encounter, PendingSave,
)

Target = tuple[Literal["character", "combatant"], int]


@dataclass
class ExpirySpec:
    anchor: Literal["owner", "source"]
    edge: Literal["start", "end"]
    count: int


@dataclass
class SaveSpec:
    ability: str
    dc: int
    edge: Literal["start", "end"]


def _target_filter(target: Target):
    kind, tid = target
    col = ConditionEffect.character_id if kind == "character" else ConditionEffect.combatant_id
    return col == tid


async def _target_combatant_id(db: AsyncSession, target: Target, encounter: Encounter) -> int | None:
    kind, tid = target
    if kind == "combatant":
        return tid
    return (await db.execute(select(Combatant.id).where(
        Combatant.encounter_id == encounter.id, Combatant.character_id == tid,
    ))).scalar_one_or_none()


async def clear_effects_for(db: AsyncSession, target: Target, slugs: Iterable[str]) -> None:
    slugs = list(slugs)
    if not slugs:
        return
    rows = (await db.execute(select(ConditionEffect).where(
        _target_filter(target), ConditionEffect.slug.in_(slugs)))).scalars().all()
    for row in rows:
        # Explicit delete of pendings: SQLite FK cascade is not guaranteed to be enabled.
        for ps in (await db.execute(select(PendingSave).where(
                PendingSave.effect_id == row.id))).scalars():
            await db.delete(ps)
        await db.delete(row)
    await db.flush()


async def upsert_effect(
    db: AsyncSession, target: Target, slug: str, *,
    expiry: ExpirySpec | None = None, save: SaveSpec | None = None,
    source_combatant_id: int | None = None, source_character_id: int | None = None,
    source_spell_id: int | None = None, ends_with_concentration: bool = False,
    applied_by_gm: bool = False, encounter: Encounter | None = None,
) -> ConditionEffect:
    """Replace the effect for (target, slug). Applies the "next turn" correction when
    ``encounter`` is active: an end-edge expiry anchored on the active combatant lasts one
    turn more, and an end-edge save on the active target skips its first edge."""
    await clear_effects_for(db, target, [slug])
    count = expiry.count if expiry else None
    skip_once = False
    if encounter is not None and encounter.status == "active" and encounter.active_combatant_id:
        active = encounter.active_combatant_id
        if expiry and expiry.edge == "end":
            anchor_id = (source_combatant_id if expiry.anchor == "source"
                         else await _target_combatant_id(db, target, encounter))
            if anchor_id == active:
                count += 1
        if save and save.edge == "end":
            skip_once = await _target_combatant_id(db, target, encounter) == active
    kind, tid = target
    effect = ConditionEffect(
        character_id=tid if kind == "character" else None,
        combatant_id=tid if kind == "combatant" else None,
        slug=slug,
        expiry_anchor=expiry.anchor if expiry else None,
        expiry_edge=expiry.edge if expiry else None,
        expiry_count=count,
        save_ability=save.ability if save else None,
        save_dc=save.dc if save else None,
        save_edge=save.edge if save else None,
        save_skip_once=skip_once,
        source_combatant_id=source_combatant_id,
        source_character_id=source_character_id,
        source_spell_id=source_spell_id,
        ends_with_concentration=ends_with_concentration,
        applied_by_gm=applied_by_gm,
        encounter_id=encounter.id if encounter is not None else None,
        created_at=datetime.utcnow().isoformat(timespec="seconds"),
    )
    db.add(effect)
    await db.flush()
    return effect


async def effects_for_character(db: AsyncSession, char_id: int) -> list[ConditionEffect]:
    return list((await db.execute(select(ConditionEffect).where(
        ConditionEffect.character_id == char_id).order_by(ConditionEffect.id))).scalars())


async def open_pending_saves(db: AsyncSession, char_id: int) -> list[PendingSave]:
    """All pending saves plus the latest non-dismissed failed one."""
    rows = list((await db.execute(select(PendingSave).where(
        PendingSave.character_id == char_id, PendingSave.dismissed.is_(False),
        PendingSave.status.in_(("pending", "failed"))).order_by(PendingSave.id))).scalars())
    failed = [r for r in rows if r.status == "failed"]
    keep_failed = failed[-1:] if failed else []
    return [r for r in rows if r.status == "pending"] + keep_failed


async def character_effect_payload(
    db: AsyncSession, char_id: int,
) -> tuple[list[ConditionEffectRead], list[PendingSaveRead]]:
    """Read models for CharacterFull (source names resolved)."""
    effects = await effects_for_character(db, char_id)
    comb_ids = {e.source_combatant_id for e in effects if e.source_combatant_id}
    char_ids = {e.source_character_id for e in effects if e.source_character_id}
    comb_names = dict((await db.execute(select(Combatant.id, Combatant.name).where(
        Combatant.id.in_(comb_ids)))).all()) if comb_ids else {}
    char_names = dict((await db.execute(select(Character.id, Character.name).where(
        Character.id.in_(char_ids)))).all()) if char_ids else {}
    reads = [ConditionEffectRead(
        slug=e.slug, expiry_anchor=e.expiry_anchor, expiry_edge=e.expiry_edge,
        expiry_count=e.expiry_count, save_ability=e.save_ability, save_dc=e.save_dc,
        save_edge=e.save_edge,
        source_name=comb_names.get(e.source_combatant_id) or char_names.get(e.source_character_id),
        ends_with_concentration=e.ends_with_concentration, applied_by_gm=e.applied_by_gm,
    ) for e in effects]
    slugs = {e.id: e.slug for e in effects}
    pendings = [PendingSaveRead(
        id=p.id, slug=slugs.get(p.effect_id, ""), ability=p.ability, dc=p.dc,
        status=p.status, created_at=p.created_at, last_roll=p.last_roll,
    ) for p in await open_pending_saves(db, char_id)]
    return reads, pendings
