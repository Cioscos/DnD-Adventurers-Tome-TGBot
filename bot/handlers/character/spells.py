"""Spell management handler.

Handles spell learning (quick: name -> level -> concentration?), detail view
with all D&D 5e properties, editing individual fields, concentration
tracking, concentration saving throws, and pin/unpin spells.
"""

from __future__ import annotations

import logging
import random

from sqlalchemy import delete, select
from telegram import Update
from telegram.ext import ContextTypes

from bot.db.engine import get_session
from bot.db.models import AbilityScore, Character, Spell, SpellSlot
from bot.handlers.character import (
    CHAR_CONC_SAVE,
    CHAR_MENU,
    CHAR_SPELL_EDIT,
    CHAR_SPELLS_MENU,
    CHAR_SPELL_LEARN,
)
from bot.keyboards.character import (
    build_cancel_keyboard,
    build_spell_detail_keyboard,
    build_spell_edit_field_keyboard,
    build_spell_level_picker_keyboard,
    build_spell_use_level_keyboard,
    build_spells_menu_keyboard,
)
from bot.utils.formatting import format_spell_detail, format_spells

logger = logging.getLogger(__name__)

_OP_KEY = "char_spell_pending"

# Editable spell fields: internal key -> (Italian label, prompt text)
SPELL_EDITABLE_FIELDS: dict[str, tuple[str, str]] = {
    "casting_time": ("Tempo di lancio", "⏱️ Inserisci il *tempo di lancio* \\(es\\. 1 azione, 1 minuto\\):"),
    "range_area": ("Gittata/Area", "📏 Inserisci la *gittata/area* \\(es\\. 30 piedi, Contatto\\):"),
    "components": ("Componenti", "🧩 Inserisci le *componenti* \\(es\\. V, S, M \\(un po\\' di zolfo\\)\\):"),
    "duration": ("Durata", "⏳ Inserisci la *durata* \\(es\\. Istantanea, 1 minuto\\):"),
    "attack_save": ("Attacco/TS", "🎯 Inserisci *attacco/tiro salvezza* \\(es\\. DEX save, Attacco a distanza\\):"),
    "description": ("Descrizione", "📝 Inserisci la *descrizione*:"),
    "higher_level": ("Livelli superiori", "📈 Inserisci la descrizione per *livelli superiori*:"),
}


# ---------------------------------------------------------------------------
# Spell list
# ---------------------------------------------------------------------------

async def show_spells_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int,
    page: int = 0, level_filter: int | None = None,
) -> int:
    """Show the spell list, respecting the character's spell_management setting.

    In *paginate_by_level* mode (default): flat paginated list ordered by level.
    In *select_level_directly* mode: level picker first; once a level is chosen
    the list is filtered to that level only.
    """
    async with get_session() as session:
        char = await session.get(Character, char_id)
        conc_id = char.concentrating_spell_id if char else None
        settings = char.settings or {} if char else {}
        result = await session.execute(
            select(Spell).where(Spell.character_id == char_id).order_by(Spell.level, Spell.name)
        )
        spells = list(result.scalars().all())

    spell_mgmt = settings.get("spell_management", "paginate_by_level")

    if spell_mgmt == "select_level_directly" and level_filter is None:
        return await show_spell_level_picker(update, context, char_id, spells)

    display_spells = (
        [s for s in spells if s.level == level_filter]
        if level_filter is not None
        else spells
    )

    keyboard = build_spells_menu_keyboard(char_id, display_spells, page, conc_id, level_filter)
    text = format_spells(display_spells, conc_id) if display_spells else "Nessun incantesimo conosciuto\\."
    await _edit_or_reply(update, text, keyboard)
    return CHAR_SPELLS_MENU


async def show_spell_level_picker(
    update: Update, context: ContextTypes.DEFAULT_TYPE,
    char_id: int, spells: list,
) -> int:
    """Show a level picker when spell_management == 'select_level_directly'."""
    available_levels = sorted({s.level for s in spells})
    text = "✨ *Scegli il livello degli incantesimi:*" if available_levels else "Nessun incantesimo conosciuto\\."
    keyboard = build_spell_level_picker_keyboard(char_id, available_levels)
    await _edit_or_reply(update, text, keyboard)
    return CHAR_SPELLS_MENU


