"""/start command handler.

Shows the top-level menu with two sections:
- 📖 Wiki D&D  (existing wiki explorer)
- ⚔️ Il mio personaggio  (character management)
"""

from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.models.character_state import CharAction
from bot.models.state import NavAction
from bot.utils.i18n import get_lang, translator

logger = logging.getLogger(__name__)


def build_main_menu_keyboard(lang: str = "it") -> InlineKeyboardMarkup:
    """Build the top-level 2-choice keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(translator.t("start.menu_wiki", lang=lang), callback_data=NavAction("wiki"))],
        [InlineKeyboardButton(translator.t("start.menu_character", lang=lang), callback_data=CharAction("char_select"))],
    ])


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command — show the main menu (private chat only)."""
    if update.message is None:
        return
    lang = get_lang(update)
    chat = update.effective_chat
    if chat is not None and chat.type in ("group", "supergroup"):
        await update.message.reply_text(
            translator.t("start.group_only", lang=lang),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return
    keyboard = build_main_menu_keyboard(lang=lang)
    await update.message.reply_text(
        translator.t("start.welcome", lang=lang),
        reply_markup=keyboard,
        parse_mode="MarkdownV2",
    )


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the main menu (usable from callback queries too)."""
    lang = get_lang(update)
    keyboard = build_main_menu_keyboard(lang=lang)
    welcome = translator.t("start.welcome", lang=lang)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            welcome, reply_markup=keyboard, parse_mode="MarkdownV2"
        )
    elif update.message:
        await update.message.reply_text(
            welcome, reply_markup=keyboard, parse_mode="MarkdownV2"
        )
