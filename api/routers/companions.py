"""Companions: familiars, companions, mounts, summons and wild shape records."""
from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.database import get_db
from api.schemas.companion import (
    DICE_RE, MAX_COMPANIONS, CompanionActivate, CompanionAttack, CompanionAttackResult, CompanionCreate,
    CompanionHp, CompanionRead, CompanionUpdate,
)
from api.services.d20 import d20_history_label, d20_records, resolve_d20
from api.services.dice_stats import record_dice
from core.db.models import Ability, Character,CharacterHistory, Companion

router = APIRouter(prefix="/characters", tags=["companions"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _history(session: AsyncSession, char_id: int, event_type: str, description: str) -> None:
    session.add(CharacterHistory(
        character_id=char_id, timestamp=datetime.utcnow().isoformat(timespec="seconds"),
        event_type=event_type, description=description,
    ))


async def _get_char(session: AsyncSession, char_id: int, user_id: int) -> Character:
    char = (await session.execute(select(Character).where(Character.id == char_id))).scalar_one_or_none()
    if char is None:
        raise HTTPException(status_code=404, detail="Character not found")
    if char.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not your character")
    return char


async def _get_companion(session: AsyncSession, char_id: int, comp_id: int) -> Companion:
    comp = (await session.execute(
        select(Companion).where(Companion.id == comp_id, Companion.character_id == char_id)
    )).scalar_one_or_none()
    if comp is None:
        raise HTTPException(status_code=404, detail="Companion not found")
    return comp


async def _deactivate_others(session: AsyncSession, char_id: int, keep_id: int | None) -> None:
    """At most one active wild shape: activating one deactivates the others (no 409)."""
    res = await session.execute(
        select(Companion).where(Companion.character_id == char_id, Companion.is_active.is_(True))
    )
    for other in res.scalars():
        if other.id != keep_id:
            other.is_active = False


@router.get("/{char_id}/companions", response_model=list[CompanionRead])
async def list_companions(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[Companion]:
    await _get_char(session, char_id, user_id)
    res = await session.execute(
        select(Companion).where(Companion.character_id == char_id).order_by(Companion.id)
    )
    return list(res.scalars())


@router.post("/{char_id}/companions", response_model=CompanionRead, status_code=status.HTTP_201_CREATED)
async def create_companion(
    char_id: int,
    body: CompanionCreate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Companion:
    await _get_char(session, char_id, user_id)
    count = len((await session.execute(
        select(Companion.id).where(Companion.character_id == char_id)
    )).all())
    if count >= MAX_COMPANIONS:
        raise HTTPException(status_code=422, detail="companion_limit")
    if body.is_active and body.kind != "wild_shape":
        raise HTTPException(status_code=422, detail="active_only_wild_shape")
    data = body.model_dump()
    data["current_hp"] = min(body.max_hp if body.current_hp is None else body.current_hp, body.max_hp)
    comp = Companion(character_id=char_id, created_at=_now(), **data)
    session.add(comp)
    await session.flush()
    if comp.is_active:
        await _deactivate_others(session, char_id, comp.id)
    _history(session, char_id, "companion_added", f"Aggiunto: {comp.name}")
    return comp


@router.patch("/{char_id}/companions/{comp_id}", response_model=CompanionRead)
async def update_companion(
    char_id: int,
    comp_id: int,
    body: CompanionUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Companion:
    await _get_char(session, char_id, user_id)
    comp = await _get_companion(session, char_id, comp_id)
    changes = body.model_dump(exclude_unset=True)
    for required in ("kind", "name", "statblock", "max_hp", "armor_class", "temp_hp", "is_active", "current_hp"):
        if required in changes and changes[required] is None:
            raise HTTPException(status_code=422, detail=f"{required}_required")
    for k, v in changes.items():
        setattr(comp, k, v)
    if comp.is_active and comp.kind != "wild_shape":
        raise HTTPException(status_code=422, detail="active_only_wild_shape")
    comp.current_hp = min(comp.current_hp, comp.max_hp)
    if changes.get("is_active"):
        await _deactivate_others(session, char_id, comp.id)
    return comp


@router.post("/{char_id}/companions/{comp_id}/activate", response_model=CompanionRead)
async def activate_wild_shape(
    char_id: int,
    comp_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    body: Annotated[CompanionActivate | None, Body()] = None,
) -> Companion:
    await _get_char(session, char_id, user_id)
    comp = await _get_companion(session, char_id, comp_id)
    if comp.kind != "wild_shape":
        raise HTTPException(status_code=422, detail="active_only_wild_shape")
    if comp.is_active:
        return comp
    ability = (await session.execute(
        select(Ability).where(Ability.character_id == char_id, Ability.feature_key == "druid.wild_shape")
    )).scalars().first()
    if ability is not None:
        if (ability.uses or 0) > 0:
            ability.uses -= 1
        elif not (body and body.force):
            raise HTTPException(status_code=409, detail="no_wild_shape_uses")
    comp.is_active = True
    comp.current_hp = comp.max_hp  # each transformation starts at full HP
    await _deactivate_others(session, char_id, comp.id)
    _history(session, char_id, "companion_hp", f"Forma selvatica: {comp.name}")
    return comp


@router.post("/{char_id}/companions/{comp_id}/deactivate", response_model=CompanionRead)
async def deactivate_wild_shape(
    char_id: int,
    comp_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Companion:
    await _get_char(session, char_id, user_id)
    comp = await _get_companion(session, char_id, comp_id)
    if comp.is_active:
        comp.is_active = False
        _history(session, char_id, "companion_hp", "Forma selvatica terminata")
    return comp


@router.delete("/{char_id}/companions/{comp_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_companion(
    char_id: int,
    comp_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await _get_char(session, char_id, user_id)
    comp = await _get_companion(session, char_id, comp_id)
    await session.delete(comp)


@router.patch("/{char_id}/companions/{comp_id}/hp", response_model=CompanionRead)
async def companion_hp(
    char_id: int,
    comp_id: int,
    body: CompanionHp,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CompanionRead:
    await _get_char(session, char_id, user_id)
    comp = await _get_companion(session, char_id, comp_id)
    if body.op == "damage":
        absorbed = min(comp.temp_hp, body.value)
        comp.temp_hp -= absorbed
        comp.current_hp = max(0, comp.current_hp - (body.value - absorbed))
    elif body.op == "heal":
        comp.current_hp = min(comp.max_hp, comp.current_hp + body.value)
    else:
        comp.temp_hp = body.value
    _history(session, char_id, "companion_hp",
             f"{comp.name}: {body.op} {body.value} → PF {comp.current_hp}/{comp.max_hp}, temp {comp.temp_hp}")
    out = CompanionRead.model_validate(comp)
    out.down = comp.current_hp == 0
    return out


@router.post("/{char_id}/companions/{comp_id}/attack", response_model=CompanionAttackResult)
async def companion_attack(
    char_id: int,
    comp_id: int,
    body: CompanionAttack,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CompanionAttackResult:
    char = await _get_char(session, char_id, user_id)
    comp = await _get_companion(session, char_id, comp_id)
    actions = (comp.statblock or {}).get("actions") or []
    if body.action_index >= len(actions):
        raise HTTPException(status_code=422, detail="unknown_action")
    action = actions[body.action_index]
    if action.get("attack_bonus") is None:
        raise HTTPException(status_code=422, detail="action_not_attack")

    outcome = resolve_d20(body.mode, body.dice, None)
    bonus = int(action["attack_bonus"])
    is_critical = outcome.kept == 20
    is_fumble = outcome.kept == 1

    rolls: list[int] = []
    flat = 0
    m = DICE_RE.match(str(action.get("damage_dice") or "").strip())
    if m:
        count, sides = int(m.group(1)), int(m.group(2))
        flat = int(m.group(3) or 0)
        need = count * (2 if is_critical else 1)
        if need > 100 or not 1 <= sides <= 1000:
            raise HTTPException(status_code=422, detail="damage_dice_out_of_range")
        if body.damage_rolls is not None:
            if len(body.damage_rolls) != need or any(not 1 <= r <= sides for r in body.damage_rolls):
                raise HTTPException(status_code=422, detail="damage_rolls_mismatch")
            rolls = list(body.damage_rolls)
        else:
            rolls = [random.randint(1, sides) for _ in range(need)]
    elif body.damage_rolls:
        raise HTTPException(status_code=422, detail="damage_rolls_mismatch")
    total = 0 if is_fumble or not m else max(0, sum(rolls) + flat)

    _history(
        session, char_id, "attack_roll",
        f"{comp.name} - {action.get('name', 'Attacco')}: colpire {d20_history_label(outcome)}+{bonus}={outcome.kept + bonus}"
        + (" (CRITICO!)" if is_critical else " (FUMBLE!)" if is_fumble else "")
        + (f" | Danno: {total}" if m else ""),
    )
    record_dice(char, d20_records(outcome) + ([(f"d{m.group(2)}", r) for r in rolls] if m and not is_fumble else []))
    return CompanionAttackResult(
        to_hit_die=outcome.kept, to_hit_bonus=bonus, to_hit_total=outcome.kept + bonus,
        dice=outcome.dice, mode=outcome.mode, is_critical=is_critical, damage_rolls=rolls,
        damage_total=total, damage_type=action.get("damage_type"),
    )
