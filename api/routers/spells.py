"""Spell management endpoints."""

from __future__ import annotations

import random
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import get_current_user
from api.database import get_db
from core.db.models import Character, CharacterClass, CharacterHistory, Spell, SpellSlot
from api.schemas.character import CharacterFull
from api.schemas.common import ConcentrationSaveResult
from api.schemas.spell import (
    ConcentrationUpdate,
    RollDamageRequest,
    RollDamageResult,
    SpellCreate,
    SpellRead,
    SpellUpdate,
    SpellUseRequest,
)
from api.routers.items import _roll_dice, _DICE_RE
from api.routers._helpers import roll_concentration_save
from api.services.character_response import build_character_response
from api.services.spellcasting import build_spellcasting_info
from core.data.spellcasting import has_ritual_caster


class ConcentrationSaveRequest(BaseModel):
    damage: int

router = APIRouter(prefix="/characters", tags=["spells"])


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _add_history(session, char_id: int, event_type: str, description: str) -> None:
    session.add(CharacterHistory(
        character_id=char_id,
        timestamp=_now(),
        event_type=event_type,
        description=description,
    ))


async def _get_owned_full(char_id: int, user_id: int, session: AsyncSession) -> Character:
    result = await session.execute(
        select(Character)
        .options(
            selectinload(Character.classes),
            selectinload(Character.ability_scores),
            selectinload(Character.spells),
            selectinload(Character.spell_slots),
            selectinload(Character.items),
            selectinload(Character.currency),
            selectinload(Character.abilities),
            selectinload(Character.maps),
        )
        .where(Character.id == char_id)
    )
    char = result.scalar_one_or_none()
    if char is None:
        raise HTTPException(status_code=404, detail="Character not found")
    if char.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not your character")
    return char


def _ensure_prepare_capacity(char: Character) -> None:
    """400 se il PG ha classi preparanti e il tetto è già raggiunto.

    Grandfathering: lo stato over-cap legacy resta valido — qui si bloccano
    solo i NUOVI prepare (count >= cap), mai gli unprepare.
    """
    info = build_spellcasting_info(char)
    if info.has_preparing_class and info.prepared_count >= (info.prepared_cap or 0):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Prepared spell cap reached "
                f"({info.prepared_count}/{info.prepared_cap or 0})"
            ),
        )


@router.get("/{char_id}/spells", response_model=list[SpellRead])
async def list_spells(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    q: str | None = None,
) -> list[Spell]:
    char = await _get_owned_full(char_id, user_id, session)
    spells = char.spells
    if q:
        try:
            from rapidfuzz import process, fuzz
            names = [s.name for s in spells]
            matches = process.extract(q, names, scorer=fuzz.partial_ratio, limit=20, score_cutoff=40)
            matched_names = {m[0] for m in matches}
            spells = [s for s in spells if s.name in matched_names]
        except ImportError:
            spells = [s for s in spells if q.lower() in s.name.lower()]
    return spells


