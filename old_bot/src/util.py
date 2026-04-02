import logging
import re
from typing import List, Union

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.aiohttp import log as graphql_requests_logger
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

from model.APIResource import APIResource

graphql_requests_logger.setLevel(logging.WARNING)
ABILITY_SCORE_CALLBACK = 'ability_score'
SPELL_LEARN_CALLBACK_DATA = "spells_learn"

API = 'https://www.dnd5eapi.co'


def is_string_in_nested_lists(target: str, nested_lists: List[Union[str, List]]) -> bool:
    """
    Check if a string is present in a list of nested lists.

    Args:
        target (str): The string to search for.
        nested_lists (List[Union[str, List]]): The list of nested lists.

    Returns:
        bool: True if the string is found, False otherwise.
    """
    for item in nested_lists:
        if isinstance(item, list):
            if is_string_in_nested_lists(target, item):
                return True
        elif isinstance(item, str) and item == target:
            return True
    return False


async def split_text_into_chunks(text: str, update: Update, reply_markup: InlineKeyboardMarkup = None,
                                 max_length: int = 4096, image: str = None,
                                 parse_mode: ParseMode = ParseMode.HTML) -> None:
    """
    Split a given text into chunks that do not exceed the maximum Telegram message length,
    ensuring that HTML tags are not cut in half.

    Args:
        text (str): The text to be split.
        update (Update): The bot update object.
        reply_markup (InlineKeyboardMarkup): Optional keyboard markup for the messages.
        max_length (int): The maximum length of each chunk (default is 4096).
        image: (str): The image to be used for the message.
        parse_mode: (ParseMode): Optional parse mode for telegram messages.

    Returns:
        None
    """
    if len(text) <= max_length:
        await update.effective_message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
        return

    tag_regex = re.compile(r'(<!--.*?-->|<[^>]*>)')
    chunks = []
    current_chunk = ""
    current_length = 0
    open_tags = []

    def close_open_tags(tags):
        return ''.join([f"</{tag}>" for tag in tags[::-1]])

    def open_tags_html(tags):
        return ''.join([f"<{tag}>" for tag in tags])

    def extract_tag_name(tag):
        return tag[1:-1].split(' ')[0].replace('/', '')

    for part in tag_regex.split(text):
        if not part:
            continue

        if part.startswith('<') and part.endswith('>'):
            tag_name = extract_tag_name(part)

            if current_length + len(part) > max_length:
                closing_tags = close_open_tags(open_tags)
                chunks.append(current_chunk + closing_tags)
                current_chunk = open_tags_html(open_tags)
                current_length = len(current_chunk)

            if part.startswith('</'):
                if open_tags and open_tags[-1] == tag_name:
                    open_tags.pop()
            elif not part.endswith('/>'):
                if current_length + len(part) > max_length:
                    chunks.append(current_chunk)
                    current_chunk = ""
                    current_length = 0
                open_tags.append(tag_name)

            current_chunk += part
            current_length += len(part)
        else:
            while len(part) > 0:
                remaining_length = max_length - current_length
                if len(part) <= remaining_length:
                    current_chunk += part
                    current_length += len(part)
                    part = ""
                else:
                    split_point = part.rfind(' ', 0, remaining_length)
                    if split_point == -1:
                        split_point = remaining_length

                    current_chunk += part[:split_point]
                    part = part[split_point:].strip()

                    closing_tags = close_open_tags(open_tags)
                    chunks.append(current_chunk + closing_tags)
                    current_chunk = open_tags_html(open_tags)
                    current_length = len(current_chunk)

    if current_chunk:
        closing_tags = close_open_tags(open_tags)
        chunks.append(current_chunk + closing_tags)

    for index, chunk in enumerate(chunks):
        if index == len(chunks) - 1:
            await update.effective_message.reply_text(chunk, parse_mode=parse_mode, reply_markup=reply_markup)
        else:
            await update.effective_message.reply_text(chunk, parse_mode=parse_mode)

    if image:
        message = await update.effective_message.reply_text("Caricamento foto...")
        await update.effective_message.reply_photo(API + image)
        await message.delete()


def generate_resource_list_keyboard(resources: List[APIResource],
                                    draw_navigation_buttons: bool = True) -> InlineKeyboardMarkup:
    """
    Generates an inline keyboard markup for the provided list of resources.

    Args:
        resources (List[APIResource]): List of APIResource objects.
        draw_navigation_buttons (bool): Choose to draw or not the navigation buttons

    Returns:
        InlineKeyboardMarkup: The generated inline keyboard markup.
    """
    keyboard = []
    row = []
    for resource in resources:
        button = InlineKeyboardButton(resource.name, callback_data=f"{resource.url}")
        row.append(button)

        if len(row) == 2:
            keyboard.append(row)
            row = []

    # Append any remaining buttons if the total is an odd number
    if row:
        keyboard.append(row)

    if draw_navigation_buttons:
        # Add navigation buttons
        navigation_buttons = [InlineKeyboardButton("⬅️ Precedente", callback_data="prev_page"),
                              InlineKeyboardButton("Successiva ➡️", callback_data="next_page")]
        keyboard.append(navigation_buttons)

    return InlineKeyboardMarkup(keyboard)


def chunk_list(input_list, chunk_size):
    """
    Divide una lista in sottoliste di dimensione massima `chunk_size`.

    Args:
        input_list (list): La lista da dividere.
        chunk_size (int): La dimensione massima di ogni sottolista.

    Returns:
        list of lists: Una lista contenente sottoliste di massimo `chunk_size` elementi.
    """
    # Utilizza una list comprehension per creare i chunk
    return [input_list[i:i + chunk_size] for i in range(0, len(input_list), chunk_size)]


def format_camel_case_to_title(input_string: str) -> str:
    """
    Converts a hyphen-separated string into a properly capitalized string with spaces.

    Args:
        input_string (str): The input string in hyphen-separated format.

    Returns:
        str: The formatted string with each word capitalized and separated by spaces.
    """
    words = input_string.split('-')
    formatted_string = ' '.join(word.capitalize() for word in words)
    return formatted_string


async def async_graphql_query(endpoint, query, variables=None, headers=None):
    """
    Perform an asynchronous GraphQL query using the gql library.

    :param endpoint: The GraphQL endpoint URL.
    :param query: The GraphQL query as a string.
    :param variables: A dictionary of variables for the query (default is None).
    :param headers: A dictionary of headers to include in the request (default is None).
    :return: The JSON response from the GraphQL server.
    """
    transport = AIOHTTPTransport(
        url=endpoint,
        headers=headers
    )

    async with Client(transport=transport, fetch_schema_from_transport=True) as session:
        gql_query = gql(query)
        response = await session.execute(gql_query, variable_values=variables)
        return response
