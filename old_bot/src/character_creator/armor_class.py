from typing import Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from . import *
from .models import Character
from .utilities import send_and_save_message

AC_KIND_AC = 'ac'
AC_KIND_SHIELD = 'shield'
AC_KIND_MAGIC_ARMOR = 'magic_armor'


def create_armor_class_main_menu(context: ContextTypes.DEFAULT_TYPE) -> Tuple[str, InlineKeyboardMarkup]:
    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    message_str = ('<b>Gestione classe armatura</b>\n\n'
                   f'<b>Classe armatura:</b> {character.ac}\n'
                   f'Formata da:\n'
                   f'Armatura: {character.base_armor_class}\n'
                   f'Scudo: {character.shield_armor_class}\n'
                   f'Armatura magica: {character.magic_armor}\n\n'
                   'Scegli una delle seguenti azioni')
    keyboard = [
        [
            InlineKeyboardButton('Sovrascrivi CA', callback_data=f'{ARMOR_CLASS_CALLBACK_DATA}|{AC_KIND_AC}')
        ],
        [
            InlineKeyboardButton('Sovrascrivi CA scudo', callback_data=f'{ARMOR_CLASS_CALLBACK_DATA}|{AC_KIND_SHIELD}')
        ],
        [
            InlineKeyboardButton('Armatura magica', callback_data=f'{ARMOR_CLASS_CALLBACK_DATA}|{AC_KIND_MAGIC_ARMOR}')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    return message_str, reply_markup


async def armor_class_main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    message_str = 'Usa /stop per terminare o un bottone del menù principale per cambiare funzione\n\n'
    if character.base_armor_class == 0:
        # means that the character still didn't set any armor class
        message_str += 'Mandami la classe armatura (CA) del tuo personaggio'
        await send_and_save_message(update, context, message_str)
        context.user_data[CHARACTERS_CREATOR_KEY][AC_KIND_KEY] = AC_KIND_AC

    else:
        message_str, reply_markup = create_armor_class_main_menu(context)
        await send_and_save_message(update, context, message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return ARMOR_CLASS


async def edit_ac_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    message_str = ('Usa /stop per terminare o un bottone del menù principale per cambiare funzione\n\n'
                   "Mandami la classe armatura (CA) del tuo personaggio! L'attuale sarà sovrascritta da quella che mi invierai")

    await send_and_save_message(update, context, message_str)
    context.user_data[CHARACTERS_CREATOR_KEY][AC_KIND_KEY] = AC_KIND_AC

    return ARMOR_CLASS


async def edit_shield_ac_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    message_str = ('Usa /stop per terminare o un bottone del menù principale per cambiare funzione\n\n'
                   "Mandami la classe armatura aggiunta dal tuo scudo! L'attuale sarà sovrascritta da quella che mi invierai")

    await send_and_save_message(update, context, message_str)
    context.user_data[CHARACTERS_CREATOR_KEY][AC_KIND_KEY] = AC_KIND_SHIELD
    return ARMOR_CLASS


async def edit_magic_armor_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    message_str = ('Usa /stop per terminare o un bottone del menù principale per cambiare funzione\n\n'
                   "Mandami la classe armatura dell'armatura magica! L'attuale sarà sovrascritta da quella che mi invierai")

    await send_and_save_message(update, context, message_str)
    context.user_data[CHARACTERS_CREATOR_KEY][AC_KIND_KEY] = AC_KIND_MAGIC_ARMOR
    return ARMOR_CLASS


async def armor_class_text_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.effective_message
    text = message.text
    context.user_data[CHARACTERS_CREATOR_KEY][LAST_MENU_MESSAGES].append(message)

    # check user input
    try:
        ac = int(text)
    except ValueError:
        await send_and_save_message(update, context, '🔴 Inserisci un numero non una parola!\n\n'
                                                     'Usa /stop per terminare o un bottone del menù principale per cambiare funzione')
        return ARMOR_CLASS

    ac_kind = context.user_data[CHARACTERS_CREATOR_KEY][AC_KIND_KEY]
    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]

    message_str = ''
    if ac_kind == AC_KIND_AC:
        message_str = f'Classe armatura (CA) impostata a {ac}!'
        character.base_armor_class = ac
    if ac_kind == AC_KIND_SHIELD:
        message_str = f'Classe armatura del tuo scudo impostata a {ac}!'
        character.shield_armor_class = ac
    if ac_kind == AC_KIND_MAGIC_ARMOR:
        message_str = f'Armatura magica impostata a {ac}!'
        character.magic_armor_class = ac

    await send_and_save_message(update, context, message_str)
    message_str, reply_markup = create_armor_class_main_menu(context)
    await send_and_save_message(update, context, message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return ARMOR_CLASS
