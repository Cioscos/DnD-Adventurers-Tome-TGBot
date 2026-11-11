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
from api.schemas.container import CoinAdjustRequest, CoinAdjustResult, CoinMoveRequest, CoinPlacement
from api.services.containers import _coin_places, apply_coin_placements, withdraw
from core.game.containers import COINS, allocate
from api.services.character_load import get_owned_full

router = APIRouter(prefix="/characters", tags=["currency"])

_VALID_COINS = {"copper", "silver", "electrum", "gold", "platinum"}


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
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> Currency:
    await get_owned_full(char_id, user_id, session)
    return await _get_or_create_currency(char_id, session)


@router.patch("/{char_id}/currency", response_model=CurrencyRead)
async def update_currency(
    char_id: int,
    body: CurrencyUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> Currency:
    await get_owned_full(char_id, user_id, session)
    currency = await _get_or_create_currency(char_id, session)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(currency, field, max(0, value))
    return currency


@router.post("/{char_id}/currency/convert", response_model=CurrencyRead)
async def convert_currency(
    char_id: int,
    body: CurrencyConvert,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> Currency:
    char = await get_owned_full(char_id, user_id, session)
    if body.source not in _VALID_COINS or body.target not in _VALID_COINS:
        raise HTTPException(status_code=400, detail="Invalid coin type")
    if body.source == body.target:
        raise HTTPException(status_code=400, detail="Source and target must differ")
    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    currency = await _get_or_create_currency(char_id, session)
    await session.refresh(char, attribute_names=["currency"])
    try:
        withdraw(char, body.source, body.amount)
    except HTTPException:
        raise HTTPException(status_code=400, detail="Insufficient funds")
    # Same math as Currency.convert: floor in target, remainder in copper — results go to the purse.
    copper = Currency.RATES[body.source] * body.amount
    setattr(currency, body.target, getattr(currency, body.target) + copper // Currency.RATES[body.target])
    currency.copper += copper % Currency.RATES[body.target]
    return currency


async def _result(session: AsyncSession, char: Character, coin: str, placements) -> CoinAdjustResult:
    await session.flush()
    places = _coin_places(char)
    return CoinAdjustResult(
        coin_totals={c: sum(p[c] for p in places.values()) for c in COINS},
        purse=CurrencyRead.model_validate(char.currency),
        placements=[CoinPlacement(container_id=loc, amount=amt) for loc, amt in placements],
    )


@router.post("/{char_id}/currency/adjust", response_model=CoinAdjustResult)
async def adjust_currency(
    char_id: int,
    body: CoinAdjustRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> CoinAdjustResult:
    char = await get_owned_full(char_id, user_id, session)
    await _get_or_create_currency(char_id, session)
    await session.refresh(char, attribute_names=["currency"])
    if body.placements is None:
        purse = {c: getattr(char.currency, c) or 0 for c in COINS}
        try:
            plan = allocate(purse, char.items, body.coin, body.delta)
        except ValueError:
            raise HTTPException(status_code=409, detail="insufficient_funds")
    else:
        plan = [(p.container_id, p.amount) for p in body.placements]
    return await _result(session, char, body.coin, apply_coin_placements(char, body.coin, plan))


@router.post("/{char_id}/currency/move", response_model=CoinAdjustResult)
async def move_currency(
    char_id: int,
    body: CoinMoveRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> CoinAdjustResult:
    char = await get_owned_full(char_id, user_id, session)
    await _get_or_create_currency(char_id, session)
    await session.refresh(char, attribute_names=["currency"])
    places = _coin_places(char)
    if any(loc is not None and loc not in places for loc in (body.from_container_id, body.to_container_id)):
        raise HTTPException(status_code=404, detail="Container not found")
    plan = [(body.from_container_id, -body.amount), (body.to_container_id, body.amount)]
    return await _result(session, char, body.coin, apply_coin_placements(char, body.coin, plan))
