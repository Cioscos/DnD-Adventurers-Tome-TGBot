import logging
from typing import Dict, Any, Union, List

from telegram import InlineKeyboardButton, Update, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ConversationHandler, ContextTypes

from DndService import DndService
from graphql_queries import CATEGORY_TO_QUERY_MAP
from model import models
from model.APIResource import APIResource
from model.AbilityScore import AbilityScore
from model.Alignment import Alignment
from model.Condition import Condition
from model.DamageType import DamageType
from model.models import GraphQLBaseModel
from src.class_submenus import CLASS_SUBMENU
from src.equipment_categories_submenus import EQUIPMENT_CATEGORIES_SUBMENU
from util import format_camel_case_to_title, chunk_list, generate_resource_list_keyboard, split_text_into_chunks, \
    async_graphql_query

logger = logging.getLogger(__name__)

# bot data keys
BOT_DATA_CHAT_IDS = 'bot_data_chat_ids'

# chat data keys
WIKI = 'wiki'
CHARACTERS_CREATOR = 'characters_creator'
CURRENT_INLINE_PAGE_FOR_SUBMENUS = 'current_inline_page_for_submenu'
INLINE_PAGES = 'inline_pages'

# callback keys
ABILITY_SCORE_CALLBACK = 'ability_score'
CLASS_SPELLS_PAGES = 'class_spells'
CLASS_SPELLS_PAGE = 'class_spells_page'

# Categories
CLASSES = 'classes'
ABILITY_SCORES = 'ability-scores'
ALIGNMENTS = 'alignments'
CONDITIONS = 'conditions'
DAMAGE_TYPES = 'damage-types'
EQUIPMENT_CATEGORIES = 'equipment-categories'
EQUIPMENT = 'equipment'
LANGUAGES = 'languages'
MONSTERS = 'monsters'
PROFICIENCIES = 'proficiencies'
RACES = 'races'
RULE_SECTIONS = 'rule-sections'
RULES = 'rules'
SKILLS = 'skills'
SPELLS = 'spells'
SUBCLASSES = 'subclasses'
SUBRACES = 'subraces'
TRAITS = 'traits'
WEAPON_PROPERTIES = 'weapon-properties'

# Excluded categories: These categories won't be shown in the first wiki menu
EXCLUDED_CATEGORIES = ['backgrounds',
                       'equipment',
                       'feats',
                       'features',
                       'magic-items',
                       'magic-schools',
                       PROFICIENCIES,
                       SUBCLASSES,
                       SUBRACES,
                       TRAITS]

# Not standard menù categories
NOT_STANDARD_MENU_CATEGORIES = [EQUIPMENT_CATEGORIES]

# graphql categories
GRAPHQL_ENDPOINT = 'https://www.dnd5eapi.co/graphql'
GRAPHQL_CATEOGRIES = [MONSTERS, PROFICIENCIES, RACES, RULE_SECTIONS, RULES, SKILLS, SPELLS, WEAPON_PROPERTIES,
                      LANGUAGES, CLASSES]

# categories with HTML Parsing
HTML_PARSING_CATEGORIES = [MONSTERS, PROFICIENCIES, RACES, SKILLS, SPELLS, WEAPON_PROPERTIES, LANGUAGES, CLASSES]

# State definitions for top-level conv handler
WIKI_MAIN_MENU, ITEM_DETAILS_MENU = map(int, range(3, 5))

# state definitions for features conversation
FEATURES_SUBMENU, FEATURE_VISUALIZATION = map(int, range(13, 15))

# user data keys
ACTIVE_CONV = 'active_conv'


def parse_resource(category: str, data: Dict[str, Any], graphql_key: str = None) -> Union[
    APIResource, GraphQLBaseModel]:
    # Add other categories and their respective parsing functions
    if category == ABILITY_SCORES:
        return AbilityScore(**data)
    elif category == CLASSES:
        return models.Class(**data[graphql_key])
    elif category == ALIGNMENTS:
        return Alignment(**data)
    elif category == CONDITIONS:
        return Condition(**data)
    elif category == DAMAGE_TYPES:
        return DamageType(**data)
    elif category == LANGUAGES:
        return models.Language(**data[graphql_key])
    elif category == MONSTERS:
        return models.Monster(**data[graphql_key])
    elif category == PROFICIENCIES:
        return models.Proficiency(**data[graphql_key])
    elif category == RACES:
        return models.Race(**data[graphql_key])
    elif category == RULE_SECTIONS:
        return models.RuleSection(**data[graphql_key])
    elif category == RULES:
        return models.Rule(**data[graphql_key])
    elif category == SKILLS:
        return models.Skill(**data[graphql_key])
    elif category == SPELLS:
        return models.Spell(**data[graphql_key])
    elif category == WEAPON_PROPERTIES:
        return models.WeaponProperty(**data[graphql_key])
    else:
        return APIResource(**data)


