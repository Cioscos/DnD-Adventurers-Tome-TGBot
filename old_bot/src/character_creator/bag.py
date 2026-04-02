from typing import Tuple, Dict

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from . import *
from .models import Character, Item, Currency
from .utilities import send_and_save_message


def create_bag_menu(character: Character, context: ContextTypes.DEFAULT_TYPE) -> Tuple[str, InlineKeyboardMarkup]:
    # Determine the max length of the quantity string for alignment
    max_quantity_length = max((len(str(item.quantity)) for item in character.bag), default=0)
    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    currency_mangement = character.settings.get('special_currency_management', 'common_values')

    # Create the message string with aligned quantities
    message_str = (
        f"Usa /stop per terminare o un bottone del menù principale per cambiare funzione\n\n"
        f"<b>Oggetti nella borsa</b>\n"
        f"<b>Peso:</b> {character.encumbrance}/{character.carry_capacity}Lb\n"
        f"🟡 {character.currency.gold} ⚪ {character.currency.silver} ️🟤 {character.currency.bronze}\n"
        f"{f'⚡️ {character.currency.electrum} 💠 {character.currency.platinum}\n\n' if currency_mangement == 'special_values' else '\n\n'}"
        f"{''.join(f'<code>• Pz {str(item.quantity).ljust(max_quantity_length)}</code>   <code>{item.name}</code>\n' for item in character.bag) if character.bag else 'Lo zaino è ancora vuoto'}"
    )

    # Create the keyboard with action buttons
    keyboard = [[InlineKeyboardButton('Inserisci nuovo oggetto', callback_data=BAG_ITEM_INSERTION_CALLBACK_DATA)]]

    second_row = []
    if character.bag:
        second_row.append(
            InlineKeyboardButton('Modifica oggetti', callback_data=BAG_ITEM_EDIT_CALLBACK_DATA)
        )

    second_row.append(
        InlineKeyboardButton('Gestisci valuta', callback_data=BAG_MANAGE_CURRENCY_CALLBACK_DATA)
    )

    keyboard.extend([second_row])

    return message_str, InlineKeyboardMarkup(keyboard)


def create_item_menu(item: Item) -> Tuple[str, InlineKeyboardMarkup]:
    message_str = (f"<b>{item.name:<{50}}</b>{item.quantity}Pz\n\n"
                   f"<b>Descrizione</b>\n{item.description}\n\n"
                   f"Usa /stop per terminare o un bottone del menù principale per cambiare funzione\n\n")

    keyboard = [
        [
            InlineKeyboardButton("-", callback_data=f"{BAG_ITEM_EDIT_CALLBACK_DATA}|-"),
            InlineKeyboardButton("+", callback_data=f"{BAG_ITEM_EDIT_CALLBACK_DATA}|+")
        ],
        [InlineKeyboardButton('Sovrascrivi quantità', callback_data=f"{BAG_ITEM_EDIT_CALLBACK_DATA}|overwrite")],
        [InlineKeyboardButton("Rimuovi tutti", callback_data=f"{BAG_ITEM_EDIT_CALLBACK_DATA}|all")]
    ]

    return message_str, InlineKeyboardMarkup(keyboard)


def create_currency_menu(currencies: Dict[str, Tuple[str, int]]) -> Dict[str, Tuple[str, InlineKeyboardMarkup]]:
    max_length = max(len(currency_name) for currency_name, _ in currencies.values())

    menu = {}
    for currency_id, (currency_name, currency_value) in currencies.items():
        formatted_currency = f"<code>{currency_name:<{max_length}} {currency_value}</code>"
        menu[currency_id] = (
            formatted_currency,
            InlineKeyboardMarkup([
                [InlineKeyboardButton('Modifica',
                                      callback_data=f"{BAG_MANAGE_SINGLE_CURRENCY_CALLBACK_DATA}|{currency_id}")]
            ])
        )

    return menu


