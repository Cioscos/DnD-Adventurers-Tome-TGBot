"""Best-effort Telegram notifications from the API to users' private chats.

Single place that talks to the Bot API ``sendMessage``. Every sender here is
fire-and-forget: failures are logged and swallowed — game flow must never
break because Telegram is unreachable. ``web_app`` buttons deep-link into the
Mini App (private chats only, which is where the bot writes).
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.db.models import Character, GameSession, SessionParticipant, SessionStatus

logger = logging.getLogger(__name__)

_BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
_MINIAPP_BASE_URL = os.environ.get(
    "MINIAPP_BASE_URL",
    "https://cioscos.github.io/DnD-Adventurers-Tome-TGBot/app/",
)


def bot_token_configured() -> bool:
    return bool(_BOT_TOKEN)


def miniapp_url(route: str) -> str:
    """Deep link nella Mini App: base URL + route hash (HashRouter)."""
    return f"{_MINIAPP_BASE_URL.rstrip('/')}/#{route}"


def notifications_enabled(char: Optional[Character], category: str) -> bool:
    """Opt-out per categoria in Character.settings['notifications'].

    Default attivo — anche quando il destinatario non ha un PG (es. il GM).
    """
    if char is None:
        return True
    prefs = (char.settings or {}).get("notifications", {})
    return bool(prefs.get(category, True))


async def send_telegram_message(
    chat_id: int,
    text: str,
    *,
    parse_mode: str | None = None,
    button: tuple[str, str] | None = None,
) -> bool:
    """sendMessage in chat privata; True su 2xx, mai solleva."""
    if not _BOT_TOKEN:
        return False
    payload: dict = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if button is not None:
        label, url = button
        payload["reply_markup"] = {
            "inline_keyboard": [[{"text": label, "web_app": {"url": url}}]]
        }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{_BOT_TOKEN}/sendMessage",
                json=payload,
            )
        if not resp.is_success:
            logger.warning(
                "Telegram sendMessage failed: %s %s", resp.status_code, resp.text)
            return False
        return True
    except Exception as exc:  # noqa: BLE001 — best-effort, il gioco prosegue
        logger.warning("Telegram sendMessage error: %s", exc)
        return False


async def notify_party_emergency(db: AsyncSession, char: Character, text: str) -> None:
    """Avvisa GM + altri giocatori della sessione ATTIVA di `char`. Best-effort.

    La preferenza è del DESTINATARIO (letta dal suo PG in sessione); il GM,
    senza PG, riceve sempre.
    """
    result = await db.execute(
        select(GameSession)
        .join(SessionParticipant, SessionParticipant.session_id == GameSession.id)
        .options(selectinload(GameSession.participants))
        .where(
            GameSession.status == SessionStatus.ACTIVE,
            SessionParticipant.user_id == char.user_id,
        )
    )
    game_session = result.scalars().first()
    if game_session is None:
        return
    recipients = [p for p in game_session.participants if p.user_id != char.user_id]
    if not recipients:
        return
    char_ids = [p.character_id for p in recipients if p.character_id is not None]
    chars_by_id: dict[int, Character] = {}
    if char_ids:
        res = await db.execute(select(Character).where(Character.id.in_(char_ids)))
        chars_by_id = {c.id: c for c in res.scalars()}
    url = miniapp_url(f"/session/{game_session.id}")
    for p in recipients:
        rec_char = chars_by_id.get(p.character_id) if p.character_id else None
        if not notifications_enabled(rec_char, "party_emergency"):
            continue
        await send_telegram_message(p.user_id, text, button=("Apri la sessione", url))
