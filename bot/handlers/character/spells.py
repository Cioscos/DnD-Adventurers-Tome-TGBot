"""Spell management handler."""

from __future__ import annotations

import logging

from sqlalchemy import delete, select
from telegram import Update
from telegram.ext import ContextTypes

from bot.db.engine import get_session
from bot.db.models import Character, Spell, SpellSlot
from bot.handlers.character import (
    CHAR_MENU,
    CHAR_SPELLS_MENU,
    CHAR_SPELL_LEARN,
)
from bot.keyboards.character import (
    build_spell_detail_keyboard,
    build_spell_use_level_keyboard,
    build_spells_menu_keyboard,
)
from bot.utils.formatting import format_spells

logger = logging.getLogger(__name__)

_OP_KEY = "char_spell_pending"


async def show_spells_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int, page: int = 0
) -> int:
    async with get_session() as session:
        result = await session.execute(
            select(Spell).where(Spell.character_id == char_id).order_by(Spell.level, Spell.name)
        )
        spells = list(result.scalars().all())

    keyboard = build_spells_menu_keyboard(char_id, spells, page)
    text = format_spells(spells) if spells else "Nessun incantesimo conosciuto\\."
    await _edit_or_reply(update, text, keyboard)
    return CHAR_SPELLS_MENU


async def show_spell_detail(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    spell_id: int,
    back_page: int = 0,
) -> int:
    async with get_session() as session:
        spell = await session.get(Spell, spell_id)
        if spell is None or spell.character_id != char_id:
            return await show_spells_menu(update, context, char_id)

    level_label = "Trucchetto" if spell.level == 0 else f"Livello {spell.level}"
    desc = spell.description or "_Nessuna descrizione_"
    text = (
        f"✨ *{_esc(spell.name)}*\n"
        f"Livello: {level_label}\n\n"
        f"{desc}"
    )
    keyboard = build_spell_detail_keyboard(char_id, spell_id, back_page)
    await _edit_or_reply(update, text, keyboard)
    return CHAR_SPELLS_MENU


async def ask_spell_learn(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    """Ask user to type the spell name."""
    context.user_data[_OP_KEY] = {"char_id": char_id, "step": "name"}
    await _edit_or_reply(
        update,
        "✨ Inserisci il *nome dell'incantesimo* da imparare:",
    )
    return CHAR_SPELL_LEARN


async def handle_spell_learn_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Multi-step spell learning: name → level → description (optional)."""
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
        context.user_data[_OP_KEY]["step"] = "desc"
        await update.message.reply_text(
            "📝 Inserisci una *descrizione* \\(facoltativa, invia \\- per saltare\\):",
            parse_mode="MarkdownV2",
        )
        return CHAR_SPELL_LEARN

    if step == "desc":
        spell_name = pending["spell_name"]
        spell_level = pending["spell_level"]
        description = None if text in ("-", "") else text
        async with get_session() as session:
            session.add(Spell(
                character_id=char_id,
                name=spell_name,
                level=spell_level,
                description=description,
            ))
        context.user_data.pop(_OP_KEY, None)
        await update.message.reply_text(
            f"✅ Incantesimo *{_esc(spell_name)}* imparato\\!", parse_mode="MarkdownV2"
        )
        return await show_spells_menu(update, context, char_id)

    return CHAR_SPELL_LEARN


async def forget_spell(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    spell_id: int,
) -> int:
    async with get_session() as session:
        await session.execute(
            delete(Spell).where(Spell.id == spell_id, Spell.character_id == char_id)
        )
    if update.callback_query:
        await update.callback_query.answer("Incantesimo dimenticato.")
    return await show_spells_menu(update, context, char_id)


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

    if update.callback_query:
        await update.callback_query.answer(f"Slot liv.{slot_level} usato!")
    return await show_spells_menu(update, context, char_id)


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
