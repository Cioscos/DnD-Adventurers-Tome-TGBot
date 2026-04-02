from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from . import *
from .models import Character
from .utilities import send_and_save_message, create_main_menu_message


async def character_long_rest_warning_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    message_str = (
        "<b>Stai per effettuare un riposo lungo!</b>\n\n"
        "Questo comporta:\n"
        "- Ripristino dei punti ferita\n"
        "- Ripristino slot incantesimo\n\n"
        "Vuoi procedere? Usa /stop per terminare o un bottone del menù principale per cambiare funzione"
    )
    keyboard = [[InlineKeyboardButton("Riposa", callback_data=LONG_REST_CALLBACK_DATA)]]

    await send_and_save_message(update, context, message_str, reply_markup=InlineKeyboardMarkup(keyboard),
                                parse_mode=ParseMode.HTML)

    return LONG_REST


async def character_long_rest_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    character.long_rest()

    await query.answer("Riposo lungo effettuato!", show_alert=True)

    msg, reply_markup = create_main_menu_message(character)
    await query.edit_message_text(msg, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return FUNCTION_SELECTION


async def character_short_rest_warning_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    message_str = (
        "<b>Stai per effettuare un riposo breve!</b>\n\n"
        "Questo comporta il ripristino di quelle azione che lo prevedono in caso di riposo breve.\n"
        "Per ora non ricarica gli slot incantesimo che prevedono di ricaricarsi con il riposo breve come quelli del Warlock.\n\n"
        "Vuoi procedere? Usa /stop per terminare o un bottone del menù principale per cambiare funzione"
    )
    keyboard = [[InlineKeyboardButton("Riposa", callback_data=SHORT_REST_CALLBACK_DATA)]]

    await send_and_save_message(update, context, message_str, reply_markup=InlineKeyboardMarkup(keyboard),
                                parse_mode=ParseMode.HTML)

    return SHORT_REST


async def character_short_rest_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    character.short_rest()

    await query.answer("Riposo breve effettuato!", show_alert=True)

    msg, reply_markup = create_main_menu_message(character)
    await query.edit_message_text(msg, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return FUNCTION_SELECTION
