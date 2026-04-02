"""Multiclassing and level management handler."""

from __future__ import annotations

import logging

from sqlalchemy import delete, select
from telegram import Update
from telegram.ext import ContextTypes

from bot.db.engine import get_session
from bot.db.models import Character, CharacterClass
from bot.handlers.character import (
    CHAR_MENU,
    CHAR_MULTICLASS_ADD,
    CHAR_MULTICLASS_ADD_LEVELS,
    CHAR_MULTICLASS_MENU,
)
from bot.keyboards.character import (
    build_cancel_keyboard,
    build_level_class_choice_keyboard,
    build_level_keyboard,
    build_multiclass_keyboard,
    build_multiclass_remove_keyboard,
)

logger = logging.getLogger(__name__)

_OP_KEY = "char_multiclass_pending"


async def show_multiclass_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    async with get_session() as session:
        result = await session.execute(
            select(CharacterClass).where(CharacterClass.character_id == char_id)
        )
        classes = list(result.scalars().all())

    if classes:
        lines = [f"  • {c.class_name}: Livello {c.level}" for c in classes]
        class_text = "\n".join(lines)
        total = sum(c.level for c in classes)
        text = f"🎭 *Multiclasse*\n\n{class_text}\n\n*Livello totale: {total}*"
    else:
        text = "🎭 *Multiclasse*\n\nNessuna classe assegnata\\."

    keyboard = build_multiclass_keyboard(char_id)
    await _edit_or_reply(update, text, keyboard)
    return CHAR_MULTICLASS_MENU


async def ask_add_class(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    context.user_data[_OP_KEY] = {"char_id": char_id, "step": "class_name"}
    await _edit_or_reply(update, "🎭 Inserisci il *nome della classe* \\(es\\. Guerriero, Mago\\):", build_cancel_keyboard(char_id, "char_multiclass"))
    return CHAR_MULTICLASS_ADD


async def handle_multiclass_add_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if update.message is None:
        return CHAR_MULTICLASS_ADD

    pending = context.user_data.get(_OP_KEY, {})
    char_id: int = pending.get("char_id")
    step: str = pending.get("step", "class_name")
    text = update.message.text.strip()

    if step == "class_name":
        if not text:
            await update.message.reply_text("❌ Nome non valido\\.", parse_mode="MarkdownV2")
            return CHAR_MULTICLASS_ADD
        context.user_data[_OP_KEY]["class_name"] = text
        context.user_data[_OP_KEY]["step"] = "levels"
        await update.message.reply_text(
            f"🔢 Quanti *livelli* in *{_esc(text)}*?",
            reply_markup=build_cancel_keyboard(char_id, "char_multiclass"),
            parse_mode="MarkdownV2",
        )
        return CHAR_MULTICLASS_ADD_LEVELS

    if step == "levels":
        try:
            levels = int(text)
            if levels < 1 or levels > 20:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❌ Valore non valido \\(1\\-20\\)\\.", parse_mode="MarkdownV2")
            return CHAR_MULTICLASS_ADD_LEVELS

        class_name = pending["class_name"]
        async with get_session() as session:
            result = await session.execute(
                select(CharacterClass).where(
                    CharacterClass.character_id == char_id,
                    CharacterClass.class_name == class_name,
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                existing.level = levels
            else:
                session.add(CharacterClass(character_id=char_id, class_name=class_name, level=levels))

        context.user_data.pop(_OP_KEY, None)
        await update.message.reply_text(
            f"✅ Classe *{_esc(class_name)}* \\(Livello {levels}\\) aggiunta\\!",
            parse_mode="MarkdownV2",
        )
        return await show_multiclass_menu(update, context, char_id)

    return CHAR_MULTICLASS_ADD


async def show_remove_class(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    async with get_session() as session:
        result = await session.execute(
            select(CharacterClass).where(CharacterClass.character_id == char_id)
        )
        classes = list(result.scalars().all())

    if not classes:
        await _edit_or_reply(update, "❌ Nessuna classe da rimuovere\\.")
        return await show_multiclass_menu(update, context, char_id)

    class_names = [c.class_name for c in classes]
    keyboard = build_multiclass_remove_keyboard(char_id, class_names)
    await _edit_or_reply(update, "🎭 Seleziona la classe da rimuovere:", keyboard)
    return CHAR_MULTICLASS_MENU


async def remove_class(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    class_name: str,
) -> int:
    async with get_session() as session:
        await session.execute(
            delete(CharacterClass).where(
                CharacterClass.character_id == char_id,
                CharacterClass.class_name == class_name,
            )
        )
    if update.callback_query:
        await update.callback_query.answer(f"{class_name} rimossa.")
    return await show_multiclass_menu(update, context, char_id)


async def change_level(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    direction: str,
) -> int:
    """Show level up/down menu — if multiple classes, pick which one."""
    async with get_session() as session:
        result = await session.execute(
            select(CharacterClass).where(CharacterClass.character_id == char_id)
        )
        classes = list(result.scalars().all())

    if not classes:
        await _edit_or_reply(update, "❌ Nessuna classe assegnata\\. Aggiungi prima una classe dal menu Multiclasse\\.")
        return CHAR_MULTICLASS_MENU

    if len(classes) == 1:
        # Directly change level
        return await apply_level_change(update, context, char_id, classes[0].class_name, direction)

    class_names = [c.class_name for c in classes]
    keyboard = build_level_class_choice_keyboard(char_id, direction, class_names)
    label = "salire" if direction == "up" else "scendere"
    await _edit_or_reply(update, f"⚔️ In quale classe vuoi {label} di livello?", keyboard)
    return CHAR_MULTICLASS_MENU


async def apply_level_change(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    class_name: str,
    direction: str,
) -> int:
    async with get_session() as session:
        result = await session.execute(
            select(CharacterClass).where(
                CharacterClass.character_id == char_id,
                CharacterClass.class_name == class_name,
            )
        )
        cls = result.scalar_one_or_none()
        if cls is None:
            return await show_multiclass_menu(update, context, char_id)

        if direction == "up":
            if cls.level >= 20:
                if update.callback_query:
                    await update.callback_query.answer("Livello massimo raggiunto.")
                return await show_multiclass_menu(update, context, char_id)
            cls.level += 1
        else:
            if cls.level <= 1:
                if update.callback_query:
                    await update.callback_query.answer("Livello minimo raggiunto.")
                return await show_multiclass_menu(update, context, char_id)
            cls.level -= 1

    if update.callback_query:
        await update.callback_query.answer()
    return await show_multiclass_menu(update, context, char_id)


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