def process_keyboard_by_category(category: str, class_: Union[APIResource, GraphQLBaseModel]) -> List:
    if category == CLASSES:
        return [
            [InlineKeyboardButton('Spell', callback_data=f"spells|{class_.index}|{class_.name}")],
            [InlineKeyboardButton('Risorse di classe per livello',
                                  callback_data=f"resources|{class_.index}|{class_.name}")]
        ]

    else:
        return []


async def wiki_main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        query = update.callback_query
        await query.answer()

    # Check if the user is already in another conversation
    if context.user_data.get(ACTIVE_CONV) == 'character':
        await update.message.reply_text("Usare /stop per uscire dalla gestione dei personaggi prima di usare la wiki.")
        return ConversationHandler.END

    context.user_data[ACTIVE_CONV] = 'wiki'

    # Check for BOT_DATA_CHAT_IDS initialization
    if BOT_DATA_CHAT_IDS not in context.bot_data or update.effective_chat.id not in context.bot_data.get(
            BOT_DATA_CHAT_IDS, []):
        await update.effective_message.reply_text("La prima volta devi interagire con il bot usando il comando /start")
        return ConversationHandler.END

    try:
        async with DndService() as dnd_service:
            main_resources = await dnd_service.get_all_resources()
    except Exception as e:
        logger.error(f"Exception while getting main resources: {e}")
        await update.effective_message.reply_text(
            'Errore nel recuperare le risorse dalle API. Provare più tardi o un\'altra volta')
        return ConversationHandler.END

    # Create the keyboard
    keyboard = []
    row = []

    for resource_name, resource in main_resources.items():
        if resource_name not in EXCLUDED_CATEGORIES:
            button = InlineKeyboardButton(format_camel_case_to_title(resource_name), callback_data=resource_name)
            row.append(button)

            if len(row) == 2:
                keyboard.append(row)
                row = []

    if row:
        keyboard.append(row)

    # send the keyboard
    reply_markup = InlineKeyboardMarkup(keyboard)

    wiki_message = ("Seleziona una categoria della Wiki da visualizzare!\n"
                    "O premi /stop per terminare il comando")
    await update.effective_message.reply_text(wiki_message, reply_markup=reply_markup)

    return WIKI_MAIN_MENU


