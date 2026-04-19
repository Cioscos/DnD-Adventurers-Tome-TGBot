"""Currency endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import get_current_user
from api.database import get_db
from core.db.models import Character, CharacterClass, Currency
from api.schemas.character import CharacterFull
from api.schemas.common import CurrencyConvert, CurrencyRead, CurrencyUpdate

router = APIRouter(prefix="/characters", tags=["currency"])

_VALID_COINS = {"copper", "silver", "electrum", "gold", "platinum"}


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


async def _get_or_create_currency(char_id: int, session: AsyncSession) -> Currency:
    result = await session.execute(
        select(Currency).where(Currency.character_id == char_id)
    )
    currency = result.scalar_one_or_none()
    if currency is None:
        currency = Currency(character_id=char_id)
        session.add(currency)
        await session.flush()
    return currency


@router.get("/{char_id}/currency", response_model=CurrencyRead)
async def get_currency(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Currency:
    await _get_owned_full(char_id, user_id, session)
    return await _get_or_create_currency(char_id, session)


@router.patch("/{char_id}/currency", response_model=CurrencyRead)
async def update_currency(
    char_id: int,
    body: CurrencyUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Currency:
    await _get_owned_full(char_id, user_id, session)
    currency = await _get_or_create_currency(char_id, session)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(currency, field, max(0, value))
    return currency


@router.post("/{char_id}/currency/convert", response_model=CurrencyRead)
async def convert_currency(
    char_id: int,
    body: CurrencyConvert,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Currency:
    await _get_owned_full(char_id, user_id, session)
    if body.source not in _VALID_COINS or body.target not in _VALID_COINS:
        raise HTTPException(status_code=400, detail="Invalid coin type")
    if body.source == body.target:
        raise HTTPException(status_code=400, detail="Source and target must differ")
    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    currency = await _get_or_create_currency(char_id, session)
    success = currency.convert(body.source, body.target, body.amount)
    if not success:
        raise HTTPException(status_code=400, detail="Insufficient funds")
    return currency
