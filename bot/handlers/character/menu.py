"""Character main menu handler."""

from __future__ import annotations

import logging

from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from bot.db.engine import get_session
from bot.db.models import Ability, Character, Item, Spell
from bot.handlers.character import CHAR_MENU
from bot.keyboards.character import build_character_main_menu_keyboard
from bot.utils.formatting import format_character_summary
from bot.utils.i18n import get_lang, translator

logger = logging.getLogger(__name__)


async def show_character_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int | None = None,
) -> int:
    """Display the character's main menu."""
    from bot.handlers.character.selection import ACTIVE_CHAR_KEY
    from bot.handlers.character.history import HISTORY_EXTRA_MSGS_KEY

    if char_id is None:
        char_id = context.user_data.get(ACTIVE_CHAR_KEY)

    # Clean up any extra history messages still open
    extra: list[tuple[int, int]] = context.user_data.pop(HISTORY_EXTRA_MSGS_KEY, [])
    for chat_id_msg, msg_id in extra:
        try:
            await context.bot.delete_message(chat_id=chat_id_msg, message_id=msg_id)
        except Exception:
            pass

    if char_id is None:
        from bot.handlers.character.selection import show_character_selection
        return await show_character_selection(update, context)

    context.user_data[ACTIVE_CHAR_KEY] = char_id
    lang = get_lang(update)

    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            from bot.handlers.character.selection import show_character_selection
            return await show_character_selection(update, context)
        # Load relationships needed for summary
        await session.refresh(char, ["classes", "ability_scores"])
        # Load spells and abilities for active status display
        spells_result = await session.execute(
            select(Spell).where(Spell.character_id == char_id)
        )
        spells = list(spells_result.scalars().all())
        abilities_result = await session.execute(
            select(Ability).where(Ability.character_id == char_id)
        )
        abilities = list(abilities_result.scalars().all())
        # Load equipped items for summary display
        items_result = await session.execute(
            select(Item).where(Item.character_id == char_id, Item.is_equipped == True)  # noqa: E712
        )
        equipped_items_raw = list(items_result.scalars().all())

    import json as _json
    equipped_items = [
        {
            "name": it.name,
            "item_type": it.item_type or "generic",
            "item_metadata": _json.loads(it.item_metadata) if it.item_metadata else {},
        }
        for it in equipped_items_raw
    ]

    keyboard = build_character_main_menu_keyboard(char_id, lang=lang)
    dex_value = next(
        (s.value for s in char.ability_scores if s.name == "dexterity"), None
    )
    text = format_character_summary(char, spells=spells, abilities=abilities, equipped_items=equipped_items, dex_score=dex_value, lang=lang)

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(
                text=text,
                reply_markup=keyboard,
                parse_mode="MarkdownV2",
            )
        except Exception:
            await update.callback_query.message.reply_text(
                text=text,
                reply_markup=keyboard,
                parse_mode="MarkdownV2",
            )
    elif update.message:
        await update.message.reply_text(
            text=text,
            reply_markup=keyboard,
            parse_mode="MarkdownV2",
        )

    return CHAR_MENU
