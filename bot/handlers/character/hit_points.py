"""HP management and combat handler (damage, healing, HP set)."""

from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.db.engine import get_session
from bot.db.models import Character
from bot.handlers.character import (
    CHAR_HP_MENU,
    CHAR_HP_SET,
    CHAR_HP_DAMAGE,
    CHAR_HP_HEAL,
    CHAR_MENU,
)
from bot.keyboards.character import build_hp_keyboard, build_cancel_keyboard
from bot.utils.formatting import format_hp
from bot.utils.i18n import get_lang, translator

logger = logging.getLogger(__name__)

# user_data keys for pending HP operations
_OP_KEY = "char_hp_pending_op"


async def show_hp_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    lang = get_lang(update)
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU

    keyboard = build_hp_keyboard(char_id, lang=lang)
    text = format_hp(char, lang=lang)
    await _edit_or_reply(update, text, keyboard)
    return CHAR_HP_MENU


async def ask_hp_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    operation: str,
) -> int:
    """Ask the user to type a numeric value for the HP operation."""
    lang = get_lang(update)
    context.user_data[_OP_KEY] = {"char_id": char_id, "op": operation}
    prompts = {
        "set_max":     translator.t("character.hp.prompt_set_max", lang=lang),
        "set_current": translator.t("character.hp.prompt_set_current", lang=lang),
        "damage":      translator.t("character.hp.prompt_damage", lang=lang),
        "heal":        translator.t("character.hp.prompt_heal", lang=lang),
    }
    text = prompts.get(operation, translator.t("character.hp.prompt_set_max", lang=lang))
    await _edit_or_reply(update, text, build_cancel_keyboard(char_id, "char_hp", lang=lang))
    state_map = {
        "set_max":     CHAR_HP_SET,
        "set_current": CHAR_HP_SET,
        "damage":      CHAR_HP_DAMAGE,
        "heal":        CHAR_HP_HEAL,
    }
    return state_map.get(operation, CHAR_HP_MENU)


async def handle_hp_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Process the numeric text input for HP operations."""
    from bot.handlers.character.menu import show_character_menu

    if update.message is None:
        return CHAR_HP_MENU

    lang = get_lang(update)
    pending = context.user_data.pop(_OP_KEY, None)
    if pending is None:
        return CHAR_HP_MENU

    char_id: int = pending["char_id"]
    operation: str = pending["op"]

    try:
        value = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text(
            translator.t("character.common.invalid_number", lang=lang),
            parse_mode="MarkdownV2",
        )
        context.user_data[_OP_KEY] = pending
        state_map = {"set_max": CHAR_HP_SET, "set_current": CHAR_HP_SET,
                     "damage": CHAR_HP_DAMAGE, "heal": CHAR_HP_HEAL}
        return state_map.get(operation, CHAR_HP_MENU)

    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU

        if operation == "set_max":
            char.hit_points = max(0, value)
        elif operation == "set_current":
            char.current_hit_points = max(0, min(value, char.hit_points))
        elif operation == "damage":
            char.current_hit_points = max(0, char.current_hit_points - value)
        elif operation == "heal":
            new_hp = char.current_hit_points + value
            if new_hp > char.hit_points:
                # Over-healing: cap to max
                char.current_hit_points = char.hit_points
            else:
                char.current_hit_points = new_hp

    await update.message.reply_text(translator.t("character.common.updated", lang=lang), parse_mode="MarkdownV2")
    # Fire-and-forget: update any active party messages for this character
    asyncio.create_task(_trigger_party_update(char_id, context))
    return await show_hp_menu(update, context, char_id)


async def handle_rest(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    rest_type: str,
) -> int:
    """Perform a short or long rest."""
    from bot.db.models import Ability, RestorationType, SpellSlot
    from bot.handlers.character.class_resources import restore_class_resources_on_rest
    from sqlalchemy import select

    lang = get_lang(update)

    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU

        if rest_type == "long":
            char.current_hit_points = char.hit_points
            # Clear active concentration
            was_concentrating = char.concentrating_spell_id is not None
            char.concentrating_spell_id = None
            # Restore all spell slots
            slots_res = await session.execute(
                select(SpellSlot).where(SpellSlot.character_id == char_id)
            )
            for slot in slots_res.scalars():
                slot.restore_all()
            # Restore long-rest abilities
            abilities_res = await session.execute(
                select(Ability).where(Ability.character_id == char_id)
            )
            for ability in abilities_res.scalars():
                if ability.restoration_type == RestorationType.LONG_REST:
                    ability.restore()
            msg = translator.t("character.rest.long_completed", lang=lang)
            if was_concentrating:
                msg += translator.t("character.rest.conc_interrupted", lang=lang)
        else:
            # Short rest: clear concentration + restore short-rest abilities
            was_concentrating = char.concentrating_spell_id is not None
            char.concentrating_spell_id = None
            abilities_res = await session.execute(
                select(Ability).where(Ability.character_id == char_id)
            )
            for ability in abilities_res.scalars():
                if ability.restoration_type == RestorationType.SHORT_REST:
                    ability.restore()
            msg = translator.t("character.rest.short_completed", lang=lang)
            if was_concentrating:
                msg += translator.t("character.rest.conc_interrupted", lang=lang)

    # Restore class resources outside the session to avoid nested session issues
    await restore_class_resources_on_rest(char_id, rest_type)

    if update.callback_query:
        await update.callback_query.answer()

    await _edit_or_reply(update, msg)
    from bot.handlers.character.menu import show_character_menu
    # Fire-and-forget: update any active party messages for this character
    asyncio.create_task(_trigger_party_update(char_id, context))
    return await show_character_menu(update, context, char_id=char_id)


# ---------------------------------------------------------------------------
# Helpers
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


async def _trigger_party_update(char_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fire-and-forget wrapper that calls maybe_update_party_message."""
    try:
        from bot.handlers.party import maybe_update_party_message
        await maybe_update_party_message(char_id, context.bot)
    except Exception as e:
        logger.warning("Party update trigger failed for char %s: %s", char_id, e)
