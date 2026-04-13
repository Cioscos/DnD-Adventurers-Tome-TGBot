"""/start command handler.

Shows the wiki inline button and sets a persistent reply keyboard with the
Mini App WebApp button for character management.

The character button MUST be a ``KeyboardButton`` (reply keyboard), not an
``InlineKeyboardButton``, so that ``Telegram.WebApp.sendData()`` works —
which is required for posting dice roll results back to the chat.
"""

from __future__ import annotations

import logging
import os

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
    WebAppInfo,
)
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.models.state import NavAction
from bot.utils.i18n import get_lang, translator

logger = logging.getLogger(__name__)

_WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://cioscos.github.io/dnd_bot_revamped/app/")


def build_wiki_keyboard(lang: str = "it") -> InlineKeyboardMarkup:
    """Build the inline keyboard that only shows the wiki entry point."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(translator.t("start.menu_wiki", lang=lang), callback_data=NavAction("wiki"))],
    ])


def build_character_keyboard(lang: str = "it") -> ReplyKeyboardMarkup:
    """Build the persistent reply keyboard with the Mini App WebApp button.

    Reply keyboard (not inline) is required for ``Telegram.WebApp.sendData()``
    to work when the Mini App needs to post dice results back to the chat.
    """
    return ReplyKeyboardMarkup(
        [[KeyboardButton(
            translator.t("start.menu_character", lang=lang),
            web_app=WebAppInfo(url=_WEBAPP_URL),
        )]],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Usa il menu qui sotto…",
    )


async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /about command — send bot info with a website link button."""
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
        parse_mode="MarkdownV2",
    )


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

    # Send the welcome message with the wiki inline button.
    # The Mini App is opened via the BotFather menu button (bottom-left icon),
    # which is the only launch method that provides initData for authentication.
    await update.message.reply_text(
        translator.t("start.welcome", lang=lang),
        reply_markup=build_wiki_keyboard(lang=lang),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the wiki inline menu (used from callback queries in the wiki navigator)."""
    lang = get_lang(update)
    keyboard = build_wiki_keyboard(lang=lang)
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
