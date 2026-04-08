"""Currency management handler (coins and conversion)."""

from __future__ import annotations

import logging

from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from bot.db.engine import get_session
from bot.db.models import Character, Currency
from bot.handlers.character import (
    CHAR_CURRENCY_CONVERT,
    CHAR_CURRENCY_EDIT,
    CHAR_CURRENCY_MENU,
    CHAR_MENU,
)
from bot.keyboards.character import (
    build_cancel_keyboard,
    build_currency_convert_source_keyboard,
    build_currency_convert_target_keyboard,
    build_currency_edit_keyboard,
    build_currency_keyboard,
)
from bot.utils.formatting import CURRENCY_LABELS, format_currency, get_currency_labels
from bot.utils.i18n import get_lang, translator

logger = logging.getLogger(__name__)

_OP_KEY = "char_currency_pending"


async def _get_or_create_currency(session, char_id: int) -> Currency:
    result = await session.execute(
        select(Currency).where(Currency.character_id == char_id)
    )
    cur = result.scalar_one_or_none()
    if cur is None:
        cur = Currency(character_id=char_id)
        session.add(cur)
        await session.flush()
    return cur


async def show_currency_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    lang = get_lang(update)
    async with get_session() as session:
        cur = await _get_or_create_currency(session, char_id)

    keyboard = build_currency_keyboard(char_id, lang=lang)
    text = format_currency(cur, lang=lang)
    await _edit_or_reply(update, text, keyboard)
    return CHAR_CURRENCY_MENU


async def show_currency_edit(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    currency_key: str,
    operation: str,
) -> int:
    """Ask amount to add/remove for a specific currency."""
    lang = get_lang(update)
    label, emoji = get_currency_labels(lang=lang)[currency_key]
    op_label = translator.t("character.currency.op_add", lang=lang) if operation == "add" else translator.t("character.currency.op_remove", lang=lang)
    context.user_data[_OP_KEY] = {
        "char_id": char_id,
        "currency_key": currency_key,
        "operation": operation,
    }
    keyboard = build_currency_edit_keyboard(char_id, currency_key, lang=lang)
    text = translator.t("character.currency.prompt_amount", lang=lang, emoji=emoji, label=label, op=op_label)
    await _edit_or_reply(update, text, keyboard)
    return CHAR_CURRENCY_EDIT


async def handle_currency_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if update.message is None:
        return CHAR_CURRENCY_MENU

    lang = get_lang(update)
    pending = context.user_data.pop(_OP_KEY, None)
    if pending is None:
        return CHAR_CURRENCY_MENU

    char_id: int = pending["char_id"]
    currency_key: str = pending["currency_key"]
    operation: str = pending["operation"]

    try:
        amount = int(update.message.text.strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(translator.t("character.currency.amount_invalid", lang=lang), parse_mode="MarkdownV2")
        context.user_data[_OP_KEY] = pending
        return CHAR_CURRENCY_EDIT

    async with get_session() as session:
        cur = await _get_or_create_currency(session, char_id)
        current = getattr(cur, currency_key, 0)
        if operation == "add":
            setattr(cur, currency_key, current + amount)
            desc = f"{currency_key}: +{amount} (da {current} a {current + amount})"
        else:
            new_val = current - amount
            if new_val < 0:
                await update.message.reply_text(
                    translator.t("character.currency.not_enough", lang=lang, current=current),
                    parse_mode="MarkdownV2",
                )
                context.user_data[_OP_KEY] = pending
                return CHAR_CURRENCY_EDIT
            setattr(cur, currency_key, new_val)
            desc = f"{currency_key}: -{amount} (da {current} a {new_val})"

    import asyncio as _asyncio
    _asyncio.create_task(_log(char_id, "currency_change", desc))
    await update.message.reply_text(translator.t("character.currency.updated", lang=lang), parse_mode="MarkdownV2")
    return await show_currency_menu(update, context, char_id)


async def show_convert_source(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    lang = get_lang(update)
    keyboard = build_currency_convert_source_keyboard(
        char_id, list(get_currency_labels(lang=lang).keys()), lang=lang
    )
    await _edit_or_reply(update, translator.t("character.currency.convert_source_title", lang=lang), keyboard)
    return CHAR_CURRENCY_CONVERT


async def show_convert_target(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    source_key: str,
) -> int:
    lang = get_lang(update)
    currency_labels = get_currency_labels(lang=lang)
    keyboard = build_currency_convert_target_keyboard(
        char_id, source_key, list(currency_labels.keys()), lang=lang
    )
    label = currency_labels[source_key][0]
    await _edit_or_reply(update, translator.t("character.currency.convert_target_title", lang=lang, label=label), keyboard)
    return CHAR_CURRENCY_CONVERT


async def ask_convert_amount(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    source_key: str,
    target_key: str,
) -> int:
    lang = get_lang(update)
    context.user_data[_OP_KEY] = {
        "char_id": char_id,
        "currency_key": source_key,
        "operation": "convert",
        "target_key": target_key,
    }
    currency_labels = get_currency_labels(lang=lang)
    src_label = currency_labels[source_key][0]
    tgt_label = currency_labels[target_key][0]
    await _edit_or_reply(
        update,
        translator.t("character.currency.convert_amount_prompt", lang=lang, source=src_label, target=tgt_label),
        build_cancel_keyboard(char_id, "char_currency", lang=lang),
    )
    return CHAR_CURRENCY_CONVERT


async def handle_convert_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if update.message is None:
        return CHAR_CURRENCY_CONVERT

    lang = get_lang(update)
    pending = context.user_data.pop(_OP_KEY, None)
    if pending is None or pending.get("operation") != "convert":
        return CHAR_CURRENCY_MENU

    char_id: int = pending["char_id"]
    source_key: str = pending["currency_key"]
    target_key: str = pending["target_key"]

    try:
        amount = int(update.message.text.strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(translator.t("character.currency.convert_invalid", lang=lang), parse_mode="MarkdownV2")
        context.user_data[_OP_KEY] = pending
        return CHAR_CURRENCY_CONVERT

    async with get_session() as session:
        cur = await _get_or_create_currency(session, char_id)
        success = cur.convert(source_key, target_key, amount)

    if not success:
        await update.message.reply_text(translator.t("character.currency.convert_insufficient", lang=lang), parse_mode="MarkdownV2")
        return await show_currency_menu(update, context, char_id)

    import asyncio as _asyncio
    _asyncio.create_task(_log(char_id, "currency_change", f"Convertiti {amount} {source_key} → {target_key}"))
    await update.message.reply_text(translator.t("character.currency.convert_completed", lang=lang), parse_mode="MarkdownV2")
    return await show_currency_menu(update, context, char_id)


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
