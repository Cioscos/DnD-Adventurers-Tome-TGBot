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
from api.routers.hp import _get_owned_full
from api.routers.items import _option_damage
from api.services.d20 import d20_history_label, d20_records, resolve_applied
from api.services.dice_stats import record_dice
from api.services.rules_options import merge_options, option_result, use_options
from api.services.rules_turn import refuse_if_incapacitated
from api.services.wild_shape import deactivate_other_forms, end_form, form_limits, start_form
from core.db.models import Ability, Character, CharacterHistory, Companion
from core.rules.companions import companion_stats
from core.rules.forms import beast_proficiency, form_violations
from core.rules.modifiers import Applied, modifiers_for

router = APIRouter(prefix="/characters", tags=["companions"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _history(session: AsyncSession, char_id: int, event_type: str, description: str) -> None:
    session.add(CharacterHistory(
        character_id=char_id, timestamp=datetime.utcnow().isoformat(timespec="seconds"),
        event_type=event_type, description=description,
    ))


async def _get_char(session: AsyncSession, char_id: int, user_id: int) -> Character:
    return await _get_owned_full(char_id, user_id, session)


def _read(char: Character, comp: Companion) -> CompanionRead:
    """La riga com'è scritta, con PF, CA e bonus del compagno di privilegio calcolati dal livello e dalla competenza."""
    out = CompanionRead.model_validate(comp)
    stats = companion_stats(char, comp)
    if stats is not None:
        out.max_hp = stats.max_hp if stats.max_hp is not None else comp.max_hp
        out.armor_class = stats.armor_class if stats.armor_class is not None else comp.armor_class
        out.attack_bonus_extra, out.damage_bonus_extra = stats.attack_bonus, stats.damage_bonus
        out.current_hp = min(comp.current_hp, out.max_hp)
    return out


def _effective_max_hp(char: Character, comp: Companion) -> int:
    stats = companion_stats(char, comp)
    return stats.max_hp if stats is not None and stats.max_hp is not None else comp.max_hp


async def _get_companion(session: AsyncSession, char_id: int, comp_id: int) -> Companion:
    comp = (await session.execute(
        select(Companion).where(Companion.id == comp_id, Companion.character_id == char_id)
    )).scalar_one_or_none()
    if comp is None:
        raise HTTPException(status_code=404, detail="Companion not found")
    return comp


@router.get("/{char_id}/companions", response_model=list[CompanionRead])
async def list_companions(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[CompanionRead]:
    char = await _get_char(session, char_id, user_id)
    res = await session.execute(
        select(Companion).where(Companion.character_id == char_id).order_by(Companion.id)
    )
    return [_read(char, c) for c in res.scalars()]


@router.post("/{char_id}/companions", response_model=CompanionRead, status_code=status.HTTP_201_CREATED)
async def create_companion(
    char_id: int,
    body: CompanionCreate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CompanionRead:
    char = await _get_char(session, char_id, user_id)
    rows = list((await session.execute(select(Companion).where(Companion.character_id == char_id))).scalars())
    if len(rows) >= MAX_COMPANIONS:
        raise HTTPException(status_code=422, detail="companion_limit")
    if body.is_active and body.kind != "wild_shape":
        raise HTTPException(status_code=422, detail="active_only_wild_shape")
    limits = form_limits(char)
    if body.kind == "wild_shape" and limits is not None and limits.known_forms is not None:
        if sum(c.kind == "wild_shape" for c in rows) >= limits.known_forms:  # 2024: forme conosciute, se ne sostituisce una
            raise HTTPException(status_code=422, detail="known_forms_limit")
    data = body.model_dump()
    data["current_hp"] = min(body.max_hp if body.current_hp is None else body.current_hp, body.max_hp)
    comp = Companion(character_id=char_id, created_at=_now(), **data)
    if body.current_hp is None and body.feature_key:  # parte dai PF che il privilegio gli dà
        comp.current_hp = _effective_max_hp(char, comp)
    session.add(comp)
    await session.flush()
    if comp.is_active:
        await deactivate_other_forms(session, char_id, comp.id)
        start_form(char, comp)
    _history(session, char_id, "companion_added", f"Aggiunto: {comp.name}")
    return _read(char, comp)


@router.patch("/{char_id}/companions/{comp_id}", response_model=CompanionRead)
async def update_companion(
    char_id: int,
    comp_id: int,
    body: CompanionUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CompanionRead:
    char = await _get_char(session, char_id, user_id)
    comp = await _get_companion(session, char_id, comp_id)
    was_active = comp.is_active
    changes = body.model_dump(exclude_unset=True)
    for required in ("kind", "name", "statblock", "max_hp", "armor_class", "temp_hp", "is_active", "current_hp"):
        if required in changes and changes[required] is None:
            raise HTTPException(status_code=422, detail=f"{required}_required")
    for k, v in changes.items():
        setattr(comp, k, v)
    if comp.is_active and comp.kind != "wild_shape":
        raise HTTPException(status_code=422, detail="active_only_wild_shape")
    comp.current_hp = min(comp.current_hp, _effective_max_hp(char, comp))
    if comp.is_active and not was_active:
        await deactivate_other_forms(session, char_id, comp.id)
        start_form(char, comp)
    elif was_active and not comp.is_active:
        end_form(char, comp)
    return _read(char, comp)


@router.post("/{char_id}/companions/{comp_id}/activate", response_model=CompanionRead)
async def activate_wild_shape(
    char_id: int,
    comp_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    body: Annotated[CompanionActivate | None, Body()] = None,
) -> CompanionRead:
    char = await _get_char(session, char_id, user_id)
    comp = await _get_companion(session, char_id, comp_id)
    if comp.kind != "wild_shape":
        raise HTTPException(status_code=422, detail="active_only_wild_shape")
    if comp.is_active:
        return _read(char, comp)
    if char.is_dead or char.current_hit_points == 0:
        raise HTTPException(status_code=409, detail="character_down")
    force = bool(body and body.force)
    limits = form_limits(char)
    reasons = form_violations(limits, comp.statblock or {}) if limits is not None else []
    if reasons and not force:  # la forma rompe i limiti di livello e circolo: si ammette solo confermando
        raise HTTPException(status_code=409, detail={"code": "form_not_allowed", "reasons": reasons})
    ability = (await session.execute(
        select(Ability).where(Ability.character_id == char_id, Ability.feature_key == "druid.wild_shape")
    )).scalars().first()
    if ability is not None and ability.max_uses is not None:  # NULL: illimitata
        if (ability.uses or 0) > 0:
            ability.uses -= 1
        elif not force:
            raise HTTPException(status_code=409, detail="no_wild_shape_uses")
    comp.is_active = True
    comp.current_hp = comp.max_hp  # each transformation starts at full HP
    comp.temp_hp = 0
    await deactivate_other_forms(session, char_id, comp.id)
    start_form(char, comp)
    _history(session, char_id, "companion_hp", f"Forma selvatica: {comp.name}")
    return _read(char, comp)


@router.post("/{char_id}/companions/{comp_id}/deactivate", response_model=CompanionRead)
async def deactivate_wild_shape(
    char_id: int,
    comp_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CompanionRead:
    char = await _get_char(session, char_id, user_id)
    comp = await _get_companion(session, char_id, comp_id)
    if comp.is_active:
        end_form(char, comp)
        _history(session, char_id, "companion_hp", "Forma selvatica terminata")
    return _read(char, comp)


@router.delete("/{char_id}/companions/{comp_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_companion(
    char_id: int,
    comp_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    char = await _get_char(session, char_id, user_id)
    comp = await _get_companion(session, char_id, comp_id)
    if comp.is_active:
        end_form(char, comp)
    await session.delete(comp)


@router.patch("/{char_id}/companions/{comp_id}/hp", response_model=CompanionRead)
async def companion_hp(
    char_id: int,
    comp_id: int,
    body: CompanionHp,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CompanionRead:
    char = await _get_char(session, char_id, user_id)
    comp = await _get_companion(session, char_id, comp_id)
    if body.op == "damage":
        absorbed = min(comp.temp_hp, body.value)
        comp.temp_hp -= absorbed
        comp.current_hp = max(0, comp.current_hp - (body.value - absorbed))
    elif body.op == "heal":
        comp.current_hp = min(_effective_max_hp(char, comp), comp.current_hp + body.value)
    else:
        comp.temp_hp = body.value
    out = _read(char, comp)
    _history(session, char_id, "companion_hp",
             f"{comp.name}: {body.op} {body.value} → PF {out.current_hp}/{out.max_hp}, temp {comp.temp_hp}")
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

    # In Forma Selvatica attacca il personaggio: le sue condizioni restano; un compagno è un altro combattente.
    applied = Applied()
    in_form = comp.kind == "wild_shape" and comp.is_active
    if in_form:
        refuse_if_incapacitated(char)
        applied = modifiers_for(char, "attack", ability="strength")
    opts = use_options(session, char, "attack", body)
    merge_options(applied, opts)
    outcome = resolve_applied(body.mode, body.dice, None, applied)
    stats = companion_stats(char, comp)
    # in forma vale il bonus di competenza più alto fra la bestia (dal GS) e il druido
    pb_extra = max(0, char.proficiency_bonus - beast_proficiency((comp.statblock or {}).get("challenge_rating"))) if in_form else 0
    bonus = int(action["attack_bonus"]) + applied.flat + opts.bonus + pb_extra + (stats.attack_bonus if stats else 0)
    is_fumble = outcome.kept == 1
    is_critical = outcome.kept >= applied.crit_min or (opts.force_crit and not is_fumble)

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
    option_rolls: list[int] = []
    option_total = 0
    total = 0
    if m and not is_fumble:
        base = max(0, sum(rolls) + flat + (stats.damage_bonus if stats else 0))
        option_rolls, option_total, total = _option_damage(char, opts, is_critical, base)

    _history(
        session, char_id, "attack_roll",
        f"{comp.name} - {action.get('name', 'Attacco')}: colpire {d20_history_label(outcome)}+{bonus}={outcome.kept + bonus}"
        + (" (CRITICO!)" if is_critical else " (FUMBLE!)" if is_fumble else "")
        + (f" | Danno: {total}" if m else ""),
    )
    record_dice(char, d20_records(outcome) + ([(f"d{m.group(2)}", r) for r in rolls] if m and not is_fumble else []))
    return CompanionAttackResult(
        to_hit_die=outcome.kept, to_hit_bonus=bonus, to_hit_total=outcome.kept + bonus,
        dice=outcome.dice, mode=outcome.mode, notes=applied.notes, is_critical=is_critical, damage_rolls=rolls,
        damage_total=total, damage_type=action.get("damage_type"),
        option_result=option_result(opts, option_rolls, option_total),
    )
