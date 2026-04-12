"""Identity handler — race, gender, speed, background, alignment, personality, languages,
proficiencies, and damage modifier editing for a character."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.db.engine import get_session
from bot.db.models import Character
from bot.handlers.character import (
    CHAR_BACKGROUND_INPUT,
    CHAR_GENDER_INPUT,
    CHAR_LANGUAGE_ADD,
    CHAR_MENU,
    CHAR_NAME_INPUT,
    CHAR_PERSONALITY_INPUT,
    CHAR_PROFICIENCY_ADD,
    CHAR_RACE_INPUT,
    CHAR_SPEED_INPUT,
)
from bot.keyboards.character import (
    build_cancel_keyboard,
    build_identity_damage_modifiers_keyboard,
    build_identity_keyboard,
    build_identity_list_keyboard,
    build_identity_personality_keyboard,
)
from bot.utils.formatting import format_identity
from bot.utils.i18n import get_lang, translator

logger = logging.getLogger(__name__)

_OP_KEY = "char_identity_pending"


async def show_identity_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
) -> int:
    lang = get_lang(update)
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU

    text = format_identity(char, lang=lang)
    keyboard = build_identity_keyboard(char_id, lang=lang)
    await _edit_or_reply(update, text, keyboard)
    return CHAR_MENU


# ---------------------------------------------------------------------------
# Rename character
# ---------------------------------------------------------------------------

async def ask_rename_character(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int,
) -> int:
    lang = get_lang(update)
    context.user_data[_OP_KEY] = {"char_id": char_id, "field": "name"}
    await _edit_or_reply(
        update,
        translator.t("character.identity.prompt_rename", lang=lang),
        build_cancel_keyboard(char_id, "char_identity", lang=lang),
    )
    return CHAR_NAME_INPUT


async def handle_rename_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return CHAR_NAME_INPUT
    lang = get_lang(update)
    pending = context.user_data.pop(_OP_KEY, None)
    if pending is None:
        return CHAR_MENU
    char_id: int = pending["char_id"]
    name = update.message.text.strip()
    if not 1 <= len(name) <= 100:
        await update.message.reply_text(
            translator.t("character.identity.rename_too_long", lang=lang),
            parse_mode="MarkdownV2",
        )
        context.user_data[_OP_KEY] = pending
        return CHAR_NAME_INPUT
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char:
            char.name = name
    from bot.utils.formatting import _esc
    await update.message.reply_text(
        translator.t("character.identity.rename_success", lang=lang, name=_esc(name)),
        parse_mode="MarkdownV2",
    )
    return await show_identity_menu(update, context, char_id)


# ---------------------------------------------------------------------------
# Speed
# ---------------------------------------------------------------------------

async def ask_speed_input(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int,
) -> int:
    lang = get_lang(update)
    context.user_data[_OP_KEY] = {"char_id": char_id, "field": "speed"}
    await _edit_or_reply(
        update,
        translator.t("character.identity.prompt_speed", lang=lang),
        build_cancel_keyboard(char_id, "char_identity", lang=lang),
    )
    return CHAR_SPEED_INPUT


async def handle_speed_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return CHAR_SPEED_INPUT
    lang = get_lang(update)
    pending = context.user_data.pop(_OP_KEY, None)
    if pending is None:
        return CHAR_MENU
    char_id: int = pending["char_id"]
    try:
        speed = int(update.message.text.strip())
        if speed < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            translator.t("character.identity.speed_invalid", lang=lang),
            parse_mode="MarkdownV2",
        )
        context.user_data[_OP_KEY] = pending
        return CHAR_SPEED_INPUT

    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU
        old = getattr(char, "speed", 30)
        char.speed = speed

    import asyncio as _asyncio
    _asyncio.create_task(_log(char_id, "identity_change", f"Velocità: {old} → {speed}"))
    await update.message.reply_text(
        translator.t("character.identity.updated", lang=lang), parse_mode="MarkdownV2"
    )
    return await show_identity_menu(update, context, char_id)


# ---------------------------------------------------------------------------
# Background & Alignment (share CHAR_BACKGROUND_INPUT state)
# ---------------------------------------------------------------------------

async def ask_background_input(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int,
) -> int:
    lang = get_lang(update)
    context.user_data[_OP_KEY] = {"char_id": char_id, "field": "background"}
    await _edit_or_reply(
        update,
        translator.t("character.identity.prompt_background", lang=lang),
        build_cancel_keyboard(char_id, "char_identity", lang=lang),
    )
    return CHAR_BACKGROUND_INPUT


async def ask_alignment_input(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int,
) -> int:
    lang = get_lang(update)
    context.user_data[_OP_KEY] = {"char_id": char_id, "field": "alignment"}
    await _edit_or_reply(
        update,
        translator.t("character.identity.prompt_alignment", lang=lang),
        build_cancel_keyboard(char_id, "char_identity", lang=lang),
    )
    return CHAR_BACKGROUND_INPUT


async def handle_background_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return CHAR_BACKGROUND_INPUT
    lang = get_lang(update)
    pending = context.user_data.pop(_OP_KEY, None)
    if pending is None:
        return CHAR_MENU
    char_id: int = pending["char_id"]
    field: str = pending.get("field", "background")
    value = update.message.text.strip()[:200]
    if not value:
        await update.message.reply_text(
            translator.t("character.identity.invalid", lang=lang), parse_mode="MarkdownV2"
        )
        context.user_data[_OP_KEY] = pending
        return CHAR_BACKGROUND_INPUT

    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU
        old = getattr(char, field, None)
        setattr(char, field, value)

    import asyncio as _asyncio
    _asyncio.create_task(_log(char_id, "identity_change", f"{field.capitalize()}: {old or '—'} → {value}"))
    await update.message.reply_text(
        translator.t("character.identity.updated", lang=lang), parse_mode="MarkdownV2"
    )
    return await show_identity_menu(update, context, char_id)


# ---------------------------------------------------------------------------
# Personality traits
# ---------------------------------------------------------------------------

async def show_personality_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int,
) -> int:
    lang = get_lang(update)
    keyboard = build_identity_personality_keyboard(char_id, lang=lang)
    await _edit_or_reply(
        update, translator.t("character.identity.personality_title", lang=lang), keyboard
    )
    return CHAR_MENU


async def ask_personality_field(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int, field: str,
) -> int:
    """field: 'traits', 'ideals', 'bonds', 'flaws'"""
    lang = get_lang(update)
    context.user_data[_OP_KEY] = {"char_id": char_id, "field": field}
    await _edit_or_reply(
        update,
        translator.t(f"character.identity.prompt_{field}", lang=lang),
        build_cancel_keyboard(char_id, "char_identity", lang=lang),
    )
    return CHAR_PERSONALITY_INPUT


async def handle_personality_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return CHAR_PERSONALITY_INPUT
    lang = get_lang(update)
    pending = context.user_data.pop(_OP_KEY, None)
    if pending is None:
        return CHAR_MENU
    char_id: int = pending["char_id"]
    field: str = pending.get("field", "traits")
    value = update.message.text.strip()[:500]
    if not value:
        await update.message.reply_text(
            translator.t("character.identity.invalid", lang=lang), parse_mode="MarkdownV2"
        )
        context.user_data[_OP_KEY] = pending
        return CHAR_PERSONALITY_INPUT

    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU
        personality = dict(char.personality or {})
        personality[field] = value
        char.personality = personality

    import asyncio as _asyncio
    _asyncio.create_task(_log(char_id, "identity_change", f"Personalità {field}: aggiornato"))
    await update.message.reply_text(
        translator.t("character.identity.updated", lang=lang), parse_mode="MarkdownV2"
    )
    return await show_identity_menu(update, context, char_id)


# ---------------------------------------------------------------------------
# Languages
# ---------------------------------------------------------------------------

async def show_languages_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int,
) -> int:
    lang = get_lang(update)
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU
        languages = list(char.languages or [])

    keyboard = build_identity_list_keyboard(char_id, "languages", languages, lang=lang)
    await _edit_or_reply(
        update, translator.t("character.identity.languages_title", lang=lang), keyboard
    )
    return CHAR_MENU


async def ask_add_language(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int,
) -> int:
    lang = get_lang(update)
    context.user_data[_OP_KEY] = {"char_id": char_id, "field": "language"}
    await _edit_or_reply(
        update,
        translator.t("character.identity.prompt_add_language", lang=lang),
        build_cancel_keyboard(char_id, "char_identity", lang=lang),
    )
    return CHAR_LANGUAGE_ADD


async def handle_language_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return CHAR_LANGUAGE_ADD
    lang = get_lang(update)
    pending = context.user_data.pop(_OP_KEY, None)
    if pending is None:
        return CHAR_MENU
    char_id: int = pending["char_id"]
    value = update.message.text.strip()[:100]
    if not value:
        await update.message.reply_text(
            translator.t("character.identity.language_invalid", lang=lang), parse_mode="MarkdownV2"
        )
        context.user_data[_OP_KEY] = pending
        return CHAR_LANGUAGE_ADD

    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU
        languages = list(char.languages or [])
        if value not in languages:
            languages.append(value)
        char.languages = languages

    import asyncio as _asyncio
    _asyncio.create_task(_log(char_id, "identity_change", f"Linguaggio aggiunto: {value}"))
    if update.message:
        await update.message.reply_text(
            translator.t("character.identity.language_added", lang=lang), parse_mode="MarkdownV2"
        )
    return await show_languages_menu(update, context, char_id)


async def remove_language(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int, value: str,
) -> int:
    lang = get_lang(update)
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU
        languages = [l for l in (char.languages or []) if l != value]
        char.languages = languages
    if update.callback_query:
        await update.callback_query.answer(
            translator.t("character.identity.language_removed", lang=lang)
        )
    return await show_languages_menu(update, context, char_id)


# ---------------------------------------------------------------------------
# General Proficiencies
# ---------------------------------------------------------------------------

async def show_proficiencies_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int,
) -> int:
    lang = get_lang(update)
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU
        profs = list(char.general_proficiencies or [])

    keyboard = build_identity_list_keyboard(char_id, "proficiencies", profs, lang=lang)
    await _edit_or_reply(
        update, translator.t("character.identity.proficiencies_title", lang=lang), keyboard
    )
    return CHAR_MENU


async def ask_add_proficiency(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int,
) -> int:
    lang = get_lang(update)
    context.user_data[_OP_KEY] = {"char_id": char_id, "field": "proficiency"}
    await _edit_or_reply(
        update,
        translator.t("character.identity.prompt_add_proficiency", lang=lang),
        build_cancel_keyboard(char_id, "char_identity", lang=lang),
    )
    return CHAR_PROFICIENCY_ADD


async def handle_proficiency_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return CHAR_PROFICIENCY_ADD
    lang = get_lang(update)
    pending = context.user_data.pop(_OP_KEY, None)
    if pending is None:
        return CHAR_MENU
    char_id: int = pending["char_id"]
    value = update.message.text.strip()[:100]
    if not value:
        await update.message.reply_text(
            translator.t("character.identity.proficiency_invalid", lang=lang), parse_mode="MarkdownV2"
        )
        context.user_data[_OP_KEY] = pending
        return CHAR_PROFICIENCY_ADD

    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU
        profs = list(char.general_proficiencies or [])
        if value not in profs:
            profs.append(value)
        char.general_proficiencies = profs

    import asyncio as _asyncio
    _asyncio.create_task(_log(char_id, "identity_change", f"Competenza aggiunta: {value}"))
    if update.message:
        await update.message.reply_text(
            translator.t("character.identity.proficiency_added", lang=lang), parse_mode="MarkdownV2"
        )
    return await show_proficiencies_menu(update, context, char_id)


async def remove_proficiency(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int, value: str,
) -> int:
    lang = get_lang(update)
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU
        profs = [p for p in (char.general_proficiencies or []) if p != value]
        char.general_proficiencies = profs
    if update.callback_query:
        await update.callback_query.answer(
            translator.t("character.identity.proficiency_removed", lang=lang)
        )
    return await show_proficiencies_menu(update, context, char_id)


# ---------------------------------------------------------------------------
# Damage Modifiers (Resistances / Immunities / Vulnerabilities)
# ---------------------------------------------------------------------------

async def show_damage_modifiers_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int,
) -> int:
    lang = get_lang(update)
    keyboard = build_identity_damage_modifiers_keyboard(char_id, lang=lang)
    await _edit_or_reply(
        update, translator.t("character.identity.damage_modifiers_title", lang=lang), keyboard
    )
    return CHAR_MENU


async def show_modifier_type_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int, modifier_type: str,
) -> int:
    """modifier_type: 'resistances', 'immunities', 'vulnerabilities'"""
    lang = get_lang(update)
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU
        dmg_mods = dict(char.damage_modifiers or {})
        items = list(dmg_mods.get(modifier_type, []))

    keyboard = build_identity_list_keyboard(char_id, modifier_type, items, lang=lang)
    await _edit_or_reply(
        update,
        translator.t(f"character.identity.damage_modifiers_title", lang=lang),
        keyboard,
    )
    return CHAR_MENU


async def ask_add_modifier(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int, modifier_type: str,
) -> int:
    lang = get_lang(update)
    context.user_data[_OP_KEY] = {"char_id": char_id, "field": modifier_type}
    prompt_key = {
        "resistances": "character.identity.prompt_add_resistance",
        "immunities": "character.identity.prompt_add_immunity",
        "vulnerabilities": "character.identity.prompt_add_vulnerability",
    }.get(modifier_type, "character.identity.prompt_add_resistance")
    await _edit_or_reply(
        update,
        translator.t(prompt_key, lang=lang),
        build_cancel_keyboard(char_id, "char_identity", lang=lang),
    )
    return CHAR_PROFICIENCY_ADD  # reuse state for generic text input


async def handle_modifier_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return CHAR_PROFICIENCY_ADD
    lang = get_lang(update)
    pending = context.user_data.pop(_OP_KEY, None)
    if pending is None:
        return CHAR_MENU
    char_id: int = pending["char_id"]
    modifier_type: str = pending.get("field", "resistances")
    value = update.message.text.strip()[:100]
    if not value:
        await update.message.reply_text(
            translator.t("character.identity.modifier_invalid", lang=lang), parse_mode="MarkdownV2"
        )
        context.user_data[_OP_KEY] = pending
        return CHAR_PROFICIENCY_ADD

    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU
        dmg_mods = dict(char.damage_modifiers or {})
        lst = list(dmg_mods.get(modifier_type, []))
        if value not in lst:
            lst.append(value)
        dmg_mods[modifier_type] = lst
        char.damage_modifiers = dmg_mods

    import asyncio as _asyncio
    _asyncio.create_task(_log(char_id, "identity_change", f"{modifier_type}: aggiunto {value}"))
    if update.message:
        await update.message.reply_text(
            translator.t("character.identity.modifier_added", lang=lang), parse_mode="MarkdownV2"
        )
    return await show_modifier_type_menu(update, context, char_id, modifier_type)


async def remove_modifier(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int,
    modifier_type: str, value: str,
) -> int:
    lang = get_lang(update)
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU
        dmg_mods = dict(char.damage_modifiers or {})
        lst = [x for x in dmg_mods.get(modifier_type, []) if x != value]
        dmg_mods[modifier_type] = lst
        char.damage_modifiers = dmg_mods
    if update.callback_query:
        await update.callback_query.answer(
            translator.t("character.identity.modifier_removed", lang=lang)
        )
    return await show_modifier_type_menu(update, context, char_id, modifier_type)


async def ask_race_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
) -> int:
    lang = get_lang(update)
    context.user_data[_OP_KEY] = {"char_id": char_id, "field": "race"}
    text = translator.t("character.identity.prompt_race", lang=lang)
    await _edit_or_reply(update, text, build_cancel_keyboard(char_id, "char_identity", lang=lang))
    return CHAR_RACE_INPUT


async def handle_race_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    if update.message is None:
        return CHAR_RACE_INPUT

    lang = get_lang(update)
    pending = context.user_data.pop(_OP_KEY, None)
    if pending is None:
        return CHAR_MENU

    char_id: int = pending["char_id"]
    value = update.message.text.strip()[:100]
    if not value:
        await update.message.reply_text(
            translator.t("character.identity.invalid", lang=lang),
            parse_mode="MarkdownV2",
        )
        context.user_data[_OP_KEY] = pending
        return CHAR_RACE_INPUT

    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU
        old = char.race
        char.race = value

    import asyncio as _asyncio
    _asyncio.create_task(_log(char_id, "identity_change", f"Razza: {old or '—'} → {value}"))
    await update.message.reply_text(
        translator.t("character.identity.updated", lang=lang),
        parse_mode="MarkdownV2",
    )
    return await show_identity_menu(update, context, char_id)


async def ask_gender_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
) -> int:
    lang = get_lang(update)
    context.user_data[_OP_KEY] = {"char_id": char_id, "field": "gender"}
    text = translator.t("character.identity.prompt_gender", lang=lang)
    await _edit_or_reply(update, text, build_cancel_keyboard(char_id, "char_identity", lang=lang))
    return CHAR_GENDER_INPUT


async def handle_gender_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    if update.message is None:
        return CHAR_GENDER_INPUT

    lang = get_lang(update)
    pending = context.user_data.pop(_OP_KEY, None)
    if pending is None:
        return CHAR_MENU

    char_id: int = pending["char_id"]
    value = update.message.text.strip()[:50]
    if not value:
        await update.message.reply_text(
            translator.t("character.identity.invalid", lang=lang),
            parse_mode="MarkdownV2",
        )
        context.user_data[_OP_KEY] = pending
        return CHAR_GENDER_INPUT

    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU
        old = char.gender
        char.gender = value

    import asyncio as _asyncio
    _asyncio.create_task(_log(char_id, "identity_change", f"Genere: {old or '—'} → {value}"))
    await update.message.reply_text(
        translator.t("character.identity.updated", lang=lang),
        parse_mode="MarkdownV2",
    )
    return await show_identity_menu(update, context, char_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _log(char_id: int, event_type: str, description: str) -> None:
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
