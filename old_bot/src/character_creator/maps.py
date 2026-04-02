import os
from typing import Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, File
from telegram.constants import ParseMode, FileSizeLimit
from telegram.ext import ContextTypes

from . import *
from .models import Character
from .utilities import send_and_save_message

MAPS_DIR_PATH = FILES_DIR_PATH + 'maps'


def create_maps_menu(character: Character) -> Tuple[str, InlineKeyboardMarkup]:
    message_str = "<b>Mappe del mondo</b>\n\n"
    keyboard = []

    if not character.maps:
        message_str += "Non ci sono ancora delle mappe memorizzate 🤷‍♂️"

    else:
        message_str += ("Seleziona una zona da visualizzare premendo i pulsanti sottostanti o inseriscine una nuova "
                        "premendo il pulsante <b><i>\"Inserisci nuove mappe\"</i></b>\n\n"
                        "Usa /stop per terminare o un bottone del menù principale per cambiare funzione")

        for zone, maps_paths in character.maps.items():
            keyboard.append([InlineKeyboardButton(zone, callback_data=(zone, maps_paths))])

    keyboard.append([InlineKeyboardButton('Inserisci nuove mappe', callback_data=INSERT_NEW_MAPS_CALLBACK_DATA)])

    return message_str, InlineKeyboardMarkup(keyboard)


