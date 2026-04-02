import logging
import re
from typing import List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode, ChatType
from telegram.error import TelegramError
from telegram.ext import ContextTypes, ConversationHandler

from . import *
from .abilities import character_abilities_query_handler
from .armor_class import armor_class_main_menu_callback
from .bag import character_bag_query_handler
from .damage_healing import character_damage_query_handler, character_healing_query_handler
from .dice import dice_handler
from .feature_points import character_feature_point_query_handler
from .hit_points import character_hit_points_query_handler
from .level import character_change_level_query_handler, character_level_change_class_choice_handler
from .maps import character_creation_maps_query_handler
from .models import Character
from .multiclassing import character_multiclassing_query_handler
from .notes import character_creator_notes_query_handler
from .rest import character_long_rest_warning_query_handler, character_short_rest_warning_query_handler
from .settings import character_creator_settings
from .spell_slots import character_spells_slots_query_handler
from .spells import character_spells_query_handler
from .utilities import send_and_save_message, create_main_menu_message

logger = logging.getLogger(__name__)


async def character_creator_stop_submenu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Rollback for multiclass management
    if PENDING_REASSIGNMENT in context.user_data[CHARACTERS_CREATOR_KEY]:
        # Get the pending reassignment information
        pending_reassignment = context.user_data[CHARACTERS_CREATOR_KEY][PENDING_REASSIGNMENT]
        removed_class_level = pending_reassignment[REMOVED_CLASS_LEVEL]
        remaining_classes = pending_reassignment[REMAINING_CLASSES]

        if len(remaining_classes) == 1:
            # Automatically reassign levels if only one class is left
            remaining_class_name = remaining_classes[0]
            character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
            multi_class = character.multi_class

            multi_class.add_class(remaining_class_name, removed_class_level)

            message_str = f"Il comando /stop è stato ricevuto.\n" \
                          f"I {removed_class_level} livelli rimossi sono stati aggiunti automaticamente alla classe {remaining_class_name}."
            await send_and_save_message(update, context, message_str, parse_mode=ParseMode.HTML)
        else:
            # Ask the user to finish reassigning the levels before stopping
            await send_and_save_message(update, context,
                                        "Devi assegnare i livelli rimanenti prima di poter usare il comando /stop.",
                                        parse_mode=ParseMode.HTML)
            return MULTICLASSING_ACTIONS

    else:

        if CURRENT_CHARACTER_KEY in context.user_data[CHARACTERS_CREATOR_KEY]:
            character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]

            # Delete messages sent by bot and user
            messages = context.user_data[CHARACTERS_CREATOR_KEY].get(LAST_MENU_MESSAGES, [])
            for message in messages:
                try:
                    await context.bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)
                except TelegramError as e:
                    logger.warning(f"Errore durante la cancellazione del messaggio: {e}")
            context.user_data[CHARACTERS_CREATOR_KEY][LAST_MENU_MESSAGES].clear()

            msg, reply_markup = create_main_menu_message(character)
            await update.effective_message.reply_text(msg, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

        else:

            await send_and_save_message(update, context,
                                        'Ok! Usa il comando /start per avviare una nuova conversazione!\n'
                                        'Oppure invia direttamente i comandi /wiki o /character',
                                        parse_mode=ParseMode.HTML)
            return ConversationHandler.END

        context.user_data[CHARACTERS_CREATOR_KEY].pop(TEMP_CHARACTER_KEY, None)
        context.user_data[CHARACTERS_CREATOR_KEY].pop(CURRENT_ITEM_KEY, None)
        context.user_data[CHARACTERS_CREATOR_KEY].pop(PENDING_REASSIGNMENT, None)
        context.user_data[CHARACTERS_CREATOR_KEY].pop(ABILITY_FEATURES_KEY, None)
        context.user_data[CHARACTERS_CREATOR_KEY].pop(TEMP_ABILITY_KEY, None)
        context.user_data[CHARACTERS_CREATOR_KEY].pop(CURRENT_ABILITY_KEY, None)
        context.user_data[CHARACTERS_CREATOR_KEY].pop(TEMP_ZONE_NAME, None)
        context.user_data[CHARACTERS_CREATOR_KEY].pop(TEMP_MAPS_PATHS, None)
        context.user_data[CHARACTERS_CREATOR_KEY].pop(ADD_OR_INSERT_MAPS, None)
        context.user_data[CHARACTERS_CREATOR_KEY].pop(TEMP_CURRENCY_KEY, None)
        context.user_data[CHARACTERS_CREATOR_KEY].pop(CURRENCY_CONVERTER, None)
        context.user_data[CHARACTERS_CREATOR_KEY].pop(TEMP_VOICE_MESSAGE_PATH, None)

        return FUNCTION_SELECTION


async def character_creation_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await send_and_save_message(update, context, 'Ok! Usa il comando /start per avviare una nuova conversazione!\n'
                                                 'Oppure invia direttamente i comandi /wiki o /character',
                                parse_mode=ParseMode.HTML)

    context.user_data[CHARACTERS_CREATOR_KEY].pop(TEMP_CHARACTER_KEY, None)
    context.user_data[CHARACTERS_CREATOR_KEY].pop(CURRENT_ITEM_KEY, None)
    context.user_data[CHARACTERS_CREATOR_KEY].pop(PENDING_REASSIGNMENT, None)
    context.user_data[CHARACTERS_CREATOR_KEY].pop(ABILITY_FEATURES_KEY, None)
    context.user_data[CHARACTERS_CREATOR_KEY].pop(TEMP_ABILITY_KEY, None)
    context.user_data[CHARACTERS_CREATOR_KEY].pop(CURRENT_ABILITY_KEY, None)
    context.user_data[CHARACTERS_CREATOR_KEY].pop(TEMP_ZONE_NAME, None)
    context.user_data[CHARACTERS_CREATOR_KEY].pop(TEMP_MAPS_PATHS, None)
    context.user_data[CHARACTERS_CREATOR_KEY].pop(ADD_OR_INSERT_MAPS, None)
    context.user_data[CHARACTERS_CREATOR_KEY].pop(TEMP_CURRENCY_KEY, None)
    context.user_data[CHARACTERS_CREATOR_KEY].pop(CURRENCY_CONVERTER, None)
    context.user_data[CHARACTERS_CREATOR_KEY].pop(TEMP_VOICE_MESSAGE_PATH, None)

    context.user_data[ACTIVE_CONV] = None

    return ConversationHandler.END


async def character_creator_start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        query = update.callback_query
        await query.answer()

    beta_message = (f"\n\n<b>The bot is in beta version and currently supports only italian language.\n"
                    f"Stay tuned for new updates!</b>")

    # Check if the user is already in another conversation
    if context.user_data.get(ACTIVE_CONV) == 'wiki':
        await update.effective_message.reply_text(
            "Usare /stop per uscire dalla wiki prima di usare la gestione dei personaggi.",
            parse_mode=ParseMode.HTML)
        return ConversationHandler.END

    context.user_data[ACTIVE_CONV] = 'character'

    # Check for BOT_DATA_CHAT_IDS initialization
    if BOT_DATA_CHAT_IDS not in context.bot_data or update.effective_chat.id not in context.bot_data.get(
            BOT_DATA_CHAT_IDS, []):
        await update.effective_message.reply_text("La prima volta devi interagire con il bot usando il comando /start",
                                                  parse_mode=ParseMode.HTML)
        return ConversationHandler.END

    # check if the function is called in a group or not
    if update.effective_chat.type != ChatType.PRIVATE:
        await update.effective_message.reply_text(
            "La funzione di gestione del personaggio può essere usata solo in privato!\n"
            "Ritorno al menù principale...",
            parse_mode=ParseMode.HTML)
        return ConversationHandler.END

    message_str = f"Benvenuto nella gestione del personaggio!\n"

    # check if the user has the character creator DB
    if CHARACTERS_CREATOR_KEY not in context.user_data:
        context.user_data[CHARACTERS_CREATOR_KEY] = {}

    # check if the user has already some characters created
    if CHARACTERS_KEY not in context.user_data[CHARACTERS_CREATOR_KEY] or not context.user_data[CHARACTERS_CREATOR_KEY][
        CHARACTERS_KEY]:
        message_str += (f"{update.effective_user.name} sembra che non hai inserito ancora nessun personaggio!\n\n"
                        f"Usa il comando /newCharacter per crearne uno nuovo o /stop per terminare la conversazione.{beta_message}")

        await update.effective_message.reply_text(message_str, parse_mode=ParseMode.HTML)
        return CHARACTER_CREATION

    else:
        characters: List[Character] = context.user_data[CHARACTERS_CREATOR_KEY][CHARACTERS_KEY]
        message_str += f"Seleziona uno dei personaggi da gestire o creane uno nuovo con /newCharacter{beta_message}"
        keyboard = []

        for character in characters:
            keyboard.append([InlineKeyboardButton(character.name, callback_data=character.name)])

        await update.effective_message.reply_text(message_str, reply_markup=InlineKeyboardMarkup(keyboard),
                                                  parse_mode=ParseMode.HTML)

        return CHARACTER_SELECTION


async def character_selection_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    character_name = query.data

    characters: List[Character] = context.user_data[CHARACTERS_CREATOR_KEY][CHARACTERS_KEY]
    character = next((character for character in characters if character.name == character_name), None)
    context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY] = character

    msg, reply_markup = create_main_menu_message(character)

    await update.effective_message.reply_text(msg, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return FUNCTION_SELECTION


async def character_creation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    character = Character()
    context.user_data[CHARACTERS_CREATOR_KEY][TEMP_CHARACTER_KEY] = character

    await update.effective_message.reply_text(
        "Qual'è il nome del personaggio?\nRispondi a questo messaggio o premi /stop per terminare"
    )

    return NAME_SELECTION


async def character_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.effective_message.text

    # check if the character already exists
    if any(character.name == name for character in context.user_data[CHARACTERS_CREATOR_KEY].get(CHARACTERS_KEY, [])):
        await update.effective_message.reply_text("🔴 Esiste già un personaggio con lo stesso nome! 🔴\n"
                                                  "Inserisci un altro nome o premi /stop per terminare"
                                                  )
        return NAME_SELECTION

    character = context.user_data[CHARACTERS_CREATOR_KEY][TEMP_CHARACTER_KEY]
    character.name = name

    await update.effective_message.reply_text(
        "Qual'è la razza del personaggio?\nRispondi a questo messaggio o premi /stop per terminare"
    )

    return RACE_SELECTION


async def character_race_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    race = update.effective_message.text

    character = context.user_data[CHARACTERS_CREATOR_KEY][TEMP_CHARACTER_KEY]
    character.race = race

    await update.effective_message.reply_text(
        "Qual'è il genere del personaggio?\nRispondi a questo messaggio o premi /stop per terminare\n\n"
        "Esempio: Maschio"
    )

    return GENDER_SELECTION


async def character_gender_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    gender = update.effective_message.text

    character = context.user_data[CHARACTERS_CREATOR_KEY][TEMP_CHARACTER_KEY]
    character.gender = gender

    await update.effective_message.reply_text(
        "Qual'è la classe del personaggio?\nRispondi a questo messaggio o premi /stop per terminare"
    )

    return CLASS_SELECTION


async def character_class_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    class_ = update.effective_message.text

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][TEMP_CHARACTER_KEY]
    character.multi_class.add_class(class_)

    await update.effective_message.reply_text(
        "Quanti punti vita ha il tuo personaggio?\nRispondi a questo messaggio o premi /stop per terminare"
    )

    return HIT_POINTS_SELECTION


