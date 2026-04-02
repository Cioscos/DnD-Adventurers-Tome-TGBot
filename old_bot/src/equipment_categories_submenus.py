from typing import List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from DndService import DndService
from model.APIResource import APIResource
from model.Equipment import Equipment
from util import generate_resource_list_keyboard

# chat data keys
WIKI = 'wiki'
CURRENT_FIRST_MENU_INLINE_PAGE = 'current_first_menu_inline_page'
INLINE_PAGES = 'inline_pages'

# state definitions for equipment-categories conversation
EQUIPMENT_CATEGORIES_SUBMENU, EQUIPMENT_VISUALIZATION = map(int, range(11, 13))


async def equipment_categories_first_menu_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    data = query.data

    if CURRENT_FIRST_MENU_INLINE_PAGE not in context.chat_data[WIKI]:
        context.chat_data[WIKI][CURRENT_FIRST_MENU_INLINE_PAGE] = 0

    if data == "prev_page":
        if context.chat_data[WIKI][CURRENT_FIRST_MENU_INLINE_PAGE] == 0:
            await query.answer('Sei alla prima pagina!')
            return EQUIPMENT_CATEGORIES_SUBMENU

        context.chat_data[WIKI][CURRENT_FIRST_MENU_INLINE_PAGE] -= 1

    elif data == "next_page":
        context.chat_data[WIKI][CURRENT_FIRST_MENU_INLINE_PAGE] += 1

    else:
        await query.answer()

        # fetch the equipments for API
        async with DndService() as dnd_service:
            resource_details = await dnd_service.get_resource_by_class_resource(data)

        equipment: Equipment = Equipment(**resource_details)
        keyboard = [[InlineKeyboardButton("Indietro 🔙", callback_data='back')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.effective_message.edit_text(str(equipment), parse_mode=ParseMode.HTML, reply_markup=reply_markup)

        return EQUIPMENT_VISUALIZATION

    # retrieve other equipments
    try:
        equipment_page: List[APIResource] = context.chat_data[WIKI][INLINE_PAGES][
            context.chat_data[WIKI][CURRENT_FIRST_MENU_INLINE_PAGE]]
    except IndexError:
        await query.answer("Non ci sono altre pagine!")
        context.chat_data[WIKI][CURRENT_FIRST_MENU_INLINE_PAGE] -= 1
        return EQUIPMENT_CATEGORIES_SUBMENU

    reply_markup = generate_resource_list_keyboard(equipment_page)
    await query.answer()
    await query.edit_message_text(f"(Premi /stop per tornare al menu principale)\n"
                                  f"Ecco la lista di equipaggiamenti:", reply_markup=reply_markup)


async def equipment_visualization_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    data = query.data

    if data == 'back':
        equipment_page: List[APIResource] = context.chat_data[WIKI][INLINE_PAGES][
            context.chat_data[WIKI][CURRENT_FIRST_MENU_INLINE_PAGE]]

        reply_markup = generate_resource_list_keyboard(equipment_page)
        await query.answer()
        await query.edit_message_text(f"(Premi /stop per tornare al menu principle)\n"
                                      f"Ecco la lista di equipaggiamenti:", reply_markup=reply_markup)

        return EQUIPMENT_CATEGORIES_SUBMENU
