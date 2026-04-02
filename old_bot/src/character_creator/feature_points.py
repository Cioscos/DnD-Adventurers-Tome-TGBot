from typing import Dict, Tuple

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from . import *
from .models import Character
from .utilities import send_and_save_message


def create_feature_points_messages(feature_points: Dict[str, int]) -> Dict[str, Tuple[str, InlineKeyboardMarkup]]:
    return {
        'strength': (
            f"<code>Forza        {' ' if feature_points['strength'] < 10 else ''}{feature_points['strength']}</code>",
            InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("-", callback_data="strength|-"),
                    InlineKeyboardButton("+", callback_data="strength|+")
                ]
            ])
        ),
        'dexterity': (
            f"<code>Destrezza    {' ' if feature_points['dexterity'] < 10 else ''}{feature_points['dexterity']}</code>",
            InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("-", callback_data="dexterity|-"),
                    InlineKeyboardButton("+", callback_data="dexterity|+")
                ]
            ])
        ),
        'constitution': (
            f"<code>Costituzione {' ' if feature_points['constitution'] < 10 else ''}{feature_points['constitution']}</code>",
            InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("-", callback_data="constitution|-"),
                    InlineKeyboardButton("+", callback_data="constitution|+")
                ]
            ])
        ),
        'intelligence': (
            f"<code>Intelligenza {' ' if feature_points['intelligence'] < 10 else ''}{feature_points['intelligence']}</code>",
            InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("-", callback_data="intelligence|-"),
                    InlineKeyboardButton("+", callback_data="intelligence|+")
                ]
            ])
        ),
        'wisdom': (
            f"<code>Saggezza     {' ' if feature_points['wisdom'] < 10 else ''}{feature_points['wisdom']}</code>",
            InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("-", callback_data="wisdom|-"),
                    InlineKeyboardButton("+", callback_data="wisdom|+")
                ]
            ])
        ),
        'charisma': (
            f"<code>Carisma      {' ' if feature_points['charisma'] < 10 else ''}{feature_points['charisma']}</code>",
            InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("-", callback_data="charisma|-"),
                    InlineKeyboardButton("+", callback_data="charisma|+")
                ]
            ])
        )
    }


async def character_feature_point_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]

    message_str = (
        "<b>Gestione punti caratteristica</b>\n\n"
        "Inserisci i punti caratteristica come meglio desideri.\n\n"
        "Usa /stop per terminare o un bottone del menù principale per cambiare funzione"
    )
    await send_and_save_message(update, context, message_str, parse_mode=ParseMode.HTML)

    feature_points = character.feature_points.points

    messages = create_feature_points_messages(feature_points)
    for feature_point, message_data in messages.items():
        await send_and_save_message(
            update, context, message_data[0], reply_markup=message_data[1], parse_mode=ParseMode.HTML
        )

    return FEATURE_POINTS_EDIT


async def character_feature_points_edit_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    feature, action = query.data.split("|", maxsplit=1)

    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    feature_points = character.feature_points.points

    # Update the feature point based on the action
    if action == "+":
        feature_points[feature] += 1
    elif action == "-" and feature_points[feature] > 0:
        feature_points[feature] -= 1
    else:
        await query.answer("Non puoi andare sotto lo zero", show_alert=True)
        return FEATURE_POINTS_EDIT

    character.change_feature_points(feature_points)

    # Update the message with the new feature points
    messagges: Dict[str, Tuple[str, InlineKeyboardMarkup]] = create_feature_points_messages(feature_points)

    text, keyboard = messagges[feature]
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    await query.answer()

    return FEATURE_POINTS_EDIT
