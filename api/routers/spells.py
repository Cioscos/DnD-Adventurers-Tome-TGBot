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
from bot.db.models import Character, CharacterClass, CharacterHistory, Spell, SpellSlot
from api.schemas.character import CharacterFull
from api.schemas.common import RollResult
from api.schemas.spell import (
    ConcentrationUpdate,
    SpellCreate,
    SpellRead,
    SpellUpdate,
    SpellUseRequest,
)


class ConcentrationSaveRequest(BaseModel):
    damage: int

router = APIRouter(prefix="/characters", tags=["spells"])


def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M")


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
            selectinload(Character.classes).selectinload(CharacterClass.resources),
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
    await _get_owned_full(char_id, user_id, session)
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
    await _get_owned_full(char_id, user_id, session)
    result = await session.execute(
        select(Spell).where(Spell.id == spell_id, Spell.character_id == char_id)
    )
    spell = result.scalar_one_or_none()
    if spell is None:
        raise HTTPException(status_code=404, detail="Spell not found")
    for field, value in body.model_dump(exclude_unset=True).items():
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
) -> Character:
    char = await _get_owned_full(char_id, user_id, session)

    # Verify the spell belongs to this character
    result = await session.execute(
        select(Spell).where(Spell.id == spell_id, Spell.character_id == char_id)
    )
    spell = result.scalar_one_or_none()
    if spell is None:
        raise HTTPException(status_code=404, detail="Spell not found")

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

    return char


@router.patch("/{char_id}/concentration", response_model=CharacterFull)
async def update_concentration(
    char_id: int,
    body: ConcentrationUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Character:
    char = await _get_owned_full(char_id, user_id, session)
    char.concentrating_spell_id = body.spell_id
    return char


# ---------------------------------------------------------------------------
# Concentration saving throw
# ---------------------------------------------------------------------------

class ConcentrationSaveResult(RollResult):
    dc: int
    success: bool
    lost_concentration: bool


@router.post("/{char_id}/concentration/save", response_model=ConcentrationSaveResult)
async def concentration_save(
    char_id: int,
    body: ConcentrationSaveRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ConcentrationSaveResult:
    char = await _get_owned_full(char_id, user_id, session)

    dc = max(10, body.damage // 2)

    # CON modifier
    con_score = next((s for s in char.ability_scores if s.name == "constitution"), None)
    con_mod = con_score.modifier if con_score else 0

    die = random.randint(1, 20)
    total = die + con_mod
    is_crit = die == 20
    is_fumble = die == 1

    # Nat 20 = auto succeed, Nat 1 = auto fail, otherwise compare to DC
    if is_crit:
        success = True
    elif is_fumble:
        success = False
    else:
        success = total >= dc

    lost_concentration = not success and char.concentrating_spell_id is not None

    if lost_concentration:
        char.concentrating_spell_id = None

    outcome = "SUCCESSO" if success else "FALLIMENTO"
    _add_history(session, char.id, "concentration_save",
                 f"TS Concentrazione (danno {body.damage}, DC {dc}): "
                 f"d20={die}+{con_mod}={total} — {outcome}"
                 + (" → concentrazione persa" if lost_concentration else ""))

    return ConcentrationSaveResult(
        die=die,
        bonus=con_mod,
        total=total,
        is_critical=is_crit,
        is_fumble=is_fumble,
        description=f"DC {dc}",
        dc=dc,
        success=success,
        lost_concentration=lost_concentration,
    )
