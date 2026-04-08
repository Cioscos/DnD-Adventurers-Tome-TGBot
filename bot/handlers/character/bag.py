"""Inventory (bag) management handler."""

from __future__ import annotations

import logging

from sqlalchemy import delete, select
from telegram import Update
from telegram.ext import ContextTypes

from bot.db.engine import get_session
from bot.db.models import Character, Item
from bot.handlers.character import (
    CHAR_BAG_ADD_NAME,
    CHAR_BAG_ADD_WEIGHT,
    CHAR_BAG_ADD_QTY,
    CHAR_BAG_MENU,
    CHAR_MENU,
)
from bot.keyboards.character import build_bag_keyboard, build_item_detail_keyboard, build_cancel_keyboard
from bot.utils.formatting import format_bag
from bot.utils.i18n import get_lang, translator

logger = logging.getLogger(__name__)

_OP_KEY = "char_bag_pending"


async def show_bag_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int, page: int = 0
) -> int:
    lang = get_lang(update)
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU
        result = await session.execute(
            select(Item).where(Item.character_id == char_id).order_by(Item.name)
        )
        items = list(result.scalars().all())

    keyboard = build_bag_keyboard(char_id, items, page, lang=lang)
    text = format_bag(items, char.carry_capacity, char.encumbrance, lang=lang)
    await _edit_or_reply(update, text, keyboard)
    return CHAR_BAG_MENU


async def show_item_detail(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    item_id: int,
    back_page: int = 0,
) -> int:
    async with get_session() as session:
        item = await session.get(Item, item_id)
        if item is None or item.character_id != char_id:
            return await show_bag_menu(update, context, char_id)

    lang = get_lang(update)
    desc = _esc(item.description) if item.description else translator.t("character.bag.no_description", lang=lang)
    text = (
        f"📦 *{_esc(item.name)}*\n\n"
        + translator.t("character.bag.item_detail_qty", lang=lang, qty=item.quantity) + "\n"
        + translator.t("character.bag.item_detail_weight_unit", lang=lang, weight=_esc(f'{item.weight:.1f}')) + "\n"
        + translator.t("character.bag.item_detail_weight_total", lang=lang, total_weight=_esc(f'{item.weight * item.quantity:.1f}')) + "\n\n"
        + desc
    )
    keyboard = build_item_detail_keyboard(char_id, item_id, back_page, lang=lang)
    await _edit_or_reply(update, text, keyboard)
    return CHAR_BAG_MENU


