import logging
import os
from typing import Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from . import *
from .models import Character
from .utilities import send_and_save_message, extract_3_words

VOICE_NOTES_PATH = FILES_DIR_PATH + 'voice_notes'
logger = logging.getLogger(__name__)


def create_notes_menu(character: Character) -> Tuple[str, InlineKeyboardMarkup]:
    message_str = "<b>Note dell'avventura</b>\n\n"
    keyboard = []

    if not character.notes:
        message_str += "Non ci sono ancora delle note memorizzate 🤷‍♂️"

    else:
        message_str += ("Seleziona una nota da visualizzare premendo i pulsanti sottostanti o inseriscine una nuova "
                        "premendo il pulsante <b><i>\"Inserisci nuova nota\"</i></b>\n\n"
                        "Usa /stop per terminare o un bottone del menù principale per cambiare funzione")

        for title, note in character.notes.items():
            keyboard.append([InlineKeyboardButton(title, callback_data=f"{OPEN_NOTE_CALLBACK_DATA}|{title}")])

    keyboard.append([InlineKeyboardButton('Inserisci nuova nota', callback_data=INSERT_NEW_NOTE_CALLBACK_DATA)])

    return message_str, InlineKeyboardMarkup(keyboard)


async def character_creator_notes_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    message_str, reply_markup = create_notes_menu(character)
    await send_and_save_message(update, context, message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return NOTES_MANAGEMENT


async def character_creator_new_note_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    message_str = ("Inserisci la nota usando questo formato:\n"
                   "<code>Titolo#testo nota</code>\n\n"
                   "Il titolo della nota non è obbligatorio, puoi inserire anche solo il testo\n\n"
                   "In alternativa puoi inviare un <b>messaggio vocale</b>\n\n"
                   "Usa /stop per terminare o un bottone del menù principale per cambiare funzione")
    await query.edit_message_text(message_str, parse_mode=ParseMode.HTML)

    return NOTE_ADD


async def character_creator_open_note_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    title_text = data.split('|')[1]

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    note_title, note_text = next(((title, text) for title, text in character.notes.items() if title == title_text))

    # distinguish behaviour if the note is a vocal message or a text note
    if os.path.exists(note_text):
        # the note is a voice note
        message_str = (f"Usa /stop per terminare o un bottone del menù principale per cambiare funzione\n\n"
                       f"<b>Titolo nota:</b> {note_title}")
        keyboard = [
            [InlineKeyboardButton('Elimina nota', callback_data=f"{DELETE_NOTE_CALLBACK_DATA}|{note_title}")],
            [InlineKeyboardButton('Indietro 🔙', callback_data=f"{BACK_BUTTON_CALLBACK_DATA}")]
        ]
        message = await update.effective_message.reply_voice(note_text,
                                                             caption=message_str,
                                                             reply_markup=InlineKeyboardMarkup(keyboard),
                                                             parse_mode=ParseMode.HTML)

        context.user_data[CHARACTERS_CREATOR_KEY][LAST_MENU_MESSAGES].append(message)

    else:
        # the note is a text note
        message_str = (f"Usa /stop per terminare o un bottone del menù principale per cambiare funzione\n\n"
                       f"<b>{note_title}</b>\n\n"
                       f"<i>{note_text}</i>")

        keyboard = [
            [InlineKeyboardButton('Modifica nota', callback_data=f"{EDIT_NOTE_CALLBACK_DATA}|{note_title}")],
            [InlineKeyboardButton('Elimina nota', callback_data=f"{DELETE_NOTE_CALLBACK_DATA}|{note_title}")],
            [InlineKeyboardButton('Indietro 🔙', callback_data=f"{BACK_BUTTON_CALLBACK_DATA}")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    # delete cached query data
    context.drop_callback_data(query)

    return NOTES_MANAGEMENT


async def character_creator_edit_note_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    title_text = data.split('|')[1]

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    note_title, note_text = next(((title, text) for title, text in character.notes.items() if title == title_text))

    message_str = (f"Usa /stop per terminare o un bottone del menù principale per cambiare funzione\n\n"
                   f"Premi una volta sul titolo e sul testo della nota per copiarli:\n"
                   f"<code>{note_title}</code>\n\n"
                   f"<code>{note_text}</code>\n\n"
                   f"Inserisci la nota usando questo formato:\n"
                   f"<code>Titolo#testo nota</code>\n\n"
                   f"Il titolo della nota non è obbligatorio, puoi inserire anche solo il testo")

    await query.edit_message_text(message_str, parse_mode=ParseMode.HTML)

    return NOTE_ADD


async def character_creator_delete_note_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    data = query.data
    title_text = data.split('|')[1]

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    character.notes.pop(title_text, None)

    await query.answer('Nota eliminata con successo ✅', show_alert=True)
    message_str, reply_markup = create_notes_menu(character)
    await send_and_save_message(update, context, message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return NOTES_MANAGEMENT


async def character_creator_notes_back_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    message_str, reply_markup = create_notes_menu(character)

    try:
        await query.edit_message_text(message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    except TelegramError as e:
        logger.warning(
            f"Errore nel modificare il messaggio per il pulsante indietro delle note, riprovare con sand_and_save: {e}")
        await send_and_save_message(update, context, message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return NOTES_MANAGEMENT


async def character_creator_insert_note_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data[CHARACTERS_CREATOR_KEY][LAST_MENU_MESSAGES].append(update.effective_message)
    text = update.effective_message.text
    message_splitted = text.split("#")

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    if len(message_splitted) == 1:
        note_title = extract_3_words(message_splitted[0])
        note_text = message_splitted[0]
    else:
        note_title = message_splitted[0]
        note_text = message_splitted[1]

    # manage insertion or edit
    if note_title in character.notes:
        character.notes.pop(note_title, None)
    character.notes[note_title] = note_text

    await send_and_save_message(update, context, "Nota salvata con successo! ✅")
    message_str, reply_markup = create_notes_menu(character)
    await send_and_save_message(update, context, message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return NOTES_MANAGEMENT


async def character_creator_insert_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # create voice notes folder if it doesn't exist
    os.makedirs(VOICE_NOTES_PATH, exist_ok=True)

    message = update.effective_message
    context.user_data[CHARACTERS_CREATOR_KEY][LAST_MENU_MESSAGES].append(message)
    voice = message.voice
    voice_file = await voice.get_file()
    voice_message_path = os.path.join(VOICE_NOTES_PATH, f"{voice.file_unique_id}.ogg")
    final_voice_path = await voice_file.download_to_drive(voice_message_path)

    # save the final vocal message path into userdata
    context.user_data[CHARACTERS_CREATOR_KEY][TEMP_VOICE_MESSAGE_PATH] = final_voice_path

    await send_and_save_message(update, context, "Mandami il titolo del messaggio vocale\n\n"
                                                 "Usa /stop per terminare o un bottone del menù principale per cambiare funzione")

    return VOICE_NOTE_TITLE


async def character_creator_save_voice_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.effective_message
    context.user_data[CHARACTERS_CREATOR_KEY][LAST_MENU_MESSAGES].append(message)
    voice_note_title = message.text

    if voice_note_title.strip() == '':
        await send_and_save_message(update, context, "🔴 Invia un titolo valido!")
        return VOICE_NOTE_TITLE

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    final_voice_path = context.user_data[CHARACTERS_CREATOR_KEY][TEMP_VOICE_MESSAGE_PATH]
    context.user_data[CHARACTERS_CREATOR_KEY].pop(TEMP_VOICE_MESSAGE_PATH, None)

    # manage insertion or edit
    if voice_note_title in character.notes:
        character.notes.pop(voice_note_title, None)
    character.notes[voice_note_title] = final_voice_path

    await send_and_save_message(update, context, "Nota salvata con successo! ✅")
    message_str, reply_markup = create_notes_menu(character)
    await send_and_save_message(update, context, message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return NOTES_MANAGEMENT
