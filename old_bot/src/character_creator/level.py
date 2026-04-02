from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from . import *
from .models import Character, MultiClass
from .utilities import send_and_save_message, create_main_menu_message


async def character_change_level_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    data = query.data
    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    multi_class = character.multi_class

    if len(multi_class.classes) > 1:
        await query.answer()
        # If the character has more than one class, prompt the user to choose which class to level up/down
        buttons = [
            [InlineKeyboardButton(f"{class_name} (Livello {multi_class.get_class_level(class_name)})",
                                  callback_data=f"{data}|{class_name}")]
            for class_name in multi_class.classes.keys()
        ]
        keyboard = InlineKeyboardMarkup(buttons)
        await send_and_save_message(
            update, context, "Usa /stop per terminare o un bottone del menù principale per cambiare funzione\n\n"
                             "Scegli quale classe livellare in positivo o negativo:", reply_markup=keyboard
        )
    else:
        # If only one class, level up/down automatically
        class_name = next(iter(multi_class.classes))  # Get the only class name
        await apply_level_change(multi_class, class_name, data, query)
        msg, reply_markup = create_main_menu_message(character)
        await query.edit_message_text(msg, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return FUNCTION_SELECTION


async def character_level_change_class_choice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data

    action, class_name = data.split("|", maxsplit=1)

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    multi_class = character.multi_class

    # Apply the level change using the chosen class and action
    await apply_level_change(multi_class, class_name, action, query)
    msg, reply_markup = create_main_menu_message(character)
    await query.edit_message_text(msg, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return FUNCTION_SELECTION


async def apply_level_change(multi_class: MultiClass, class_name: str, data: str, query: CallbackQuery) -> None:
    """Apply the level change to the selected class and update the user."""
    try:
        if data == LEVEL_UP_CALLBACK_DATA:
            multi_class.level_up(class_name)
        else:
            multi_class.level_down(class_name)

        await query.answer(f"{class_name} è ora di livello {multi_class.get_class_level(class_name)}!", show_alert=True)
    except ValueError as e:
        await query.answer(str(e), show_alert=True)