async def ask_add_item(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    lang = get_lang(update)
    context.user_data[_OP_KEY] = {"char_id": char_id, "step": "name"}
    await _edit_or_reply(update, translator.t("character.bag.prompt_name", lang=lang), build_cancel_keyboard(char_id, "char_bag", lang=lang))
    return CHAR_BAG_ADD_NAME


async def handle_bag_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if update.message is None:
        return CHAR_BAG_MENU

    lang = get_lang(update)
    pending = context.user_data.get(_OP_KEY, {})
    char_id: int = pending.get("char_id")
    step: str = pending.get("step", "name")
    text = update.message.text.strip()

    if step == "name":
        if not text:
            await update.message.reply_text(translator.t("character.bag.name_invalid", lang=lang), parse_mode="MarkdownV2")
            return CHAR_BAG_ADD_NAME
        context.user_data[_OP_KEY]["item_name"] = text
        context.user_data[_OP_KEY]["step"] = "weight"
        await update.message.reply_text(
            translator.t("character.bag.prompt_weight", lang=lang),
            reply_markup=build_cancel_keyboard(char_id, "char_bag", lang=lang),
            parse_mode="MarkdownV2",
        )
        return CHAR_BAG_ADD_WEIGHT

    if step == "weight":
        try:
            weight = float(text.replace(",", "."))
            if weight < 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text(translator.t("character.bag.weight_invalid", lang=lang), parse_mode="MarkdownV2")
            return CHAR_BAG_ADD_WEIGHT
        context.user_data[_OP_KEY]["item_weight"] = weight
        context.user_data[_OP_KEY]["step"] = "qty"
        await update.message.reply_text(
            translator.t("character.bag.prompt_qty", lang=lang),
            reply_markup=build_cancel_keyboard(char_id, "char_bag", lang=lang),
            parse_mode="MarkdownV2",
        )
        return CHAR_BAG_ADD_QTY

    if step == "qty":
        try:
            qty = int(text)
            if qty < 1:
                raise ValueError
        except ValueError:
            await update.message.reply_text(translator.t("character.bag.qty_invalid", lang=lang), parse_mode="MarkdownV2")
            return CHAR_BAG_ADD_QTY

        item_name = pending["item_name"]
        item_weight = pending["item_weight"]

        async with get_session() as session:
            # Check if item with same name already exists
            result = await session.execute(
                select(Item).where(
                    Item.character_id == char_id, Item.name == item_name
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                existing.quantity += qty
            else:
                session.add(Item(
                    character_id=char_id,
                    name=item_name,
                    weight=item_weight,
                    quantity=qty,
                ))
            # Recalculate encumbrance
            char = await session.get(Character, char_id)
            if char:
                all_items_res = await session.execute(
                    select(Item).where(Item.character_id == char_id)
                )
                char.encumbrance = sum(i.weight * i.quantity for i in all_items_res.scalars())

        context.user_data.pop(_OP_KEY, None)
        import asyncio as _asyncio
        _asyncio.create_task(_log(char_id, "bag_change", f"Aggiunto: {item_name} x{qty} ({item_weight} kg)"))
        await update.message.reply_text(
            translator.t("character.bag.item_added", lang=lang, name=_esc(item_name)), parse_mode="MarkdownV2"
        )
        return await show_bag_menu(update, context, char_id)

    return CHAR_BAG_MENU


async def modify_item_quantity(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    item_id: int,
    delta: int,
) -> int:
    """Add or remove 1 from an item's quantity. Remove item if qty reaches 0."""
    async with get_session() as session:
        item = await session.get(Item, item_id)
        if item is None or item.character_id != char_id:
            return await show_bag_menu(update, context, char_id)
        item_name = item.name
        old_qty = item.quantity
        item.quantity += delta
        removed = item.quantity <= 0
        if removed:
            await session.delete(item)
        new_qty = max(0, item.quantity)
        # Recalculate encumbrance
        char = await session.get(Character, char_id)
        if char:
            all_items_res = await session.execute(
                select(Item).where(Item.character_id == char_id)
            )
            char.encumbrance = sum(i.weight * i.quantity for i in all_items_res.scalars())

    import asyncio as _asyncio
    if removed:
        _asyncio.create_task(_log(char_id, "bag_change", f"Rimosso: {item_name}"))
    else:
        sign = "+" if delta > 0 else ""
        _asyncio.create_task(_log(char_id, "bag_change", f"{item_name}: qty {old_qty} → {new_qty} ({sign}{delta})"))
    if update.callback_query:
        await update.callback_query.answer()
    return await show_bag_menu(update, context, char_id)


async def remove_all_item(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    item_id: int,
) -> int:
    async with get_session() as session:
        item = await session.get(Item, item_id)
        item_name = item.name if item and item.character_id == char_id else "?"
        await session.execute(
            delete(Item).where(Item.id == item_id, Item.character_id == char_id)
        )
        char = await session.get(Character, char_id)
        if char:
            all_items_res = await session.execute(
                select(Item).where(Item.character_id == char_id)
            )
            char.encumbrance = sum(i.weight * i.quantity for i in all_items_res.scalars())

    import asyncio as _asyncio
    _asyncio.create_task(_log(char_id, "bag_change", f"Rimosso tutto: {item_name}"))
    if update.callback_query:
        await update.callback_query.answer("Oggetto rimosso.")
    return await show_bag_menu(update, context, char_id)


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
