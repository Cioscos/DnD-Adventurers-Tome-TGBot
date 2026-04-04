"""Maps management handler — store Telegram file_ids organised by zone."""

from __future__ import annotations

import logging

from sqlalchemy import delete, select
from telegram import Update
from telegram.ext import ContextTypes

from bot.db.engine import get_session
from bot.db.models import Character, FileType, Map
from bot.handlers.character import (
    CHAR_MAP_ADD_FILE,
    CHAR_MAP_NEW_ZONE,
    CHAR_MAPS_MENU,
    CHAR_MENU,
)
from bot.keyboards.character import build_map_zone_keyboard, build_maps_keyboard, build_cancel_keyboard
from bot.utils.formatting import format_maps
from bot.utils.i18n import get_lang, translator

logger = logging.getLogger(__name__)

_OP_KEY = "char_maps_pending"


async def show_maps_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int, page: int = 0
) -> int:
    async with get_session() as session:
        result = await session.execute(
            select(Map).where(Map.character_id == char_id).order_by(Map.zone_name)
        )
        maps = list(result.scalars().all())

    lang = get_lang(update)
    zone_names = sorted({m.zone_name for m in maps})
    keyboard = build_maps_keyboard(char_id, zone_names, page)
    text = format_maps(maps, lang=lang)
    await _edit_or_reply(update, text, keyboard)
    return CHAR_MAPS_MENU


async def show_zone(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    zone: str,
    back_page: int = 0,
) -> int:
    async with get_session() as session:
        result = await session.execute(
            select(Map).where(
                Map.character_id == char_id, Map.zone_name == zone
            ).order_by(Map.id)
        )
        maps = list(result.scalars().all())

    lang = get_lang(update)
    count = len(maps)
    zone_title = translator.t("character.maps.zone_detail", lang=lang, zone=_esc(zone))
    count_str = translator.t("character.maps.zone_count", lang=lang, count=count)
    text = f"{zone_title}\n\n{count_str}"
    keyboard = build_map_zone_keyboard(char_id, zone, maps, back_page)
    await _edit_or_reply(update, text, keyboard)
    return CHAR_MAPS_MENU


async def send_map_file(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    map_id: int,
) -> int:
    """Send the file to the user using its stored Telegram file_id."""
    async with get_session() as session:
        m = await session.get(Map, map_id)
        if m is None or m.character_id != char_id:
            return await show_maps_menu(update, context, char_id)
        file_id = m.file_id
        file_type = m.file_type
        zone = m.zone_name

    chat_id = update.effective_chat.id
    if update.callback_query:
        await update.callback_query.answer()

    if file_type == FileType.PHOTO:
        await context.bot.send_photo(chat_id=chat_id, photo=file_id, caption=f"📍 {zone}")
    else:
        await context.bot.send_document(chat_id=chat_id, document=file_id, caption=f"📍 {zone}")

    return CHAR_MAPS_MENU


async def ask_new_zone(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    lang = get_lang(update)
    context.user_data[_OP_KEY] = {"char_id": char_id, "step": "zone_name"}
    await _edit_or_reply(update, translator.t("character.maps.prompt_zone", lang=lang), build_cancel_keyboard(char_id, "char_maps", lang=lang))
    return CHAR_MAP_NEW_ZONE


async def handle_new_zone_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if update.message is None:
        return CHAR_MAP_NEW_ZONE
    lang = get_lang(update)
    pending = context.user_data.pop(_OP_KEY, None)
    if pending is None:
        return CHAR_MAPS_MENU

    char_id: int = pending["char_id"]
    zone = update.message.text.strip()
    if not zone:
        await update.message.reply_text(translator.t("character.maps.zone_invalid", lang=lang), parse_mode="MarkdownV2")
        context.user_data[_OP_KEY] = pending
        return CHAR_MAP_NEW_ZONE

    await update.message.reply_text(
        translator.t("character.maps.zone_created", lang=lang, zone=_esc(zone)),
        parse_mode="MarkdownV2",
    )
    return await show_zone(update, context, char_id, zone)


async def ask_add_file(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    zone: str,
) -> int:
    lang = get_lang(update)
    context.user_data[_OP_KEY] = {"char_id": char_id, "zone": zone, "step": "file"}
    await _edit_or_reply(
        update,
        translator.t("character.maps.prompt_file", lang=lang, zone=_esc(zone)),
        build_cancel_keyboard(char_id, "char_maps", lang=lang),
    )
    return CHAR_MAP_ADD_FILE


async def handle_map_file(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Receive photo or document and store its Telegram file_id."""
    pending = context.user_data.pop(_OP_KEY, None)
    if pending is None or update.message is None:
        return CHAR_MAPS_MENU
    lang = get_lang(update)
    char_id: int = pending["char_id"]
    zone: str = pending["zone"]

    file_id: str | None = None
    file_type = FileType.DOCUMENT

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        file_type = FileType.PHOTO
    elif update.message.document:
        file_id = update.message.document.file_id
        file_type = FileType.DOCUMENT

    if file_id is None:
        await update.message.reply_text(translator.t("character.maps.file_invalid", lang=lang), parse_mode="MarkdownV2")
        context.user_data[_OP_KEY] = pending
        return CHAR_MAP_ADD_FILE

    async with get_session() as session:
        session.add(Map(
            character_id=char_id,
            zone_name=zone,
            file_id=file_id,
            file_type=file_type,
        ))

    await update.message.reply_text(
        translator.t("character.maps.file_added", lang=lang, zone=_esc(zone)), parse_mode="MarkdownV2"
    )
    return await show_zone(update, context, char_id, zone)


async def delete_map_file(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    map_id: int,
    zone: str,
) -> int:
    async with get_session() as session:
        await session.execute(
            delete(Map).where(Map.id == map_id, Map.character_id == char_id)
        )
    if update.callback_query:
        await update.callback_query.answer("File rimosso.")
    return await show_zone(update, context, char_id, zone)


async def delete_zone(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    zone: str,
) -> int:
    async with get_session() as session:
        await session.execute(
            delete(Map).where(Map.character_id == char_id, Map.zone_name == zone)
        )
    if update.callback_query:
        await update.callback_query.answer(f"Zona '{zone}' eliminata.")
    return await show_maps_menu(update, context, char_id)


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
