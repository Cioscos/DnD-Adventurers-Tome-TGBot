"""Special abilities / features handler."""

from __future__ import annotations

import logging

from sqlalchemy import delete, select
from telegram import Update
from telegram.ext import ContextTypes

from bot.db.engine import get_session
from bot.db.models import Ability, Character, RestorationType
from bot.handlers.character import (
    CHAR_ABILITIES_MENU,
    CHAR_ABILITY_LEARN_DESC,
    CHAR_ABILITY_LEARN_NAME,
    CHAR_ABILITY_LEARN_USES,
    CHAR_MENU,
)
from bot.keyboards.character import build_abilities_keyboard, build_ability_detail_keyboard, build_cancel_keyboard
from bot.utils.formatting import RESTORATION_LABELS, format_abilities, get_restoration_labels
from bot.utils.i18n import get_lang, translator

logger = logging.getLogger(__name__)

_OP_KEY = "char_ability_pending"


async def show_abilities_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int, page: int = 0
) -> int:
    lang = get_lang(update)
    async with get_session() as session:
        result = await session.execute(
            select(Ability).where(Ability.character_id == char_id).order_by(Ability.name)
        )
        abilities = list(result.scalars().all())

    keyboard = build_abilities_keyboard(char_id, abilities, page, lang=lang)
    text = format_abilities(abilities, lang=lang)
    await _edit_or_reply(update, text, keyboard)
    return CHAR_ABILITIES_MENU


async def show_ability_detail(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    ability_id: int,
    back_page: int = 0,
) -> int:
    async with get_session() as session:
        ability = await session.get(Ability, ability_id)
        if ability is None or ability.character_id != char_id:
            return await show_abilities_menu(update, context, char_id)

    lang = get_lang(update)
    passive_label = "✅ Passiva" if ability.is_passive else "⚡ Attiva"
    active_mark = "✅ Attivata" if ability.is_active else "⬛ Non attivata"
    uses_text = (
        f"Usi: *{ability.uses}*/*{ability.max_uses}*"
        if ability.max_uses is not None
        else "Usi: illimitati"
    )
    rest_labels = get_restoration_labels(lang=lang)
    rest_label = rest_labels.get(ability.restoration_type, rest_labels.get(str(ability.restoration_type), "—"))
    desc = _esc(ability.description) if ability.description else "_Nessuna descrizione_"
    text = (
        f"⚡ *{_esc(ability.name)}*\n\n"
        f"{desc}\n\n"
        f"{passive_label} \\| {active_mark}\n"
        f"{uses_text}\n"
        f"Ripristino: {_esc(rest_label)}"
    )
    keyboard = build_ability_detail_keyboard(char_id, ability, back_page, lang=lang)
    await _edit_or_reply(update, text, keyboard)
    return CHAR_ABILITIES_MENU


