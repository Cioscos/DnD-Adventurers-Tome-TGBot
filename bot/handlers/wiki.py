"""Inline-keyboard callback-query dispatcher for the D&D 5e wiki.

Routes :class:`~bot.models.state.NavAction` objects to the appropriate
view logic.  Supports N-level deep navigation: categories → items →
sub-entity lists → sub-item details → …

Entity-specific rendering lives in :mod:`bot.handlers.wiki_formatters`.
"""

from __future__ import annotations

import logging
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes, InvalidCallbackData

from bot.dnd5e.client import APIError, dnd_client
from bot.dnd5e.query_builder import (
    build_detail_query,
    build_list_query,
    build_sub_list_query,
)
from bot.handlers.wiki_formatters import _esc, format_detail
from bot.keyboards.builder import (
    PAGE_SIZE,
    build_categories_keyboard,
    build_detail_keyboard,
    build_list_keyboard,
    build_sub_list_keyboard,
)
from bot.models.state import NavAction
from bot.schema.registry import MENU_CATEGORIES, registry
from bot.utils.i18n import get_lang, translator

logger = logging.getLogger(__name__)


async def navigation_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle all inline-keyboard button presses for the wiki."""
    query = update.callback_query
    if query is None:
        return

    await query.answer()
    data = query.data
    lang = get_lang(update)

    if isinstance(data, InvalidCallbackData):
        await _send_error(query, translator.t("wiki.error_session_expired", lang=lang), lang=lang)
        return

    if not isinstance(data, NavAction):
        logger.warning("Unexpected callback_data type: %r", data)
        return

    try:
        if data.action == "noop":
            return
        if data.action == "menu":
            await _show_main_menu(query, lang=lang)
        elif data.action == "wiki":
            await _show_wiki_categories(query, lang=lang)
        elif data.action == "list":
            await _show_item_list(query, data, lang=lang)
        elif data.action == "detail":
            await _show_item_detail(query, data, lang=lang)
        elif data.action == "sub_list":
            await _show_sub_list(query, data, lang=lang)
        else:
            logger.warning("Unhandled NavAction: %s", data)
    except APIError as exc:
        await _send_error(query, str(exc), lang=lang)
    except BadRequest as exc:
        logger.error("Telegram BadRequest: %s (action=%s)", exc, data.action)
    except Exception:
        logger.exception("Unexpected error handling action=%s", data.action)
        await _send_error(query, translator.t("wiki.error_generic", lang=lang), lang=lang)


# ------------------------------------------------------------------
# Views
# ------------------------------------------------------------------

async def _show_main_menu(query: Any, lang: str = "it") -> None:
    from bot.handlers.start import build_wiki_keyboard
    await query.edit_message_text(
        text=translator.t("start.welcome", lang=lang),
        reply_markup=build_wiki_keyboard(lang=lang),
        parse_mode="MarkdownV2",
    )


async def _show_wiki_categories(query: Any, lang: str = "it") -> None:
    keyboard = build_categories_keyboard(lang=lang)
    await query.edit_message_text(
        text=translator.t("wiki.categories_title", lang=lang),
        reply_markup=keyboard,
        parse_mode="MarkdownV2",
    )


async def _show_item_list(query: Any, nav: NavAction, lang: str = "it") -> None:
    ti = registry.get_type(nav.type_name)
    if ti is None or ti.list_query_field is None:
        await _send_error(query, translator.t("wiki.error_unknown_category", lang=lang), lang=lang)
        return

    q = build_list_query(ti, registry)
    page = nav.page

    if ti.has_pagination:
        variables: dict[str, Any] = {
            "skip": page * PAGE_SIZE,
            "limit": PAGE_SIZE + 1,
        }
        data = await dnd_client.execute(q, variables)
        items: list[dict] = data.get(ti.list_query_field, [])
        has_next = len(items) > PAGE_SIZE
        display = items[:PAGE_SIZE]
    else:
        data = await dnd_client.execute(q)
        items = data.get(ti.list_query_field, [])
        has_next = False
        display = items

    if not display:
        await _send_error(query, translator.t("wiki.no_items", lang=lang), lang=lang)
        return

    emoji = _emoji_for(nav.type_name)
    label = _label_for(nav.type_name)
    page_info = translator.t("wiki.page_info", lang=lang, page=page + 1) if ti.has_pagination else ""
    header = (
        f"{emoji} *{_esc(label)}*{_esc(page_info)}\n\n"
        + translator.t("wiki.select_item", lang=lang)
    )

    keyboard = build_list_keyboard(display, nav.type_name, page, has_next, lang=lang)
    await query.edit_message_text(
        text=header, reply_markup=keyboard, parse_mode="MarkdownV2",
    )


async def _show_item_detail(query: Any, nav: NavAction, lang: str = "it") -> None:
    fetch_type_name = nav.type_name
    concrete = nav.concrete_type

    ti = registry.get_type(fetch_type_name)
    if ti is None:
        await _send_error(query, translator.t("wiki.error_unknown_type", lang=lang), lang=lang)
        return

    if ti.detail_query_field is None:
        parent_union = _find_union_parent(fetch_type_name)
        if parent_union and parent_union.detail_query_field:
            concrete = fetch_type_name
            fetch_type_name = parent_union.name
            ti = parent_union
        else:
            await _send_error(query, translator.t("wiki.error_cannot_fetch", lang=lang), lang=lang)
            return

    q = build_detail_query(ti, registry)
    data = await dnd_client.execute(q, {"index": nav.index})
    item = data.get(ti.detail_query_field, {})
    if not item:
        await _send_error(query, translator.t("wiki.error_not_found", lang=lang, index=nav.index), lang=lang)
        return

    if not concrete and "__typename" in item:
        concrete = item["__typename"]

    text = format_detail(concrete or fetch_type_name, item)
    back_nav = nav.back_nav()
    keyboard = build_detail_keyboard(
        fetch_type_name, nav.index, item,
        concrete_type=concrete,
        back_nav=back_nav,
        lang=lang,
    )

    try:
        await query.edit_message_text(
            text=text, reply_markup=keyboard, parse_mode="MarkdownV2",
        )
    except BadRequest as exc:
        logger.warning("Detail edit failed (%s); retrying without MarkdownV2", exc)
        await query.edit_message_text(
            text=text.replace("\\", ""), reply_markup=keyboard,
        )


async def _show_sub_list(query: Any, nav: NavAction, lang: str = "it") -> None:
    parent_ti = registry.get_type(nav.type_name)
    if parent_ti is None:
        await _send_error(query, translator.t("wiki.error_unknown_type", lang=lang), lang=lang)
        return

    actual_parent = parent_ti
    if parent_ti.detail_query_field is None:
        union_parent = _find_union_parent(nav.type_name)
        if union_parent:
            actual_parent = union_parent

    q = build_sub_list_query(
        actual_parent, nav.field, registry,
        concrete_type=nav.concrete_type or (
            nav.type_name if actual_parent.name != nav.type_name else ""
        ),
    )
    data = await dnd_client.execute(q, {"index": nav.index})

    root_data = data.get(actual_parent.detail_query_field, {})
    all_items: list[dict] = root_data.get(nav.field, [])

    page = nav.page
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    display = all_items[start:end]
    has_next = end < len(all_items)

    if not display:
        await _send_error(query, translator.t("wiki.no_items", lang=lang), lang=lang)
        return

    fi = (parent_ti.fields if parent_ti.kind != "UNION" else {}).get(nav.field)
    sub_type_name = fi.type_name if fi else ""

    nice_label = nav.field.replace("_", " ").title()
    page_info = translator.t("wiki.page_info", lang=lang, page=page + 1) if has_next or page > 0 else ""
    header = (
        f"📂 *{_esc(nice_label)}*{_esc(page_info)}\n\n"
        + translator.t("wiki.select_item", lang=lang)
    )

    keyboard = build_sub_list_keyboard(
        display,
        sub_type_name,
        page,
        has_next,
        parent_type=nav.type_name,
        parent_index=nav.index,
        field_name=nav.field,
        parent_concrete=nav.concrete_type,
        lang=lang,
    )
    await query.edit_message_text(
        text=header, reply_markup=keyboard, parse_mode="MarkdownV2",
    )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

async def _send_error(query: Any, message: str, lang: str = "it") -> None:
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(text=translator.t("nav.menu", lang=lang), callback_data=NavAction("menu"))]]
    )
    try:
        await query.edit_message_text(
            text=f"⚠️ {_esc(message)}", reply_markup=keyboard,
            parse_mode="MarkdownV2",
        )
    except BadRequest:
        await query.edit_message_text(
            text=f"⚠️ {message}", reply_markup=keyboard,
        )


def _emoji_for(type_name: str) -> str:
    for mc in MENU_CATEGORIES:
        if mc.type_name == type_name:
            return mc.emoji
    return "📋"


def _label_for(type_name: str) -> str:
    for mc in MENU_CATEGORIES:
        if mc.type_name == type_name:
            return mc.label
    return type_name


def _find_union_parent(concrete_type_name: str):
    """Find the union TypeInfo that contains *concrete_type_name*."""
    for ti in registry.get_all_types().values():
        if ti.kind == "UNION" and concrete_type_name in ti.possible_types:
            if ti.detail_query_field:
                return ti
    return None
