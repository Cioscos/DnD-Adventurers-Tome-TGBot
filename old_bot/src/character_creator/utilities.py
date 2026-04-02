from typing import List, Tuple

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from . import *
from .models import Spell, Ability, Character


async def send_and_save_message(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, **kwargs):
    """Wrapper for reply_text that saves the last message in user_data."""
    message = await update.effective_message.reply_text(text, **kwargs)

    # Check if the mailing list already exists, if not, create it
    if LAST_MENU_MESSAGES not in context.user_data[CHARACTERS_CREATOR_KEY]:
        context.user_data[CHARACTERS_CREATOR_KEY][LAST_MENU_MESSAGES] = []

    # Add new message to the list
    context.user_data[CHARACTERS_CREATOR_KEY][LAST_MENU_MESSAGES].append(message)

    return message


def create_skull_asciart() -> str:
    return r"""<code>
           ______
        .-"      "-.
       /            \
      |              |
      |,  .-.  .-.  ,|
      | )(_o/  \o_)( |
      |/     /\     \|
      (_     ^^     _)
       \__|IIIIII|__/
        | \IIIIII/ |
        \          /
         `--------`

     SSSSS   EEEEE  III       
     S       E       I 
     SSS     EEEE    I
         S   E       I
     SSSSS   EEEEE  III        

M   M   OOO   RRRR  TTTTT  OOO
MM MM  O   O  R   R   T   O   O
M M M  O   O  RRRR    T   O   O
M   M  O   O  R  R    T   O   O
M   M   OOO   R   R   T    OOO</code>"""


def generate_spells_list_keyboard(spells: List[Spell],
                                  draw_navigation_buttons: bool = True,
                                  draw_back_button: bool = True) -> InlineKeyboardMarkup:
    """
    Generates an inline keyboard markup for the provided list of spells.

    Args:
        spells (List[Spell]): List of ability objects.
        draw_navigation_buttons (bool): Choose to draw or not the navigation buttons

    Returns:
        InlineKeyboardMarkup: The generated inline keyboard markup.
    """
    keyboard = []
    row = []
    for spell in spells:
        button = InlineKeyboardButton(spell.name, callback_data=f"spell_name|{spell.name}")
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
    keyboard.append([InlineKeyboardButton("Impara nuova spell", callback_data=SPELL_LEARN_CALLBACK_DATA)])

    if draw_back_button:
        keyboard.append([InlineKeyboardButton('Indietro 🔙', callback_data='spell_usage_back_menu')])

    return InlineKeyboardMarkup(keyboard)


def generate_abilities_list_keyboard(abilities: List[Ability],
                                     draw_navigation_buttons: bool = True) -> InlineKeyboardMarkup:
    """
    Generates an inline keyboard markup for the provided list of abilities.

    Args:
        abilities (List[Ability]): List of ability objects.
        draw_navigation_buttons (bool): Choose to draw or not the navigation buttons

    Returns:
        InlineKeyboardMarkup: The generated inline keyboard markup.
    """
    keyboard = []
    row = []
    for ability in abilities:
        button = InlineKeyboardButton(f"{'✅ ' if ability.activated else ''}{ability.name}",
                                      callback_data=f"ability_name|{ability.name}")
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

    keyboard.append([InlineKeyboardButton("Impara nuova abilità", callback_data=SPELL_LEARN_CALLBACK_DATA)])

    return InlineKeyboardMarkup(keyboard)


