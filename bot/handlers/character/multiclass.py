"""Multiclassing and level management handler.

Supports both guided class selection (from predefined D&D 5e class list)
and free-form custom class entry. Also manages subclass names and
class-specific resource tracking.
"""

from __future__ import annotations

import logging

from sqlalchemy import delete, select
from telegram import Update
from telegram.ext import ContextTypes

from bot.data.classes import DND_CLASSES, CLASS_RESOURCES, get_resources_for_class
from bot.db.engine import get_session
from bot.db.models import Character, CharacterClass, ClassResource
from bot.handlers.character import (
    CHAR_CLASS_SUBCLASS_INPUT,
    CHAR_MENU,
    CHAR_MULTICLASS_ADD,
    CHAR_MULTICLASS_ADD_LEVELS,
    CHAR_MULTICLASS_MENU,
)
from bot.keyboards.character import (
    build_cancel_keyboard,
    build_class_add_mode_keyboard,
    build_class_guided_keyboard,
    build_class_resources_keyboard,
    build_level_class_choice_keyboard,
    build_level_keyboard,
    build_multiclass_keyboard,
    build_multiclass_remove_keyboard,
    build_subclass_input_keyboard,
)

logger = logging.getLogger(__name__)

_OP_KEY = "char_multiclass_pending"


async def show_multiclass_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    from bot.utils.formatting import format_multiclass_menu

    async with get_session() as session:
        result = await session.execute(
            select(CharacterClass).where(CharacterClass.character_id == char_id)
        )
        classes = list(result.scalars().all())
        # Load resources for each class
        for cls in classes:
            await session.refresh(cls, ["resources"])

    text = format_multiclass_menu(classes)
    keyboard = build_multiclass_keyboard(char_id, classes)
    await _edit_or_reply(update, text, keyboard)
    return CHAR_MULTICLASS_MENU


async def ask_add_class(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int,
    flow: str = "multiclass",
) -> int:
    """Show the choice between guided class selection and custom entry."""
    context.user_data[_OP_KEY] = {"char_id": char_id, "step": "mode", "flow": flow}
    keyboard = build_class_add_mode_keyboard(char_id)
    await _edit_or_reply(
        update,
        "🎭 *Aggiungi Classe*\n\nCome vuoi scegliere la classe?",
        keyboard,
    )
    return CHAR_MULTICLASS_MENU


