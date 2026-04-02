from collections import defaultdict
from typing import Tuple

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from . import *
from .models import Character, Spell
from .models.Spell import SpellLevel
from .utilities import send_and_save_message, generate_spells_list_keyboard


async def create_spells_menu(character: Character, update: Update, context: ContextTypes.DEFAULT_TYPE,
                             edit_mode: bool = False) -> int:
    message_str = f"<b>Gestione spells</b>\nUsa /stop per terminare o un bottone del menù principale per cambiare funzione\n\n"
    if not character.spells:

        message_str += "Non conosci ancora nessun incantesimo ‍🤷‍♂️"
        keyboard = [
            [InlineKeyboardButton("Impara nuovo incantesimo", callback_data=SPELL_LEARN_CALLBACK_DATA)]
        ]

        if edit_mode:
            await update.effective_message.edit_text(message_str, reply_markup=InlineKeyboardMarkup(keyboard),
                                                     parse_mode=ParseMode.HTML)
        else:
            await send_and_save_message(update, context, message_str, reply_markup=InlineKeyboardMarkup(keyboard),
                                        parse_mode=ParseMode.HTML)

        return SPELL_LEARN

    spells = character.spells

    # Group spells by level
    level_to_spells = defaultdict(list)
    for spell in spells:
        level_to_spells[spell.level.value].append(spell)

    # Create pages as a list of tuples (level, spells of that level)
    levels = sorted(level_to_spells.keys())
    pages = []
    for level in levels:
        pages.append((level, level_to_spells[level]))

    # Save pages in user context
    context.user_data[CHARACTERS_CREATOR_KEY][INLINE_PAGES_KEY] = pages
    context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_INLINE_PAGE_INDEX_KEY] = 0

    # Get the current page
    current_page_index = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_INLINE_PAGE_INDEX_KEY]
    current_page = pages[current_page_index]
    level, spells_in_page = current_page

    message_str += f"Ecco la lista degli incantesimi di livello {level}"

    # Generates the keyboard for spells on the current page
    reply_markup = generate_spells_list_keyboard(spells_in_page, draw_back_button=False)
    if edit_mode:
        await update.effective_message.edit_text(message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    else:
        await send_and_save_message(update, context, message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return SPELLS_MENU


async def create_spell_levels_menu(character: Character, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                   edit_mode: bool = False) -> int:
    message_str = (
        f"<b>Gestione spells</b>\nUsa /stop per terminare o un bottone del menù principale per cambiare funzione\n\n"
        f"❌ Significa che non hai più slot incantesimo disponibili di quel livello\n\n")

    if not character.spells:
        message_str += "Non conosci ancora nessun incantesimo ‍🤷‍♂️"
        keyboard = [
            [InlineKeyboardButton("Impara nuovo incantesimo", callback_data=SPELL_LEARN_CALLBACK_DATA)]
        ]

        if edit_mode:
            await update.effective_message.edit_text(message_str, reply_markup=InlineKeyboardMarkup(keyboard),
                                                     parse_mode=ParseMode.HTML)
        else:
            await send_and_save_message(update, context, message_str, reply_markup=InlineKeyboardMarkup(keyboard),
                                        parse_mode=ParseMode.HTML)

        return SPELL_LEARN

    spells = character.spells
    buttons = []

    # Group spells by their level
    # generate keyboared with spell level
    spells_by_level = {}

    for spell in spells:
        spells_by_level.setdefault(spell.level.value, []).append(spell)

    # Iterate over the available spell levels (from 1 to 9)
    for level in SpellLevel:
        spell_level = level.value

        # Check if there is at least one spell of this level
        if spell_level in spells_by_level:
            # Check if slots are available for this level
            spell_slot = character.spell_slots.get(spell_level)
            if spell_slot:
                if spell_slot.slots_remaining() > 0:
                    button_text = f"Livello {spell_level}"
                else:
                    button_text = f"Livello {spell_level} ❌"

                buttons.append(
                    InlineKeyboardButton(button_text, callback_data=f"spell_of_level|{spell_level}")
                )

    # Return the keyboard with buttons in rows
    keyboard = [[button] for button in buttons]
    keyboard.append([InlineKeyboardButton("Impara nuovo incantesimo", callback_data=SPELL_LEARN_CALLBACK_DATA)])
    keyboard = InlineKeyboardMarkup(keyboard)

    if edit_mode:
        await update.effective_message.edit_text(message_str, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    else:
        await send_and_save_message(update, context, message_str, reply_markup=keyboard, parse_mode=ParseMode.HTML)

    return SPELL_LEVEL_MENU


def create_spell_menu(spell: Spell) -> Tuple[str, InlineKeyboardMarkup]:
    message_str = (f"<b>{spell.name}</b>\n\n"
                   f"<b>Livello incantesimo:</b> {spell.level.value}\n"
                   f"<b>Descrizione</b>\n{spell.description}\n\n"
                   f"Usa /stop per terminare o un bottone del menù principale per cambiare funzione")
    keyboard = [
        [InlineKeyboardButton("Usa", callback_data=SPELL_USE_CALLBACK_DATA)],
        [InlineKeyboardButton("Modifica", callback_data=SPELL_EDIT_CALLBACK_DATA),
         InlineKeyboardButton("Dimentica", callback_data=SPELL_DELETE_CALLBACK_DATA)],
        [InlineKeyboardButton("Indietro 🔙", callback_data=SPELL_BACK_MENU_CALLBACK_DATA)]
    ]

    return message_str, InlineKeyboardMarkup(keyboard)


def create_spell_slots_menu_for_spell(character: Character, spell: Spell) -> Tuple[str, InlineKeyboardMarkup]:
    keyboard = []
    message_str = (
        "Seleziona i pulsanti con gli slot liberi 🟦 per utilizzare un incantesimo del livello corrispondente al livello dello slot utilizzato.\n\n"
        "Usa /stop per terminare o un bottone del menù principale per cambiare funzione")

    if not character.spell_slots:

        message_str += ("Non hai ancora nessuno slot incantesimo!\n"
                        "Usa il menu <i><b>Gestisci slot incantesimo</b></i> per aggiungerli")

    else:

        spell_slots_buttons = []

        # Sort slots by level (dictionary key)
        for level, slot in sorted(character.spell_slots.items()):
            if level >= spell.level.value:
                spell_slots_buttons.append(InlineKeyboardButton(
                    f"{str(slot.level)} {'🟥' * slot.used_slots}{'🟦' * (slot.total_slots - slot.used_slots)}",
                    callback_data=f"{SPELL_SLOT_SELECTED_CALLBACK_DATA}|{slot.level}"))

        # Group buttons into rows of maximum 3 buttons each
        for slot in spell_slots_buttons:
            keyboard.append([slot])

        if not keyboard:
            message_str += f"Non hai slot incantesimo del livello necessario a castare questa spell!"

    keyboard.append([InlineKeyboardButton("Indietro 🔙", callback_data=SPELL_USAGE_BACK_MENU_CALLBACK_DATA)])

    return message_str, InlineKeyboardMarkup(keyboard)


async def character_spells_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    spell_management_preference = character.settings.get('spell_management', 'default_value')

    if spell_management_preference == 'paginate_by_level':
        return await create_spells_menu(character, update, context)
    else:
        return await create_spell_levels_menu(character, update, context)


async def character_spells_by_level_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == SPELL_LEARN_CALLBACK_DATA:
        return await character_spell_new_query_handler(update, context)

    _, spell_level = data.split('|', maxsplit=1)
    spell_level = int(spell_level)

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    spells_of_selected_level = [spell for spell in character.spells if spell.level.value == spell_level]
    message_str = (f"Ecco la lista degli incantesimi di livello {spell_level}\n\n"
                   f"Usa /stop per terminare o un bottone del menù principale per cambiare funzione")

    # Generates the keyboard for spells on the current page
    reply_markup = generate_spells_list_keyboard(spells_of_selected_level, draw_navigation_buttons=False,
                                                 draw_back_button=True)
    await query.edit_message_text(message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return SPELLS_MENU


async def character_spells_menu_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    data = query.data

    pages = context.user_data[CHARACTERS_CREATOR_KEY][INLINE_PAGES_KEY]
    current_page_index = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_INLINE_PAGE_INDEX_KEY]

    if data == "prev_page":
        if current_page_index == 0:
            await query.answer("Sei alla prima pagina!", show_alert=True)
        else:
            context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_INLINE_PAGE_INDEX_KEY] -= 1
            current_page_index -= 1
            # Refresh current page
            current_page = pages[current_page_index]
            level, spells_in_page = current_page
            message_str = ("Usa /stop per terminare o un bottone del menù principale per cambiare funzione\n"
                           f"Ecco la lista degli incantesimi di livello {level}")
            reply_markup = generate_spells_list_keyboard(spells_in_page, draw_back_button=False)
            await query.edit_message_text(message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        return SPELLS_MENU

    elif data == "next_page":
        if current_page_index >= len(pages) - 1:
            await query.answer("Non ci sono altre pagine!", show_alert=True)
        else:
            context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_INLINE_PAGE_INDEX_KEY] += 1
            current_page_index += 1  # Aggiorna l'indice locale
            # Aggiorna la pagina corrente
            current_page = pages[current_page_index]
            level, spells_in_page = current_page
            message_str = ("Usa /stop per terminare o un bottone del menù principale per cambiare funzione\n"
                           f"Ecco la lista degli incantesimi di livello {level}")
            reply_markup = generate_spells_list_keyboard(spells_in_page, draw_back_button=False)
            await query.edit_message_text(message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        return SPELLS_MENU

    elif data == SPELL_LEARN_CALLBACK_DATA:

        await query.answer()
        return await character_spell_new_query_handler(update, context)

    elif data == SPELL_USAGE_BACK_MENU_CALLBACK_DATA:

        await query.answer()
        character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
        spell_management_preference = character.settings.get('spell_management', 'default_value')
        if spell_management_preference == 'paginate_by_level':
            return await create_spells_menu(character, update, context)
        else:
            return await create_spell_levels_menu(character, update, context)

    else:
        await query.answer()
        _, spell_name = data.split('|', maxsplit=1)
        character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
        spell: Spell = next((spell for spell in character.spells if spell.name == spell_name), None)

        if spell is None:
            await query.answer("Incantesimo non trovato.", show_alert=True)
            return SPELLS_MENU

        message_str, reply_markup = create_spell_menu(spell)
        await query.edit_message_text(message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

        # Salva l'incantesimo corrente nei dati utente
        context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_SPELL_KEY] = spell

        return SPELL_VISUALIZATION


async def character_spell_visualization_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    data = query.data

    if data == SPELL_EDIT_CALLBACK_DATA:

        await query.answer()
        spell: Spell = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_SPELL_KEY]
        message_str = ("Usa /stop per terminare o un bottone del menù principale per cambiare funzione\n\n"
                       "Inviami l'incantesimo inserendo il nome, descrizione e livello separati da un #\n\n"
                       "Premi sul titolo, descrizione e livello per copiarli.\n\n"
                       f"<b>Nome incantesimo attuale</b>\n<code>{spell.name}</code>\n"
                       f"<b>Descrizione attuale:</b> <code>{spell.description}</code>\n"
                       f"<b>Livello attuale:</b> <code>{spell.level.value}</code>")
        await query.edit_message_text(message_str, parse_mode=ParseMode.HTML)

    elif data == SPELL_DELETE_CALLBACK_DATA:

        await query.answer()
        keyboard = [
            [
                InlineKeyboardButton("Si", callback_data='y'),
                InlineKeyboardButton("No", callback_data='n')
            ]
        ]
        await query.edit_message_text(
            "Sicuro di voler cancellare l'incantesimo\n\n"
            "Usa /stop per terminare o un bottone del menù principale per cambiare funzione?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == SPELL_BACK_MENU_CALLBACK_DATA:

        await query.answer()

        character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
        spell_management_preference = character.settings.get('spell_management', 'default_value')
        if spell_management_preference == 'paginate_by_level':
            # Retrieve current pages and index
            pages = context.user_data[CHARACTERS_CREATOR_KEY][INLINE_PAGES_KEY]
            current_page_index = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_INLINE_PAGE_INDEX_KEY]

            try:
                current_page = pages[current_page_index]
                level, spells_in_page = current_page
            except IndexError:
                await query.answer("Errore nel recuperare la pagina corrente.", show_alert=True)
                return SPELLS_MENU

            message_str = (
                "Usa /stop per terminare o un bottone del menù principale per cambiare funzione\n"
                f"Ecco la lista degli incantesimi di livello {level}"
            )
            reply_markup = generate_spells_list_keyboard(spells_in_page, True)
            await query.edit_message_text(message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

            return SPELLS_MENU
        else:

            return await create_spell_levels_menu(character, update, context, edit_mode=True)

    elif data == SPELL_USE_CALLBACK_DATA:

        await query.answer()
        spell: Spell = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_SPELL_KEY]
        character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]

        # Generate inline keyboard with available spell slots
        message_str, reply_markup = create_spell_slots_menu_for_spell(character, spell)

        await query.edit_message_text(message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return SPELL_ACTIONS


async def character_spell_new_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    await send_and_save_message(
        update,
        context,
        "Inviami l'incantesimo inserendo il nome, descrizione e livello "
        "separati da un #\n\n"
        "<b>Esempio:</b> <code>Palla di fuoco#Unico incantesimo dei maghi#3</code>\n\n"
        "Usa /stop per terminare o un bottone del menù principale per cambiare funzione",
        parse_mode=ParseMode.HTML
    )

    return SPELL_LEARN


async def character_spell_learn_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    spell_info = update.effective_message.text
    context.user_data[CHARACTERS_CREATOR_KEY][LAST_MENU_MESSAGES].append(update.effective_message)

    try:
        spell_name, spell_desc, spell_level = spell_info.split("#", 2)
    except ValueError:
        await send_and_save_message(
            update,
            context,
            "🔴 Hai inserito i dati in un formato non valido!\n\n"
            "Invia di nuovo l'incantesimo o usa /stop per terminare o un bottone del menù principale per cambiare funzione"
        )
        return SPELL_ACTIONS

    if spell_name.isdigit() or spell_desc.isdigit() or not spell_level.isdigit():
        await send_and_save_message(
            update,
            context,
            "🔴 Hai inserito i dati in un formato non valido!\n\n"
            "Invia di nuovo l'incantesimo o usa /stop per terminare o un bottone del menù principale per cambiare funzione"
        )
        return SPELL_ACTIONS

    spell = Spell(spell_name, spell_desc, SpellLevel(int(spell_level)))
    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]

    if any(spell_name == spell.name for spell in character.spells):
        await send_and_save_message(
            update,
            context,
            "🔴 Hai già appreso questa spell!\n\n"
            "Invia un altro incantesimo o usa /stop per terminare o un bottone del menù principale per cambiare funzione"
        )
        return SPELL_ACTIONS

    if spell.level.value not in character.spell_slots.keys():
        await send_and_save_message(update,
                                    context,
                                    f"🔴 Questo incantesimo è di livello troppo alto!\n\n"
                                    f"Sblocca prima almeno uno slot di livello {spell.level.value} per impararlo.\n"
                                    f"Invia un altro incantesimo o usa /stop per terminare o un bottone del menù principale per cambiare funzione")
        return SPELL_ACTIONS

    character.learn_spell(spell)
    await send_and_save_message(update, context, "Incantesimo appreso con successo! ✅")

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    spell_management_preference = character.settings.get('spell_management', 'default_value')
    if spell_management_preference == 'paginate_by_level':
        return await create_spells_menu(character, update, context)
    else:
        return await create_spell_levels_menu(character, update, context)


async def character_spell_edit_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    spell_info = update.effective_message.text
    context.user_data[CHARACTERS_CREATOR_KEY][LAST_MENU_MESSAGES].append(update.effective_message)

    try:
        spell_name, spell_desc, spell_level = spell_info.split("#", 2)
    except ValueError:
        await send_and_save_message(
            update,
            context,
            "🔴 Hai inserito i dati in un formato non valido!\n\n"
            "Invia di nuovo l'incantesimo o usa /stop per terminare o un bottone del menù principale per cambiare funzione"
        )
        return SPELL_ACTIONS

    if spell_name.isdigit() or spell_desc.isdigit() or not spell_level.isdigit():
        await send_and_save_message(
            update,
            context,
            "🔴 Hai inserito i dati in un formato non valido!\n\n"
            "Invia di nuovo l'incantesimo o usa /stop per terminare o un bottone del menù principale per cambiare funzione"
        )
        return SPELL_ACTIONS

    old_spell: Spell = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_SPELL_KEY]
    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]

    for spell in character.spells:
        if spell.name == old_spell.name:
            old_spell.name = spell_name
            old_spell.description = spell_desc
            old_spell.level = SpellLevel(int(spell_level))
            break

    await send_and_save_message(update, context, "Incantesimo modificato con successo!")
    message_str, reply_markup = create_spell_menu(old_spell)
    await send_and_save_message(update, context, message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return SPELL_VISUALIZATION


async def character_spell_delete_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    spell_to_forget: Spell = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_SPELL_KEY]

    if data == 'y':
        character.forget_spell(spell_to_forget.name)
    elif data == 'n':
        await send_and_save_message(
            update,
            context,
            f"Hai una buona memoria, ti ricordi ancora l'incantesimo {spell_to_forget.name}"
        )

    spell_management_preference = character.settings.get('spell_management', 'default_value')
    if spell_management_preference == 'paginate_by_level':
        return await create_spells_menu(character, update, context)
    else:
        return await create_spell_levels_menu(character, update, context)


async def character_spell_use_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    data = query.data

    spell: Spell = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_SPELL_KEY]
    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]

    if data != SPELL_USAGE_BACK_MENU_CALLBACK_DATA:

        _, slot_level = data.split("|", maxsplit=1)

        try:
            character.use_spell(spell, int(slot_level))
        except ValueError as e:
            await query.answer(str(e), show_alert=True)
        else:
            await query.answer(f"Slot di livello {slot_level} usato", show_alert=True)

    else:
        await query.answer()

    message_str, reply_markup = create_spell_menu(spell)
    await query.edit_message_text(message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return SPELL_VISUALIZATION
