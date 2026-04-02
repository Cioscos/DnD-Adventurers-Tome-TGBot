from typing import Tuple, Dict

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src.util import chunk_list
from . import *
from .models import Character, Ability
from .models.Ability import RestorationType
from .utilities import send_and_save_message, generate_abilities_list_keyboard


async def create_abilities_menu(character: Character, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message_str = f"<b>Gestione abilità</b>\nUsa /stop per terminare o un bottone del menù principale per cambiare funzione\n\n"
    if not character.abilities:
        message_str += "Non hai ancora nessuna azione 🤷‍♂️"
        keyboard = [
            [InlineKeyboardButton("Impara nuova azione", callback_data=ABILITY_LEARN_CALLBACK_DATA)]
        ]
        await send_and_save_message(update, context, message_str, reply_markup=InlineKeyboardMarkup(keyboard),
                                    parse_mode=ParseMode.HTML)

        return ABILITY_LEARN

    message_str += "Ecco la lista delle azioni"

    abilities = character.abilities
    abilities_pages = chunk_list(abilities, 10)

    context.user_data[CHARACTERS_CREATOR_KEY][INLINE_PAGES_KEY] = abilities_pages
    context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_INLINE_PAGE_INDEX_KEY] = 0
    current_page = abilities_pages[context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_INLINE_PAGE_INDEX_KEY]]

    reply_markup = generate_abilities_list_keyboard(current_page)

    await send_and_save_message(update, context, message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return ABILITIES_MENU


def create_ability_menu(ability: Ability) -> Tuple[str, InlineKeyboardMarkup]:
    message_str = (f"<b>{ability.name}</b>\n\n"
                   f"<b>Descrizione</b>\n{ability.description}\n\n"
                   f"<b>Usi</b> {ability.uses}x\n\n"
                   f"<i>Azione {'passiva' if ability.is_passive else 'attiva'}, si ricarica con un riposo "
                   f"{'breve' if ability.restoration_type == RestorationType.SHORT_REST else 'lungo'}</i>")
    message_str += '\n\nUsa /stop per terminare o un bottone del menù principale per cambiare funzione'
    keyboard = [
        [
            InlineKeyboardButton("Modifica", callback_data=ABILITY_EDIT_CALLBACK_DATA),
            InlineKeyboardButton("Dimentica", callback_data=ABILITY_DELETE_CALLBACK_DATA)
        ]
    ]

    if ability.is_passive:
        second_row = [InlineKeyboardButton(f'{'Attiva' if not ability.activated else 'Disattiva'}',
                                           callback_data=ABILITY_ACTIVE_CALLBACK_DATA)]
    else:
        second_row = [InlineKeyboardButton('Usa', callback_data=ABILITY_USE_CALLBACK_DATA)]

    keyboard.append(second_row)
    keyboard.append([InlineKeyboardButton("Indietro 🔙", callback_data=ABILITY_BACK_MENU_CALLBACK_DATA)])

    return message_str, InlineKeyboardMarkup(keyboard)


def create_ability_keyboard(features_chosen: Dict[str, str | bool]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f'Abilità passiva {'✅' if features_chosen['is_passive'] else '❌'}',
                callback_data=f'{ABILITY_IS_PASSIVE_CALLBACK_DATA}|1'),
            InlineKeyboardButton(
                f'Abilità attiva {'✅' if not features_chosen['is_passive'] else '❌'}',
                callback_data=f'{ABILITY_IS_PASSIVE_CALLBACK_DATA}|0'),
        ],
        [
            InlineKeyboardButton(
                f'Riposo breve {'✅' if features_chosen['restoration_type'] == RestorationType.SHORT_REST else '❌'}',
                callback_data=f'{ABILITY_RESTORATION_TYPE_CALLBACK_DATA}|short'
            ),
            InlineKeyboardButton(
                f'Riposo lungo {'✅' if features_chosen['restoration_type'] == RestorationType.LONG_REST else '❌'}',
                callback_data=f'{ABILITY_RESTORATION_TYPE_CALLBACK_DATA}|long'
            )
        ],
        [
            InlineKeyboardButton('Impara abilità', callback_data=ABILITY_INSERT_CALLBACK_DATA)
        ]
    ])


async def character_abilities_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]

    return await create_abilities_menu(character, update, context)


