"""HP management and combat handler (damage, healing, HP set)."""

from __future__ import annotations

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
from bot.keyboards.character import build_hp_keyboard
from bot.utils.formatting import format_hp

logger = logging.getLogger(__name__)

# user_data keys for pending HP operations
_OP_KEY = "char_hp_pending_op"


async def show_hp_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU

    keyboard = build_hp_keyboard(char_id)
    text = format_hp(char)
    await _edit_or_reply(update, text, keyboard)
    return CHAR_HP_MENU


async def ask_hp_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    operation: str,
) -> int:
    """Ask the user to type a numeric value for the HP operation."""
    context.user_data[_OP_KEY] = {"char_id": char_id, "op": operation}
    prompts = {
        "set_max":     "✏️ Inserisci i *Punti Vita massimi*:",
        "set_current": "✏️ Inserisci i *Punti Vita attuali*:",
        "damage":      "⚔️ Inserisci i *danni subiti*:",
        "heal":        "💚 Inserisci i *Punti Vita curati*:",
    }
    text = prompts.get(operation, "Inserisci un numero:")
    await _edit_or_reply(update, text)
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

    pending = context.user_data.pop(_OP_KEY, None)
    if pending is None:
        return CHAR_HP_MENU

    char_id: int = pending["char_id"]
    operation: str = pending["op"]

    try:
        value = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text(
            "❌ Valore non valido\\. Inserisci un numero intero\\.",
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

    await update.message.reply_text("✅ Aggiornato\\!", parse_mode="MarkdownV2")
    return await show_hp_menu(update, context, char_id)


async def handle_rest(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    rest_type: str,
) -> int:
    """Perform a short or long rest."""
    from bot.db.models import Ability, RestorationType, SpellSlot
    from sqlalchemy import select

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
            msg = "🌙 *Riposo lungo completato\\!*\nHP ripristinati e slot incantesimi recuperati\\."
            if was_concentrating:
                msg += "\n🔮 Concentrazione interrotta\\."
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
            msg = "⏸️ *Riposo breve completato\\!*\nAbilità ripristinate\\."
            if was_concentrating:
                msg += "\n🔮 Concentrazione interrotta\\."

    if update.callback_query:
        await update.callback_query.answer()

    await _edit_or_reply(update, msg)
    from bot.handlers.character.menu import show_character_menu
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