async def character_hit_points_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    hit_points = update.effective_message.text

    character = context.user_data[CHARACTERS_CREATOR_KEY][TEMP_CHARACTER_KEY]
    character.hit_points = character.current_hit_points = int(hit_points)

    context.user_data[CHARACTERS_CREATOR_KEY][CHARACTERS_KEY] = []
    context.user_data[CHARACTERS_CREATOR_KEY][CHARACTERS_KEY].append(character)
    del context.user_data[CHARACTERS_CREATOR_KEY][TEMP_CHARACTER_KEY]
    context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY] = character

    msg, reply_markup = create_main_menu_message(character)
    await update.effective_message.reply_text(msg, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return FUNCTION_SELECTION


async def character_deleting_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]

    keyboard = [
        [
            InlineKeyboardButton('Si', callback_data=AFFERMATIVE_CHARACTER_DELETION_CALLBACK_DATA),
            InlineKeyboardButton('No', callback_data=NEGATIVE_CHARACTER_DELETION_CALLBACK_DATA)
        ]
    ]

    message_str = (
        "Sei sicuro di voler cancellare il personaggio?\n\n"
        f"{character.name} - classe {', '.join(f'{class_name} (Livello {level})' for class_name, level in character.multi_class.classes.items())} "
        f"di L. {character.total_levels()}"
    )

    await send_and_save_message(update, context, message_str, reply_markup=InlineKeyboardMarkup(keyboard))

    return CHARACTER_DELETION