async def main_menu_buttons_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Manage inline buttons from main menu
    """
    query = update.callback_query
    category = query.data

    async with DndService() as dnd_service:
        resources = await dnd_service.get_available_resources(category)

    if len(resources) <= 100:

        # Create the keyboard
        keyboard = []
        row = []

        for resource in resources:
            button = InlineKeyboardButton(resource.name, callback_data=f"{category}/{resource.index}")
            row.append(button)

            if len(row) == 2:
                keyboard.append(row)
                row = []

        if row:
            keyboard.append(row)

        # send the keyboard
        reply_markup = InlineKeyboardMarkup(keyboard)

    else:
        # split the list into pages
        resource_pages = chunk_list(resources, 10)

        # save the inline pages in the context data
        context.chat_data[WIKI][INLINE_PAGES] = resource_pages

        if CURRENT_INLINE_PAGE_FOR_SUBMENUS not in context.chat_data[WIKI]:
            context.chat_data[WIKI][CURRENT_INLINE_PAGE_FOR_SUBMENUS] = 0

        # send the keyboard
        reply_markup = generate_resource_list_keyboard(
            resource_pages[context.chat_data[WIKI][CURRENT_INLINE_PAGE_FOR_SUBMENUS]])

    await query.answer()
    await query.edit_message_text(f"Seleziona un elemento in {category} o usa /stop per annullare il comando:",
                                  reply_markup=reply_markup)

    return ITEM_DETAILS_MENU


async def handle_pagination(query, context, direction):
    """Handle pagination of resource lists."""
    # initialize the CURRENT_INLINE_PAGE_FOR_SUBMENUS
    if CURRENT_INLINE_PAGE_FOR_SUBMENUS not in context.chat_data[WIKI]:
        context.chat_data[WIKI][CURRENT_INLINE_PAGE_FOR_SUBMENUS] = 0

    if direction == "prev_page":
        if context.chat_data[WIKI][CURRENT_INLINE_PAGE_FOR_SUBMENUS] == 0:
            await query.answer('Sei alla prima pagina!')
            return ITEM_DETAILS_MENU

        context.chat_data[WIKI][CURRENT_INLINE_PAGE_FOR_SUBMENUS] -= 1

    elif direction == "next_page":
        context.chat_data[WIKI][CURRENT_INLINE_PAGE_FOR_SUBMENUS] += 1

    try:
        resource_page = context.chat_data[WIKI][INLINE_PAGES][context.chat_data[WIKI][CURRENT_INLINE_PAGE_FOR_SUBMENUS]]
    except IndexError:
        await query.answer("Non ci sono altre pagine!")
        context.chat_data[WIKI][CURRENT_INLINE_PAGE_FOR_SUBMENUS] -= 1
        return ITEM_DETAILS_MENU

    reply_markup = generate_resource_list_keyboard(resource_page)
    await query.answer()
    await query.edit_message_text(f"(Premi /stop per tornare al menu principale)\n"
                                  f"Ecco la lista di equipaggiamenti:", reply_markup=reply_markup)
    return ITEM_DETAILS_MENU


async def handle_standard_category(query, update, category, path):
    """Handle standard categories."""
    async with DndService() as dnd_service:
        resource_details = await dnd_service.get_resource_detail(f"{category}/{path}")

    resource = parse_resource(category, resource_details)
    details = str(resource)

    keyboard = process_keyboard_by_category(category, resource)
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    await query.answer()

    if len(details) <= 4096:
        await query.edit_message_text(details, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    else:
        await split_text_into_chunks(details, update, reply_markup=reply_markup)


async def handle_not_standard_category(query, context, resource_details):
    """Handle non-standard categories."""
    key_name = next(k for k, v in resource_details.items() if isinstance(v, list))

    resource_list = [APIResource(**result) for result in resource_details[key_name]]
    resource_pages = chunk_list(resource_list, 8)

    context.chat_data[WIKI][INLINE_PAGES] = resource_pages

    reply_markup = generate_resource_list_keyboard(resource_pages[0])

    await query.answer()
    await query.edit_message_text("Seleziona un elemento dalla lista o premi "
                                  "/stop per terminare la conversazione", reply_markup=reply_markup)


async def handle_graphql_category(query, update, category, data):
    """Handle GraphQL categories."""
    if data.startswith("/api"):
        variables = {'index': data.split('/')[3]}
    else:
        variables = {'index': data.split('/')[1]}
    resource_details = await async_graphql_query(GRAPHQL_ENDPOINT, CATEGORY_TO_QUERY_MAP[category], variables=variables)
    key = list(resource_details.keys())[0]
    resource = parse_resource(category, resource_details, key)
    details = str(resource)

    keyboard = process_keyboard_by_category(category, resource)
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    await query.answer()

    parse_mode = ParseMode.HTML if category in HTML_PARSING_CATEGORIES else ParseMode.MARKDOWN

    if len(details) > 4096 or hasattr(resource, 'image'):
        await split_text_into_chunks(details, update, reply_markup=reply_markup, parse_mode=parse_mode,
                                     image=getattr(resource, 'image', None))
    else:
        await query.edit_message_text(details, parse_mode=parse_mode, reply_markup=reply_markup)


async def details_menu_buttons_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    data = query.data

    if data in ["prev_page", "next_page"]:
        return await handle_pagination(query, context, data)

    if not data.startswith("/api"):
        category, path = (data.split('/', 1) + [""])[:2]  # Safely split data into category and path

        if category in NOT_STANDARD_MENU_CATEGORIES:
            async with DndService() as dnd_service:
                resource_details = await dnd_service.get_resource_detail(f"{category}/{path}")
            await handle_not_standard_category(query, context, resource_details)
        elif category in GRAPHQL_CATEOGRIES:
            await handle_graphql_category(query, update, category, data)
        else:
            await handle_standard_category(query, update, category, path)

    else:
        category = data.split('/')[2]
        if category not in GRAPHQL_CATEOGRIES:
            async with DndService() as dnd_service:
                resource_details = await dnd_service.get_resource_by_class_resource(data)
            resource = parse_resource(category, resource_details)

            await query.answer()

            details = str(resource)
            keyboard = process_keyboard_by_category(category, resource)
            reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

            if len(details) <= 4096:
                await query.edit_message_text(details, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
            else:
                await split_text_into_chunks(details, update, reply_markup=reply_markup)
        else:
            await handle_graphql_category(query, update, category, data)

    if category == CLASSES:
        return CLASS_SUBMENU
    elif category == EQUIPMENT_CATEGORIES:
        return EQUIPMENT_CATEGORIES_SUBMENU
    else:
        return ConversationHandler.END
