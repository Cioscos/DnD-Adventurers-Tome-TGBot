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

    await update.message.reply_text(
        translator.t("start.welcome", lang=lang),
        reply_markup=build_wiki_keyboard(lang=lang),
        parse_mode=ParseMode.MARKDOWN_V2,
    )
