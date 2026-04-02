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
from bot.utils.formatting import CURRENCY_LABELS, format_currency

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
    async with get_session() as session:
        cur = await _get_or_create_currency(session, char_id)

    keyboard = build_currency_keyboard(char_id)
    text = format_currency(cur)
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
    label, emoji = CURRENCY_LABELS[currency_key]
    op_label = "aggiungere" if operation == "add" else "rimuovere"
    context.user_data[_OP_KEY] = {
        "char_id": char_id,
        "currency_key": currency_key,
        "operation": operation,
    }
    keyboard = build_currency_edit_keyboard(char_id, currency_key)
    text = (
        f"{emoji} *{label}*\n\n"
        f"Quante monete vuoi {op_label}? Inserisci un numero:"
    )
    await _edit_or_reply(update, text, keyboard)
    return CHAR_CURRENCY_EDIT


async def handle_currency_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if update.message is None:
        return CHAR_CURRENCY_MENU

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
        await update.message.reply_text("❌ Valore non valido\\.", parse_mode="MarkdownV2")
        context.user_data[_OP_KEY] = pending
        return CHAR_CURRENCY_EDIT

    async with get_session() as session:
        cur = await _get_or_create_currency(session, char_id)
        current = getattr(cur, currency_key, 0)
        if operation == "add":
            setattr(cur, currency_key, current + amount)
        else:
            new_val = current - amount
            if new_val < 0:
                await update.message.reply_text(
                    f"❌ Non hai abbastanza monete \\(hai {current}\\)\\.",
                    parse_mode="MarkdownV2",
                )
                context.user_data[_OP_KEY] = pending
                return CHAR_CURRENCY_EDIT
            setattr(cur, currency_key, new_val)

    await update.message.reply_text("✅ Monete aggiornate\\!", parse_mode="MarkdownV2")
    return await show_currency_menu(update, context, char_id)


async def show_convert_source(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    keyboard = build_currency_convert_source_keyboard(
        char_id, list(CURRENCY_LABELS.keys())
    )
    await _edit_or_reply(update, "🔄 Seleziona la valuta da *convertire*:", keyboard)
    return CHAR_CURRENCY_CONVERT


async def show_convert_target(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    source_key: str,
) -> int:
    keyboard = build_currency_convert_target_keyboard(
        char_id, source_key, list(CURRENCY_LABELS.keys())
    )
    label = CURRENCY_LABELS[source_key][0]
    await _edit_or_reply(update, f"🔄 Converti *{label}* in:", keyboard)
    return CHAR_CURRENCY_CONVERT


async def ask_convert_amount(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    source_key: str,
    target_key: str,
) -> int:
    context.user_data[_OP_KEY] = {
        "char_id": char_id,
        "currency_key": source_key,
        "operation": "convert",
        "target_key": target_key,
    }
    src_label = CURRENCY_LABELS[source_key][0]
    tgt_label = CURRENCY_LABELS[target_key][0]
    await _edit_or_reply(
        update,
        f"🔢 Quante monete di *{src_label}* convertire in *{tgt_label}*?",
        build_cancel_keyboard(char_id, "char_currency"),
    )
    return CHAR_CURRENCY_CONVERT


async def handle_convert_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if update.message is None:
        return CHAR_CURRENCY_CONVERT

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
        await update.message.reply_text("❌ Valore non valido\\.", parse_mode="MarkdownV2")
        context.user_data[_OP_KEY] = pending
        return CHAR_CURRENCY_CONVERT

    async with get_session() as session:
        cur = await _get_or_create_currency(session, char_id)
        success = cur.convert(source_key, target_key, amount)

    if not success:
        await update.message.reply_text("❌ Monete insufficienti\\.", parse_mode="MarkdownV2")
        return await show_currency_menu(update, context, char_id)

    await update.message.reply_text("✅ Conversione completata\\!", parse_mode="MarkdownV2")
    return await show_currency_menu(update, context, char_id)


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
