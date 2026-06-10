"""Condivisione via messaggi preparati (Mini App → picker nativo Telegram).

La webapp chiede qui un ``prepared_message_id`` e poi chiama
``Telegram.WebApp.shareMessage(id)``. Spec:
docs/superpowers/specs/2026-06-10-group-sharing-design.md
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import get_current_user
from api.database import get_db
from api.services import telegram_notify
from core.db.models import Character, GameSession, SessionStatus

router = APIRouter(tags=["share"])


def _require_token() -> None:
    if not telegram_notify.bot_token_configured():
        raise HTTPException(status_code=503, detail="BOT_TOKEN not configured")


async def _get_owned_char(
    char_id: int, user_id: int, db: AsyncSession
) -> Character:
    result = await db.execute(
        select(Character)
        .options(selectinload(Character.classes), selectinload(Character.items))
        .where(Character.id == char_id)
    )
    char = result.scalar_one_or_none()
    if char is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")
    if char.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your character")
    return char


def _prepared_or_502(prep_id: str | None) -> dict:
    if prep_id is None:
        raise HTTPException(status_code=502, detail="Failed to prepare Telegram message")
    return {"prepared_message_id": prep_id}


@router.post("/characters/{char_id}/share/card")
async def share_character_card(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    _require_token()
    char = await _get_owned_char(char_id, user_id, db)

    classes = ", ".join(
        f"{c.class_name.capitalize()} {c.level}" for c in char.classes
    ) or "—"
    ac = (char.base_armor_class or 0) + (char.shield_armor_class or 0) + (char.magic_armor or 0)
    nat20 = int(((char.dice_stats or {}).get("d20") or {}).get("20", 0))

    lines = [f"🛡 *{char.name}*"]
    if char.race:
        lines.append(f"_{char.race}_")
    lines.append(f"⚔️ {classes}")
    lines.append(f"❤️ {char.current_hit_points}/{char.hit_points} PF · 🛡 CA {ac}")
    if nat20 > 0:
        lines.append(f"🎲 {nat20} naturali 20 in carriera")
    text = "\n".join(lines)

    prep_id = await telegram_notify.save_prepared_message(
        user_id, title=char.name, text=text, parse_mode="Markdown")
    return _prepared_or_502(prep_id)


@router.post("/characters/{char_id}/share/items/{item_id}")
async def share_item(
    char_id: int,
    item_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    _require_token()
    char = await _get_owned_char(char_id, user_id, db)
    item = next((i for i in (char.items or []) if i.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    qty = f" ×{item.quantity}" if (item.quantity or 1) > 1 else ""
    lines = [f"🎒 *{item.name}*{qty}", f"_{char.name}_"]
    if item.description:
        lines.append(item.description)
    text = "\n".join(lines)

    prep_id = await telegram_notify.save_prepared_message(
        user_id, title=item.name, text=text, parse_mode="Markdown")
    return _prepared_or_502(prep_id)


@router.post("/sessions/{session_id}/share/invite")
async def share_session_invite(
    session_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    _require_token()
    result = await db.execute(select(GameSession).where(GameSession.id == session_id))
    game_session = result.scalar_one_or_none()
    if game_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if game_session.gm_user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the Game Master can share the invite",
        )
    if game_session.status != SessionStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Session is closed")

    username = await telegram_notify.get_bot_username()
    if not username:
        raise HTTPException(status_code=502, detail="Bot username unavailable")

    title = game_session.title or "Sessione D&D"
    text = (
        f"🗡 *{title}*\n"
        f"Unisciti alla sessione con il codice *{game_session.code}* "
        f"oppure tocca il bottone qui sotto."
    )
    prep_id = await telegram_notify.save_prepared_message(
        user_id,
        title=title,
        text=text,
        parse_mode="Markdown",
        button=("Unisciti alla sessione",
                f"https://t.me/{username}?startapp=join_{game_session.code}"),
    )
    return _prepared_or_502(prep_id)
