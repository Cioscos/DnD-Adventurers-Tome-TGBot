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
from bot.keyboards.character import build_bag_keyboard, build_item_detail_keyboard
from bot.utils.formatting import format_bag

logger = logging.getLogger(__name__)

_OP_KEY = "char_bag_pending"


async def show_bag_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int, page: int = 0
) -> int:
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU
        result = await session.execute(
            select(Item).where(Item.character_id == char_id).order_by(Item.name)
        )
        items = list(result.scalars().all())

    keyboard = build_bag_keyboard(char_id, items, page)
    text = format_bag(items, char.carry_capacity, char.encumbrance)
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

    desc = item.description or "_Nessuna descrizione_"
    text = (
        f"📦 *{_esc(item.name)}*\n\n"
        f"Quantità: *{item.quantity}*\n"
        f"Peso unitario: *{item.weight} kg*\n"
        f"Peso totale: *{item.weight * item.quantity:.1f} kg*\n\n"
        f"{desc}"
    )
    keyboard = build_item_detail_keyboard(char_id, item_id, back_page)
    await _edit_or_reply(update, text, keyboard)
    return CHAR_BAG_MENU


async def ask_add_item(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    context.user_data[_OP_KEY] = {"char_id": char_id, "step": "name"}
    await _edit_or_reply(update, "📦 Inserisci il *nome* dell'oggetto:")
    return CHAR_BAG_ADD_NAME


async def handle_bag_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if update.message is None:
        return CHAR_BAG_MENU

    pending = context.user_data.get(_OP_KEY, {})
    char_id: int = pending.get("char_id")
    step: str = pending.get("step", "name")
    text = update.message.text.strip()

    if step == "name":
        if not text:
            await update.message.reply_text("❌ Nome non valido\\.", parse_mode="MarkdownV2")
            return CHAR_BAG_ADD_NAME
        context.user_data[_OP_KEY]["item_name"] = text
        context.user_data[_OP_KEY]["step"] = "weight"
        await update.message.reply_text(
            "⚖️ Inserisci il *peso* unitario in kg \\(es\\. 1\\.5, o 0 se non pesa\\):",
            parse_mode="MarkdownV2",
        )
        return CHAR_BAG_ADD_WEIGHT

    if step == "weight":
        try:
            weight = float(text.replace(",", "."))
            if weight < 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❌ Peso non valido\\.", parse_mode="MarkdownV2")
            return CHAR_BAG_ADD_WEIGHT
        context.user_data[_OP_KEY]["item_weight"] = weight
        context.user_data[_OP_KEY]["step"] = "qty"
        await update.message.reply_text(
            "🔢 Inserisci la *quantità* \\(es\\. 1\\):",
            parse_mode="MarkdownV2",
        )
        return CHAR_BAG_ADD_QTY

    if step == "qty":
        try:
            qty = int(text)
            if qty < 1:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❌ Quantità non valida\\.", parse_mode="MarkdownV2")
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
        await update.message.reply_text(
            f"✅ *{_esc(item_name)}* aggiunto allo zaino\\!", parse_mode="MarkdownV2"
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
        item.quantity += delta
        if item.quantity <= 0:
            await session.delete(item)
        # Recalculate encumbrance
        char = await session.get(Character, char_id)
        if char:
            all_items_res = await session.execute(
                select(Item).where(Item.character_id == char_id)
            )
            char.encumbrance = sum(i.weight * i.quantity for i in all_items_res.scalars())

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
        await session.execute(
            delete(Item).where(Item.id == item_id, Item.character_id == char_id)
        )
        char = await session.get(Character, char_id)
        if char:
            all_items_res = await session.execute(
                select(Item).where(Item.character_id == char_id)
            )
            char.encumbrance = sum(i.weight * i.quantity for i in all_items_res.scalars())

    if update.callback_query:
        await update.callback_query.answer("Oggetto rimosso.")
    return await show_bag_menu(update, context, char_id)


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
