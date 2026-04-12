"""HP, rest, and death save endpoints."""

from __future__ import annotations

import random
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import get_current_user
from api.database import get_db
from bot.db.models import Character, CharacterHistory
from api.schemas.character import CharacterFull
from api.schemas.common import (
    DeathSaveUpdate,
    DeathSaveAction,
    HPOp,
    HPUpdate,
    RestRequest,
)


class HitDiceSpendRequest(BaseModel):
    class_id: int
    count: int


class HitDiceSpendResult(BaseModel):
    rolls: list[int]
    con_bonus: int
    healed: int
    new_current_hp: int

router = APIRouter(prefix="/characters", tags=["hp"])


def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M")


def _add_history(session, char_id: int, event_type: str, description: str) -> None:
    session.add(CharacterHistory(
        character_id=char_id,
        timestamp=_now(),
        event_type=event_type,
        description=description,
    ))


async def _get_owned_full(
    char_id: int, user_id: int, session: AsyncSession
) -> Character:
    from bot.db.models import CharacterClass
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")
    if char.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your character")
    return char


# ---------------------------------------------------------------------------
# HP update
# ---------------------------------------------------------------------------

@router.patch("/{char_id}/hp", response_model=CharacterFull)
async def update_hp(
    char_id: int,
    body: HPUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Character:
    char = await _get_owned_full(char_id, user_id, session)

    if body.op == HPOp.DAMAGE:
        amount = body.value
        # Absorb temp HP first
        if char.temp_hp > 0:
            absorbed = min(char.temp_hp, amount)
            char.temp_hp -= absorbed
            amount -= absorbed
        old = char.current_hit_points
        char.current_hit_points = max(0, char.current_hit_points - amount)
        _add_history(session, char.id, "hp_change",
                     f"Danni: -{body.value} HP ({old} → {char.current_hit_points})")

    elif body.op == HPOp.HEAL:
        old = char.current_hit_points
        char.current_hit_points = min(char.hit_points, char.current_hit_points + body.value)
        _add_history(session, char.id, "hp_change",
                     f"Cura: +{body.value} HP ({old} → {char.current_hit_points})")

    elif body.op == HPOp.SET_MAX:
        old = char.hit_points
        char.hit_points = max(0, body.value)
        # Clamp current to new max
        char.current_hit_points = min(char.current_hit_points, char.hit_points)
        _add_history(session, char.id, "hp_change",
                     f"HP max impostati: {old} → {char.hit_points}")

    elif body.op == HPOp.SET_CURRENT:
        old = char.current_hit_points
        char.current_hit_points = max(0, min(char.hit_points, body.value))
        _add_history(session, char.id, "hp_change",
                     f"HP correnti impostati: {old} → {char.current_hit_points}")

    elif body.op == HPOp.SET_TEMP:
        char.temp_hp = max(0, body.value)

    return char


# ---------------------------------------------------------------------------
# Rest
# ---------------------------------------------------------------------------

@router.post("/{char_id}/rest", response_model=CharacterFull)
async def rest(
    char_id: int,
    body: RestRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Character:
    char = await _get_owned_full(char_id, user_id, session)

    if body.rest_type == "long":
        char.current_hit_points = char.hit_points
        char.temp_hp = 0
        # Reset all spell slots
        for slot in char.spell_slots:
            slot.used = 0
        # Restore long-rest abilities
        for ability in char.abilities:
            if ability.restoration_type == "long_rest" and ability.max_uses is not None:
                ability.uses = ability.max_uses
        # Restore long-rest class resources
        for cls in char.classes:
            for res in cls.resources:
                if res.restoration_type == "long_rest":
                    res.current = res.total
        # Reset death saves
        char.death_saves = {"successes": 0, "failures": 0, "stable": False}
        _add_history(session, char.id, "rest", "Riposo lungo completato")

    elif body.rest_type == "short":
        healed = 0
        if body.hit_dice_used and body.hit_dice_used > 0:
            # Simple roll: average hit die value * count (frontend handles the roll display)
            healed = body.hit_dice_used
            char.current_hit_points = min(char.hit_points, char.current_hit_points + healed)
        # Restore short-rest abilities
        for ability in char.abilities:
            if ability.restoration_type == "short_rest" and ability.max_uses is not None:
                ability.uses = ability.max_uses
        # Restore short-rest class resources
        for cls in char.classes:
            for res in cls.resources:
                if res.restoration_type == "short_rest":
                    res.current = res.total
        _add_history(session, char.id, "rest",
                     f"Riposo breve completato (HP recuperati: {healed})")
    else:
        raise HTTPException(status_code=400, detail="rest_type must be 'long' or 'short'")

    return char


# ---------------------------------------------------------------------------
# Death saves
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Hit dice spending (during short rest)
# ---------------------------------------------------------------------------

@router.post("/{char_id}/hit_dice/spend", response_model=HitDiceSpendResult)
async def spend_hit_dice(
    char_id: int,
    body: HitDiceSpendRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> HitDiceSpendResult:
    char = await _get_owned_full(char_id, user_id, session)

    # Find the class
    cls = next((c for c in char.classes if c.id == body.class_id), None)
    if cls is None:
        raise HTTPException(status_code=404, detail="Class not found")
    if body.count < 1:
        raise HTTPException(status_code=400, detail="count must be >= 1")

    hit_die = cls.hit_die or 8

    # CON modifier
    con_score = next((s for s in char.ability_scores if s.name == "constitution"), None)
    con_mod = con_score.modifier if con_score else 0

    rolls = [random.randint(1, hit_die) for _ in range(body.count)]
    # Each die heals roll + CON mod (minimum 1 per die)
    per_die = [max(1, r + con_mod) for r in rolls]
    total_healed = sum(per_die)

    old_hp = char.current_hit_points
    char.current_hit_points = min(char.hit_points, old_hp + total_healed)
    actual_healed = char.current_hit_points - old_hp

    _add_history(session, char.id, "hit_dice",
                 f"Dado vita {body.count}d{hit_die}+{con_mod}: "
                 f"tiri={rolls}, curati={actual_healed} HP ({old_hp} → {char.current_hit_points})")

    return HitDiceSpendResult(
        rolls=rolls,
        con_bonus=con_mod,
        healed=actual_healed,
        new_current_hp=char.current_hit_points,
    )


@router.patch("/{char_id}/death_saves", response_model=CharacterFull)
async def update_death_saves(
    char_id: int,
    body: DeathSaveUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Character:
    char = await _get_owned_full(char_id, user_id, session)
    ds = dict(char.death_saves or {"successes": 0, "failures": 0, "stable": False})

    if body.action == DeathSaveAction.SUCCESS:
        ds["successes"] = min(3, ds.get("successes", 0) + 1)
        if ds["successes"] >= 3:
            ds["stable"] = True
            _add_history(session, char.id, "death_save", "Stabilizzato (3 successi)")
        else:
            _add_history(session, char.id, "death_save",
                         f"Tiro morte: successo ({ds['successes']}/3)")

    elif body.action == DeathSaveAction.FAILURE:
        ds["failures"] = min(3, ds.get("failures", 0) + 1)
        _add_history(session, char.id, "death_save",
                     f"Tiro morte: fallimento ({ds['failures']}/3)")

    elif body.action == DeathSaveAction.STABILIZE:
        ds["stable"] = True
        char.current_hit_points = 1
        _add_history(session, char.id, "death_save", "Stabilizzato")

    elif body.action == DeathSaveAction.RESET:
        ds = {"successes": 0, "failures": 0, "stable": False}

    char.death_saves = ds
    return char