async def character_creation_maps_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    message_str, reply_markup = create_maps_menu(character)

    await send_and_save_message(update, context, message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return MAPS_MANAGEMENT


async def character_creation_show_maps_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    zone, maps_paths = query.data

    await send_and_save_message(update, context,
                                f"Usa /stop per terminare o un bottone del menù principale per cambiare funzione\n\n"
                                f"Queste sono le mappe della zona {zone}")

    for path in maps_paths:
        keyboard = [
            [InlineKeyboardButton('Cancella', callback_data=f"{DELETE_SINGLE_MAP_CALLBACK_DATA}|{path}|{zone}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        message = await update.effective_message.reply_document(path, reply_markup=reply_markup)
        context.user_data[CHARACTERS_CREATOR_KEY][LAST_MENU_MESSAGES].append(message)

    message_str = "Scegli cosa vuoi fare"
    keyboard = [
        [InlineKeyboardButton('Aggiungi nuova mappa', callback_data=f"{ADD_NEW_MAP_CALLBACK_DATA}|{zone}")],
        [InlineKeyboardButton('Cancella tutte le mappe', callback_data=f"{DELETE_ALL_ZONE_MAPMS_CALLBACK_DATA}|{zone}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await send_and_save_message(update, context, message_str, reply_markup=reply_markup)

    return MAPS_MANAGEMENT


async def character_creator_delete_single_map_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data

    _, path, zone = data.split('|')
    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    character.maps[zone].remove(path)

    await query.delete_message()

    return MAPS_MANAGEMENT


async def character_creator_add_map_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data

    _, zone = data.split('|')
    context.user_data[CHARACTERS_CREATOR_KEY][TEMP_ZONE_NAME] = zone

    message_str = (f"Usa /stop per terminare o un bottone del menù principale per cambiare funzione\n\n"
                   f"Mandami la mappa come immagine o file")
    await send_and_save_message(update, context, message_str)

    context.user_data[CHARACTERS_CREATOR_KEY][ADD_OR_INSERT_MAPS] = 'add'

    return ADD_MAPS_FILES


async def character_creation_add_maps_done_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data[CHARACTERS_CREATOR_KEY][LAST_MENU_MESSAGES].append(update.effective_message)
    zone = context.user_data[CHARACTERS_CREATOR_KEY][TEMP_ZONE_NAME]
    files_paths = context.user_data[CHARACTERS_CREATOR_KEY][TEMP_MAPS_PATHS]

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    character.maps[zone].extend(files_paths)

    context.user_data[CHARACTERS_CREATOR_KEY].pop(TEMP_ZONE_NAME, None)
    context.user_data[CHARACTERS_CREATOR_KEY].pop(TEMP_MAPS_PATHS, None)

    await send_and_save_message(update, context, "Mappe aggiunte con successo ✅")
    message_str, reply_markup = create_maps_menu(character)
    await send_and_save_message(update, context, message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return MAPS_MANAGEMENT


async def character_creation_maps_delete_all_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data

    _, zone = data.split('|')
    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    character.maps.pop(zone, None)

    await send_and_save_message(update, context, f"Le mappe della zona {zone} sono state cancellate con successo ✅")
    message_str, reply_markup = create_maps_menu(character)
    await send_and_save_message(update, context, message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return MAPS_MANAGEMENT


async def character_creation_new_maps_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    message_str = (f"Usa /stop per terminare o un bottone del menù principale per cambiare funzione\n\n"
                   f"Inviami il nome della zona rappresentata dalle mappe")
    await query.edit_message_text(message_str)

    context.user_data[CHARACTERS_CREATOR_KEY][ADD_OR_INSERT_MAPS] = 'insert'

    return MAPS_ZONE


async def character_creation_ask_maps_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.effective_message
    context.user_data[CHARACTERS_CREATOR_KEY][LAST_MENU_MESSAGES].append(message)
    text = message.text
    context.user_data[CHARACTERS_CREATOR_KEY][TEMP_ZONE_NAME] = text

    message_str = (f"Usa /stop per terminare o un bottone del menù principale per cambiare funzione\n\n"
                   f"Mandami la mappa come immagine o file")
    await send_and_save_message(update, context, message_str)

    return MAPS_FILES


async def store_map_file_or_photo(file: File, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # create the folder for the file
    os.makedirs(MAPS_DIR_PATH, exist_ok=True)
    # Download the file on the disk
    file_name = file.file_path.split('/')[-1].split('.')[0]
    file_ext = file.file_path.split('/')[-1].split('.')[1]
    file_path = os.path.join(MAPS_DIR_PATH, f"{file_name}.{file_ext}")
    final_file_path = await file.download_to_drive(file_path)
    # save the file path in a temp location
    if TEMP_MAPS_PATHS not in context.user_data[CHARACTERS_CREATOR_KEY]:
        context.user_data[CHARACTERS_CREATOR_KEY][TEMP_MAPS_PATHS] = []

    context.user_data[CHARACTERS_CREATOR_KEY][TEMP_MAPS_PATHS].append(str(final_file_path))

    message_str = (f"Invia un altro file o foto oppure usa il comando /done per terminare\n\n"
                   f"Puoi sempre usare il comando /stop per terminare la conversazione oppure premere su un pulsante "
                   f"del menu principale")
    await send_and_save_message(update, context, message_str)

    if context.user_data[CHARACTERS_CREATOR_KEY][ADD_OR_INSERT_MAPS] == 'insert':
        return MAPS_FILES
    else:
        return ADD_MAPS_FILES


async def character_creation_store_map_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.effective_message
    context.user_data[CHARACTERS_CREATOR_KEY][LAST_MENU_MESSAGES].append(message)
    document = message.effective_attachment

    if document.file_size > FileSizeLimit.FILESIZE_DOWNLOAD:
        await send_and_save_message(update, context, "Il file inviato è troppo grande!\n"
                                                     "La dimensione massima è di 20MB")
        return MAPS_FILES

    file = await document.get_file()
    return await store_map_file_or_photo(file, update, context)


async def character_creation_store_map_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.effective_message
    context.user_data[CHARACTERS_CREATOR_KEY][LAST_MENU_MESSAGES].append(message)
    photo = await message.effective_attachment[-1].get_file()

    return await store_map_file_or_photo(photo, update, context)


async def character_creation_maps_done_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data[CHARACTERS_CREATOR_KEY][LAST_MENU_MESSAGES].append(update.effective_message)
    zone = context.user_data[CHARACTERS_CREATOR_KEY][TEMP_ZONE_NAME]
    files_paths = context.user_data[CHARACTERS_CREATOR_KEY][TEMP_MAPS_PATHS]

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    character.maps[zone] = files_paths

    context.user_data[CHARACTERS_CREATOR_KEY].pop(TEMP_ZONE_NAME, None)
    context.user_data[CHARACTERS_CREATOR_KEY].pop(TEMP_MAPS_PATHS, None)

    await send_and_save_message(update, context, "Mappe salvate con successo!")
    message_str, reply_markup = create_maps_menu(character)
    await send_and_save_message(update, context, message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return MAPS_MANAGEMENT
