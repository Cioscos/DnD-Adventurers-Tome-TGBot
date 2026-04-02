import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from . import *
from .models import Character
from .utilities import create_skull_asciart, send_and_save_message, create_main_menu_message


async def character_damage_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    await send_and_save_message(update, context, "Quanti danni hai subito?\n\n"
                                                 "Usa /stop per terminare o un bottone del menù principale per cambiare funzione")

    return DAMAGE_REGISTRATION


async def character_damage_registration_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data[CHARACTERS_CREATOR_KEY][LAST_MENU_MESSAGES].append(update.effective_message)
    damage = update.effective_message.text

    if not damage or damage.isalpha():
        await send_and_save_message(update, context, "🔴 Inserisci un numero non una parola!\n\n"
                                                     "Usa /stop per terminare o un bottone del menù principale per cambiare funzione")
        return DAMAGE_REGISTRATION

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]

    # Fix retro-compatibility problem with the bug
    if isinstance(character.current_hit_points, str):
        character.current_hit_points = int(character.current_hit_points)

    character.current_hit_points -= int(damage)

    you_died_str = f"{damage} danni subiti!\n\n\n"
    character_died = False
    if character.current_hit_points <= -character.hit_points:
        you_died_str += create_skull_asciart()
        character_died = False

    await send_and_save_message(update, context, you_died_str, parse_mode=ParseMode.HTML)
    if character_died:
        await asyncio.sleep(3)

    msg, reply_markup = create_main_menu_message(character)
    await update.effective_message.reply_text(msg, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return FUNCTION_SELECTION


async def character_healing_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    await send_and_save_message(update, context, "Di quanto ti vuoi curare?\n\n"
                                                 "Usa /stop per terminare o un bottone del menù principale per cambiare funzione")

    return HEALING_REGISTRATION


async def character_healing_value_check_or_registration_handler(update: Update,
                                                                context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data[CHARACTERS_CREATOR_KEY][LAST_MENU_MESSAGES].append(update.effective_message)
    healing = update.effective_message.text

    if not healing or not healing.isdigit():
        await send_and_save_message(update, context, "🔴 Inserisci un numero non una parola!\n\n"
                                                     "Usa /stop per terminare o un bottone del menù principale per cambiare funzione")
        return HEALING_REGISTRATION
    healing = int(healing)

    if healing <= 0:
        await send_and_save_message(update, context, "🔴 Inserisci un valore superiore a 0!\n\n"
                                                     "Usa /stop per terminare o un bottone del menù principale per cambiare funzione")
        return HEALING_REGISTRATION

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]

    if (character.current_hit_points + healing) > character.hit_points:
        keyboard = [
            [InlineKeyboardButton('Si', callback_data='y'), InlineKeyboardButton('No', callback_data='n')]
        ]
        await send_and_save_message(
            update,
            context,
            f"Se ti curi di {healing} punti ferita, aggiungerai "
            f"{(character.current_hit_points + healing) - character.hit_points} punti ferita temporanei.\n\n"
            "Vuoi aggiungere i punti ferita temporanei?\n\n"
            "Usa /stop per terminare o un bottone del menù principale per cambiare funzione",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        context.user_data[CHARACTERS_CREATOR_KEY][TEMP_HEALING_KEY] = healing
        return OVER_HEALING_CONFIRMATION

    # Fix retro-compatibility problem with the bug
    if isinstance(character.current_hit_points, str):
        character.current_hit_points = int(character.current_hit_points)
    character.current_hit_points += healing

    # flavour message
    message_str = ''
    if healing > 50:
        message_str = '<b>Diamine! Qualche divinità ti ha voluto proprio bene!</b>\n\n'

    message_str += f"Sei stato curato di {healing} PF!"
    await update.effective_message.reply_text(message_str, parse_mode=ParseMode.HTML)

    msg, reply_markup = create_main_menu_message(character)
    await update.effective_message.reply_text(msg, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return FUNCTION_SELECTION


async def character_over_healing_registration_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    healing = context.user_data[CHARACTERS_CREATOR_KEY][TEMP_HEALING_KEY]

    if data == 'y':

        character.current_hit_points += int(healing)
        await update.effective_message.reply_text(f"Sei stato curato di {healing} PF!\n"
                                                  f"{(character.current_hit_points + healing) - character.hit_points} punti ferita temporanei aggiunti!")

    elif data == 'n':
        character.current_hit_points = character.hit_points
        await update.effective_message.reply_text(f"Sei stato curato di {healing} PF!")

    context.user_data[CHARACTERS_CREATOR_KEY].pop(TEMP_HEALING_KEY, None)
    msg, reply_markup = create_main_menu_message(character)
    await update.effective_message.reply_text(msg, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return FUNCTION_SELECTION
