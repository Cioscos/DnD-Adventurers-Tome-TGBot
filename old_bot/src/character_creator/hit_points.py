from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from . import *
from .models import Character
from .utilities import send_and_save_message, create_main_menu_message


async def character_hit_points_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]

    await send_and_save_message(
        update,
        context,
        f"Quanti sono ora i punti ferita di {character.name}?\n"
        f"N.B. I punti ferita attuali saranno ripristinati al massimo!\n\n"
        f"Usa /stop per terminare o un bottone del menù principale per cambiare funzione"
    )

    return HIT_POINTS_REGISTRATION


async def character_hit_points_registration_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data[CHARACTERS_CREATOR_KEY][LAST_MENU_MESSAGES].append(update.effective_message)
    hit_points = update.effective_message.text

    if not hit_points or hit_points.isalpha():
        await send_and_save_message(update, context, "🔴 Inserisci un numero non una parola!\n\n"
                                                     "Usa /stop per terminare o un bottone del menù principale per cambiare funzione")
        return HIT_POINTS_REGISTRATION

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]

    # Fix retro-compatibility problem with the bug
    if isinstance(character.current_hit_points, str):
        character.current_hit_points = int(character.current_hit_points)
    if isinstance(character.hit_points, str):
        character.hit_points = int(character.hit_points)

    character.hit_points = character.current_hit_points = int(hit_points)

    await update.effective_message.reply_text(f"Punti ferita aumentati a {hit_points}!")

    msg, reply_markup = create_main_menu_message(character)
    await update.effective_message.reply_text(msg, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return FUNCTION_SELECTION
