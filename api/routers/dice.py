"""Dice roll endpoints."""

from __future__ import annotations

import logging
import os
import random
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.database import get_db
from bot.db.models import Character
from api.schemas.common import DiceRollRequest, DiceRollResult

logger = logging.getLogger(__name__)
_BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

router = APIRouter(prefix="/characters", tags=["dice"])

_VALID_DICE = {"d4": 4, "d6": 6, "d8": 8, "d10": 10, "d12": 12, "d20": 20, "d100": 100}
_MAX_HISTORY = 50


async def _get_owned(char_id: int, user_id: int, session: AsyncSession) -> Character:
    result = await session.execute(
        select(Character).where(Character.id == char_id)
    )
    char = result.scalar_one_or_none()
    if char is None:
        raise HTTPException(status_code=404, detail="Character not found")
    if char.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not your character")
    return char


@router.post("/{char_id}/dice/roll", response_model=DiceRollResult)
async def roll_dice(
    char_id: int,
    body: DiceRollRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DiceRollResult:
    if body.die not in _VALID_DICE:
        raise HTTPException(status_code=400, detail=f"Invalid die: {body.die}")
    if not 1 <= body.count <= 20:
        raise HTTPException(status_code=400, detail="count must be between 1 and 20")

    sides = _VALID_DICE[body.die]
    rolls = [random.randint(1, sides) for _ in range(body.count)]
    total = sum(rolls)
    notation = f"{body.count}{body.die}" if body.count > 1 else body.die

    # Save to history (capped at _MAX_HISTORY entries)
    char = await _get_owned(char_id, user_id, session)
    history = list(char.rolls_history or [])
    history.append({"notation": notation, "rolls": rolls, "total": total})
    char.rolls_history = history[-_MAX_HISTORY:]

    return DiceRollResult(notation=notation, rolls=rolls, total=total)


@router.get("/{char_id}/dice/history", response_model=list[DiceRollResult])
async def get_dice_history(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[DiceRollResult]:
    char = await _get_owned(char_id, user_id, session)
    history = list(char.rolls_history or [])
    return [
        DiceRollResult(
            notation=entry.get("notation", "?"),
            rolls=entry.get("rolls", []),
            total=entry.get("total", 0),
        )
        for entry in reversed(history)  # most recent first
    ]


class DicePostToChatRequest(BaseModel):
    notation: str
    rolls: list[int]
    total: int


@router.post("/{char_id}/dice/post-to-chat", status_code=200)
async def post_dice_to_chat(
    char_id: int,
    body: DicePostToChatRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Send a dice roll result to the user's private Telegram chat.

    Replaces the ``Telegram.WebApp.sendData()`` mechanism, which only works
    when the Mini App is opened via a reply keyboard button (and therefore
    cannot authenticate). This endpoint is called from the Mini App when
    opened via the BotFather menu button (initData present → auth works).
    """
    await _get_owned(char_id, user_id, session)

    if not _BOT_TOKEN:
        raise HTTPException(status_code=503, detail="BOT_TOKEN not configured")

    rolls = body.rolls
    if len(rolls) > 1:
        rolls_str = " + ".join(str(r) for r in rolls)
        text = f"🎲 {body.notation}: {rolls_str} = *{body.total}*"
    else:
        text = f"🎲 {body.notation}: *{body.total}*"

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"https://api.telegram.org/bot{_BOT_TOKEN}/sendMessage",
            json={"chat_id": user_id, "text": text, "parse_mode": "Markdown"},
        )

    if not resp.is_success:
        logger.warning("Telegram sendMessage failed: %s %s", resp.status_code, resp.text)
        raise HTTPException(status_code=502, detail="Failed to send Telegram message")

    return {"ok": True}


@router.delete("/{char_id}/dice/history", status_code=204)
async def clear_dice_history(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    char = await _get_owned(char_id, user_id, session)
    char.rolls_history = []