async def character_deleting_answer_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    data = query.data
    current_character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]

    if data == AFFERMATIVE_CHARACTER_DELETION_CALLBACK_DATA:
        await query.answer()
        characters: List[Character] = context.user_data[CHARACTERS_CREATOR_KEY][CHARACTERS_KEY]

        # Remove the character from the list
        characters = [character for character in characters if character.name != current_character.name]
        context.user_data[CHARACTERS_CREATOR_KEY][CHARACTERS_KEY] = characters

        context.user_data[CHARACTERS_CREATOR_KEY].pop(CURRENT_CHARACTER_KEY, None)

        await update.effective_message.reply_text("Personaggio eliminato con successo ✅\n\n"
                                                  "Usa il comando /start per avviare una nuova conversazione!\n"
                                                  "Oppure invia direttamente i comandi /wiki o /character"
                                                  )

        return ConversationHandler.END

    elif data == NEGATIVE_CHARACTER_DELETION_CALLBACK_DATA:
        await query.answer("Eliminazione personaggio annullata", show_alert=True)
        msg, reply_markup = create_main_menu_message(current_character)
        await query.edit_message_text(msg, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

        return FUNCTION_SELECTION


async def character_generic_main_menu_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    await check_pending_reassignment_for_multiclassing_and_wipe_user_data(update, context)

    MAINMENU_CALLBACKDATA_TO_CALLBACK = {
        r"^level_(up|down)$": character_change_level_query_handler,
        fr"^{LEVEL_UP_CALLBACK_DATA}\|.*$|^{LEVEL_DOWN_CALLBACK_DATA}\|.*$": character_level_change_class_choice_handler,
        fr"^{BAG_CALLBACK_DATA}$": character_bag_query_handler,
        fr"^{SPELLS_CALLBACK_DATA}$": character_spells_query_handler,
        fr"^{ABILITIES_CALLBACK_DATA}$": character_abilities_query_handler,
        fr"^{SPELLS_SLOT_CALLBACK_DATA}$": character_spells_slots_query_handler,
        fr"^{FEATURE_POINTS_CALLBACK_DATA}$": character_feature_point_query_handler,
        fr"^{MULTICLASSING_CALLBACK_DATA}$": character_multiclassing_query_handler,
        fr"^{DELETE_CHARACTER_CALLBACK_DATA}$": character_deleting_query_handler,
        fr"^{DAMAGE_CALLBACK_DATA}$": character_damage_query_handler,
        fr"^{HEALING_CALLBACK_DATA}$": character_healing_query_handler,
        fr"^{HIT_POINTS_CALLBACK_DATA}$": character_hit_points_query_handler,
        fr"^{LONG_REST_WARNING_CALLBACK_DATA}$": character_long_rest_warning_query_handler,
        fr"^{SHORT_REST_WARNING_CALLBACK_DATA}$": character_short_rest_warning_query_handler,
        fr"^{ROLL_DICE_MENU_CALLBACK_DATA}$": dice_handler,
        fr"^{SETTINGS_CALLBACK_DATA}$": character_creator_settings,
        fr"^{MAPS_CALLBACK_DATA}$": character_creation_maps_query_handler,
        fr"^{NOTES_CALLBACK_DATA}$": character_creator_notes_query_handler,
        fr"^{ARMOR_CLASS_CALLBACK_DATA}$": armor_class_main_menu_callback
    }

    for regex, func in MAINMENU_CALLBACKDATA_TO_CALLBACK.items():
        if re.match(regex, query.data):
            messages = context.user_data[CHARACTERS_CREATOR_KEY].get(LAST_MENU_MESSAGES, [])
            for message in messages:
                try:
                    await context.bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)
                except TelegramError as e:
                    logger.warning(f"Errore durante la cancellazione del messaggio: {e}")
            context.user_data[CHARACTERS_CREATOR_KEY][LAST_MENU_MESSAGES].clear()
            return await func(update, context)


