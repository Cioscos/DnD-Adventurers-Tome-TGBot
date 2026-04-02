from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from . import *
from .models import Character
from .utilities import send_and_save_message

# Definition of settings and their options
SETTINGS = [
    {
        'key': 'spell_management',
        'title': 'Gestione delle spell',
        'description': 'Seleziona la modalità di gestione delle spell:',
        'options': [
            {'value': 'paginate_by_level', 'text': 'Paginazione per livello spell'},
            {'value': 'select_level_directly', 'text': 'Selezione diretta del livello spell'}
        ]
    },
    {
        'key': 'special_currency_management',
        'title': 'Gestione delle valuta',
        'description': 'Scegli se usare anche le valute meno comuni o no',
        'options': [
            {'value': 'special_values', 'text': 'Valute speciali'},
            {'value': 'common_values', 'text': 'Valute comuni'}
        ]
    }
]


def create_setting_message(setting, character):
    key = setting['key']
    title = setting['title']
    description = setting['description']
    options = setting['options']

    # Get the current value from the character's settings
    current_value = character.settings.get(key, options[0]['value'])

    # Build the message text
    message_text = f"<b>{title}</b>\n{description}"

    # Build the keyboard
    option_buttons = []
    for option in options:
        option_text = option['text']
        if option['value'] == current_value:
            option_text = '✅ ' + option_text

        callback_data = f'setting|{key}|{option["value"]}'
        option_buttons.append([InlineKeyboardButton(option_text, callback_data=callback_data)])

    keyboard = InlineKeyboardMarkup(option_buttons)

    return message_text, keyboard


async def character_creator_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    # Send a message for each setting
    for setting in SETTINGS:
        message_text, keyboard = create_setting_message(setting, character)

        # Send the message
        await send_and_save_message(
            update,
            context,
            message_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )

    return SETTINGS_MENU_STATE


async def character_creator_settings_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    data = query.data

    # Expected format: 'setting|key|value'
    if data.startswith('setting|'):
        _, setting_key, selected_value = data.split('|')

        character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]

        # Update the character's settings
        character.settings[setting_key] = selected_value

        # Answer the query
        await query.answer()

        # Regenerate the message and keyboard for this setting
        setting = next((s for s in SETTINGS if s['key'] == setting_key), None)
        if setting:
            message_text, keyboard = create_setting_message(setting, character)

            # Edit the message
            try:
                await query.edit_message_text(
                    text=message_text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML
                )
            except BadRequest as e:
                print(f"Error editing message: {e}")
                await query.answer('Could not update settings.', show_alert=True)

            return SETTINGS_MENU_STATE
        else:
            # Handle unknown setting key
            await query.answer('Unknown setting.', show_alert=True)
            return SETTINGS_MENU_STATE

    else:
        # Handle unrecognized callback data
        await query.answer('Option not recognized.', show_alert=True)
        return SETTINGS_MENU_STATE
