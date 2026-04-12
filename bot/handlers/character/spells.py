"""Spell management handler.

Handles spell learning (quick: name -> level -> concentration?), detail view
with all D&D 5e properties, editing individual fields, concentration
tracking, concentration saving throws, and pin/unpin spells.
"""

from __future__ import annotations

import logging
import random
import re

from rapidfuzz import fuzz, process as rfuzz_process
from sqlalchemy import delete, select
from telegram import Update
from telegram.ext import ContextTypes

from bot.db.engine import get_session
from bot.db.models import AbilityScore, Character, Spell, SpellSlot
from bot.handlers.character import (
    CHAR_CONC_SAVE,
    CHAR_MENU,
    CHAR_SPELL_EDIT,
    CHAR_SPELL_SEARCH,
    CHAR_SPELLS_MENU,
    CHAR_SPELL_LEARN,
)
from bot.keyboards.character import (
    build_cancel_keyboard,
    build_spell_detail_keyboard,
    build_spell_edit_field_keyboard,
    build_spell_level_picker_keyboard,
    build_spell_search_results_keyboard,
    build_spell_use_level_keyboard,
    build_spells_menu_keyboard,
)
from bot.utils.formatting import format_spell_detail, format_spells
from bot.utils.i18n import get_lang, translator

logger = logging.getLogger(__name__)

_OP_KEY = "char_spell_pending"
_SEARCH_KEY = "char_spell_search_pending"

# Editable spell fields: internal key -> (Italian label, prompt text)
SPELL_EDITABLE_FIELDS: dict[str, tuple[str, str]] = {
    "casting_time": ("Tempo di lancio", "⏱️ Inserisci il *tempo di lancio* \\(es\\. 1 azione, 1 minuto\\):"),
    "range_area": ("Gittata/Area", "📏 Inserisci la *gittata/area* \\(es\\. 30 piedi, Contatto\\):"),
    "components": ("Componenti", "🧩 Inserisci le *componenti* \\(es\\. V, S, M \\(un po\\' di zolfo\\)\\):"),
    "duration": ("Durata", "⏳ Inserisci la *durata* \\(es\\. Istantanea, 1 minuto\\):"),
    "attack_save": ("Attacco/TS", "🎯 Inserisci *attacco/tiro salvezza* \\(es\\. DEX save, Attacco a distanza\\):"),
    "damage_dice": ("Dado danno", "🎲 Inserisci il *dado danno* \\(es\\. 3d10, 2d8\\+3\\):"),
    "damage_type": ("Tipo danno", "💥 Inserisci il *tipo di danno* \\(es\\. fuoco, lampo\\):"),
    "description": ("Descrizione", "📝 Inserisci la *descrizione*:"),
    "higher_level": ("Livelli superiori", "📈 Inserisci la descrizione per *livelli superiori*:"),
}

# Maps editable spell field → i18n prompt key
_SPELL_FIELD_PROMPT_KEYS: dict[str, str] = {
    "casting_time": "character.spells.prompt_edit_casting_time",
    "range_area": "character.spells.prompt_edit_range",
    "components": "character.spells.prompt_edit_components",
    "duration": "character.spells.prompt_edit_duration",
    "attack_save": "character.spells.prompt_edit_attack_save",
    "damage_dice": "character.spells.prompt_edit_damage_dice",
    "damage_type": "character.spells.prompt_edit_damage_type",
    "description": "character.spells.prompt_edit_description",
    "higher_level": "character.spells.prompt_edit_higher_level",
}



# ---------------------------------------------------------------------------
# Spell search (fuzzy)
# ---------------------------------------------------------------------------

_FUZZY_THRESHOLD = 50   # minimum WRatio score to include a result
_FUZZY_MAX = 20         # maximum results to show


async def ask_spell_search(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int,
) -> int:
    """Ask the user to type a search query for fuzzy spell name matching."""
    lang = get_lang(update)
    context.user_data[_SEARCH_KEY] = {"char_id": char_id}
    await _edit_or_reply(
        update,
        translator.t("character.spells.prompt_search", lang=lang),
        build_cancel_keyboard(char_id, "char_spells", lang=lang),
    )
    return CHAR_SPELL_SEARCH


