"""Condition effects: expiry / repeated-save / source metadata for an active condition.

The ``conditions`` map stays the source of truth for "is it on"; an effect exists only
while the condition is on. Exactly one of character_id / combatant_id is set (no DB
constraint: guaranteed here via ``Target``).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Iterable, Literal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.data.labels import condition_label
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


@dataclass
class UndoLog:
    """What one forward turn advance changed, stored on ``Encounter.last_advance_undo``.

    ``decremented`` holds only effects that survived; expired ones are in ``expired``
    (snapshot taken before the decrement, so recreating it restores the prior count).
    """
    from_combatant_id: int | None = None
    to_combatant_id: int | None = None
    round_before: int | None = None
    round_after: int | None = None
    decremented: list[dict] = field(default_factory=list)  # {effect_id, prev_count}
    # {target, slug, prev_value, effect_snapshot, pending_saves: [snapshot]}
    expired: list[dict] = field(default_factory=list)
    created_saves: list[int] = field(default_factory=list)
    skip_cleared: list[int] = field(default_factory=list)  # effect ids whose save_skip_once was consumed
    # {char_id, prev_rounds, prev_spell_id, prev_item_spell, released_effects: [snapshot]}
    concentration: dict | None = None

    def to_json(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict) -> "UndoLog":
        return cls(**data)


def effect_snapshot(effect: ConditionEffect | PendingSave) -> dict:
    return {c.name: getattr(effect, c.name) for c in type(effect).__table__.columns}


async def _restore_row(db: AsyncSession, model, snap: dict):
    """Recreate a deleted row, keeping its id unless something reused it meanwhile."""
    data = dict(snap)
    if await db.get(model, data["id"]) is not None:
        data.pop("id")
    row = model(**data)
    db.add(row)
    await db.flush()
    return row


async def undo_last_advance(db: AsyncSession, enc: Encounter) -> None:
    """Revert the last forward advance (spec §2 "Turno indietro"), one step only and
    only if the pointer is still where that advance left it. Each entry is reverted
    only if its state is still the one the advance left; conflicting ones are skipped."""
    data, enc.last_advance_undo = enc.last_advance_undo, None
    if not data:
        return
    log = UndoLog.from_json(data)
    if enc.active_combatant_id != log.to_combatant_id or enc.round != log.round_after:
        return
    created = set(log.created_saves)
    for sid in log.created_saves:
        ps = await db.get(PendingSave, sid)
        if ps is not None and ps.status == "pending":
            await db.delete(ps)
    for d in log.decremented:
        eff = await db.get(ConditionEffect, d["effect_id"])
        if eff is not None and eff.expiry_count == d["prev_count"] - 1:
            eff.expiry_count = d["prev_count"]
    new_ids: dict[int, int] = {}
    await _restore_released(db, log.expired, created, new_ids)
    c = log.concentration
    char = await db.get(Character, c["char_id"]) if c else None
    if char is not None:
        prev = c["prev_rounds"]
        s = dict(char.settings or {})
        left = prev - 1 if isinstance(prev, int) and not isinstance(prev, bool) and prev > 1 else None
        ended = left is None and isinstance(prev, int) and not isinstance(prev, bool)
        still = (char.concentrating_spell_id is None and not s.get("concentration_item_spell")
                 and "concentration_rounds_left" not in s) if ended else (
            char.concentrating_spell_id == c["prev_spell_id"]
            and s.get("concentration_item_spell") == c["prev_item_spell"]
            and s.get("concentration_rounds_left") == left)
        if still:
            char.concentrating_spell_id = c["prev_spell_id"]
            s["concentration_rounds_left"] = prev
            if c["prev_item_spell"] is not None:
                s["concentration_item_spell"] = c["prev_item_spell"]
            char.settings = s
            await _restore_released(db, c.get("released_effects", []), created, new_ids)
    for eid in log.skip_cleared:
        eff = await db.get(ConditionEffect, new_ids.get(eid, eid))
        if eff is not None:
            eff.save_skip_once = True
    await db.flush()


async def _restore_released(db: AsyncSession, entries: list[dict], created: set[int],
                            new_ids: dict[int, int]) -> None:
    """Recreate effects an advance switched off, skipping targets changed meanwhile."""
    for x in entries:
        kind, tid = x["target"]
        slug = x["slug"]
        owner = await db.get(Character if kind == "character" else Combatant, tid)
        if owner is None or (owner.conditions or {}).get(slug) or (await db.execute(
                select(ConditionEffect.id).where(_target_filter((kind, tid)),
                                                 ConditionEffect.slug == slug))).first():
            continue
        owner.conditions = {**(owner.conditions or {}), slug: x["prev_value"]}
        eff = await _restore_row(db, ConditionEffect, x["effect_snapshot"])
        new_ids[x["effect_snapshot"]["id"]] = eff.id
        for ps in x.get("pending_saves", []):
            if ps["id"] not in created:  # created by this advance: stays undone
                await _restore_row(db, PendingSave, {**ps, "effect_id": eff.id})


async def expire_effect(db: AsyncSession, eff: ConditionEffect, history: str | None,
                        undo_list: list[dict] | None) -> str:
    """Switch the condition off on its target (dropping the effect row); returns its label.
    ``history`` (formatted with ``{label}``) is logged on a PC target."""
    from api.services.effects import _add_history, apply_conditions  # circular import
    label = condition_label(eff.slug)
    snapshot = effect_snapshot(eff)
    saves = [effect_snapshot(ps) for ps in (await db.execute(select(PendingSave).where(
        PendingSave.effect_id == eff.id).order_by(PendingSave.id))).scalars()]
    if eff.character_id is not None:
        target = ("character", eff.character_id)
        char = await db.get(Character, eff.character_id)
        prev = (char.conditions or {}).get(eff.slug)
        if history:
            _add_history(db, char.id, "condition_change", history.format(label=label))
        await apply_conditions(db, char, {eff.slug: False})
    else:
        target = ("combatant", eff.combatant_id)
        comb = await db.get(Combatant, eff.combatant_id)
        conds = dict(comb.conditions or {})
        prev = conds.pop(eff.slug, None)
        comb.conditions = conds
        await clear_effects_for(db, target, [eff.slug])
    if undo_list is not None:
        undo_list.append({"target": list(target), "slug": eff.slug, "prev_value": prev,
                          "effect_snapshot": snapshot, "pending_saves": saves})
    return label


async def release_concentration_effects(db: AsyncSession, char: Character,
                                        undo_list: list[dict] | None = None) -> list[str]:
    """Spec §5: end the effects tied to ``char``'s concentration on a spell other than the
    current one (all of them if it no longer concentrates). Returns their labels."""
    q = select(ConditionEffect).where(ConditionEffect.ends_with_concentration.is_(True),
                                      ConditionEffect.source_character_id == char.id)
    if char.concentrating_spell_id is not None:
        q = q.where(or_(ConditionEffect.source_spell_id.is_(None),
                        ConditionEffect.source_spell_id != char.concentrating_spell_id))
    history = f"Terminata (fine concentrazione di {char.name}): {{label}}"
    return [await expire_effect(db, eff, history, undo_list)
            for eff in (await db.execute(q.order_by(ConditionEffect.id))).scalars().all()]


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
    """All pending saves plus each effect's failed save, unless a newer save superseded it."""
    newest = dict((await db.execute(select(PendingSave.effect_id, func.max(PendingSave.id)).where(
        PendingSave.character_id == char_id).group_by(PendingSave.effect_id))).all())
    rows = list((await db.execute(select(PendingSave).where(
        PendingSave.character_id == char_id, PendingSave.dismissed.is_(False),
        PendingSave.status.in_(("pending", "failed"))).order_by(PendingSave.id))).scalars())
    return [r for r in rows if r.status == "pending" or newest.get(r.effect_id) == r.id]