def create_currency_converter_main_menu(context: ContextTypes.DEFAULT_TYPE) -> Tuple[str, InlineKeyboardMarkup]:
    character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    # retrieve currency and quantity
    currencies = character.currency.currencies
    keyboard = []
    message_str = (f"Usa /stop per terminare o un bottone del menù principale per cambiare funzione\n\n"
                   f"1) Seleziona nella colonna di <b>sinistra</b> la valuta da convertire\n"
                   f"2) Seleziona nella colonna di <b>destra</b> la valuta a cui convertire quella selezionata a sinistra\n"
                   f"3) Premi il pulsante <b>converti</b> per effettuare la conversione")

    # Initialise selections if they do not exist
    if CURRENCY_CONVERTER not in context.user_data[CHARACTERS_CREATOR_KEY]:
        context.user_data[CHARACTERS_CREATOR_KEY][CURRENCY_CONVERTER] = {
            SELECTED_SOURCE_CURRENCY: None,
            SELECTED_TARGET_CURRENCY: None
        }

    selected_source_currency = context.user_data[CHARACTERS_CREATOR_KEY][CURRENCY_CONVERTER][SELECTED_SOURCE_CURRENCY]
    selected_target_currency = context.user_data[CHARACTERS_CREATOR_KEY][CURRENCY_CONVERTER][SELECTED_TARGET_CURRENCY]

    for currency_id, (currency_name, amount) in currencies.items():
        # Start currency button
        source_selected = currency_id == selected_source_currency
        source_text = ('✅ ' if source_selected else '') + f"{currency_name.title()} ({amount})"
        source_callback_data = (SELECT_SOURCE_CALLBACK_DATA, currency_id)
        source_button = InlineKeyboardButton(source_text, callback_data=source_callback_data)

        # Destination currency button
        target_selected = currency_id == selected_target_currency
        target_text = ('✅ ' if target_selected else '') + f"{currency_name.title()} ({amount})"
        target_callback_data = (SELECT_TARGET_CALLBACK_DATA, currency_id)
        target_button = InlineKeyboardButton(target_text, callback_data=target_callback_data)

        keyboard.append([source_button, target_button])

    # Bottone per eseguire la conversione
    if selected_source_currency and selected_target_currency:
        source_currency_name = currencies[selected_source_currency][0]
        target_currency_name = currencies[selected_target_currency][0]
        convert_text = f"Converti {source_currency_name} in {target_currency_name}"
        convert_callback_data = (CONVERT_CURRENCY_CALLBACK_DATA, selected_source_currency, selected_target_currency)
        convert_button = InlineKeyboardButton(convert_text, callback_data=convert_callback_data)
    else:
        convert_text = "Seleziona le valute da convertire"
        convert_callback_data = ('noop',)  # Azione no-op se le valute non sono selezionate
        convert_button = InlineKeyboardButton(convert_text, callback_data=convert_callback_data)

    keyboard.append([convert_button])

    return message_str, InlineKeyboardMarkup(keyboard)