def create_main_menu_message(character: Character) -> Tuple[str, InlineKeyboardMarkup]:
    if character.current_hit_points <= -character.hit_points:
        health_str = '☠️\n'
    else:
        health_str = f"{character.current_hit_points if character.current_hit_points <= character.hit_points else character.hit_points}/{character.hit_points} PF\n"
        f"{f'({(character.current_hit_points - character.hit_points)} Punti ferita temporanei)\n' if character.current_hit_points > character.hit_points else '\n'}"

    message_str = (f"Benvenuto nella gestione personaggio! v.{CHARACTER_CREATOR_VERSION}\n"
                   f"<b>Nome personaggio:</b> {character.name} L. {character.total_levels()}\n"
                   f"<b>Razza:</b> {character.race}\n"
                   f"<b>Genere:</b> {character.gender}\n"
                   f"<b>Classe:</b> {', '.join(f"{class_name} (Level {level})" for class_name, level in character.multi_class.classes.items())}\n"
                   f"<b>Punti ferita:</b> {health_str}"
                   f"<b>Classe armatura:</b> {character.ac}\n"
                   f"<b>Peso trasportato:</b> {character.encumbrance} Lb\n\n"
                   f"<b>Punti caratteristica</b>\n<code>{str(character.feature_points)}\n\n</code>"
                   f"<b>Slot incantesimo</b>\n{"\n".join([f"L{str(slot.level)}  {"🟥" * slot.used_slots}{"🟦" * (slot.total_slots - slot.used_slots)}" for _, slot in sorted(character.spell_slots.items())]) if character.spell_slots else "Non hai registrato ancora nessuno Slot incantesimo"}\n\n"
                   f"<b>Abilità passive attivate:</b>\n{'\n'.join(ability.name for ability in character.abilities if ability.activated) if any(ability.activated for ability in character.abilities) else 'Nessuna abilità attiva'}\n")

    keyboard = [
        [
            InlineKeyboardButton('⬇️ Level down', callback_data=LEVEL_DOWN_CALLBACK_DATA),
            InlineKeyboardButton('⬆️ Level up', callback_data=LEVEL_UP_CALLBACK_DATA)
        ],
        [
            InlineKeyboardButton('💔 Prendi danni', callback_data=DAMAGE_CALLBACK_DATA),
            InlineKeyboardButton('❤️‍🩹 Curati', callback_data=HEALING_CALLBACK_DATA)
        ],
        [
            InlineKeyboardButton('🧬 Gestisci punti ferita 💉', callback_data=HIT_POINTS_CALLBACK_DATA)
        ],
        [
            InlineKeyboardButton('🛡 Punti Armatura 🛡', callback_data=ARMOR_CLASS_CALLBACK_DATA)
        ],
        [
            InlineKeyboardButton('🧳 Borsa', callback_data=BAG_CALLBACK_DATA),
            InlineKeyboardButton('🗯 Azioni', callback_data=ABILITIES_CALLBACK_DATA),
            InlineKeyboardButton('📖 Spell', callback_data=SPELLS_CALLBACK_DATA)
        ],
        [InlineKeyboardButton('🔮 Gestisci slot incantesimo', callback_data=SPELLS_SLOT_CALLBACK_DATA)],
        [InlineKeyboardButton('🧮 Punti caratteristica', callback_data=FEATURE_POINTS_CALLBACK_DATA)],
        [InlineKeyboardButton('🪓🛡🪄 Gestisci multiclasse', callback_data=MULTICLASSING_CALLBACK_DATA)],
        [
            InlineKeyboardButton('🌙 Riposo lungo', callback_data=LONG_REST_WARNING_CALLBACK_DATA),
            InlineKeyboardButton('🍻 Riposo breve', callback_data=SHORT_REST_WARNING_CALLBACK_DATA)
        ],
        [InlineKeyboardButton('🎲 Lancia Dado', callback_data=ROLL_DICE_MENU_CALLBACK_DATA)],
        [
            InlineKeyboardButton('🗒 Note', callback_data=NOTES_CALLBACK_DATA),
            InlineKeyboardButton('🗺 Mappe', callback_data=MAPS_CALLBACK_DATA)
        ],
        [InlineKeyboardButton('⚙️ Impostazioni', callback_data=SETTINGS_CALLBACK_DATA)],
        [InlineKeyboardButton('🗑️ Elimina personaggio', callback_data=DELETE_CHARACTER_CALLBACK_DATA)]
    ]

    return message_str, InlineKeyboardMarkup(keyboard)


def extract_3_words(string: str) -> str:
    words = string.split()
    if len(words) > 3:
        return ' '.join(words[:3]) + "..."
    else:
        return ' '.join(words) + "..."
