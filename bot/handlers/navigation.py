"""Inline-keyboard callback-query navigation handlers.

Routes :class:`~bot.models.state.NavAction` objects to the appropriate
view logic.  Supports N-level deep navigation: categories → items →
sub-entity lists → sub-item details → …
"""

from __future__ import annotations

import logging
import re
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes, InvalidCallbackData

from bot.api.client import APIError, dnd_client
from bot.api.query_builder import (
    build_detail_query,
    build_list_query,
    build_sub_list_query,
)
from bot.keyboards.builder import (
    PAGE_SIZE,
    build_categories_keyboard,
    build_detail_keyboard,
    build_list_keyboard,
    build_sub_list_keyboard,
)
from bot.models.state import NavAction, make_back
from bot.schema.registry import MENU_CATEGORIES, registry
from bot.utils.i18n import get_lang, translator

logger = logging.getLogger(__name__)

_MD2_ESCAPE_RE = re.compile(r"([_*\[\]()~`>#+\-=|{}.!\\])")


def _esc(text: Any) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    return _MD2_ESCAPE_RE.sub(r"\\\1", str(text))


# Patterns used by _md_to_telegram to convert API Markdown → MarkdownV2
_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_MD_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def _md_to_telegram(text: str) -> str:
    """Convert API Markdown (headings, bold) to Telegram MarkdownV2.

    The D&D 5e API returns ``desc`` for Rule / RuleSection types in
    Markdown format.  Telegram MarkdownV2 does *not* support ``#``
    headings, so we convert them to bold lines and escape the rest.
    """
    lines: list[str] = []
    for line in text.split("\n"):
        heading = _MD_HEADING_RE.match(line)
        if heading:
            # Convert # Heading → bold line with separator
            title = heading.group(2).strip()
            lines.append(f"*{_esc(title)}*")
            continue

        # Handle **bold** spans before escaping
        parts: list[str] = []
        last = 0
        for m in _MD_BOLD_RE.finditer(line):
            # Escape text before the bold span
            parts.append(_esc(line[last:m.start()]))
            parts.append(f"*{_esc(m.group(1))}*")
            last = m.end()
        parts.append(_esc(line[last:]))
        lines.append("".join(parts))

    return "\n".join(lines)


# ------------------------------------------------------------------
# Main dispatcher
# ------------------------------------------------------------------

