"""/start and /about command handlers.

The Mini App for character management is opened via the BotFather menu
button (bottom-left icon) — no reply keyboard is needed.  /start shows
only the wiki inline button and the welcome message, and is restricted
to private chats.
"""

from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.models.state import NavAction
from core.db.bot_users import register_start, set_announcements
from core.db.engine import AsyncSessionLocal
from bot.utils.i18n import get_lang, translator

logger = logging.getLogger(__name__)


def build_wiki_keyboard(lang: str = "it") -> InlineKeyboardMarkup:
    """Inline keyboard with a single entry point into the wiki."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            translator.t("start.menu_wiki", lang=lang),
            callback_data=NavAction("wiki"),
        )],
    ])


async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/about — bot info with a website link button."""
    if update.message is None:
        return
    lang = get_lang(update)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            translator.t("start.about_btn", lang=lang),
            url="https://cioscos.github.io/DnD-Adventurers-Tome-TGBot/",
        )],
    ])
    await update.message.reply_text(
        translator.t("start.about_text", lang=lang),
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start — welcome message + wiki button.  Private chat only."""
    if update.message is None:
        return
    lang = get_lang(update)
    chat = update.effective_chat
    if chat is None or chat.type != "private":
        await update.message.reply_text(
            translator.t("start.group_only", lang=lang),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    try:
        async with AsyncSessionLocal() as session:
            await register_start(session, update.effective_user.id, lang)
    except Exception:  # best-effort: /start risponde comunque
        logger.exception("Registrazione bot_users fallita")

    await update.message.reply_text(
        translator.t("start.welcome", lang=lang),
        reply_markup=build_wiki_keyboard(lang=lang),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def _set_announcements_command(update: Update, enabled: bool) -> None:
    if update.message is None:
        return
    lang = get_lang(update)
    chat = update.effective_chat
    if chat is None or chat.type != "private":
        await update.message.reply_text(
            translator.t("start.group_only", lang=lang),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return
    key = "start.subscribed" if enabled else "start.unsubscribed"
    try:
        async with AsyncSessionLocal() as session:
            await set_announcements(session, update.effective_user.id, enabled, lang)
    except Exception:
        logger.exception("Aggiornamento preferenza annunci fallito")
        key = "start.announce_error"
    await update.message.reply_text(
        translator.t(key, lang=lang), parse_mode=ParseMode.MARKDOWN_V2
    )


async def unsubscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/unsubscribe — smette di ricevere gli annunci delle nuove versioni."""
    await _set_announcements_command(update, False)


async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/subscribe — riattiva gli annunci delle nuove versioni."""
    await _set_announcements_command(update, True)