async def character_abilities_menu_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    data = query.data

    if data == "prev_page":

        if context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_INLINE_PAGE_INDEX_KEY] == 0:
            await query.answer("Sei alla prima pagina!", show_alert=True)
        else:
            context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_INLINE_PAGE_INDEX_KEY] -= 1

        return ABILITIES_MENU

    elif data == "next_page":

        context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_INLINE_PAGE_INDEX_KEY] += 1

    else:

        await query.answer()
        _, ability_name = data.split('|', maxsplit=1)
        character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
        ability: Ability = next((ability for ability in character.abilities if ability.name == ability_name), None)

        message_str, reply_markup = create_ability_menu(ability)
        await query.edit_message_text(message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

        # save the current ability in the userdata
        context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_ABILITY_KEY] = ability

        return ABILITY_VISUALIZATION

    # retrieves other abilities
    try:
        ability_page = context.user_data[CHARACTERS_CREATOR_KEY][INLINE_PAGES_KEY][
            context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_INLINE_PAGE_INDEX_KEY]
        ]
    except IndexError:
        await query.answer("Non ci sono altre pagine!", show_alert=True)
        context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_INLINE_PAGE_INDEX_KEY] -= 1
        return ABILITIES_MENU

    message_str = ("Usa /stop per terminare o un bottone del menù principale per cambiare funzione\n"
                   "Ecco la lista delle azioni")
    reply_markup = generate_abilities_list_keyboard(ability_page)
    await query.edit_message_text(message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)


async def character_ability_visualization_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    data = query.data

    if data == ABILITY_EDIT_CALLBACK_DATA:

        await query.answer()
        ability_to_edit: Ability = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_ABILITY_KEY]
        message_str = ("Usa /stop per terminare o un bottone del menù principale per cambiare funzione\n\n"
                       "Inviami l'azione inserendo il nome, descrizione e numero utilizzi separati da un #\n\n"
                       f"<b>Nome azione da modificare:</b> <code>{ability_to_edit.name}\n\n</code>"
                       f"<b>Descrizione azione:</b> <code>{ability_to_edit.description}\n\n</code>"
                       f"<b>Numero utilizzi:</b> <code>{ability_to_edit.max_uses}</code>")
        await query.edit_message_text(message_str, parse_mode=ParseMode.HTML)

    elif data == ABILITY_DELETE_CALLBACK_DATA:

        await query.answer()
        keyboard = [
            [
                InlineKeyboardButton("Si", callback_data='y'),
                InlineKeyboardButton("No", callback_data='n')
            ]
        ]
        await query.edit_message_text("Sicuro di voler cancellare l'azione?\n\n"
                                      "Usa /stop per terminare o un bottone del menù principale per cambiare funzione",
                                      reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == ABILITY_BACK_MENU_CALLBACK_DATA:

        await query.answer()
        ability_page = context.user_data[CHARACTERS_CREATOR_KEY][INLINE_PAGES_KEY][
            context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_INLINE_PAGE_INDEX_KEY]]

        message_str = ("Usa /stop per terminare o un bottone del menù principale per cambiare funzione\n\n"
                       "Ecco la lista delle azioni")
        reply_markup = generate_abilities_list_keyboard(ability_page)
        await query.edit_message_text(message_str, reply_markup=reply_markup)

        return ABILITIES_MENU

    elif data == ABILITY_USE_CALLBACK_DATA:

        character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
        ability: Ability = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_ABILITY_KEY]

        if ability.uses == 0:
            await query.answer("Non hai più utilizzi per questa azione!", show_alert=True)
            return ABILITY_VISUALIZATION

        await query.answer()
        character.use_ability(ability)

        message_str, reply_keyboard = create_ability_menu(ability)
        await query.edit_message_text(message_str, reply_markup=reply_keyboard, parse_mode=ParseMode.HTML)

        return ABILITY_VISUALIZATION

    elif data == ABILITY_ACTIVE_CALLBACK_DATA:

        character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
        ability: Ability = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_ABILITY_KEY]

        await query.answer()
        character.toggle_activate_ability(ability)

        message_str, reply_keyboard = create_ability_menu(ability)
        await query.edit_message_text(message_str, reply_markup=reply_keyboard, parse_mode=ParseMode.HTML)

        return ABILITY_VISUALIZATION

    return ABILITY_ACTIONS


async def character_ability_new_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "Inviami l'azione inserendo il nome, descrizione e numero utilizzi per tipo di riposo separati da un #\n\n"
        "<b>Esempio:</b> <code>nome#bella descrizione#2</code>\n\n"
        "Usa /stop per terminare o un bottone del menù principale per cambiare funzione",
        parse_mode=ParseMode.HTML
    )

    return ABILITY_LEARN


