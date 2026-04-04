"""Character settings handler."""

from __future__ import annotations

import logging

from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from bot.db.engine import get_session
from bot.db.models import Character
from bot.handlers.character import CHAR_MENU, CHAR_SETTINGS_MENU
from bot.keyboards.character import build_settings_keyboard
from bot.utils.i18n import get_lang, translator

logger = logging.getLogger(__name__)


async def show_settings_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    lang = get_lang(update)
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU
        settings = char.settings or {}
        is_party_active = char.is_party_active

    spell_mgmt = settings.get("spell_management", "paginate_by_level")
    spell_label = (
        translator.t("character.settings.spell_mgmt_by_level", lang=lang)
        if spell_mgmt == "paginate_by_level"
        else translator.t("character.settings.spell_mgmt_direct", lang=lang)
    )
    party_label = (
        translator.t("character.settings.party_yes", lang=lang)
        if is_party_active
        else translator.t("character.settings.party_no", lang=lang)
    )
    title = translator.t("character.settings.title", lang=lang)
    spell_mgmt_text = translator.t("character.settings.spell_mgmt_label", lang=lang, label=spell_label)
    party_active_text = translator.t("character.settings.party_active_label", lang=lang, label=party_label)
    text = f"{title}\n\n{spell_mgmt_text}\n{party_active_text}"
    keyboard = build_settings_keyboard(char_id, settings, is_party_active=is_party_active)
    await _edit_or_reply(update, text, keyboard)
    return CHAR_SETTINGS_MENU


async def toggle_spell_management(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    lang = get_lang(update)
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU
        settings = dict(char.settings or {})
        current = settings.get("spell_management", "paginate_by_level")
        settings["spell_management"] = (
            "select_level_directly"
            if current == "paginate_by_level"
            else "paginate_by_level"
        )
        char.settings = settings

    if update.callback_query:
        await update.callback_query.answer("Impostazione aggiornata.")
    return await show_settings_menu(update, context, char_id)


async def toggle_party_active(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    """Toggle whether this character is the user's active party character.

    Ensures only one character per user has ``is_party_active = True``.
    """
    lang = get_lang(update)
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU

        if char.is_party_active:
            # Deactivate
            char.is_party_active = False
        else:
            # Deactivate all other characters for this user, then activate this one
            other_chars_result = await session.execute(
                select(Character).where(
                    Character.user_id == char.user_id,
                    Character.id != char_id,
                    Character.is_party_active.is_(True),
                )
            )
            for other in other_chars_result.scalars().all():
                other.is_party_active = False
            char.is_party_active = True

    if update.callback_query:
        await update.callback_query.answer("Impostazione aggiornata.")
    return await show_settings_menu(update, context, char_id)


# ---------------------------------------------------------------------------

async def _edit_or_reply(update: Update, text: str, keyboard=None) -> None:
    kwargs = dict(text=text, parse_mode="MarkdownV2")
    if keyboard:
        kwargs["reply_markup"] = keyboard
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(**kwargs)
    elif update.message:
        await update.message.reply_text(**kwargs)