async def navigation_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle all inline-keyboard button presses."""
    query = update.callback_query
    if query is None:
        return

    await query.answer()
    data = query.data
    lang = get_lang(update)

    # Handle expired/invalid callback data from the LRU cache
    if isinstance(data, InvalidCallbackData):
        await _send_error(query, translator.t("wiki.error_session_expired", lang=lang), lang=lang)
        return

    if not isinstance(data, NavAction):
        # Legacy string callbacks or unexpected data
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
# Menu
# ------------------------------------------------------------------

async def _show_main_menu(query: Any, lang: str = "it") -> None:
    from bot.handlers.start import build_main_menu_keyboard
    keyboard = build_main_menu_keyboard(lang=lang)
    await query.edit_message_text(
        text=translator.t("start.welcome", lang=lang),
        reply_markup=keyboard,
        parse_mode="MarkdownV2",
    )


async def _show_wiki_categories(query: Any, lang: str = "it") -> None:
    keyboard = build_categories_keyboard(lang=lang)
    await query.edit_message_text(
        text=translator.t("wiki.categories_title", lang=lang),
        reply_markup=keyboard,
        parse_mode="MarkdownV2",
    )


# ------------------------------------------------------------------
# Category item list
# ------------------------------------------------------------------

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


# ------------------------------------------------------------------
# Item detail
# ------------------------------------------------------------------

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

    text = _format_detail(concrete or fetch_type_name, item)
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
    except BadRequest:
        await query.edit_message_text(
            text=text.replace("\\", ""), reply_markup=keyboard,
        )


# ------------------------------------------------------------------
# Sub-list (navigable field drill-down)
# ------------------------------------------------------------------

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
# Error helper
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


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

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


# ------------------------------------------------------------------
# Detail formatters
# ------------------------------------------------------------------

def _format_detail(type_name: str, item: dict[str, Any]) -> str:
    formatter = _FORMATTERS.get(type_name, _format_generic)
    return formatter(item)


def _format_spell(item: dict[str, Any]) -> str:
    name = _esc(item.get("name", "Unknown"))
    level = item.get("level", 0)
    level_str = "Cantrip" if level == 0 else f"Level {level}"
    school = _esc((item.get("school") or {}).get("name", ""))
    lines = [
        f"🔮 *{name}*",
        f"_{_esc(level_str)} {school}_\n",
        f"*Casting Time:* {_esc(item.get('casting_time', '—'))}",
        f"*Range:* {_esc(item.get('range', '—'))}",
        f"*Duration:* {_esc(item.get('duration', '—'))}",
        f"*Components:* {_esc(', '.join(item.get('components', [])))}",
    ]
    if item.get("material"):
        lines.append(f"*Material:* {_esc(item['material'])}")
    if item.get("concentration"):
        lines.append("*Concentration:* Yes")
    if item.get("ritual"):
        lines.append("*Ritual:* Yes")

    desc = item.get("desc", [])
    if desc:
        lines.append(f"\n{_esc(' '.join(desc))}")

    higher = item.get("higher_level", [])
    if higher:
        lines.append(f"\n*At Higher Levels:* {_esc(' '.join(higher))}")

    damage = item.get("damage")
    if damage:
        dmg_type = (damage.get("damage_type") or {}).get("name", "")
        if dmg_type:
            lines.append(f"\n*Damage Type:* {_esc(dmg_type)}")
        slots = damage.get("damage_at_slot_level", [])
        if slots:
            slot_str = ", ".join(f"Lvl {s['level']}: {s['value']}" for s in slots[:5])
            lines.append(f"*Damage by Slot:* {_esc(slot_str)}")

    classes = [c["name"] for c in item.get("classes", []) if "name" in c]
    if classes:
        lines.append(f"\n*Classes:* {_esc(', '.join(classes))}")

    return "\n".join(lines)


def _format_monster(item: dict[str, Any]) -> str:
    name = _esc(item.get("name", "Unknown"))
    lines = [
        f"🐉 *{name}*",
        f"_{_esc(item.get('size', ''))} {_esc(item.get('type', ''))}"
        + (f" \\({_esc(item.get('subtype', ''))}\\)" if item.get("subtype") else "")
        + f", {_esc(item.get('alignment', ''))}_\n",
    ]

    ac_list = item.get("armor_class", [])
    ac_str = ", ".join(str(a.get("value", "?")) for a in ac_list) if ac_list else "?"
    lines.append(
        f"*AC:* {_esc(ac_str)}  |  *HP:* {_esc(item.get('hit_points', '?'))} "
        f"\\({_esc(item.get('hit_dice', ''))}\\)"
    )

    cr = item.get("challenge_rating", "?")
    xp = item.get("xp", "?")
    lines.append(
        f"*CR:* {_esc(f'{cr:g}' if isinstance(cr, float) else str(cr))}  "
        f"|  *XP:* {_esc(str(xp))}"
    )

    abilities = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]
    abbr = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
    scores = " | ".join(f"{a} {_esc(str(item.get(ab, '—')))}" for a, ab in zip(abbr, abilities))
    lines.append(f"\n{scores}")

    speed = item.get("speed", {})
    if speed:
        parts = [f"{k} {v}" for k, v in speed.items() if v]
        if parts:
            lines.append(f"\n*Speed:* {_esc(', '.join(parts))}")

    senses = item.get("senses", {})
    if senses:
        sense_parts = [f"{k.replace('_', ' ')}: {v}" for k, v in senses.items() if v]
        if sense_parts:
            lines.append(f"*Senses:* {_esc(', '.join(sense_parts))}")

    if item.get("languages"):
        lines.append(f"*Languages:* {_esc(item['languages'])}")

    for sa in item.get("special_abilities", []) or []:
        desc_text = (sa.get("desc", "") or "")[:300]
        lines.append(f"\n⭐ *{_esc(sa.get('name', ''))}:* {_esc(desc_text)}")

    actions = (item.get("actions", []) or [])[:3]
    if actions:
        lines.append("\n*Actions:*")
        for act in actions:
            desc_text = (act.get("desc", "") or "")[:200]
            lines.append(f"• *{_esc(act.get('name', ''))}:* {_esc(desc_text)}")

    return "\n".join(lines)


def _format_class(item: dict[str, Any]) -> str:
    name = _esc(item.get("name", "Unknown"))
    lines = [
        f"⚔️ *{name}*\n",
        f"*Hit Die:* d{_esc(str(item.get('hit_die', '?')))}",
    ]
    saves = [s["name"] for s in item.get("saving_throws", []) or [] if "name" in s]
    if saves:
        lines.append(f"*Saving Throws:* {_esc(', '.join(saves))}")

    profs = [p["name"] for p in item.get("proficiencies", []) or [] if "name" in p]
    if profs:
        lines.append(f"*Proficiencies:* {_esc(', '.join(profs))}")

    sc = item.get("spellcasting")
    if sc:
        ability = (sc.get("spellcasting_ability") or {}).get("name", "")
        lines.append(f"\n*Spellcasting Ability:* {_esc(ability)}")

    return "\n".join(lines)


def _format_race(item: dict[str, Any]) -> str:
    name = _esc(item.get("name", "Unknown"))
    lines = [
        f"🧝 *{name}*\n",
        f"*Speed:* {_esc(str(item.get('speed', '?')))} ft",
        f"*Size:* {_esc(item.get('size', '?'))}",
    ]
    if item.get("alignment"):
        lines.append(f"*Alignment:* {_esc(item['alignment'][:200])}")
    if item.get("age"):
        lines.append(f"*Age:* {_esc(item['age'][:200])}")

    bonuses = item.get("ability_bonuses", []) or []
    if bonuses:
        parts = [
            f"{b.get('ability_score', {}).get('name', '?')} +{b.get('bonus', 0)}"
            for b in bonuses
        ]
        lines.append(f"*Ability Bonuses:* {_esc(', '.join(parts))}")

    langs = [la["name"] for la in item.get("languages", []) or [] if "name" in la]
    if langs:
        lines.append(f"*Languages:* {_esc(', '.join(langs))}")

    traits = [t["name"] for t in item.get("traits", []) or [] if "name" in t]
    if traits:
        lines.append(f"*Traits:* {_esc(', '.join(traits))}")

    return "\n".join(lines)


def _format_equipment(item: dict[str, Any]) -> str:
    name = _esc(item.get("name", "Unknown"))
    cat_name = (item.get("equipment_category") or {}).get("name", "")
    lines = [f"🎒 *{name}*"]
    if cat_name:
        lines.append(f"_{_esc(cat_name)}_\n")
    cost = item.get("cost", {})
    if cost:
        lines.append(f"*Cost:* {_esc(str(cost.get('quantity', '?')))} {_esc(cost.get('unit', ''))}")
    if item.get("weight"):
        lines.append(f"*Weight:* {_esc(str(item['weight']))} lb")
    desc = item.get("desc", [])
    if desc:
        lines.append(f"\n{_esc(' '.join(desc)[:500])}")
    return "\n".join(lines)


def _format_condition(item: dict[str, Any]) -> str:
    name = _esc(item.get("name", "Unknown"))
    desc = item.get("desc", [])
    text = " ".join(desc) if isinstance(desc, list) else str(desc or "")
    return f"🩹 *{name}*\n\n{_esc(text[:1500])}"


def _format_magic_item(item: dict[str, Any]) -> str:
    name = _esc(item.get("name", "Unknown"))
    rarity = (item.get("rarity") or {}).get("name", "")
    lines = [f"✨ *{name}*"]
    if rarity:
        lines.append(f"_{_esc(rarity)}_\n")
    desc = item.get("desc", [])
    if desc:
        lines.append(_esc(" ".join(desc)[:1500]))
    return "\n".join(lines)


def _format_feat(item: dict[str, Any]) -> str:
    name = _esc(item.get("name", "Unknown"))
    desc = item.get("desc", [])
    lines = [f"💪 *{name}*\n"]
    prereqs = item.get("prerequisites", []) or []
    if prereqs:
        parts = [
            f"{p.get('ability_score', {}).get('name', '?')} ≥ {p.get('minimum_score', '?')}"
            for p in prereqs
            if isinstance(p, dict) and "ability_score" in p
        ]
        if parts:
            lines.append(f"*Prerequisites:* {_esc(', '.join(parts))}\n")
    if desc:
        lines.append(_esc(" ".join(desc)[:1500]))
    return "\n".join(lines)


def _format_rule(item: dict[str, Any]) -> str:
    name = _esc(item.get("name", "Unknown"))
    desc = item.get("desc", "")
    if isinstance(desc, list):
        desc = "\n".join(desc)
    return f"📖 *{name}*\n\n{_md_to_telegram(desc[:2000])}"


def _format_rule_section(item: dict[str, Any]) -> str:
    name = _esc(item.get("name", "Unknown"))
    desc = item.get("desc", "")
    if isinstance(desc, list):
        desc = "\n".join(desc)
    return f"📖 *{name}*\n\n{_md_to_telegram(desc[:3000])}"


def _format_background(item: dict[str, Any]) -> str:
    name = _esc(item.get("name", "Unknown"))
    lines = [f"📜 *{name}*\n"]
    profs = [p["name"] for p in item.get("starting_proficiencies", []) or [] if "name" in p]
    if profs:
        lines.append(f"*Starting Proficiencies:* {_esc(', '.join(profs))}")
    equip = item.get("starting_equipment", []) or []
    if equip:
        parts = [
            f"{e.get('equipment', {}).get('name', '?')} ×{e.get('quantity', 1)}"
            for e in equip
        ]
        lines.append(f"*Starting Equipment:* {_esc(', '.join(parts))}")
    feature = item.get("feature", {})
    if feature:
        lines.append(f"\n⭐ *{_esc(feature.get('name', ''))}*")
        feat_desc = feature.get("desc", [])
        if feat_desc:
            text = " ".join(feat_desc) if isinstance(feat_desc, list) else str(feat_desc)
            lines.append(_esc(text[:800]))
    return "\n".join(lines)


def _format_weapon_property(item: dict[str, Any]) -> str:
    name = _esc(item.get("name", "Unknown"))
    desc = item.get("desc", [])
    text = " ".join(desc) if isinstance(desc, list) else (desc or "")
    return f"🗡️ *{name}*\n\n{_esc(text[:1500])}"


def _format_generic(item: dict[str, Any]) -> str:
    """Generic formatter for types without a custom formatter.

    Shows the item name as a header, then all scalar fields as
    ``*Key:* value`` pairs, and any list-of-string fields inline.
    """
    name = _esc(item.get("name", "Unknown"))
    lines = [f"📋 *{name}*\n"]

    # Collect desc separately to show at the bottom
    desc_text = ""
    for key, value in item.items():
        if key in ("index", "name", "__typename", "updated_at"):
            continue

        if key == "desc":
            if isinstance(value, list):
                desc_text = " ".join(str(v) for v in value)
            else:
                desc_text = str(value or "")
            continue

        nice_key = key.replace("_", " ").title()

        if isinstance(value, (str, int, float, bool)):
            lines.append(f"*{_esc(nice_key)}:* {_esc(str(value))}")
        elif isinstance(value, list):
            if not value:
                continue
            if isinstance(value[0], str):
                lines.append(f"*{_esc(nice_key)}:* {_esc(', '.join(value))}")
            elif isinstance(value[0], dict):
                # List of objects — show names if available
                names = [v.get("name", v.get("index", "")) for v in value if isinstance(v, dict)]
                names = [n for n in names if n]
                if names:
                    lines.append(f"*{_esc(nice_key)}:* {_esc(', '.join(names[:20]))}")
        elif isinstance(value, dict):
            # Single object — show its name or first string value
            obj_name = value.get("name", "")
            if obj_name:
                lines.append(f"*{_esc(nice_key)}:* {_esc(obj_name)}")

    if desc_text:
        lines.append(f"\n{_esc(desc_text[:1500])}")

    return "\n".join(lines)


# Formatter dispatch table (by GraphQL type name)
_FORMATTERS: dict[str, Any] = {
    "Spell": _format_spell,
    "Monster": _format_monster,
    "Class": _format_class,
    "Race": _format_race,
    "Gear": _format_equipment,
    "Weapon": _format_equipment,
    "Armor": _format_equipment,
    "Tool": _format_equipment,
    "Pack": _format_equipment,
    "Ammunition": _format_equipment,
    "Vehicle": _format_equipment,
    "Condition": _format_condition,
    "MagicItem": _format_magic_item,
    "Feat": _format_feat,
    "Rule": _format_rule,
    "RuleSection": _format_rule_section,
    "Background": _format_background,
    "WeaponProperty": _format_weapon_property,
}
