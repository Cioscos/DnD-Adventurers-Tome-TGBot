from random import randint
from typing import Dict

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from . import *
from .models import Character
from .utilities import send_and_save_message

STARTING_DICE = {
    'd4': 0,
    'd6': 0,
    'd8': 0,
    'd100': 0,
    'd10': 0,
    'd12': 0,
    'd20': 0
}
ROLLS_MAP = {
    'd4': 4,
    'd6': 6,
    'd8': 8,
    'd100': 100,
    'd10': 10,
    'd12': 12,
    'd20': 20
}


def create_dice_keyboard(selected_dice: Dict[str, int]) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(f"{selected_dice['d4']} D4", callback_data=f"d4|+"),
            InlineKeyboardButton(f"{selected_dice['d6']} D6", callback_data=f"d6|+"),
            InlineKeyboardButton(f"{selected_dice['d8']} D8", callback_data=f"d8|+")
        ],
        [
            InlineKeyboardButton(f"-", callback_data=f"d4|-"),
            InlineKeyboardButton(f"-", callback_data=f"d6|-"),
            InlineKeyboardButton(f"-", callback_data=f"d8|-")
        ],
        [
            InlineKeyboardButton(f"{selected_dice['d10']} D10", callback_data=f"d10|+"),
            InlineKeyboardButton(f"{selected_dice['d12']} D12", callback_data=f"d12|+"),
            InlineKeyboardButton(f"{selected_dice['d100']} D100", callback_data=f"d100|+")
        ],
        [
            InlineKeyboardButton(f"-", callback_data=f"d10|-"),
            InlineKeyboardButton(f"-", callback_data=f"d12|-"),
            InlineKeyboardButton(f"-", callback_data=f"d100|-")
        ],
        [
            InlineKeyboardButton(f"{selected_dice['d20']} D20", callback_data=f"d20|+")
        ],
        [
            InlineKeyboardButton(f"-", callback_data=f"d20|-"),
        ]
    ]

    roll_text = 'Seleziona un dado' if sum(
        selected_dice.values()) == 0 else f'Lancia {', '.join([f'{roll_to_do}{die}' for die, roll_to_do in selected_dice.items() if roll_to_do > 0])}'
    keyboard.append([InlineKeyboardButton(roll_text, callback_data=ROLL_DICE_CALLBACK_DATA)])
    keyboard.append(
        [InlineKeyboardButton(f"Cancella cronologia", callback_data=ROLL_DICE_DELETE_HISTORY_CALLBACK_DATA)])

    return InlineKeyboardMarkup(keyboard)


async def send_dice_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, is_edit: bool = True):
    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    roll_history = character.get_rolls_history()
    message_str = (
        f"<b>Gestione tiri di dado</b>\n"
        "Usa /stop per terminare o un bottone del menù principale per cambiare funzione\n"
        f"<code>{roll_history if roll_history != '' else 'Cronologia lanci vuota!\n\n'}</code>"
        "Seleziona quanti dadi vuoi tirare:\n\n"
    )

    if is_edit:
        starting_dice = context.user_data[CHARACTERS_CREATOR_KEY][DICE]
        reply_markup = create_dice_keyboard(starting_dice)
        message = await update.effective_message.edit_text(
            message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )
    else:
        starting_dice = STARTING_DICE.copy()
        reply_markup = create_dice_keyboard(starting_dice)
        context.user_data[CHARACTERS_CREATOR_KEY][DICE] = starting_dice
        message = await send_and_save_message(
            update, context, message_str, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )

    context.user_data[CHARACTERS_CREATOR_KEY][DICE_MESSAGES] = message


async def delete_dice_menu(context: ContextTypes.DEFAULT_TYPE):
    message_to_delete = context.user_data[CHARACTERS_CREATOR_KEY][DICE_MESSAGES]
    await message_to_delete.delete()


async def dice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        query = update.callback_query
        await query.answer()

    await send_dice_menu(update, context, is_edit=False)

    return DICE_ACTION


async def dice_actions_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    temp_dice = context.user_data[CHARACTERS_CREATOR_KEY][DICE]
    character: Character = context.user_data[CHARACTERS_CREATOR_KEY][CURRENT_CHARACTER_KEY]
    if '|' in query.data:

        die, action = query.data.split('|', maxsplit=1)

        # update the dice number based on action
        if action == '+':
            temp_dice[die] += 1
        elif action == '-' and temp_dice[die] != 0:
            temp_dice[die] -= 1
        else:
            await query.answer("Non puoi tirare meno di un dado... genio", show_alert=True)
            return DICE_ACTION
        await query.answer()
        await send_dice_menu(update, context, is_edit=True)

    elif query.data == ROLL_DICE_CALLBACK_DATA:

        total_rolls = []

        for die, roll_to_do in temp_dice.items():
            if roll_to_do != 0:
                rolls = []

                for i in range(roll_to_do):
                    rolls.append(randint(1, ROLLS_MAP[die]))

                total_rolls.append((die, rolls))

        if not total_rolls:
            await query.answer("Non hai selezionato nemmeno un dado da rollare!", show_alert=True)
            return DICE_ACTION

        message_str = 'Roll eseguiti:\n'
        for die_name, die_rolls in total_rolls:
            message_str += f"{len(die_rolls)}{die_name}: [{', '.join([str(roll) for roll in die_rolls])}] = {sum(die_rolls)}\n"

        await query.answer(message_str, show_alert=True)

        # update history
        character.rolls_history.extend(total_rolls)
        await delete_dice_menu(context)
        await send_dice_menu(update, context, is_edit=False)

    elif query.data == ROLL_DICE_DELETE_HISTORY_CALLBACK_DATA:

        character.delete_rolls_history()
        await query.answer("Cronologia dadi cancellata!", show_alert=True)

        await send_dice_menu(update, context, is_edit=True)

    return DICE_ACTION