async def show_guided_class_list(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    """Show the list of predefined D&D 5e classes."""
    keyboard = build_class_guided_keyboard(char_id)
    await _edit_or_reply(update, "🎭 *Scegli una classe:*", keyboard)
    return CHAR_MULTICLASS_MENU


async def handle_guided_class_selected(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int, class_name: str
) -> int:
    """User picked a class from the guided list — now ask for level."""
    pending = context.user_data.get(_OP_KEY, {})
    pending["class_name"] = class_name
    pending["step"] = "levels"
    context.user_data[_OP_KEY] = pending
    await _edit_or_reply(
        update,
        f"🔢 Quanti *livelli* in *{_esc(class_name)}*? \\(1\\-20\\)",
        build_cancel_keyboard(char_id, "char_multiclass"),
    )
    return CHAR_MULTICLASS_ADD_LEVELS


async def ask_custom_class(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    """Ask for a free-form custom class name."""
    pending = context.user_data.get(_OP_KEY, {})
    pending["step"] = "class_name"
    context.user_data[_OP_KEY] = pending
    await _edit_or_reply(
        update,
        "✍️ Inserisci il *nome della classe personalizzata*:",
        build_cancel_keyboard(char_id, "char_multiclass"),
    )
    return CHAR_MULTICLASS_ADD


async def handle_multiclass_add_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle text input for custom class name or level number."""
    if update.message is None:
        return CHAR_MULTICLASS_ADD

    pending = context.user_data.get(_OP_KEY, {})
    char_id: int = pending.get("char_id", 0)
    step: str = pending.get("step", "class_name")
    text = update.message.text.strip()

    if step == "class_name":
        if not text or len(text) > 100:
            await update.message.reply_text(
                "❌ Nome non valido \\(max 100 caratteri\\)\\.",
                parse_mode="MarkdownV2",
            )
            return CHAR_MULTICLASS_ADD
        context.user_data[_OP_KEY]["class_name"] = text
        context.user_data[_OP_KEY]["step"] = "levels"
        await update.message.reply_text(
            f"🔢 Quanti *livelli* in *{_esc(text)}*? \\(1\\-20\\)",
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
            await update.message.reply_text(
                "❌ Valore non valido \\(inserisci un numero tra 1 e 20\\)\\.",
                parse_mode="MarkdownV2",
            )
            return CHAR_MULTICLASS_ADD_LEVELS

        context.user_data[_OP_KEY]["level"] = levels
        context.user_data[_OP_KEY]["step"] = "subclass"

        class_name = pending.get("class_name", "")
        await update.message.reply_text(
            f"📛 Inserisci la *sottoclasse* per *{_esc(class_name)}* "
            f"\\(es\\. Campione, Abiuratore\\) oppure salta:",
            reply_markup=build_subclass_input_keyboard(char_id),
            parse_mode="MarkdownV2",
        )
        return CHAR_CLASS_SUBCLASS_INPUT

    return CHAR_MULTICLASS_ADD


async def handle_subclass_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle subclass text input (or skip callback)."""
    if update.message is None:
        return CHAR_CLASS_SUBCLASS_INPUT

    pending = context.user_data.get(_OP_KEY, {})
    char_id: int = pending.get("char_id", 0)
    subclass_text = update.message.text.strip()

    return await _finalize_add_class(update, context, char_id, subclass_text or None)


async def skip_subclass(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    """Skip subclass entry and finalize class addition."""
    return await _finalize_add_class(update, context, char_id, None)


async def _finalize_add_class(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    subclass: str | None,
) -> int:
    """Save the CharacterClass and auto-generate class resources."""
    pending = context.user_data.pop(_OP_KEY, {})
    class_name: str = pending.get("class_name", "")
    level: int = pending.get("level", 1)
    flow: str = pending.get("flow", "multiclass")

    if not class_name:
        return await show_multiclass_menu(update, context, char_id)

    async with get_session() as session:
        # Load character for CHA-based resource calculation
        char = await session.get(Character, char_id)
        if char:
            await session.refresh(char, ["ability_scores"])

        # Upsert class
        result = await session.execute(
            select(CharacterClass).where(
                CharacterClass.character_id == char_id,
                CharacterClass.class_name == class_name,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.level = level
            existing.subclass = subclass
            cls_id = existing.id
            # Remove old resources before re-generating
            await session.execute(
                delete(ClassResource).where(ClassResource.class_id == cls_id)
            )
            await session.flush()
        else:
            new_cls = CharacterClass(
                character_id=char_id,
                class_name=class_name,
                level=level,
                subclass=subclass,
            )
            session.add(new_cls)
            await session.flush()
            cls_id = new_cls.id

        # Auto-generate class resources for predefined classes
        resources = get_resources_for_class(class_name, level, char)
        for res_dict in resources:
            session.add(ClassResource(class_id=cls_id, **res_dict))

    sub_str = f" \\({_esc(subclass)}\\)" if subclass else ""
    await _send_reply(update, f"✅ Classe *{_esc(class_name)}*{sub_str} \\(Livello {level}\\) aggiunta\\!")

    if flow == "creation":
        from bot.handlers.character.menu import show_character_menu
        return await show_character_menu(update, context, char_id=char_id)
    return await show_multiclass_menu(update, context, char_id)


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
        await _edit_or_reply(
            update,
            "❌ Nessuna classe assegnata\\. Aggiungi prima una classe dal menu Multiclasse\\.",
        )
        return CHAR_MULTICLASS_MENU

    if len(classes) == 1:
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
    from bot.handlers.character.class_resources import update_class_resources_on_level_change

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

        new_level = cls.level
        cls_id = cls.id

    # Update class resources outside the session
    await update_class_resources_on_level_change(cls_id, class_name, new_level)

    if update.callback_query:
        await update.callback_query.answer()
    return await show_multiclass_menu(update, context, char_id)


# ---------------------------------------------------------------------------
# Internal helpers
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


async def _send_reply(update: Update, text: str) -> None:
    """Always send as a new message (for text input confirmation)."""
    if update.message:
        await update.message.reply_text(text, parse_mode="MarkdownV2")
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, parse_mode="MarkdownV2")


def _esc(text: str) -> str:
    special = r"\_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in str(text))