async def effect_reads(db: AsyncSession, effects: list[ConditionEffect]) -> list[ConditionEffectRead]:
    """Read models with source names resolved (PC and monster targets alike)."""
    comb_ids = {e.source_combatant_id for e in effects if e.source_combatant_id}
    char_ids = {e.source_character_id for e in effects if e.source_character_id}
    comb_names = dict((await db.execute(select(Combatant.id, Combatant.name).where(
        Combatant.id.in_(comb_ids)))).all()) if comb_ids else {}
    char_names = dict((await db.execute(select(Character.id, Character.name).where(
        Character.id.in_(char_ids)))).all()) if char_ids else {}
    return [ConditionEffectRead(
        slug=e.slug, expiry_anchor=e.expiry_anchor, expiry_edge=e.expiry_edge,
        expiry_count=e.expiry_count, save_ability=e.save_ability, save_dc=e.save_dc,
        save_edge=e.save_edge,
        source_name=comb_names.get(e.source_combatant_id) or char_names.get(e.source_character_id),
        ends_with_concentration=e.ends_with_concentration, applied_by_gm=e.applied_by_gm,
    ) for e in effects]


def pending_read(p: PendingSave, slug: str) -> PendingSaveRead:
    return PendingSaveRead(id=p.id, slug=slug, ability=p.ability, dc=p.dc, status=p.status,
                           created_at=p.created_at, last_roll=p.last_roll)


async def character_effect_payload(
    db: AsyncSession, char_id: int,
) -> tuple[list[ConditionEffectRead], list[PendingSaveRead]]:
    """Read models for CharacterFull (source names resolved)."""
    effects = await effects_for_character(db, char_id)
    slugs = {e.id: e.slug for e in effects}
    pendings = [pending_read(p, slugs.get(p.effect_id, ""))
                for p in await open_pending_saves(db, char_id)]
    return await effect_reads(db, effects), pendings
