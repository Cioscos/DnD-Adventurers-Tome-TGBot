from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from . import *
from .models import Character
from .utilities import send_and_save_message, create_main_menu_message


async def character_multiclassing_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    message_str = "<b>Gestione multi-classe</b>\n\n"
    keyboard = [[InlineKeyboardButton("Aggiungi classe", callback_data=MULTICLASSING_ADD_CALLBACK_DATA)]]

    if len(character.multi_class.classes) == 1:
        message_str += f"{character.name} non è un personaggio multi-classe."
    else:
        message_str += f"<code>{character.multi_class.list_classes()}</code>"
        keyboard.append(
            [InlineKeyboardButton("Rimuovi multi-classe", callback_data=MULTICLASSING_REMOVE_CALLBACK_DATA)])

    await send_and_save_message(
        update,
        context,
        message_str,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )

    return MULTICLASSING_ACTIONS


async def character_multiclassing_add_class_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    message_str = (
        "Mandami il nome della classe da aggiungere e il livello separati da un #\n\n"
        "Esempio: <code>Guerriero#3</code>\n\n"
        "Usa /stop per terminare o un bottone del menù principale per cambiare funzione"
    )

    await send_and_save_message(update, context, message_str, parse_mode=ParseMode.HTML)

    return MULTICLASSING_ACTIONS


async def character_multiclassing_add_class_answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    multi_class_info = update.effective_message.text
    context.user_data[CHARACTERS_CREATOR_KEY][LAST_MENU_MESSAGES].append(update.effective_message)

    try:
        class_name, class_level = multi_class_info.split("#", maxsplit=1)
    except ValueError:
        await send_and_save_message(
            update,
            context,
            "🔴 Hai inviato il messaggio in un formato sbagliato!\n\n"
            "Invialo come classe#livello o usa /stop per terminare o un bottone del menù principale per cambiare funzione"
        )
        return MULTICLASSING_ACTIONS

    if not class_name or class_name.isdigit() or not class_level or not class_level.isdigit():
        await send_and_save_message(
            update,
            context,
            "🔴 Hai inviato il messaggio in un formato sbagliato!\n\n"
            "Invialo come classe#livello o usa /stop per terminare o un bottone del menù principale per cambiare funzione"
        )
        return MULTICLASSING_ACTIONS

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]

    try:
        character.add_class(class_name, int(class_level))
    except ValueError as e:
        await send_and_save_message(update, context, str(e), parse_mode=ParseMode.HTML)
        return MULTICLASSING_ACTIONS

    await send_and_save_message(
        update,
        context,
        "Classe inserita con successo! ✅\n\n"
        f"Complimenti adesso appartieni a {character.total_classes()} classi"
    )

    msg, reply_markup = create_main_menu_message(character)
    await update.effective_message.reply_text(msg, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return FUNCTION_SELECTION


async def character_multiclassing_remove_class_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    keyboard = [
        [InlineKeyboardButton(class_name, callback_data=f"remove|{class_name}")]
        for class_name in character.multi_class.classes
    ]

    await send_and_save_message(
        update,
        context,
        "Che classe vuoi rimuovere?\n\n"
        "Usa /stop per terminare o un bottone del menù principale per cambiare funzione",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return MULTICLASSING_ACTIONS


async def character_multiclassing_remove_class_answer_query_handler(update: Update,
                                                                    context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    _, class_name = data.split("|", maxsplit=1)

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    multi_class = character.multi_class

    # Get the levels of the class to be removed
    removed_class_level = multi_class.get_class_level(class_name)

    # Remove the class from the multiclass
    multi_class.remove_class(class_name)

    # Check how many classes are left
    remaining_classes = list(multi_class.classes.keys())

    if len(remaining_classes) == 1:
        # If only one class is left, automatically assign the removed levels to it
        remaining_class_name = remaining_classes[0]
        multi_class.add_class(remaining_class_name, removed_class_level)

        # Send a confirmation message to the user
        await query.edit_message_text(
            f"La classe {class_name} è stata rimossa.\n"
            f"I {removed_class_level} livelli rimossi sono stati aggiunti alla classe {remaining_class_name}."
        )

        msg, reply_markup = create_main_menu_message(character)
        await update.effective_message.reply_text(msg, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

        return FUNCTION_SELECTION

    else:
        # Store pending reassignment information in user_data
        context.user_data[CHARACTERS_CREATOR_KEY][PENDING_REASSIGNMENT] = {
            REMOVED_CLASS_LEVEL: removed_class_level,
            REMAINING_CLASSES: remaining_classes
        }

        # If more than one class remains, ask the user to select where to allocate the removed levels
        buttons = [
            [InlineKeyboardButton(f"{class_name} (Livello {multi_class.get_class_level(class_name)})",
                                  callback_data=f"assign_levels|{class_name}|{removed_class_level}")]
            for class_name in remaining_classes
        ]
        keyboard = InlineKeyboardMarkup(buttons)

        # Send a message asking the user to select the class to assign the removed levels to
        await query.edit_message_text(
            f"La classe {class_name} è stata rimossa.\n"
            f"Seleziona una classe a cui assegnare i rimanenti {removed_class_level} livelli:",
            reply_markup=keyboard
        )

        return MULTICLASSING_ACTIONS


async def character_multiclassing_reassign_levels_query_handler(update: Update,
                                                                context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    _, class_name, removed_class_level = data.split("|", maxsplit=2)

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]

    try:
        character.add_class(class_name, int(removed_class_level))
    except ValueError as e:
        await send_and_save_message(update, context, str(e), parse_mode=ParseMode.HTML)
        return MULTICLASSING_ACTIONS

    # Clear pending reassignment since it has been handled
    context.user_data[CHARACTERS_CREATOR_KEY].pop(PENDING_REASSIGNMENT, None)

    msg, reply_markup = create_main_menu_message(character)
    await update.effective_message.reply_text(msg, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return FUNCTION_SELECTION
