"""Character selection and creation handler.

Entry point for the character management flow.  The user can:
- Select an existing character
- Create a new one (only name required)
- Delete a character
"""

from __future__ import annotations

import logging

from sqlalchemy import delete, select
from telegram import Update
from telegram.ext import ContextTypes

from bot.db.engine import get_session
from bot.db.models import ABILITY_NAMES, AbilityScore, Character, Currency
from bot.handlers.character import CHAR_NEW_NAME, CHAR_MENU, CHAR_SELECT
from bot.keyboards.character import (
    build_character_selection_keyboard,
    build_delete_confirm_keyboard,
)
from bot.models.character_state import CharAction

logger = logging.getLogger(__name__)

# user_data key
ACTIVE_CHAR_KEY = "active_char_id"


# ---------------------------------------------------------------------------
# Show character selection screen
# ---------------------------------------------------------------------------

async def show_character_selection(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Fetch user's characters and show selection menu."""
    user_id = update.effective_user.id
    async with get_session() as session:
        result = await session.execute(
            select(Character).where(Character.user_id == user_id)
        )
        characters = list(result.scalars().all())
        # Eagerly load classes for each character to build labels
        for char in characters:
            await session.refresh(char, ["classes"])

    if not characters:
        text = (
            "⚔️ *Benvenuto nel gestore dei personaggi\\!*\n\n"
            "Non hai ancora nessun personaggio\\. "
            "Inserisci il nome del tuo primo eroe:"
        )
        await _reply_or_edit(update, text)
        return CHAR_NEW_NAME

    keyboard = build_character_selection_keyboard(characters)
    text = (
        "⚔️ *I tuoi personaggi*\n\n"
        "Seleziona un personaggio o creane uno nuovo:"
    )
    await _reply_or_edit(update, text, keyboard)
    return CHAR_SELECT


# ---------------------------------------------------------------------------
# Handle new character name input
# ---------------------------------------------------------------------------

async def handle_new_character_name(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Receive the character name text, create character, show its menu."""
    from bot.handlers.character.menu import show_character_menu

    if update.message is None:
        return CHAR_NEW_NAME

    name = update.message.text.strip()
    if not name or len(name) > 100:
        await update.message.reply_text(
            "❌ Nome non valido\\. Inserisci un nome tra 1 e 100 caratteri:",
            parse_mode="MarkdownV2",
        )
        return CHAR_NEW_NAME

    user_id = update.effective_user.id
    async with get_session() as session:
        char = Character(user_id=user_id, name=name, current_hit_points=0)
        session.add(char)
        await session.flush()  # get char.id

        # Initialise default ability scores
        for ability_name in ABILITY_NAMES:
            session.add(AbilityScore(character_id=char.id, name=ability_name, value=10))

        # Initialise empty currency
        session.add(Currency(character_id=char.id))

        await session.commit()
        await session.refresh(char, ["classes", "ability_scores", "currency"])
        char_id = char.id

    context.user_data[ACTIVE_CHAR_KEY] = char_id
    await update.message.reply_text(
        f"✅ Personaggio *{_esc(name)}* creato con successo\\!",
        parse_mode="MarkdownV2",
    )
    # Start class selection as part of the creation wizard
    from bot.handlers.character.multiclass import ask_add_class
    return await ask_add_class(update, context, char_id, flow="creation")


# ---------------------------------------------------------------------------
# Character deletion
# ---------------------------------------------------------------------------

async def show_delete_confirm(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    """Show deletion confirmation screen."""
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return await show_character_selection(update, context)
        name = char.name

    keyboard = build_delete_confirm_keyboard(char_id)
    text = (
        f"🗑️ *Eliminare il personaggio '{_esc(name)}'?*\n\n"
        "⚠️ Questa azione è *irreversibile*\\. Tutti i dati del personaggio "
        "\\(oggetti, incantesimi, note, mappe\\) saranno cancellati\\."
    )
    await _reply_or_edit(update, text, keyboard)
    return CHAR_SELECT


async def handle_delete_confirm(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    """Delete character and return to selection screen."""
    async with get_session() as session:
        await session.execute(
            delete(Character).where(Character.id == char_id)
        )

    if context.user_data.get(ACTIVE_CHAR_KEY) == char_id:
        context.user_data.pop(ACTIVE_CHAR_KEY, None)

    if update.callback_query:
        await update.callback_query.answer("Personaggio eliminato.")

    return await show_character_selection(update, context)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _reply_or_edit(update: Update, text: str, keyboard=None) -> None:
    kwargs = dict(text=text, parse_mode="MarkdownV2")
    if keyboard:
        kwargs["reply_markup"] = keyboard
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(**kwargs)
    elif update.message:
        await update.message.reply_text(**kwargs)


def _esc(text: str) -> str:
    special = r"\_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in str(text))