async def character_ability_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ability_info = update.effective_message.text
    context.user_data[CHARACTERS_CREATOR_KEY][LAST_MENU_MESSAGES].append(update.effective_message)

    try:
        ability_name, ability_desc, ability_max_uses = ability_info.split("#", 2)
    except ValueError:
        await send_and_save_message(
            update,
            context,
            "🔴 Inserisci l'azione utilizzando il formato richiesto!\n\n"
            "Invia di nuovo l'azione o usa /stop per terminare o un bottone del menù principale per cambiare funzione\n\n"
            "<b>Esempio:</b> <code>nome#bella descrizione#2</code>",
            parse_mode=ParseMode.HTML
        )
        return ABILITY_LEARN

    if (not ability_name or ability_name.isdigit()
            or not ability_desc or ability_desc.isdigit()
            or not ability_max_uses or not ability_max_uses.isdigit()):
        await send_and_save_message(
            update,
            context,
            "🔴 Inserisci l'azione utilizzando il formato richiesto!\n\n"
            "Invia di nuovo l'azione o usa /stop per terminare o un bottone del menù principale per cambiare funzione\n\n"
            "<b>Esempio:</b> <code>nome#bella descrizione#2</code>",
            parse_mode=ParseMode.HTML
        )
        return ABILITY_LEARN

    # Ask for ability features
    features_chosen = {'is_passive': True, 'restoration_type': RestorationType.SHORT_REST}
    context.user_data[CHARACTERS_CREATOR_KEY][ABILITY_FEATURES_KEY] = features_chosen
    context.user_data[CHARACTERS_CREATOR_KEY][TEMP_ABILITY_KEY] = (ability_name, ability_desc, int(ability_max_uses))
    reply_markup = create_ability_keyboard(features_chosen)

    await send_and_save_message(
        update,
        context,
        "Scegli se l'azione è passiva o se si ricarica con un riposo lungo o corto\n"
        "Usa /stop per terminare o un bottone del menù principale per cambiare funzione", reply_markup=reply_markup
    )

    return ABILITY_LEARN


async def character_ability_features_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    feature, state = data.split('|', maxsplit=1)
    features_chosen = context.user_data[CHARACTERS_CREATOR_KEY][ABILITY_FEATURES_KEY]

    if feature == ABILITY_IS_PASSIVE_CALLBACK_DATA:
        features_chosen['is_passive'] = True if state == '1' else False
    elif feature == ABILITY_RESTORATION_TYPE_CALLBACK_DATA:
        features_chosen['restoration_type'] = RestorationType(state)

    reply_markup = create_ability_keyboard(features_chosen)
    context.user_data[CHARACTERS_CREATOR_KEY][ABILITY_FEATURES_KEY] = features_chosen
    await query.edit_message_reply_markup(reply_markup)

    return ABILITY_LEARN


async def character_ability_insert_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    ability_name, ability_desc, ability_max_uses = context.user_data[CHARACTERS_CREATOR_KEY][TEMP_ABILITY_KEY]
    context.user_data[CHARACTERS_CREATOR_KEY].pop(TEMP_ABILITY_KEY, None)
    features_chosen = context.user_data[CHARACTERS_CREATOR_KEY][ABILITY_FEATURES_KEY]

    ability = Ability(
        name=ability_name,
        description=ability_desc,
        is_passive=features_chosen['is_passive'],
        restoration_type=features_chosen['restoration_type'],
        max_uses=ability_max_uses,
        uses=ability_max_uses
    )
    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]

    if any(ability_name == ability.name for ability in character.abilities):
        await send_and_save_message(
            update,
            context,
            "🔴 Hai già appreso questa azione!\n\n"
            "Invia un'altra azione o usa /stop per terminare o un bottone del menù principale per cambiare funzione"
        )
        return ABILITY_LEARN

    character.learn_ability(ability)
    await send_and_save_message(update, context, "Azione appresa con successo! ✅")

    return await create_abilities_menu(character, update, context)


async def character_ability_edit_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ability_info = update.effective_message.text
    context.user_data[CHARACTERS_CREATOR_KEY][LAST_MENU_MESSAGES].append(update.effective_message)

    try:
        ability_name, ability_desc, ability_max_uses = ability_info.split("#", 2)
    except ValueError:
        await send_and_save_message(
            update,
            context,
            "🔴 Inserisci l'azione utilizzando il formato richiesto!\n\n"
            "Invia di nuovo l'azione o usa /stop per terminare o un bottone del menù principale per cambiare funzione\n\n"
            "<b>Esempio:</b> <code>nome#bella descrizione#2</code>",
            parse_mode=ParseMode.HTML
        )
        return ABILITY_ACTIONS

    if (not ability_name or ability_name.isdigit()
            or not ability_desc or ability_desc.isdigit()
            or not ability_max_uses or not ability_max_uses.isdigit()):
        await send_and_save_message(
            update,
            context,
            "🔴 Inserisci l'azione utilizzando il formato richiesto!\n\n"
            "Invia di nuovo l'azione o usa /stop per terminare o un bottone del menù principale per cambiare funzione\n\n"
            "<b>Esempio:</b> <code>nome#bella descrizione#2</code>",
            parse_mode=ParseMode.HTML
        )
        return ABILITY_ACTIONS

    old_ability: Ability = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_ABILITY_KEY]
    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]

    for ability in character.abilities:
        if ability == old_ability:
            ability.name = ability_name
            ability.description = ability_desc
            ability.max_uses = int(ability_max_uses)
            break

    await send_and_save_message(update, context, "Azione modificata con successo!")

    return await create_abilities_menu(character, update, context)


async def character_ability_delete_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    ability_to_forget: Ability = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_ABILITY_KEY]

    if data == 'y':
        character.forget_ability(ability_to_forget.name)
    elif data == 'n':
        await send_and_save_message(
            update,
            context,
            f"Hai una buona memoria, ti ricordi ancora l'azione {ability_to_forget.name}"
        )

    return await create_abilities_menu(character, update, context)
