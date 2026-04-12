"""Handler for web_app_data messages from the Telegram Mini App.

These messages arrive when the user interacts with the character sheet Mini App
and the app calls ``Telegram.WebApp.sendData(json_string)``.

This ONLY works when the Mini App was opened via a reply keyboard button
(``KeyboardButton.web_app``), which is how we open the character sheet in
``bot/handlers/start.py``.

Currently handled payload types:
    - ``dice_roll``: Post the dice result as a plain-text message in the chat.
    - ``character_updated``: (future) Trigger a party message refresh.
"""

from __future__ import annotations

import json
import logging

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


def _format_dice_result(payload: dict) -> str:
    notation = payload.get("notation", "?")
    rolls = payload.get("rolls", [])
    total = payload.get("total", "?")

    if len(rolls) > 1:
        rolls_str = " + ".join(str(r) for r in rolls)
        return f"🎲 {notation}: {rolls_str} = **{total}**"
    return f"🎲 {notation}: **{total}**"


async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Receive structured data sent from the Mini App via ``sendData()``."""
    if update.effective_message is None:
        return
    raw = update.effective_message.web_app_data
    if raw is None:
        return

    try:
        payload = json.loads(raw.data)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Received non-JSON web_app_data: %s", raw.data)
        return

    payload_type = payload.get("type")

    if payload_type == "dice_roll":
        text = _format_dice_result(payload)
        await update.effective_message.reply_text(text, parse_mode="Markdown")

    elif payload_type == "character_updated":
        # Future: refresh the party message when the character HP changes
        # from the Mini App while a party session is active.
        char_id = payload.get("char_id")
        logger.info("Character %s updated via Mini App", char_id)

    else:
        logger.info("Unhandled web_app_data type: %s", payload_type)