async def check_pending_reassignment_for_multiclassing_and_wipe_user_data(update, context):
    # Rollback for multiclass management
    if PENDING_REASSIGNMENT in context.user_data[CHARACTERS_CREATOR_KEY]:
        # Get the pending reassignment information
        pending_reassignment = context.user_data[CHARACTERS_CREATOR_KEY][PENDING_REASSIGNMENT]
        removed_class_level = pending_reassignment[REMOVED_CLASS_LEVEL]
        remaining_classes = pending_reassignment[REMAINING_CLASSES]

        if len(remaining_classes) == 1:
            # Automatically reassign levels if only one class is left
            remaining_class_name = remaining_classes[0]
            character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
            multi_class = character.multi_class

            multi_class.add_class(remaining_class_name, removed_class_level)

            await update.message.reply_text(f"Il comando /stop è stato ricevuto.\n"
                                            f"I {removed_class_level} livelli rimossi sono stati aggiunti automaticamente alla classe {remaining_class_name}.")
        else:
            # Ask the user to finish reassigning the levels before stopping
            await update.message.reply_text("Devi assegnare i livelli rimanenti prima di poter usare il comando /stop.")
            return MULTICLASSING_ACTIONS

    else:

        context.user_data[CHARACTERS_CREATOR_KEY].pop(TEMP_CHARACTER_KEY, None)
        context.user_data[CHARACTERS_CREATOR_KEY].pop(CURRENT_ITEM_KEY, None)
        context.user_data[CHARACTERS_CREATOR_KEY].pop(PENDING_REASSIGNMENT, None)
        context.user_data[CHARACTERS_CREATOR_KEY].pop(ABILITY_FEATURES_KEY, None)
        context.user_data[CHARACTERS_CREATOR_KEY].pop(TEMP_ABILITY_KEY, None)
        context.user_data[CHARACTERS_CREATOR_KEY].pop(CURRENT_ABILITY_KEY, None)
        context.user_data[CHARACTERS_CREATOR_KEY].pop(TEMP_ZONE_NAME, None)
        context.user_data[CHARACTERS_CREATOR_KEY].pop(TEMP_MAPS_PATHS, None)
        context.user_data[CHARACTERS_CREATOR_KEY].pop(ADD_OR_INSERT_MAPS, None)
        context.user_data[CHARACTERS_CREATOR_KEY].pop(TEMP_CURRENCY_KEY, None)
        context.user_data[CHARACTERS_CREATOR_KEY].pop(CURRENCY_CONVERTER, None)
        context.user_data[CHARACTERS_CREATOR_KEY].pop(TEMP_VOICE_MESSAGE_PATH, None)