async def character_bag_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    message_str, reply_markup = create_bag_menu(character, context)

    await send_and_save_message(
        update,
        context,
        message_str,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

    return BAG_MANAGEMENT


async def character_bag_new_object_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    message_str = (
        f"Rispondi con il nome dell'oggetto, quantità, descrizione e peso!\n\n"
        f"<b>Esempio:</b> <code>Pozione di guarigione superiore#2#Mi cura 8d4 + 8 di vita#1</code>\n"
        f"Il peso è opzionale!\n\n"
        f"Usa /stop per terminare o un bottone del menù principale per cambiare funzione"
    )

    await query.edit_message_text(message_str, parse_mode=ParseMode.HTML)

    return BAG_ITEM_INSERTION


async def character_bag_item_insert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data[CHARACTERS_CREATOR_KEY][LAST_MENU_MESSAGES].append(update.effective_message)
    item_info = update.effective_message.text
    context.user_data[CHARACTERS_CREATOR_KEY][LAST_MENU_MESSAGES].append(update.effective_message)

    # Split the input, allowing up to 3 splits
    components = item_info.split('#', maxsplit=3)

    # Ensure there are either 3 or 4 components
    if len(components) < 3 or len(components) > 4:
        await send_and_save_message(
            update,
            context,
            "🔴 Formato errato! Assicurati di usare:\n"
            "nome#quantità#descrizione#(peso) 🔴"
        )
        return BAG_ITEM_INSERTION

    item_name, item_quantity, item_description = components[:3]
    item_weight = components[3] if len(components) == 4 else None

    # Validate item_quantity
    if not item_quantity.isdigit():
        await send_and_save_message(
            update,
            context,
            "🔴 La quantità deve essere un numero! 🔴"
        )
        return BAG_ITEM_INSERTION

    # Validate item_weight if provided
    if item_weight and not item_weight.isdigit():
        await send_and_save_message(
            update,
            context,
            "🔴 Il peso deve essere un numero se fornito! 🔴"
        )
        return BAG_ITEM_INSERTION

    # Convert quantity and weight to integers
    item_quantity = int(item_quantity)
    item_weight = int(item_weight) if item_weight else 0

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]

    # Check if there is enough space, considering item weight
    if item_weight > character.available_space():
        await send_and_save_message(
            update,
            context,
            "🔴 Ehy! Hai la borsa piena... eh vendi qualcosa! 🔴"
        )
    else:
        # Create the item and add it to the character's bag
        item = Item(item_name, item_description, item_quantity, item_weight)
        character.add_item(item)

        # Notify the user of success and available space
        available_space = character.available_space()
        success_message = (
            "Oggetto inserito con successo! ✅\n\n"
            f"{f'Puoi ancora trasportare {available_space} lb' if available_space > 0 else 'Psss... ora hai lo zaino pieno!'}"
        )
        await update.effective_message.reply_text(success_message)

    # Send the bag main menu
    message_str, reply_markup = create_bag_menu(character)
    await send_and_save_message(update, context, message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return BAG_MANAGEMENT


async def character_bag_edit_object_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    message_str = (
        f"Rispondi con il nome dell'oggetto!\n"
        f"Usa /stop per terminare o un bottone del menù principale per cambiare funzione\n\n"
        f"<b>Esempio:</b> <code>Pozione di guarigione superiore</code>\n"
    )

    await send_and_save_message(update, context, message_str, parse_mode=ParseMode.HTML)

    return BAG_ITEM_EDIT


async def character_bag_item_edit_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    item_name = update.effective_message.text
    context.user_data[CHARACTERS_CREATOR_KEY][LAST_MENU_MESSAGES].append(update.effective_message)

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    item: Item = next((item for item in character.bag if item_name == item.name), None)

    if not item:
        await send_and_save_message(
            update,
            context,
            "🔴 Oggetto non trovato! Prova di nuovo o usa /stop per terminare o un bottone del menù principale per cambiare funzione 🔴"
        )
        return BAG_ITEM_EDIT

    message_str, reply_markup = create_item_menu(item)

    # save the current item name
    context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_ITEM_KEY] = item.name

    await send_and_save_message(update, context, message_str, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    return BAG_ITEM_EDIT


async def character_bag_item_delete_one_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query

    item_name = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_ITEM_KEY]
    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    character.decrement_item_quantity(item_name)
    item: Item = next((item for item in character.bag if item_name == item.name), None)

    if item:
        await query.answer()
        message_str, reply_markup = create_item_menu(item)
        await query.edit_message_text(message_str, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        return BAG_ITEM_EDIT
    else:
        await query.answer(f'{item_name} rimosso dalla borsa!', show_alert=True)
        context.user_data[CHARACTERS_CREATOR_KEY].pop(CURRENT_ITEM_KEY, None)
        message_str, reply_markup = create_bag_menu(character)
        await query.edit_message_text(message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

        return BAG_MANAGEMENT


async def character_bag_item_add_one_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    item_name = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_ITEM_KEY]
    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    character.increment_item_quantity(item_name)
    item: Item = next((item for item in character.bag if item_name == item.name), None)

    message_str, reply_markup = create_item_menu(item)
    await query.edit_message_text(message_str, parse_mode=ParseMode.HTML, reply_markup=reply_markup)

    return BAG_ITEM_EDIT


async def character_bag_item_delete_all_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    item_name = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_ITEM_KEY]
    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    item: Item = next((item for item in character.bag if item_name == item.name), None)
    character.remove_item(item)
    context.user_data[CHARACTERS_CREATOR_KEY].pop(CURRENT_ITEM_KEY, None)

    message_str = "Oggetto rimosso con successo! ✅"
    await update.effective_message.reply_text(message_str)

    message_str, reply_markup = create_bag_menu(character)
    await update.effective_message.reply_text(message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return BAG_MANAGEMENT


async def character_bag_ask_item_overwrite_quantity_query_handler(update: Update,
                                                                  context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "Inviami la quntità da sovrascrivere\n\nUsa /stop per terminare o un bottone del menù principale per cambiare funzione")

    return BAG_ITEM_OVERWRITE


async def character_bag_currencies_menu_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    messages = create_currency_menu(character.currency.currencies)
    message_str = (f"Usa /stop per terminare o un bottone del menù principale per cambiare funzione\n\n"
                   f"Seleziona una delle seguenti valute da modificare oppure usa i tasti funzione\n"
                   f"per accedere alle funzioni speciali per la valuta")
    await query.edit_message_text(message_str, parse_mode=ParseMode.HTML)

    # send currency messages
    for message_data in messages.values():
        await send_and_save_message(
            update, context, message_data[0], reply_markup=message_data[1], parse_mode=ParseMode.HTML
        )

    # send special functions message
    message_str = f"Scegli una delle seguenti funzioni speciali per la valuta"
    keyboard = [
        [
            InlineKeyboardButton('Converti valute', callback_data=BAG_MANAGE_CURRENCY_CONVERT_FUNCTION_CALLBACK_DATA)
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await send_and_save_message(update, context, message_str, reply_markup=reply_markup)

    return BAG_MANAGEMENT


async def character_bag_currency_select_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data

    _, currency_type = data.split('|', maxsplit=1)

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    currency = character.currency
    currency_value = currency.get_currency_value(currency_type)

    # Costruzione del messaggio formattato
    message_str = (
        f"Usa /stop per terminare o un bottone del menù principale per cambiare funzione\n\n"
        f"<b>💰 Quantità di {currency.get_currency_human_name(currency_type)}</b> {currency.get_currency_emoji(currency_type)}\n\n"
        f"<code>{currency_value}</code> {currency.get_currency_emoji(currency_type)}\n"
        "————————————\n"
        "🔧 <i>Modifica il valore usando i pulsanti qui sotto</i>"
    )
    keyboard = [
        [
            InlineKeyboardButton('Modifica quantità', callback_data=(currency_type, currency))
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await send_and_save_message(update, context, message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    return BAG_MANAGEMENT


async def character_bag_currency_edit_quantity_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    currency_type: str
    currency: Currency
    currency_type, currency = query.data
    human_currency_name = currency.get_currency_human_name(currency_type)
    context.user_data[CHARACTERS_CREATOR_KEY][TEMP_CURRENCY_KEY] = query.data

    message_str = (f"Usa /stop per terminare o un bottone del menù principale per cambiare funzione\n\n"
                   f"Inserisci la quantità di monete di {human_currency_name} da modificare.\n\n"
                   f"<b>Esempio:</b>\n"
                   f"-40 (Rimuove 40 monete di {human_currency_name} dal borsello\n"
                   f"+50 (Aggiunge 50 monete di {human_currency_name} dal borsello)")

    await query.edit_message_text(message_str, parse_mode=ParseMode.HTML)
    return BAG_CURRENCY_INSERT


async def character_bag_currency_edit_quantity_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    quantity = update.effective_message.text
    context.user_data[CHARACTERS_CREATOR_KEY][LAST_MENU_MESSAGES].append(update.effective_message)

    try:
        quantity = int(quantity)
    except ValueError:
        await send_and_save_message(update, context, "🔴 La quantità di monete inserita non è un numero!\n\n"
                                                     "Inserisci una quantità corretta o usa /stop per terminare "
                                                     "o un bottone del menù principale per cambiare funzione")

    currency_type: str
    currency: Currency
    currency_type, currency = context.user_data[CHARACTERS_CREATOR_KEY][TEMP_CURRENCY_KEY]

    current_currency_value = currency.get_currency_value(currency_type)
    currency.set_currency_value(currency_type, current_currency_value + quantity)

    message_str = f"✅ {quantity} monete di {currency.get_currency_human_name(currency_type)} aggiunte"
    await send_and_save_message(update, context, message_str, parse_mode=ParseMode.HTML)

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    message_str, reply_markup = create_bag_menu(character, context)
    await send_and_save_message(update, context, message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return BAG_MANAGEMENT


async def character_bag_currency_convert_function_query_handler(update: Update,
                                                                context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    message_str, reply_markup = create_currency_converter_main_menu(context)
    await query.edit_message_text(message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return BAG_CURRENCY_FUNCTIONS


async def character_currency_convert_menu_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    action, *data = query.data

    # Ensure that 'currency_converter' exists in user_data
    if CURRENCY_CONVERTER not in context.user_data[CHARACTERS_CREATOR_KEY]:
        context.user_data[CHARACTERS_CREATOR_KEY][CURRENCY_CONVERTER] = {
            SELECTED_SOURCE_CURRENCY: None,
            SELECTED_TARGET_CURRENCY: None
        }

    currency_data = context.user_data[CHARACTERS_CREATOR_KEY][CURRENCY_CONVERTER]
    currency: Currency = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY].currency

    if action == 'select_source':
        currency_data[SELECTED_SOURCE_CURRENCY] = data[0]
        await query.answer()
    elif action == 'select_target':
        currency_data[SELECTED_TARGET_CURRENCY] = data[0]
        await query.answer()
    elif action == 'convert':
        await query.answer()
        message_str = (
            f"Inviami quante monete di {currency.get_currency_human_name(currency_data[SELECTED_SOURCE_CURRENCY])} vuoi convertire in "
            f"{currency.get_currency_human_name(currency_data[SELECTED_TARGET_CURRENCY])}")
        await send_and_save_message(update, context, message_str)
        return BAG_CURRENCY_CONVERT
    elif action == 'noop':
        await query.answer("Per favore, seleziona sia la valuta di partenza che quella di destinazione.",
                           show_alert=True)

    # Aggiorna il messaggio con la nuova tastiera
    _, reply_markup = create_currency_converter_main_menu(context)
    await query.edit_message_reply_markup(reply_markup=reply_markup)

    return BAG_CURRENCY_FUNCTIONS


async def character_currency_convert_quantity_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    currency_quantity_text = update.effective_message.text
    context.user_data[CHARACTERS_CREATOR_KEY][LAST_MENU_MESSAGES].append(update.effective_message)

    try:
        currency_quantity = int(currency_quantity_text)
        if currency_quantity <= 0:
            await send_and_save_message(update, context, "🔴 La quantità deve essere un numero positivo!")
            return BAG_CURRENCY_CONVERT
    except ValueError:
        await send_and_save_message(
            update,
            context,
            "🔴 La quantità inserita non è un numero valido!\n\n"
            "Inserisci una quantità corretta o usa /stop per terminare "
            "o un bottone del menù principale per cambiare funzione"
        )
        return BAG_CURRENCY_CONVERT

    currency_data = context.user_data[CHARACTERS_CREATOR_KEY][CURRENCY_CONVERTER]
    source_currency = currency_data[SELECTED_SOURCE_CURRENCY]
    target_currency = currency_data[SELECTED_TARGET_CURRENCY]

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    currency = character.currency

    source_currency_quantity = currency.get_currency_value(source_currency)
    if currency_quantity > source_currency_quantity:
        await send_and_save_message(
            update,
            context,
            f"🔴 Non hai abbastanza {currency.get_currency_human_name(source_currency)} "
            f"da convertire! Hai solo {source_currency_quantity} unità."
        )
        message_str, reply_markup = create_currency_converter_main_menu(context)
        await send_and_save_message(update, context, message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        return BAG_CURRENCY_FUNCTIONS

    # Define conversion rates
    currency_to_cp = currency.currency_to_cp

    # Converti la quantità della valuta di partenza in pezzi di rame
    amount_in_cp = currency_quantity * currency_to_cp[source_currency]

    # Converti i pezzi di rame nella valuta di destinazione
    target_currency_quantity = amount_in_cp // currency_to_cp[target_currency]
    remainder_cp = amount_in_cp % currency_to_cp[target_currency]

    # Aggiorna le valute del personaggio
    currency.set_currency_value(
        source_currency,
        source_currency_quantity - currency_quantity
    )
    target_currency_quantity_existing = currency.get_currency_value(target_currency)
    currency.set_currency_value(
        target_currency,
        target_currency_quantity_existing + target_currency_quantity
    )

    # Se c'è un resto in pezzi di rame, potresti volerlo gestire
    if remainder_cp > 0:
        # Ad esempio, aggiungilo ai pezzi di rame del personaggio
        copper_quantity_existing = currency.get_currency_value('bronze')
        currency.set_currency_value(
            'bronze',
            copper_quantity_existing + remainder_cp
        )
        remainder_message = f"\nHai ricevuto {remainder_cp} pezzi di bronzo come resto."
    else:
        remainder_message = ""

    # Conferma la conversione all'utente
    await send_and_save_message(
        update,
        context,
        f"✅ Hai convertito {currency_quantity} {currency.get_currency_human_name(source_currency)} "
        f"in {target_currency_quantity} {currency.get_currency_human_name(target_currency)}.{remainder_message}"
    )

    # Reimposta le selezioni per una nuova conversione
    currency_data[SELECTED_SOURCE_CURRENCY] = None
    currency_data[SELECTED_TARGET_CURRENCY] = None

    # Aggiorna il menu principale o termina la conversazione
    message_str, reply_markup = create_bag_menu(character, context)
    await send_and_save_message(update, context, message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return BAG_MANAGEMENT


async def character_ask_item_overwrite_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text
    context.user_data[CHARACTERS_CREATOR_KEY][LAST_MENU_MESSAGES].append(update.effective_message)

    try:
        item_quantity = int(text)
    except ValueError:
        await send_and_save_message(update, context, "🔴 La quantità inserita non è un numero!\n\n"
                                                     "Inserisci una quantità corretta o usa /stop per terminare "
                                                     "o un bottone del menù principale per cambiare funzione")
        return BAG_ITEM_OVERWRITE

    item_name = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_ITEM_KEY]
    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    item: Item = next((item for item in character.bag if item_name == item.name), None)

    if item.quantity + item_quantity < 0:
        await send_and_save_message(update, context, f'Non hai almeno {item_quantity * -1} Pz di {item_name}')

    elif item_quantity < 0:

        character.decrement_item_quantity(item_name, item_quantity * -1)
        await send_and_save_message(update, context,
                                    f"{'Sono stati rimossi' if item_quantity > 1 else 'È stato rimosso'} "
                                    f"{item_quantity} Pz di {item_name} dal tuo inventario")
    elif item_quantity > 0:
        character.increment_item_quantity(item_name, item_quantity)
        await send_and_save_message(update, context,
                                    f"{'Sono stati aggiunti' if item_quantity > 1 else 'È stato aggiunto'} "
                                    f"{item_quantity} Pz di {item_name} al tuo inventario")
    else:
        await send_and_save_message(update, context, "🔴 La quantità inviata è uguale a quella presente!")

    message_str, reply_markup = create_bag_menu(character, context)
    await send_and_save_message(update, context, message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return BAG_MANAGEMENT