async def ask_learn_ability(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    lang = get_lang(update)
    context.user_data[_OP_KEY] = {"char_id": char_id, "step": "name"}
    await _edit_or_reply(update, translator.t("character.abilities.prompt_name", lang=lang), build_cancel_keyboard(char_id, "char_abilities", lang=lang))
    return CHAR_ABILITY_LEARN_NAME


async def handle_ability_learn_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if update.message is None:
        return CHAR_ABILITY_LEARN_NAME

    lang = get_lang(update)
    pending = context.user_data.get(_OP_KEY, {})
    char_id: int = pending.get("char_id")
    step: str = pending.get("step", "name")
    text = update.message.text.strip()

    if step == "name":
        if not text:
            await update.message.reply_text(translator.t("character.abilities.name_invalid", lang=lang), parse_mode="MarkdownV2")
            return CHAR_ABILITY_LEARN_NAME
        context.user_data[_OP_KEY]["ability_name"] = text
        context.user_data[_OP_KEY]["step"] = "desc"
        await update.message.reply_text(
            translator.t("character.abilities.prompt_desc", lang=lang),
            reply_markup=build_cancel_keyboard(char_id, "char_abilities", lang=lang),
            parse_mode="MarkdownV2",
        )
        return CHAR_ABILITY_LEARN_DESC

    if step == "desc":
        context.user_data[_OP_KEY]["ability_desc"] = None if text == "-" else text
        context.user_data[_OP_KEY]["step"] = "passive"
        await update.message.reply_text(
            translator.t("character.abilities.prompt_passive", lang=lang),
            reply_markup=build_cancel_keyboard(char_id, "char_abilities", lang=lang),
            parse_mode="MarkdownV2",
        )
        return CHAR_ABILITY_LEARN_USES

    if step == "passive":
        is_passive = text.lower() in ("si", "sì", "yes", "y")
        context.user_data[_OP_KEY]["is_passive"] = is_passive
        context.user_data[_OP_KEY]["step"] = "uses"
        await update.message.reply_text(
            translator.t("character.abilities.prompt_uses", lang=lang),
            reply_markup=build_cancel_keyboard(char_id, "char_abilities", lang=lang),
            parse_mode="MarkdownV2",
        )
        return CHAR_ABILITY_LEARN_USES

    if step == "uses":
        try:
            uses = int(text)
            if uses < 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text(translator.t("character.abilities.uses_invalid", lang=lang), parse_mode="MarkdownV2")
            return CHAR_ABILITY_LEARN_USES
        context.user_data[_OP_KEY]["max_uses"] = uses if uses > 0 else None
        context.user_data[_OP_KEY]["step"] = "restoration"
        await update.message.reply_text(
            translator.t("character.abilities.prompt_restoration", lang=lang),
            reply_markup=build_cancel_keyboard(char_id, "char_abilities", lang=lang),
            parse_mode="MarkdownV2",
        )
        return CHAR_ABILITY_LEARN_USES

    if step == "restoration":
        rest_map = {
            "long_rest": RestorationType.LONG_REST,
            "short_rest": RestorationType.SHORT_REST,
            "none": RestorationType.NONE,
        }
        restoration = rest_map.get(text.lower(), RestorationType.NONE)

        ability_name = pending["ability_name"]
        ability_desc = pending.get("ability_desc")
        is_passive = pending.get("is_passive", False)
        max_uses = pending.get("max_uses")

        async with get_session() as session:
            session.add(Ability(
                character_id=char_id,
                name=ability_name,
                description=ability_desc,
                is_passive=is_passive,
                max_uses=max_uses,
                uses=max_uses,
                restoration_type=restoration,
            ))

        context.user_data.pop(_OP_KEY, None)
        import asyncio as _asyncio
        _asyncio.create_task(_log(char_id, "ability_change", f"Imparata: {ability_name}"))
        await update.message.reply_text(
            translator.t("character.abilities.learned", lang=lang, name=_esc(ability_name)), parse_mode="MarkdownV2"
        )
        return await show_abilities_menu(update, context, char_id)

    return CHAR_ABILITY_LEARN_NAME


async def use_ability(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    ability_id: int,
) -> int:
    async with get_session() as session:
        ability = await session.get(Ability, ability_id)
        if ability is None or ability.character_id != char_id:
            return await show_abilities_menu(update, context, char_id)
        ability_name = ability.name
        try:
            ability.use()
        except ValueError as e:
            if update.callback_query:
                await update.callback_query.answer(str(e))
            return await show_ability_detail(update, context, char_id, ability_id)

    import asyncio as _asyncio
    _asyncio.create_task(_log(char_id, "ability_change", f"Usata: {ability_name}"))
    if update.callback_query:
        await update.callback_query.answer("Abilità usata.")
    return await show_ability_detail(update, context, char_id, ability_id)


async def toggle_ability(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    ability_id: int,
) -> int:
    async with get_session() as session:
        ability = await session.get(Ability, ability_id)
        if ability and ability.character_id == char_id:
            ability.is_active = not ability.is_active
            ability_name = ability.name
            new_state = ability.is_active
        else:
            ability_name = None

    if ability_name:
        import asyncio as _asyncio
        state_label = "attivata" if new_state else "disattivata"
        _asyncio.create_task(_log(char_id, "ability_change", f"{ability_name} {state_label}"))
    if update.callback_query:
        await update.callback_query.answer()
    return await show_ability_detail(update, context, char_id, ability_id)


async def forget_ability(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    ability_id: int,
) -> int:
    async with get_session() as session:
        ability = await session.get(Ability, ability_id)
        ability_name = ability.name if ability and ability.character_id == char_id else "?"
        await session.execute(
            delete(Ability).where(Ability.id == ability_id, Ability.character_id == char_id)
        )

    import asyncio as _asyncio
    _asyncio.create_task(_log(char_id, "ability_change", f"Dimenticata: {ability_name}"))
    if update.callback_query:
        await update.callback_query.answer("Abilità dimenticata.")
    return await show_abilities_menu(update, context, char_id)


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
