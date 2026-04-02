"""Spell slot management handler."""

from __future__ import annotations

import logging

from sqlalchemy import delete, select
from telegram import Update
from telegram.ext import ContextTypes

from bot.db.engine import get_session
from bot.db.models import Character, SpellSlot
from bot.handlers.character import (
    CHAR_MENU,
    CHAR_SPELL_SLOTS_MENU,
    CHAR_SPELL_SLOT_ADD,
    CHAR_SPELL_SLOT_REMOVE,
)
from bot.keyboards.character import build_spell_slot_detail_keyboard, build_spell_slots_keyboard, build_cancel_keyboard
from bot.utils.formatting import format_spell_slots

logger = logging.getLogger(__name__)

_OP_KEY = "char_slot_pending"


async def show_spell_slots_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    async with get_session() as session:
        result = await session.execute(
            select(SpellSlot).where(SpellSlot.character_id == char_id).order_by(SpellSlot.level)
        )
        slots = list(result.scalars().all())

    keyboard = build_spell_slots_keyboard(char_id, slots)
    text = format_spell_slots(slots)
    await _edit_or_reply(update, text, keyboard)
    return CHAR_SPELL_SLOTS_MENU


async def show_slot_detail(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    slot_id: int,
) -> int:
    async with get_session() as session:
        slot = await session.get(SpellSlot, slot_id)
        if slot is None or slot.character_id != char_id:
            return await show_spell_slots_menu(update, context, char_id)

    text = (
        f"🎲 *Slot Livello {slot.level}*\n\n"
        f"Disponibili: *{slot.available}* / {slot.total}\n"
        f"Usati: *{slot.used}*"
    )
    keyboard = build_spell_slot_detail_keyboard(char_id, slot)
    await _edit_or_reply(update, text, keyboard)
    return CHAR_SPELL_SLOTS_MENU


async def ask_add_slot(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    context.user_data[_OP_KEY] = {"char_id": char_id, "step": "level"}
    await _edit_or_reply(
        update, "🔢 Inserisci il *livello* dello slot \\(1\\-9\\):",
        build_cancel_keyboard(char_id, "char_slots"),
    )
    return CHAR_SPELL_SLOT_ADD


async def handle_slot_add_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if update.message is None:
        return CHAR_SPELL_SLOT_ADD

    pending = context.user_data.get(_OP_KEY, {})
    char_id: int = pending.get("char_id")
    step: str = pending.get("step", "level")
    text = update.message.text.strip()

    if step == "level":
        try:
            level = int(text)
            if not 1 <= level <= 9:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❌ Livello non valido \\(1\\-9\\)\\.", parse_mode="MarkdownV2")
            return CHAR_SPELL_SLOT_ADD
        context.user_data[_OP_KEY]["slot_level"] = level
        context.user_data[_OP_KEY]["step"] = "total"
        await update.message.reply_text(
            "🔢 Inserisci il numero *totale* di slot per questo livello:",
            reply_markup=build_cancel_keyboard(char_id, "char_slots"),
            parse_mode="MarkdownV2",
        )
        return CHAR_SPELL_SLOT_ADD

    if step == "total":
        try:
            total = int(text)
            if total < 1:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❌ Valore non valido\\.", parse_mode="MarkdownV2")
            return CHAR_SPELL_SLOT_ADD

        level = pending["slot_level"]
        async with get_session() as session:
            result = await session.execute(
                select(SpellSlot).where(
                    SpellSlot.character_id == char_id, SpellSlot.level == level
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                existing.total = total
                existing.used = min(existing.used, total)
            else:
                session.add(SpellSlot(character_id=char_id, level=level, total=total, used=0))

        context.user_data.pop(_OP_KEY, None)
        await update.message.reply_text(
            f"✅ Slot livello {level} configurati \\({total} totali\\)\\!", parse_mode="MarkdownV2"
        )
        return await show_spell_slots_menu(update, context, char_id)

    return CHAR_SPELL_SLOT_ADD


async def use_slot(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int, slot_id: int
) -> int:
    async with get_session() as session:
        slot = await session.get(SpellSlot, slot_id)
        if slot is None or slot.character_id != char_id:
            return await show_spell_slots_menu(update, context, char_id)
        try:
            slot.use_slot()
        except ValueError as e:
            if update.callback_query:
                await update.callback_query.answer(str(e))
            return await show_spell_slots_menu(update, context, char_id)

    if update.callback_query:
        await update.callback_query.answer("Slot usato.")
    return await show_spell_slots_menu(update, context, char_id)


async def restore_slot(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int, slot_id: int
) -> int:
    async with get_session() as session:
        slot = await session.get(SpellSlot, slot_id)
        if slot and slot.character_id == char_id:
            slot.restore_slot()

    if update.callback_query:
        await update.callback_query.answer("Slot ripristinato.")
    return await show_spell_slots_menu(update, context, char_id)


async def reset_all_slots(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    async with get_session() as session:
        result = await session.execute(
            select(SpellSlot).where(SpellSlot.character_id == char_id)
        )
        for slot in result.scalars():
            slot.restore_all()

    if update.callback_query:
        await update.callback_query.answer("Tutti gli slot ripristinati.")
    return await show_spell_slots_menu(update, context, char_id)


async def remove_slot_level(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int, slot_id: int
) -> int:
    async with get_session() as session:
        await session.execute(
            delete(SpellSlot).where(SpellSlot.id == slot_id, SpellSlot.character_id == char_id)
        )

    if update.callback_query:
        await update.callback_query.answer("Livello slot rimosso.")
    return await show_spell_slots_menu(update, context, char_id)


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
