"""Character modification history handler.

Displays a paginated (multi-message) log of all changes made to a character.
The first message always contains the navigation keyboard (🏠 Menu).  If the
history is too long for one Telegram message (> 3800 chars) additional messages
are sent and their IDs stored in ``context.user_data["char_history_extra_msgs"]``
so they can be cleaned up when the user navigates back to the main menu.
"""

from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from bot.db.history import clear_history as db_clear_history
from bot.db.history import get_history
from bot.db.engine import get_session
from bot.db.models import Character
from bot.handlers.character import CHAR_HISTORY_MENU, CHAR_MENU
from bot.models.character_state import CharAction
from bot.utils.i18n import get_lang, translator

logger = logging.getLogger(__name__)

# Max chars per Telegram message (safe limit with some margin)
_CHUNK_SIZE = 3800

# Keys stored in user_data
HISTORY_EXTRA_MSGS_KEY = "char_history_extra_msgs"


def _esc(text: str) -> str:
    """Escape special MarkdownV2 characters in plain text."""
    special = r"\_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in str(text))


# Map event_type slugs to locale keys
_EVENT_TYPE_KEYS: dict[str, str] = {
    "hp_change":       "character.history.hp_change",
    "rest":            "character.history.rest",
    "ac_change":       "character.history.ac_change",
    "level_change":    "character.history.level_change",
    "multiclass_change": "character.history.multiclass_change",
    "stats_change":    "character.history.stats_change",
    "spell_slot_change": "character.history.spell_slot_change",
    "spell_change":    "character.history.spell_change",
    "bag_change":      "character.history.bag_change",
    "currency_change": "character.history.currency_change",
    "ability_change":  "character.history.ability_change",
    "condition_change": "character.history.condition_change",
}


def _format_history_chunks(
    entries: list,
    char_name: str,
    lang: str,
) -> list[str]:
    """Format history entries into MarkdownV2 chunks that fit within _CHUNK_SIZE."""
    if not entries:
        header = translator.t("character.history.title", lang=lang, name=_esc(char_name)) + "\n\n"
        header += translator.t("character.history.empty", lang=lang)
        return [header]

    total = len(entries)
    title = (
        translator.t("character.history.title", lang=lang, name=_esc(char_name)) + "\n"
        + translator.t("character.history.count", lang=lang, count=total) + "\n\n"
    )

    lines: list[str] = []
    for entry in entries:
        type_key = _EVENT_TYPE_KEYS.get(entry.event_type, "character.history.other")
        type_label = translator.t(type_key, lang=lang)
        desc_escaped = _esc(entry.description)
        ts_escaped = _esc(entry.timestamp)
        line = f"🕐 _{ts_escaped}_\n{type_label}: {desc_escaped}\n"
        lines.append(line)

    # Build chunks
    chunks: list[str] = []
    current = title
    for line in lines:
        if len(current) + len(line) + 1 > _CHUNK_SIZE:
            chunks.append(current.rstrip())
            current = line
        else:
            current += line + "\n"
    if current.strip():
        chunks.append(current.rstrip())

    return chunks


async def show_history(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
) -> int:
    """Show the character modification history, splitting into multiple messages if needed."""
    lang = get_lang(update)

    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU
        char_name = char.name

    entries = await get_history(char_id)
    chunks = _format_history_chunks(entries, char_name, lang)
    total_chunks = len(chunks)

    # Build the navigation keyboard (only on the first message)
    clear_btn = InlineKeyboardButton(
        text=translator.t("character.history.btn_clear", lang=lang),
        callback_data=CharAction("char_history", char_id=char_id, sub="clear"),
    )
    menu_btn = InlineKeyboardButton(
        text=translator.t("nav.menu", lang=lang),
        callback_data=CharAction("char_menu", char_id=char_id),
    )
    nav_keyboard = InlineKeyboardMarkup([[clear_btn], [menu_btn]])

    # Append part indicator if multiple chunks
    def _annotate(chunk: str, n: int) -> str:
        if total_chunks <= 1:
            return chunk
        indicator = translator.t(
            "character.history.part_indicator", lang=lang, n=n, total=total_chunks
        )
        return chunk + f"\n\n{indicator}"

    first_chunk = _annotate(chunks[0], 1)

    # Delete any previously stale extra messages
    await _cleanup_extra_msgs(context)

    query = update.callback_query
    if query:
        await query.answer()
        try:
            await query.edit_message_text(
                text=first_chunk,
                reply_markup=nav_keyboard,
                parse_mode="MarkdownV2",
            )
        except BadRequest:
            await query.message.reply_text(
                text=first_chunk,
                reply_markup=nav_keyboard,
                parse_mode="MarkdownV2",
            )
    elif update.message:
        await update.message.reply_text(
            text=first_chunk,
            reply_markup=nav_keyboard,
            parse_mode="MarkdownV2",
        )

    # Send additional chunks (no keyboard, just content)
    if total_chunks > 1:
        extra_msg_refs: list[tuple[int, int]] = []
        chat_id = (
            query.message.chat_id if query else update.effective_chat.id
        )
        for i, chunk in enumerate(chunks[1:], start=2):
            annotated = _annotate(chunk, i)
            try:
                sent = await context.bot.send_message(
                    chat_id=chat_id,
                    text=annotated,
                    parse_mode="MarkdownV2",
                )
                extra_msg_refs.append((chat_id, sent.message_id))
            except Exception as exc:
                logger.warning("Failed to send history chunk %s: %s", i, exc)
        context.user_data[HISTORY_EXTRA_MSGS_KEY] = extra_msg_refs

    return CHAR_HISTORY_MENU


async def handle_clear_history(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
) -> int:
    """Delete all history entries and reload the (now empty) history screen."""
    lang = get_lang(update)
    await db_clear_history(char_id)
    if update.callback_query:
        await update.callback_query.answer(
            translator.t("character.history.cleared", lang=lang)
        )
    return await show_history(update, context, char_id)


async def _cleanup_extra_msgs(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete any extra history messages stored in user_data."""
    extra: list[tuple[int, int]] = context.user_data.pop(HISTORY_EXTRA_MSGS_KEY, [])
    for chat_id, msg_id in extra:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception:
            pass
