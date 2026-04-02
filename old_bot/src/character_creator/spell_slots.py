from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from . import *
from .models import Character, SpellSlot
from .models.Character import SpellsSlotMode
from .utilities import send_and_save_message


def create_spell_slots_menu(context: ContextTypes.DEFAULT_TYPE):
    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    message_str = (f"Seleziona i pulsanti con gli slot liberi 🟦 per utilizzare uno slot del livello corrispondente.\n\n"
                   f"Usa /stop per terminare o un bottone del menù principale per cambiare funzione")
    keyboard = []
    if not character.spell_slots:

        message_str += "Non hai ancora nessuno slot incantesimo"

    else:

        spell_slots_buttons = []

        # Sort slots by level (dictionary key)
        for level, slot in sorted(character.spell_slots.items()):
            spell_slots_buttons.append(InlineKeyboardButton(
                f"{str(slot.level)} {'🟥' * slot.used_slots}{'🟦' * (slot.total_slots - slot.used_slots)}",
                callback_data=f"{SPELL_SLOT_SELECTED_CALLBACK_DATA}|{slot.level}"))

        # Group buttons into rows of maximum 3 buttons each
        for slot in spell_slots_buttons:
            keyboard.append([slot])

    keyboard.append(
        [
            InlineKeyboardButton("Inserisci nuovo slot", callback_data=SPELLS_SLOTS_INSERT_CALLBACK_DATA),
            InlineKeyboardButton("Rimuovi slot", callback_data=SPELLS_SLOTS_REMOVE_CALLBACK_DATA),
        ]
    )
    keyboard.append(
        [
            InlineKeyboardButton("Resetta utilizzi slot", callback_data=SPELLS_SLOTS_RESET_CALLBACK_DATA)
        ]
    )
    keyboard.append(
        [
            InlineKeyboardButton("Cambia modalità", callback_data=SPELLS_SLOTS_CHANGE_CALLBACK_DATA)
        ]
    )

    return message_str, InlineKeyboardMarkup(keyboard)


