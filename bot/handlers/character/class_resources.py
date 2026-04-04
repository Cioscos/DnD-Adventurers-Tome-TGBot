"""Class-specific resource management handler.

Handles viewing and using class resources (Ki points, Rage uses, etc.)
for each CharacterClass. Resources are stored in the ClassResource table
and are linked to a CharacterClass row.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from bot.db.engine import get_session
from bot.db.models import CharacterClass, ClassResource, RestorationType
from bot.handlers.character import CHAR_MULTICLASS_MENU

logger = logging.getLogger(__name__)

from bot.utils.i18n import get_lang, translator


async def show_class_resources_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    class_id: int,
) -> int:
    """Show the resource management screen for a specific class."""
    from bot.keyboards.character import build_class_resources_keyboard
    from bot.utils.formatting import format_class_resources
    lang = get_lang(update)

    async with get_session() as session:
        cls = await session.get(CharacterClass, class_id)
        if cls is None or cls.character_id != char_id:
            return await _back_to_multiclass(update, context, char_id)
        await session.refresh(cls, ["resources"])
        resources = list(cls.resources)
        class_name = cls.class_name
        subclass = cls.subclass
        level = cls.level

    if not resources:
        text = (
            f"🎭 *{_esc(class_name)}*"
            + (f" \\({_esc(subclass)}\\)" if subclass else "")
            + f" — Livello {level}\n\n"
            "_Nessuna risorsa di classe da gestire\\._"
        )
        keyboard = build_class_resources_keyboard(char_id, class_id, [])
    else:
        text = format_class_resources(class_name, subclass, level, resources, lang=lang)
        keyboard = build_class_resources_keyboard(char_id, class_id, resources)

    await _edit_or_reply(update, text, keyboard)
    return CHAR_MULTICLASS_MENU


async def use_class_resource(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    class_id: int,
    resource_id: int,
) -> int:
    """Decrement current by 1 for the given resource."""
    async with get_session() as session:
        resource = await session.get(ClassResource, resource_id)
        if resource is None or resource.class_id != class_id:
            return await show_class_resources_menu(update, context, char_id, class_id)
        try:
            resource.use()
        except ValueError:
            if update.callback_query:
                await update.callback_query.answer("Nessuna risorsa disponibile.")
            return await show_class_resources_menu(update, context, char_id, class_id)

    if update.callback_query:
        await update.callback_query.answer()
    return await show_class_resources_menu(update, context, char_id, class_id)


async def restore_one_class_resource(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    class_id: int,
    resource_id: int,
) -> int:
    """Increment current by 1 for the given resource (up to total)."""
    async with get_session() as session:
        resource = await session.get(ClassResource, resource_id)
        if resource is None:
            return await show_class_resources_menu(update, context, char_id, class_id)
        if resource.current < resource.total:
            resource.current += 1
        else:
            if update.callback_query:
                await update.callback_query.answer("Risorsa già al massimo.")
            return await show_class_resources_menu(update, context, char_id, class_id)

    if update.callback_query:
        await update.callback_query.answer()
    return await show_class_resources_menu(update, context, char_id, class_id)


async def restore_all_class_resources(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    class_id: int,
) -> int:
    """Restore all resources of the given class to their maximum."""
    async with get_session() as session:
        result = await session.execute(
            select(ClassResource).where(ClassResource.class_id == class_id)
        )
        for resource in result.scalars():
            resource.restore_all()

    if update.callback_query:
        await update.callback_query.answer("Risorse ripristinate.")
    return await show_class_resources_menu(update, context, char_id, class_id)


async def update_class_resources_on_level_change(
    class_id: int,
    class_name: str,
    new_level: int,
    char=None,
) -> None:
    """Recalculate all resource totals after a level change.

    Also adds newly available resources (e.g. Action Surge unlocks at level 2).
    """
    from bot.data.classes import CLASS_RESOURCES, get_resources_for_class, update_resources_for_level

    async with get_session() as session:
        result = await session.execute(
            select(ClassResource).where(ClassResource.class_id == class_id)
        )
        existing_resources = list(result.scalars())

        # Update existing resources
        update_resources_for_level(class_name, new_level, existing_resources, char)

        # Check for newly available resources (total was 0 at old level, now > 0)
        existing_names = {r.name for r in existing_resources}
        new_configs = get_resources_for_class(class_name, new_level, char)
        for res_dict in new_configs:
            if res_dict["name"] not in existing_names:
                session.add(ClassResource(
                    class_id=class_id,
                    **res_dict,
                ))

        # Remove resources that are no longer available (total became 0)
        configs_by_name = {cfg["name"]: cfg for cfg in get_resources_for_class(class_name, new_level, char)}
        cfg_list = CLASS_RESOURCES.get(class_name, [])
        for resource in existing_resources:
            if resource.name in configs_by_name:
                continue  # still available, total already updated above
            cfg = next((c for c in cfg_list if c.name == resource.name), None)
            if cfg is not None and cfg.formula(new_level) <= 0:
                await session.delete(resource)


async def restore_class_resources_on_rest(
    char_id: int,
    rest_type: str,
) -> None:
    """Restore class resources based on rest type for all classes of a character."""
    async with get_session() as session:
        classes_result = await session.execute(
            select(CharacterClass).where(CharacterClass.character_id == char_id)
        )
        for cls in classes_result.scalars():
            resources_result = await session.execute(
                select(ClassResource).where(ClassResource.class_id == cls.id)
            )
            for resource in resources_result.scalars():
                if rest_type == "long" and resource.restoration_type == RestorationType.LONG_REST:
                    resource.restore_all()
                elif rest_type == "short" and resource.restoration_type == RestorationType.SHORT_REST:
                    resource.restore_all()


async def _back_to_multiclass(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
) -> int:
    from bot.handlers.character.multiclass import show_multiclass_menu
    return await show_multiclass_menu(update, context, char_id)


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