@router.post("/{char_id}/spells", response_model=SpellRead, status_code=201)
async def add_spell(
    char_id: int,
    body: SpellCreate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Spell:
    char = await _get_owned_full(char_id, user_id, session)
    if body.is_prepared and body.level >= 1:
        _ensure_prepare_capacity(char)
    spell = Spell(character_id=char_id, **body.model_dump())
    session.add(spell)
    await session.flush()
    return spell


@router.patch("/{char_id}/spells/{spell_id}", response_model=SpellRead)
async def update_spell(
    char_id: int,
    spell_id: int,
    body: SpellUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Spell:
    char = await _get_owned_full(char_id, user_id, session)
    result = await session.execute(
        select(Spell).where(Spell.id == spell_id, Spell.character_id == char_id)
    )
    spell = result.scalar_one_or_none()
    if spell is None:
        raise HTTPException(status_code=404, detail="Spell not found")
    data = body.model_dump(exclude_unset=True)
    new_level = data.get("level", spell.level)
    if data.get("is_prepared") is True and not spell.is_prepared and new_level >= 1:
        _ensure_prepare_capacity(char)
    for field, value in data.items():
        setattr(spell, field, value)
    return spell


@router.delete("/{char_id}/spells/{spell_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_spell(
    char_id: int,
    spell_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await _get_owned_full(char_id, user_id, session)
    result = await session.execute(
        select(Spell).where(Spell.id == spell_id, Spell.character_id == char_id)
    )
    spell = result.scalar_one_or_none()
    if spell is None:
        raise HTTPException(status_code=404, detail="Spell not found")
    await session.delete(spell)


@router.post("/{char_id}/spells/{spell_id}/use", response_model=CharacterFull)
async def use_spell(
    char_id: int,
    spell_id: int,
    body: SpellUseRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CharacterFull:
    char = await _get_owned_full(char_id, user_id, session)

    # Verify the spell belongs to this character
    result = await session.execute(
        select(Spell).where(Spell.id == spell_id, Spell.character_id == char_id)
    )
    spell = result.scalar_one_or_none()
    if spell is None:
        raise HTTPException(status_code=404, detail="Spell not found")

    if body.as_ritual:
        # Lancio rituale: +10 min, nessuno slot (PHB). Richiede il tag ritual
        # e una classe con Ritual Casting; il vincolo "preparato" è solo un
        # avviso FE (spec 2026-06-10).
        if not spell.is_ritual:
            raise HTTPException(status_code=400, detail="Spell is not a ritual")
        if not has_ritual_caster(char.classes):
            raise HTTPException(
                status_code=400, detail="No class with Ritual Casting"
            )
        _add_history(
            session, char_id, "spell_ritual_cast",
            f"Lancio rituale: {spell.name}",
        )
    else:
        if body.slot_level is None:
            raise HTTPException(status_code=400, detail="slot_level is required")
        # Use the slot
        slot = next(
            (s for s in char.spell_slots if s.level == body.slot_level), None
        )
        if slot is None:
            raise HTTPException(status_code=400, detail=f"No slot configured for level {body.slot_level}")
        if slot.available == 0:
            raise HTTPException(status_code=400, detail=f"No slots available at level {body.slot_level}")
        slot.use_slot()

    # Activate concentration if the spell requires it
    if spell.is_concentration:
        char.concentrating_spell_id = spell_id

    return await build_character_response(session, char)


@router.patch("/{char_id}/concentration", response_model=CharacterFull)
async def update_concentration(
    char_id: int,
    body: ConcentrationUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CharacterFull:
    char = await _get_owned_full(char_id, user_id, session)
    char.concentrating_spell_id = body.spell_id
    return await build_character_response(session, char)


# ---------------------------------------------------------------------------
# Concentration saving throw
# ---------------------------------------------------------------------------

@router.post("/{char_id}/concentration/save", response_model=ConcentrationSaveResult)
async def concentration_save(
    char_id: int,
    body: ConcentrationSaveRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ConcentrationSaveResult:
    char = await _get_owned_full(char_id, user_id, session)
    return roll_concentration_save(char, body.damage, session)


# ---------------------------------------------------------------------------
# Spell damage roll
# ---------------------------------------------------------------------------

@router.post(
    "/{char_id}/spells/{spell_id}/roll_damage",
    response_model=RollDamageResult,
)
async def roll_spell_damage(
    char_id: int,
    spell_id: int,
    body: RollDamageRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RollDamageResult:
    char = await _get_owned_full(char_id, user_id, session)
    spell = next((s for s in char.spells if s.id == spell_id), None)
    if spell is None:
        raise HTTPException(status_code=404, detail="Spell not found")
    if not spell.damage_dice:
        raise HTTPException(status_code=400, detail="Spell has no damage_dice")

    casting_level = body.casting_level if body.casting_level is not None else spell.level
    if casting_level < spell.level:
        raise HTTPException(
            status_code=400,
            detail=f"casting_level {casting_level} < spell.level {spell.level}",
        )
    if casting_level > 9:
        raise HTTPException(status_code=400, detail="casting_level must be <= 9")

    # Parse spell.damage_dice using shared regex
    m = _DICE_RE.match(spell.damage_dice.strip())
    if not m:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid spell.damage_dice format: {spell.damage_dice!r}",
        )
    base_count = int(m.group(1))
    sides = int(m.group(2))
    base_bonus = int(m.group(3)) if m.group(3) else 0

    # Apply critical (double dice count, not the flat bonus)
    dice_count = base_count * 2 if body.is_critical else base_count
    if body.main_rolls is not None:
        if len(body.main_rolls) != dice_count:
            raise HTTPException(
                status_code=400,
                detail=f"main_rolls length {len(body.main_rolls)} != expected {dice_count}",
            )
        if any(v < 1 or v > sides for v in body.main_rolls):
            raise HTTPException(
                status_code=400,
                detail=f"main_rolls values must be in [1, {sides}]",
            )
        main_rolls = list(body.main_rolls)
    else:
        main_rolls = [random.randint(1, sides) for _ in range(dice_count)]

    # Optional extra_dice
    extra_rolls: list[int] = []
    extra_bonus = 0
    extra_sides = 0
    if body.extra_dice:
        em = _DICE_RE.match(body.extra_dice)
        if em:
            e_count = int(em.group(1))
            extra_sides = int(em.group(2))
            extra_bonus = int(em.group(3)) if em.group(3) else 0
            extra_dice_count = e_count * 2 if body.is_critical else e_count
            if body.extra_rolls is not None:
                if len(body.extra_rolls) != extra_dice_count:
                    raise HTTPException(
                        status_code=400,
                        detail=f"extra_rolls length {len(body.extra_rolls)} != expected {extra_dice_count}",
                    )
                if any(v < 1 or v > extra_sides for v in body.extra_rolls):
                    raise HTTPException(
                        status_code=400,
                        detail=f"extra_rolls values must be in [1, {extra_sides}]",
                    )
                extra_rolls = list(body.extra_rolls)
            else:
                extra_rolls = [random.randint(1, extra_sides) for _ in range(extra_dice_count)]

    total = sum(main_rolls) + sum(extra_rolls) + base_bonus + extra_bonus
    half_damage = (total + 1) // 2  # round up half damage (D&D 5e)

    breakdown_parts = [f"{dice_count}d{sides}={main_rolls}"]
    if extra_rolls:
        breakdown_parts.append(f"+{len(extra_rolls)}d{extra_sides}={extra_rolls}")
    if base_bonus:
        breakdown_parts.append(f"{'+' if base_bonus >= 0 else ''}{base_bonus}")
    if extra_bonus:
        breakdown_parts.append(f"{'+' if extra_bonus >= 0 else ''}{extra_bonus}")
    breakdown = " ".join(breakdown_parts) + f" = {total}"

    # Append to rolls_history if character supports it
    history_entry = {
        "type": "spell_damage",
        "spell_name": spell.name,
        "rolls": main_rolls + extra_rolls,
        "total": total,
        "damage_type": spell.damage_type,
        "casting_level": casting_level,
        "is_critical": body.is_critical,
    }
    if hasattr(char, "rolls_history") and isinstance(char.rolls_history, list):
        char.rolls_history.append(history_entry)
        await session.commit()

    main_kind = f"d{sides}"
    extra_kind = f"d{extra_sides}" if extra_rolls else None

    return RollDamageResult(
        rolls=main_rolls + extra_rolls,
        total=total,
        half_damage=half_damage,
        damage_type=spell.damage_type,
        breakdown=breakdown,
        casting_level=casting_level,
        is_critical=bool(body.is_critical),
        main_kind=main_kind,
        main_rolls=main_rolls,
        extra_kind=extra_kind,
        extra_rolls=extra_rolls,
    )