async def character_spells_slots_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]

    if character.spell_slots_mode is None:
        keyboard = [
            [
                InlineKeyboardButton("Automatica", callback_data=SPELL_SLOTS_AUTO_CALLBACK_DATA),
                InlineKeyboardButton("Manuale", callback_data=SPELL_SLOTS_MANUAL_CALLBACK_DATA),
            ]
        ]
        message_str = (
            "Che tipo di gestione vuoi scegliere per gli slot incantesimo?\n\n"
            "<b>Automatica:</b> scegli collegare il tuo personaggio ad una predefinita\n"
            "in questo modo quando sale di livello gli slot si modificano automaticamente.\n"
            "<b>N.B.</b> Questa gestione non considera il multi classing\n\n"
            "<b>Manuale:</b> Decidi tu quanti slot incantesimo avere e come gestirli"
        )
        await send_and_save_message(
            update, context, message_str, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML
        )
    else:
        message_str, reply_markup = create_spell_slots_menu(context)
        await send_and_save_message(update, context, message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return SPELLS_SLOTS_MANAGEMENT


async def character_spells_slots_mode_answer_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    data = query.data
    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]

    # Temporary check for automatic mode
    if data == SPELL_SLOTS_AUTO_CALLBACK_DATA:
        await query.answer("Modalità automatica ancora non gestita!", show_alert=True)
        return SPELLS_SLOTS_MANAGEMENT

    else:
        await query.answer()
        character.spell_slots_mode = SpellsSlotMode.MANUAL

        await send_and_save_message(
            update, context, "Modalità di gestione slot incantesimo impostata correttamente! ✅"
        )

        message_str, reply_markup = create_spell_slots_menu(context)
        await send_and_save_message(update, context, message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

        return SPELLS_SLOTS_MANAGEMENT


async def character_spells_slots_add_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    message_str = ("Inserisci quanti slot inserire e di che livello in questo modo:\n\n"
                   "<code>numero slot#livello</code>\n\n"
                   "<b>Esempio:</b> 4#1 (4 slot di livello 1)\n\n"
                   "Usa /stop per terminare o un bottone del menù principale per cambiare funzione")

    await query.edit_message_text(message_str, parse_mode=ParseMode.HTML)

    return SPELL_SLOT_ADDING


async def character_spell_slot_add_answer_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    data = update.effective_message.text
    context.user_data[CHARACTERS_CREATOR_KEY][LAST_MENU_MESSAGES].append(update.effective_message)

    try:
        slot_number, slot_level = data.split("#", maxsplit=1)
    except ValueError:
        await send_and_save_message(
            update,
            context,
            f"🔴 Formato sbagliato prova di nuovo!\n\nCorretto: 5#5 Usato: {data}\n\n"
            f"Usa /stop per terminare o un bottone del menù principale per cambiare funzione"
        )
        return SPELL_SLOT_ADDING

    if not slot_number or not slot_level or not slot_number.isdigit() or not slot_level.isdigit():
        await send_and_save_message(
            update,
            context,
            f"🔴 Formato sbagliato prova di nuovo!\n\nCorretto: 5#5 Usato: {data}\n\n"
            f"Usa /stop per terminare o un bottone del menù principale per cambiare funzione"
        )
        return SPELL_SLOT_ADDING

    if int(slot_level) > 9:
        await send_and_save_message(
            update, context, "🔴 Non puoi inserire uno slot di livello superiore al 9! 🔴\n\n"
                             "Usa /stop per terminare o un bottone del menù principale per cambiare funzione"
        )
        return SPELL_SLOT_ADDING

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]

    if slot_level in character.spell_slots:
        await send_and_save_message(
            update, context, f"Slot di livello {slot_level} già presente, andrai a sostituire la quantità già esistente"
        )

    spell_slot = SpellSlot(int(slot_level), int(slot_number))
    character.add_spell_slot(spell_slot)

    await send_and_save_message(
        update, context, f"{slot_number} slot di livello {slot_level} aggiunti!"
    )

    message_str, reply_markup = create_spell_slots_menu(context)
    await send_and_save_message(update, context, message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return SPELLS_SLOTS_MANAGEMENT


async def character_spells_slots_remove_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    message_str = ("Inserisci quanti slot rimuovere e di che livello in questo modo:\n\n"
                   "<code>numero slot#livello</code>\n\n"
                   "<b>Esempio:</b> 4#1 (4 slot di livello 1)\n\n"
                   "Usa /stop per terminare o un bottone del menù principale per cambiare funzione")

    await query.edit_message_text(message_str, parse_mode=ParseMode.HTML)

    return SPELL_SLOT_REMOVING


async def character_spell_slot_remove_answer_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    data = update.effective_message.text
    context.user_data[CHARACTERS_CREATOR_KEY][LAST_MENU_MESSAGES].append(update.effective_message)

    try:
        slot_number, slot_level = data.split("#", maxsplit=1)
    except ValueError:
        await send_and_save_message(
            update,
            context,
            f"🔴 Formato sbagliato prova di nuovo!\n\nCorretto: 5#5 Usato: {data}\n\n"
            f"Usa /stop per terminare o un bottone del menù principale per cambiare funzione"
        )
        return SPELL_SLOT_REMOVING

    if not slot_number or not slot_level or not slot_number.isdigit() or not slot_level.isdigit():
        await send_and_save_message(
            update,
            context,
            f"🔴 Formato sbagliato prova di nuovo!\n\nCorretto: 5#5 Usato: {data}\n\n"
            f"Usa /stop per terminare o un bottone del menù principale per cambiare funzione"
        )
        return SPELL_SLOT_REMOVING

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    slot_number = int(slot_number)
    slot_level = int(slot_level)

    if slot_level not in character.spell_slots:
        await send_and_save_message(
            update,
            context,
            f"Slot di livello {slot_level} non presente!\n\n"
            "Manda un nuovo messaggio con lo slot di livello corretto o Usa /stop per terminare o un bottone del menù principale per cambiare funzione"
        )
        return SPELL_SLOT_REMOVING

    spell_slot_to_edit = character.spell_slots[slot_level]

    if spell_slot_to_edit.total_slots - slot_number <= 0:
        await send_and_save_message(
            update,
            context,
            f"Il numero di slot da rimuovere copre o supera il numero di slot di livello {slot_level} già presenti.\n"
            f"Gli slot di questo livello sono stati tutti rimossi!"
        )
        character.spell_slots.pop(slot_level, None)
    else:
        spell_slot_to_edit.total_slots -= slot_number
        await send_and_save_message(update, context, f"{slot_number} slot di livello {slot_level} rimossi!")

    message_str, reply_markup = create_spell_slots_menu(context)
    await send_and_save_message(update, context, message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return SPELLS_SLOTS_MANAGEMENT


async def character_spells_slot_use_slot_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    data = query.data
    _, slot_level = data.split("|", maxsplit=1)

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]

    try:
        character.use_spell_slot(int(slot_level))
        await query.answer()
    except ValueError as e:
        await query.answer(str(e), show_alert=True)

    message_str, reply_markup = create_spell_slots_menu(context)
    await query.edit_message_text(message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return SPELLS_SLOTS_MANAGEMENT


async def character_spells_slot_use_reset_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    character.restore_all_spell_slots()
    await query.answer("Tutti gli spell slot sono stati ripristinati!", show_alert=True)

    message_str, reply_markup = create_spell_slots_menu(context)
    await query.edit_message_text(message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return SPELLS_SLOTS_MANAGEMENT


async def character_spells_slot_change_mode_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer("Funzione ancora non gestita!", show_alert=True)

    return SPELLS_SLOTS_MANAGEMENT