# ---------------------------------------------------------------------------
# Spell detail
# ---------------------------------------------------------------------------

async def show_spell_detail(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    spell_id: int,
    back_page: int = 0,
    back_extra: str = "",
) -> int:
    """Show detailed spell view with all D&D 5e properties."""
    async with get_session() as session:
        spell = await session.get(Spell, spell_id)
        if spell is None or spell.character_id != char_id:
            return await show_spells_menu(update, context, char_id)
        char = await session.get(Character, char_id)
        is_concentrating = char.concentrating_spell_id == spell_id if char else False

    text = format_spell_detail(spell)
    keyboard = build_spell_detail_keyboard(
        char_id, spell, back_page, is_concentrating=is_concentrating,
        back_extra=back_extra,
    )
    await _edit_or_reply(update, text, keyboard)
    return CHAR_SPELLS_MENU


# ---------------------------------------------------------------------------
# Quick learn: name → level → concentration?
# ---------------------------------------------------------------------------

async def ask_spell_learn(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    """Ask user to type the spell name."""
    context.user_data[_OP_KEY] = {"char_id": char_id, "step": "name"}
    await _edit_or_reply(
        update,
        "✨ Inserisci il *nome dell'incantesimo* da imparare:",
        build_cancel_keyboard(char_id, "char_spells"),
    )
    return CHAR_SPELL_LEARN


async def handle_spell_learn_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Multi-step spell learning: name -> level -> save to DB.

    Concentration flag is set via inline keyboard callback (learn_conc sub).
    """
    if update.message is None:
        return CHAR_SPELL_LEARN

    pending = context.user_data.get(_OP_KEY, {})
    char_id: int = pending.get("char_id")
    step: str = pending.get("step", "name")
    text = update.message.text.strip()

    if step == "name":
        if not text:
            await update.message.reply_text("❌ Nome non valido\\.", parse_mode="MarkdownV2")
            return CHAR_SPELL_LEARN
        context.user_data[_OP_KEY]["spell_name"] = text
        context.user_data[_OP_KEY]["step"] = "level"
        await update.message.reply_text(
            "🔢 Inserisci il *livello* dell'incantesimo \\(0 per trucchetto, 1\\-9\\):",
            reply_markup=build_cancel_keyboard(char_id, "char_spells"),
            parse_mode="MarkdownV2",
        )
        return CHAR_SPELL_LEARN

    if step == "level":
        try:
            level = int(text)
            if not 0 <= level <= 9:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                "❌ Livello non valido \\(0\\-9\\)\\.", parse_mode="MarkdownV2"
            )
            return CHAR_SPELL_LEARN
        context.user_data[_OP_KEY]["spell_level"] = level
        context.user_data[_OP_KEY]["step"] = "conc"
        # Show concentration yes/no keyboard
        from bot.keyboards.character import build_yes_no_keyboard
        keyboard = build_yes_no_keyboard(
            char_id, yes_sub="learn_conc_yes", no_sub="learn_conc_no",
            action="char_spells",
        )
        await update.message.reply_text(
            "🔮 L'incantesimo richiede *concentrazione*?",
            reply_markup=keyboard,
            parse_mode="MarkdownV2",
        )
        return CHAR_SPELL_LEARN

    return CHAR_SPELL_LEARN


async def finalize_spell_learn(
    update: Update, context: ContextTypes.DEFAULT_TYPE, is_concentration: bool,
) -> int:
    """Save the new spell after the concentration choice."""
    pending = context.user_data.pop(_OP_KEY, {})
    char_id: int = pending.get("char_id")
    spell_name: str = pending.get("spell_name", "???")
    spell_level: int = pending.get("spell_level", 0)

    async with get_session() as session:
        session.add(Spell(
            character_id=char_id,
            name=spell_name,
            level=spell_level,
            is_concentration=is_concentration,
        ))

    if update.callback_query:
        await update.callback_query.answer(f"Incantesimo {spell_name} imparato!")
    return await show_spells_menu(update, context, char_id)


# ---------------------------------------------------------------------------
# Forget spell
# ---------------------------------------------------------------------------

async def forget_spell(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    spell_id: int,
) -> int:
    """Remove a spell from the character's known spells."""
    async with get_session() as session:
        # Clear concentration if forgetting the concentrated spell
        char = await session.get(Character, char_id)
        if char and char.concentrating_spell_id == spell_id:
            char.concentrating_spell_id = None
        await session.execute(
            delete(Spell).where(Spell.id == spell_id, Spell.character_id == char_id)
        )
    if update.callback_query:
        await update.callback_query.answer("Incantesimo dimenticato.")
    return await show_spells_menu(update, context, char_id)


# ---------------------------------------------------------------------------
# Use spell (slot picker + auto-concentration)
# ---------------------------------------------------------------------------

async def show_use_spell_level_picker(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    spell_id: int,
) -> int:
    """Show available spell slots to cast the spell with."""
    async with get_session() as session:
        spell = await session.get(Spell, spell_id)
        if spell is None:
            return await show_spells_menu(update, context, char_id)

        # Cantrips don't need slots
        if spell.level == 0:
            if spell.is_concentration:
                return await _activate_concentration(update, context, char_id, spell_id)
            if update.callback_query:
                await update.callback_query.answer("Trucchetto lanciato!")
            return await show_spells_menu(update, context, char_id)

        result = await session.execute(
            select(SpellSlot).where(
                SpellSlot.character_id == char_id,
                SpellSlot.level >= spell.level,
                SpellSlot.total > 0,
            ).order_by(SpellSlot.level)
        )
        slots = [s for s in result.scalars() if s.available > 0]

    if not slots:
        await _edit_or_reply(update, "❌ Nessuno slot disponibile per questo livello\\.")
        return CHAR_SPELLS_MENU

    keyboard = build_spell_use_level_keyboard(char_id, spell_id, slots)
    await _edit_or_reply(update, "🎯 Scegli il livello dello slot da usare:", keyboard)
    return CHAR_SPELLS_MENU


async def use_spell_at_level(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    spell_id: int,
    slot_level: int,
) -> int:
    """Use a spell slot and auto-activate concentration if applicable."""
    async with get_session() as session:
        result = await session.execute(
            select(SpellSlot).where(
                SpellSlot.character_id == char_id,
                SpellSlot.level == slot_level,
            )
        )
        slot = result.scalar_one_or_none()
        if slot is None or slot.available == 0:
            await _edit_or_reply(update, "❌ Slot non disponibile\\.")
            return await show_spells_menu(update, context, char_id)
        slot.use_slot()

        # Auto-activate concentration
        spell = await session.get(Spell, spell_id)
        if spell and spell.is_concentration:
            char = await session.get(Character, char_id)
            if char:
                char.concentrating_spell_id = spell_id

    if update.callback_query:
        msg = f"Slot liv.{slot_level} usato!"
        if spell and spell.is_concentration:
            msg += f" 🔮 Concentrazione su {spell.name}"
        await update.callback_query.answer(msg)
    return await show_spells_menu(update, context, char_id)


# ---------------------------------------------------------------------------
# Concentration management
# ---------------------------------------------------------------------------

async def _activate_concentration(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    spell_id: int,
) -> int:
    """Activate concentration on a spell (internal helper)."""
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char:
            char.concentrating_spell_id = spell_id
    if update.callback_query:
        await update.callback_query.answer("🔮 Concentrazione attivata!")
    return await show_spells_menu(update, context, char_id)


async def activate_concentration(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    spell_id: int,
) -> int:
    """Activate concentration on a spell from detail view."""
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if not char:
            return await show_spells_menu(update, context, char_id)

        old_spell_id = char.concentrating_spell_id
        if old_spell_id and old_spell_id != spell_id:
            old_spell = await session.get(Spell, old_spell_id)
            old_name = old_spell.name if old_spell else "?"
            # Switch concentration
            char.concentrating_spell_id = spell_id
            new_spell = await session.get(Spell, spell_id)
            new_name = new_spell.name if new_spell else "?"
            if update.callback_query:
                await update.callback_query.answer(
                    f"🔮 Concentrazione spostata da {old_name} a {new_name}"
                )
        else:
            char.concentrating_spell_id = spell_id
            if update.callback_query:
                await update.callback_query.answer("🔮 Concentrazione attivata!")

    return await show_spell_detail(update, context, char_id, spell_id)


async def drop_concentration(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
) -> int:
    """Drop active concentration."""
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char:
            char.concentrating_spell_id = None
    if update.callback_query:
        await update.callback_query.answer("❌ Concentrazione interrotta.")
    return await show_spells_menu(update, context, char_id)


# ---------------------------------------------------------------------------
# Concentration saving throw
# ---------------------------------------------------------------------------

async def ask_concentration_save_damage(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
) -> int:
    """Ask the user for the damage taken to compute the concentration DC."""
    context.user_data[_OP_KEY] = {"char_id": char_id, "step": "conc_save"}
    await _edit_or_reply(
        update,
        "🎲 Inserisci il *danno subito* per il tiro salvezza concentrazione:",
        build_cancel_keyboard(char_id, "char_spells"),
    )
    return CHAR_CONC_SAVE


async def handle_concentration_save_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Roll a concentration saving throw: d20 + CON mod vs DC = max(10, damage/2)."""
    if update.message is None:
        return CHAR_CONC_SAVE

    pending = context.user_data.pop(_OP_KEY, {})
    char_id: int = pending.get("char_id")

    try:
        damage = int(update.message.text.strip())
        if damage < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "❌ Valore non valido\\. Inserisci un numero intero positivo\\.",
            parse_mode="MarkdownV2",
        )
        context.user_data[_OP_KEY] = pending
        return CHAR_CONC_SAVE

    dc = max(10, damage // 2)
    roll = random.randint(1, 20)

    async with get_session() as session:
        char = await session.get(Character, char_id)
        if not char:
            return CHAR_MENU

        # Get CON modifier
        result = await session.execute(
            select(AbilityScore).where(
                AbilityScore.character_id == char_id,
                AbilityScore.name == "constitution",
            )
        )
        con_score = result.scalar_one_or_none()
        con_mod = con_score.modifier if con_score else 0

        total = roll + con_mod
        success = total >= dc

        # Natural 1 always fails, natural 20 always succeeds
        if roll == 1:
            success = False
        elif roll == 20:
            success = True

        if not success and char.concentrating_spell_id:
            conc_spell = await session.get(Spell, char.concentrating_spell_id)
            spell_name = conc_spell.name if conc_spell else "?"
            char.concentrating_spell_id = None
        else:
            spell_name = None

    mod_str = f"\\+{con_mod}" if con_mod >= 0 else str(con_mod)
    nat_tag = ""
    if roll == 20:
        nat_tag = " 🌟 *NAT 20\\!*"
    elif roll == 1:
        nat_tag = " 💀 *NAT 1\\!*"

    if success:
        result_text = "✅ *Successo\\!* Concentrazione mantenuta\\."
    else:
        lost_text = f" su *{_esc(spell_name)}*" if spell_name else ""
        result_text = f"❌ *Fallimento\\!* Concentrazione persa{lost_text}\\."

    text = (
        f"🎲 *Tiro Salvezza Concentrazione*\n\n"
        f"Danno subito: *{damage}*\n"
        f"CD: *{dc}* \\(max\\(10, {damage}÷2\\)\\)\n"
        f"Tiro: 🎲 *{roll}* {mod_str} \\= *{total}*{nat_tag}\n\n"
        f"{result_text}"
    )

    await update.message.reply_text(text, parse_mode="MarkdownV2")

    from bot.handlers.character.menu import show_character_menu
    return await show_character_menu(update, context, char_id=char_id)


# ---------------------------------------------------------------------------
# Spell field editing
# ---------------------------------------------------------------------------

async def ask_spell_edit_field(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    spell_id: int,
    field: str,
) -> int:
    """Prompt the user to enter a new value for a spell field."""
    if field == "is_concentration":
        return await _toggle_spell_bool(update, context, char_id, spell_id, "is_concentration")
    if field == "is_ritual":
        return await _toggle_spell_bool(update, context, char_id, spell_id, "is_ritual")
    if field == "level":
        context.user_data[_OP_KEY] = {
            "char_id": char_id, "spell_id": spell_id, "field": field, "step": "edit",
        }
        await _edit_or_reply(
            update,
            "🔢 Inserisci il nuovo *livello* \\(0\\-9\\):",
            build_cancel_keyboard(char_id, "char_spells"),
        )
        return CHAR_SPELL_EDIT

    field_info = SPELL_EDITABLE_FIELDS.get(field)
    if not field_info:
        return await show_spell_detail(update, context, char_id, spell_id)

    _, prompt = field_info
    context.user_data[_OP_KEY] = {
        "char_id": char_id, "spell_id": spell_id, "field": field, "step": "edit",
    }
    await _edit_or_reply(update, prompt, build_cancel_keyboard(char_id, "char_spells"))
    return CHAR_SPELL_EDIT


async def handle_spell_edit_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Process text input for spell field editing."""
    if update.message is None:
        return CHAR_SPELL_EDIT

    pending = context.user_data.pop(_OP_KEY, {})
    char_id: int = pending.get("char_id")
    spell_id: int = pending.get("spell_id")
    field: str = pending.get("field")
    text = update.message.text.strip()

    if field == "level":
        try:
            level = int(text)
            if not 0 <= level <= 9:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                "❌ Livello non valido \\(0\\-9\\)\\.", parse_mode="MarkdownV2"
            )
            context.user_data[_OP_KEY] = pending
            return CHAR_SPELL_EDIT
        async with get_session() as session:
            spell = await session.get(Spell, spell_id)
            if spell and spell.character_id == char_id:
                spell.level = level
        await update.message.reply_text("✅ Livello aggiornato\\!", parse_mode="MarkdownV2")
        return await show_spell_detail(update, context, char_id, spell_id)

    # Text fields — dash or empty means clear
    value = None if text in ("-", "") else text
    async with get_session() as session:
        spell = await session.get(Spell, spell_id)
        if spell and spell.character_id == char_id and hasattr(spell, field):
            setattr(spell, field, value)

    await update.message.reply_text("✅ Aggiornato\\!", parse_mode="MarkdownV2")
    return await show_spell_detail(update, context, char_id, spell_id)