async def handle_spell_search_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Process the typed search query and display fuzzy-matched results."""
    if update.message is None:
        return CHAR_SPELL_SEARCH

    lang = get_lang(update)
    pending = context.user_data.get(_SEARCH_KEY, {})
    char_id: int = pending.get("char_id", 0)
    query = update.message.text.strip()

    if not query:
        await update.message.reply_text(
            translator.t("character.spells.search_empty", lang=lang), parse_mode="MarkdownV2"
        )
        return CHAR_SPELL_SEARCH

    context.user_data[_SEARCH_KEY]["query"] = query
    return await show_spell_search_results(update, context, char_id, query=query)


async def show_spell_search_results(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    query: str | None = None,
) -> int:
    """Display fuzzy-matched spells for the stored (or provided) query.

    When *query* is None the query is read from ``context.user_data[_SEARCH_KEY]``.
    This lets the function be called both right after text input and when
    navigating back from a spell detail view.
    """
    lang = get_lang(update)
    if query is None:
        pending = context.user_data.get(_SEARCH_KEY, {})
        query = pending.get("query", "")

    async with get_session() as session:
        char = await session.get(Character, char_id)
        conc_id = char.concentrating_spell_id if char else None
        result = await session.execute(
            select(Spell).where(Spell.character_id == char_id).order_by(Spell.level, Spell.name)
        )
        spells = list(result.scalars().all())

    matched: list[Spell] = []
    if query and spells:
        spell_names = [s.name for s in spells]
        hits = rfuzz_process.extract(
            query,
            spell_names,
            scorer=fuzz.WRatio,
            score_cutoff=_FUZZY_THRESHOLD,
            limit=_FUZZY_MAX,
        )
        # Map name back to Spell preserving result order (best match first)
        name_to_spell = {s.name: s for s in spells}
        matched = [name_to_spell[name] for name, _score, _idx in hits if name in name_to_spell]

    escaped_query = _esc(query)
    if matched:
        text = translator.t("character.spells.search_results", lang=lang, query=escaped_query, count=_esc(str(len(matched))))
        keyboard = build_spell_search_results_keyboard(char_id, matched, conc_id, lang=lang)
    else:
        text = translator.t("character.spells.search_no_results", lang=lang, query=escaped_query)
        keyboard = build_spell_search_results_keyboard(char_id, [], conc_id, lang=lang)

    await _edit_or_reply(update, text, keyboard)
    return CHAR_SPELLS_MENU


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
    lang = get_lang(update)
    async with get_session() as session:
        char = await session.get(Character, char_id)
        conc_id = char.concentrating_spell_id if char else None
        settings = char.settings or {} if char else {}
        result = await session.execute(
            select(Spell).where(Spell.character_id == char_id).order_by(Spell.level, Spell.name)
        )
        spells = list(result.scalars().all())

    spell_mgmt = settings.get("spell_management", "paginate_by_level")

    if spell_mgmt == "paginate_by_level" and level_filter is None:
        return await show_spell_level_picker(update, context, char_id, spells)

    display_spells = (
        [s for s in spells if s.level == level_filter]
        if level_filter is not None
        else spells
    )

    keyboard = build_spells_menu_keyboard(char_id, display_spells, page, conc_id, level_filter, lang=lang)
    text = format_spells(display_spells, conc_id, lang=lang) if display_spells else translator.t("character.spells.no_spells", lang=lang)
    await _edit_or_reply(update, text, keyboard)
    return CHAR_SPELLS_MENU


async def show_spell_level_picker(
    update: Update, context: ContextTypes.DEFAULT_TYPE,
    char_id: int, spells: list,
) -> int:
    """Show a level picker when spell_management == 'select_level_directly'."""
    lang = get_lang(update)
    available_levels = sorted({s.level for s in spells})
    text = translator.t("character.spells.level_picker_title", lang=lang) if available_levels else translator.t("character.spells.no_spells", lang=lang)
    keyboard = build_spell_level_picker_keyboard(char_id, available_levels, lang=lang)
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
    lang = get_lang(update)
    async with get_session() as session:
        spell = await session.get(Spell, spell_id)
        if spell is None or spell.character_id != char_id:
            return await show_spells_menu(update, context, char_id)
        char = await session.get(Character, char_id)
        is_concentrating = char.concentrating_spell_id == spell_id if char else False

    text = format_spell_detail(spell, lang=lang)
    keyboard = build_spell_detail_keyboard(
        char_id, spell, back_page, is_concentrating=is_concentrating,
        back_extra=back_extra, lang=lang,
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
    lang = get_lang(update)
    context.user_data[_OP_KEY] = {"char_id": char_id, "step": "name"}
    await _edit_or_reply(
        update,
        translator.t("character.spells.prompt_learn_name", lang=lang),
        build_cancel_keyboard(char_id, "char_spells", lang=lang),
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

    lang = get_lang(update)
    pending = context.user_data.get(_OP_KEY, {})
    char_id: int = pending.get("char_id")
    step: str = pending.get("step", "name")
    text = update.message.text.strip()

    if step == "name":
        if not text:
            await update.message.reply_text(translator.t("character.spells.learn_name_invalid", lang=lang), parse_mode="MarkdownV2")
            return CHAR_SPELL_LEARN
        context.user_data[_OP_KEY]["spell_name"] = text
        context.user_data[_OP_KEY]["step"] = "level"
        await update.message.reply_text(
            translator.t("character.spells.prompt_learn_level", lang=lang),
            reply_markup=build_cancel_keyboard(char_id, "char_spells", lang=lang),
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
                translator.t("character.spells.learn_level_invalid", lang=lang), parse_mode="MarkdownV2"
            )
            return CHAR_SPELL_LEARN
        context.user_data[_OP_KEY]["spell_level"] = level
        context.user_data[_OP_KEY]["step"] = "conc"
        # Show concentration yes/no keyboard
        from bot.keyboards.character import build_yes_no_keyboard
        keyboard = build_yes_no_keyboard(
            char_id, yes_sub="learn_conc_yes", no_sub="learn_conc_no",
            action="char_spells", lang=lang,
        )
        await update.message.reply_text(
            translator.t("character.spells.prompt_learn_concentration", lang=lang),
            reply_markup=keyboard,
            parse_mode="MarkdownV2",
        )
        return CHAR_SPELL_LEARN

    return CHAR_SPELL_LEARN


async def finalize_spell_learn(
    update: Update, context: ContextTypes.DEFAULT_TYPE, is_concentration: bool,
) -> int:
    """Save the new spell after the concentration choice."""
    lang = get_lang(update)
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

    import asyncio as _asyncio
    level_label = "Trucchetto" if spell_level == 0 else f"Liv.{spell_level}"
    conc_label = " (conc.)" if is_concentration else ""
    _asyncio.create_task(_log(char_id, "spell_change", f"Imparato: {spell_name} [{level_label}{conc_label}]"))
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
        spell = await session.get(Spell, spell_id)
        spell_name = spell.name if spell else "?"
        await session.execute(
            delete(Spell).where(Spell.id == spell_id, Spell.character_id == char_id)
        )

    import asyncio as _asyncio
    _asyncio.create_task(_log(char_id, "spell_change", f"Dimenticato: {spell_name}"))
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
    lang = get_lang(update)
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
            return await show_spell_detail(update, context, char_id, spell_id)

        result = await session.execute(
            select(SpellSlot).where(
                SpellSlot.character_id == char_id,
                SpellSlot.level >= spell.level,
                SpellSlot.total > 0,
            ).order_by(SpellSlot.level)
        )
        slots = [s for s in result.scalars() if s.available > 0]

    if not slots:
        if update.callback_query:
            await update.callback_query.answer(
                translator.t("character.spells.no_slots", lang=lang), show_alert=True
            )
        return await show_spell_detail(update, context, char_id, spell_id)

    keyboard = build_spell_use_level_keyboard(char_id, spell_id, slots, lang=lang)
    await _edit_or_reply(update, translator.t("character.spells.slot_picker_title", lang=lang), keyboard)
    return CHAR_SPELLS_MENU


async def use_spell_at_level(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    spell_id: int,
    slot_level: int,
) -> int:
    """Use a spell slot and auto-activate concentration if applicable."""
    lang = get_lang(update)
    async with get_session() as session:
        result = await session.execute(
            select(SpellSlot).where(
                SpellSlot.character_id == char_id,
                SpellSlot.level == slot_level,
            )
        )
        slot = result.scalar_one_or_none()
        if slot is None or slot.available == 0:
            if update.callback_query:
                await update.callback_query.answer(
                    translator.t("character.spells.no_slots", lang=lang), show_alert=True
                )
            return await show_spell_detail(update, context, char_id, spell_id)
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

    # Track the cast level for potential damage roll at higher levels
    context.user_data[f"spell_{spell_id}_cast_level"] = slot_level

    import asyncio as _asyncio
    spell_name = spell.name if spell else "?"
    _asyncio.create_task(_log(char_id, "spell_change", f"Usato: {spell_name} (Slot Liv.{slot_level})"))
    return await show_spell_detail(update, context, char_id, spell_id)


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
    return await show_spell_detail(update, context, char_id, spell_id)


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
    spell_id: int,
) -> int:
    """Drop active concentration and return to the spell detail."""
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char:
            char.concentrating_spell_id = None
    if update.callback_query:
        await update.callback_query.answer("❌ Concentrazione interrotta.")
    return await show_spell_detail(update, context, char_id, spell_id)


# ---------------------------------------------------------------------------
# Concentration saving throw
# ---------------------------------------------------------------------------

async def ask_concentration_save_damage(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
) -> int:
    """Ask the user for the damage taken to compute the concentration DC."""
    lang = get_lang(update)
    context.user_data[_OP_KEY] = {"char_id": char_id, "step": "conc_save"}
    await _edit_or_reply(
        update,
        translator.t("character.spells.prompt_conc_damage", lang=lang),
        build_cancel_keyboard(char_id, "char_spells", lang=lang),
    )
    return CHAR_CONC_SAVE


async def handle_concentration_save_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Roll a concentration saving throw: d20 + CON mod vs DC = max(10, damage/2)."""
    if update.message is None:
        return CHAR_CONC_SAVE

    lang = get_lang(update)
    pending = context.user_data.pop(_OP_KEY, {})
    char_id: int = pending.get("char_id")

    try:
        damage = int(update.message.text.strip())
        if damage < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            translator.t("character.spells.conc_damage_invalid", lang=lang),
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
        nat_tag = translator.t("character.spells.conc_save_nat20", lang=lang)
    elif roll == 1:
        nat_tag = translator.t("character.spells.conc_save_nat1", lang=lang)

    if success:
        result_text = translator.t("character.spells.conc_save_success", lang=lang)
    else:
        lost_text = f" su *{_esc(spell_name)}*" if spell_name else ""
        result_text = translator.t("character.spells.conc_save_failure", lang=lang) + lost_text + "\\."

    text = (
        translator.t("character.spells.conc_save_title", lang=lang) + "\n\n"
        + translator.t("character.spells.conc_save_dc", lang=lang, dc=dc, damage=damage) + "\n"
        + translator.t("character.spells.conc_save_roll", lang=lang, roll=roll, mod_str=mod_str, total=total) + nat_tag + "\n\n"
        + result_text
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
    lang = get_lang(update)
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
            translator.t("character.spells.prompt_edit_level", lang=lang),
            build_cancel_keyboard(char_id, "char_spells", lang=lang),
        )
        return CHAR_SPELL_EDIT

    prompt_key = _SPELL_FIELD_PROMPT_KEYS.get(field)
    if not prompt_key:
        return await show_spell_detail(update, context, char_id, spell_id)

    prompt = translator.t(prompt_key, lang=lang)
    context.user_data[_OP_KEY] = {
        "char_id": char_id, "spell_id": spell_id, "field": field, "step": "edit",
    }
    await _edit_or_reply(update, prompt, build_cancel_keyboard(char_id, "char_spells", lang=lang))
    return CHAR_SPELL_EDIT


