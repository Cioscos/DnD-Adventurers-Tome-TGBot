from typing import List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler
from thefuzz import fuzz

from DndService import DndService
from model.APIResource import APIResource
from model.ClassLevelResource import ClassLevelResource
from model.SpellResource import SpellResource
from util import chunk_list, generate_resource_list_keyboard

# State definitions for class sub conversation
CLASS_SUBMENU, CLASS_SPELLS_SUBMENU, CLASS_RESOURCES_SUBMENU, CLASS_MANUAL_SPELLS_SEARCHING, CLASS_READING_SPELLS_SEARCHING, CLASS_SPELL_VISUALIZATION = map(
    int, range(5, 11))

STOPPING = 99

# chat data keys
WIKI = 'wiki'
CURRENT_CLASS_SPELLS_INLINE_PAGE = 'current_class_spells_inline_page'
ABILITY_SCORE_CALLBACK = 'ability_score'
CLASS_SPELLS_PAGES = 'class_spells'
CLASS_SPELLS_PAGE = 'class_spells_page'
CLASS_INDEX = 'class_index'


async def class_submenus_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    data = query.data
    await query.answer()

    submenu, class_index, class_name = data.split('|')
    # save the endpoint in chat data
    context.chat_data[WIKI][CLASS_INDEX] = class_index

    if submenu == 'spells':
        if class_index == 'None':
            await update.effective_message.reply_text("Questa classe non ha spell!")
            return CLASS_SUBMENU

        keyboard = [[InlineKeyboardButton('Consulta', callback_data='read-spells'),
                     InlineKeyboardButton('Cerca', callback_data='search-spell')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.effective_message.reply_text(f"Vuoi consultare tutte le spell del {class_name} o cercarne una?\n"
                                                  "Manda /stop per terminare la conversazione",
                                                  reply_markup=reply_markup)
        return CLASS_SPELLS_SUBMENU

    elif submenu == 'resources':
        await update.effective_message.reply_text(
            f"A che livello vuoi consultare la classe {class_name}? Rispondi con un messaggio da 1 a 20\n"
            f"Premi /stop per terminare la conversazione")

        return CLASS_RESOURCES_SUBMENU


async def class_spells_menu_buttons_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    data = query.data
    await query.answer()

    if data == 'search-spell':
        await update.effective_message.reply_text("Mandami il nome della spell da cercare")
        return CLASS_MANUAL_SPELLS_SEARCHING

    elif data == 'read-spells':
        class_index = context.chat_data[WIKI][CLASS_INDEX]
        async with DndService() as dnd_service:
            resource_details = await dnd_service.get_spells_by_class_index(class_index)

        # set the current inline page in chat_data
        context.chat_data[WIKI][CURRENT_CLASS_SPELLS_INLINE_PAGE] = 0

        spell_list = [APIResource(**result) for result in resource_details['results']]
        spell_pages = chunk_list(spell_list, 8)

        # save the spells in the chat data
        context.chat_data[WIKI][CLASS_SPELLS_PAGES] = spell_pages

        reply_markup = generate_resource_list_keyboard(
            spell_pages[context.chat_data[WIKI][CURRENT_CLASS_SPELLS_INLINE_PAGE]])

        await update.effective_message.reply_text(f"(Premi /stop per tornare al menu principle)\n"
                                                  f"Ecco la lista delle spell :", reply_markup=reply_markup)

        return CLASS_READING_SPELLS_SEARCHING

    return STOPPING


async def class_reading_spells_menu_buttons_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    data = query.data

    if data == "prev_page":
        if context.chat_data[WIKI][CURRENT_CLASS_SPELLS_INLINE_PAGE] == 0:
            await query.answer('Sei alla prima pagina!')
            return CLASS_READING_SPELLS_SEARCHING

        context.chat_data[WIKI][CURRENT_CLASS_SPELLS_INLINE_PAGE] -= 1

    elif data == "next_page":
        context.chat_data[WIKI][CURRENT_CLASS_SPELLS_INLINE_PAGE] += 1

    else:
        await query.answer()

        # fetch the spell for API
        async with DndService() as dnd_service:
            resource_details = await dnd_service.get_resource_by_class_resource(data)

        spell = SpellResource(**resource_details)
        keyboard = [[InlineKeyboardButton("Indietro 🔙", callback_data='back')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.effective_message.reply_text(str(spell), parse_mode=ParseMode.HTML, reply_markup=reply_markup)

        return CLASS_SPELL_VISUALIZATION

    # retrieve other spells
    spells_page: List[APIResource] = context.chat_data[WIKI][CLASS_SPELLS_PAGES][
        context.chat_data[WIKI][CURRENT_CLASS_SPELLS_INLINE_PAGE]]

    if not spells_page:
        await query.answer("Non ci sono altre pagine!")
        return CLASS_READING_SPELLS_SEARCHING

    reply_markup = generate_resource_list_keyboard(spells_page)
    await query.answer()
    await query.edit_message_text(f"(Premi /stop per tornare al menu principle)\n"
                                  f"Ecco la lista delle spell :", reply_markup=reply_markup)


async def class_spell_visualization_buttons_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    data = query.data

    if data == 'back':
        spells_page: List[APIResource] = context.chat_data[WIKI][CLASS_SPELLS_PAGES][
            context.chat_data[WIKI][CURRENT_CLASS_SPELLS_INLINE_PAGE]]

        reply_markup = generate_resource_list_keyboard(spells_page)
        await query.answer()
        await query.edit_message_text(f"(Premi /stop per tornare al menu principle)\n"
                                      f"Ecco la lista delle spell :", reply_markup=reply_markup)

        return CLASS_READING_SPELLS_SEARCHING


async def class_search_spells_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text
    class_index = context.chat_data[WIKI][CLASS_INDEX]

    # check if the input is a number
    if text.isdigit():
        await update.effective_message.reply_text('Inserisci un nome valido. Hai inserito un numero...')
        return CLASS_MANUAL_SPELLS_SEARCHING

    async with DndService() as dnd_service:
        resource_details = await dnd_service.get_spells_by_class_index(class_index)

    spells = resource_details['results']
    spells_dict = {spell['name'].lower(): spell['url'] for spell in spells}

    if text in spells_dict:
        # the spell exists in the dict exactly how it's been written
        # call the spell endpoint
        async with DndService() as dnd_service:
            resource_details = await dnd_service.get_resource_by_class_resource(spells_dict[text])

        spell = SpellResource(**resource_details)
        await update.effective_message.reply_text(str(spell), parse_mode=ParseMode.HTML)

    else:
        # do fuzzy research
        for spell in spells_dict:
            if fuzz.token_set_ratio(text, spell) > 50:
                # call the spell endpoint
                async with DndService() as dnd_service:
                    resource_details = await dnd_service.get_resource_by_class_resource(spells_dict[spell])
                    spell = SpellResource(**resource_details)
                    await update.effective_message.reply_text(str(spell), parse_mode=ParseMode.HTML)

    return ConversationHandler.END


async def class_resources_submenu_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text

    if text.isalpha() or int(text) < 1 or int(text) > 20:
        await update.effective_message.reply_text('Inserisci un numero tra 1 a 20. Dovresti saperlo...')
        return CLASS_RESOURCES_SUBMENU

    class_index = context.chat_data[WIKI][CLASS_INDEX]

    async with DndService() as dnd_service:
        resource_details = await dnd_service.get_class_levels_by_class_index(class_index, text)

    class_resource = ClassLevelResource(**resource_details)
    await class_resource.fetch_features()

    await update.effective_message.reply_text(str(class_resource), parse_mode=ParseMode.HTML)
    await update.effective_message.reply_text("Se vuoi puoi consultare la tua classe con un altro livello o terminare "
                                              "la conversazione usando il comando /stop")

    return CLASS_RESOURCES_SUBMENU