async def _toggle_spell_bool(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    spell_id: int,
    field: str,
) -> int:
    """Toggle a boolean field on a spell."""
    async with get_session() as session:
        spell = await session.get(Spell, spell_id)
        if spell and spell.character_id == char_id:
            current = getattr(spell, field, False)
            setattr(spell, field, not current)
            # If turning off concentration and this is the active concentration spell, drop it
            if field == "is_concentration" and not (not current) and spell.character:
                char = await session.get(Character, char_id)
                if char and char.concentrating_spell_id == spell_id:
                    char.concentrating_spell_id = None

    if update.callback_query:
        await update.callback_query.answer("Aggiornato!")
    return await show_spell_detail(update, context, char_id, spell_id)


# ---------------------------------------------------------------------------
# Pin / Unpin
# ---------------------------------------------------------------------------

async def toggle_pin_spell(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    spell_id: int,
) -> int:
    """Toggle the pinned status of a spell."""
    async with get_session() as session:
        spell = await session.get(Spell, spell_id)
        if spell and spell.character_id == char_id:
            spell.is_pinned = not spell.is_pinned
    if update.callback_query:
        await update.callback_query.answer(
            "📌 Fissato!" if spell and spell.is_pinned else "📌 Rimosso!"
        )
    return await show_spell_detail(update, context, char_id, spell_id)


# ---------------------------------------------------------------------------
# Show edit menu (list of editable fields)
# ---------------------------------------------------------------------------

async def show_spell_edit_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    spell_id: int,
) -> int:
    """Show the keyboard with editable spell fields."""
    keyboard = build_spell_edit_field_keyboard(char_id, spell_id)
    await _edit_or_reply(update, "✏️ *Scegli il campo da modificare:*", keyboard)
    return CHAR_SPELLS_MENU


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _edit_or_reply(update: Update, text: str, keyboard=None) -> None:
    kwargs = dict(text=text, parse_mode="MarkdownV2")
    if keyboard:
        kwargs["reply_markup"] = keyboard
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(**kwargs)
    elif update.message:
        await update.message.reply_text(**kwargs)


def _esc(text: str) -> str:
    special = r"\_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in str(text))