async def handle_spell_edit_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Process text input for spell field editing."""
    if update.message is None:
        return CHAR_SPELL_EDIT

    lang = get_lang(update)
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
                translator.t("character.spells.edit_level_invalid", lang=lang), parse_mode="MarkdownV2"
            )
            context.user_data[_OP_KEY] = pending
            return CHAR_SPELL_EDIT
        async with get_session() as session:
            spell = await session.get(Spell, spell_id)
            if spell and spell.character_id == char_id:
                spell.level = level
        await update.message.reply_text(translator.t("character.spells.edit_updated", lang=lang), parse_mode="MarkdownV2")
        return await show_spell_edit_menu(update, context, char_id, spell_id)

    # Text fields — dash or empty means clear
    value = None if text in ("-", "") else text
    async with get_session() as session:
        spell = await session.get(Spell, spell_id)
        if spell and spell.character_id == char_id and hasattr(spell, field):
            setattr(spell, field, value)

    await update.message.reply_text(translator.t("character.spells.edit_updated", lang=lang), parse_mode="MarkdownV2")
    return await show_spell_edit_menu(update, context, char_id, spell_id)


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
    return await show_spell_edit_menu(update, context, char_id, spell_id)


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
    lang = get_lang(update)
    keyboard = build_spell_edit_field_keyboard(char_id, spell_id, lang=lang)
    await _edit_or_reply(update, translator.t("character.spells.edit_menu_title", lang=lang), keyboard)
    return CHAR_SPELLS_MENU


# ---------------------------------------------------------------------------
# Spell damage roll
# ---------------------------------------------------------------------------

_DICE_RE = re.compile(r"^(\d+)d(\d+)([+-]\d+)?$", re.IGNORECASE)
# Detects patterns like "1d10 for each slot level above 3rd" in higher_level text
_HIGHER_LEVEL_RE = re.compile(
    r"(\d+)d(\d+)\s+(?:for each|per each|for every|per ogni)\s+(?:slot\s+)?level",
    re.IGNORECASE,
)


async def roll_spell_damage(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    spell_id: int,
) -> int:
    """Roll damage dice for a spell and send the result as a new message."""
    lang = get_lang(update)
    async with get_session() as session:
        spell = await session.get(Spell, spell_id)
        if spell is None or not spell.damage_dice:
            if update.callback_query:
                await update.callback_query.answer("Nessun dado danno configurato.")
            return CHAR_SPELLS_MENU

        spell_name = spell.name
        damage_dice_str = spell.damage_dice.strip()
        damage_type = spell.damage_type or ""
        spell_level = spell.level
        higher_level_text = spell.higher_level or ""

    m = _DICE_RE.match(damage_dice_str)
    if not m:
        if update.callback_query:
            await update.callback_query.answer("Formato dado non valido.")
        return CHAR_SPELLS_MENU

    num_dice = int(m.group(1))
    die_sides = int(m.group(2))
    flat_bonus = int(m.group(3)) if m.group(3) else 0

    base_rolls = [random.randint(1, die_sides) for _ in range(num_dice)]
    total = sum(base_rolls) + flat_bonus

    # Check for higher-level bonus dice (detect pattern in higher_level text)
    cast_level: int | None = context.user_data.get(f"spell_{spell_id}_cast_level")
    bonus_rolls: list[int] = []
    bonus_dice_str = ""
    if cast_level and cast_level > spell_level and higher_level_text:
        hl_match = _HIGHER_LEVEL_RE.search(higher_level_text)
        if hl_match:
            hl_num = int(hl_match.group(1))
            hl_sides = int(hl_match.group(2))
            extra_levels = cast_level - spell_level
            bonus_rolls = [random.randint(1, hl_sides) for _ in range(hl_num * extra_levels)]
            total += sum(bonus_rolls)
            bonus_dice_str = f"{hl_num * extra_levels}d{hl_sides}"

    # Build result text
    rolls_str = _esc(", ".join(str(r) for r in base_rolls))
    flat_str = f" \\+{flat_bonus}" if flat_bonus > 0 else (f" \\-{abs(flat_bonus)}" if flat_bonus < 0 else "")
    type_str = f" \\({_esc(damage_type)}\\)" if damage_type else ""
    dice_notation = _esc(damage_dice_str)

    higher_str = ""
    if bonus_rolls:
        bonus_rolls_str = _esc(", ".join(str(r) for r in bonus_rolls))
        higher_str = translator.t(
            "character.spells.damage_higher_level",
            lang=lang,
            extra=_esc(bonus_dice_str),
            bonus_rolls=bonus_rolls_str,
        )

    text = translator.t(
        "character.spells.damage_roll_result",
        lang=lang,
        name=_esc(spell_name),
        dice=dice_notation,
        rolls=rolls_str + flat_str,
        total=total,
        type=type_str,
        higher=higher_str,
    )

    if update.callback_query:
        await update.callback_query.answer(
            f"🎲 {damage_dice_str} = {total}{(' ' + damage_type) if damage_type else ''}"
        )
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            parse_mode="MarkdownV2",
        )
    return CHAR_SPELLS_MENU


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _log(char_id: int, event_type: str, description: str) -> None:
    """Fire-and-forget wrapper for history logging."""
    try:
        from bot.db.history import log_history_event
        await log_history_event(char_id, event_type, description)
    except Exception as exc:
        logger.warning("History log failed for char %s: %s", char_id, exc)


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
