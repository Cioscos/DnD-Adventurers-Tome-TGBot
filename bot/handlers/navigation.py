"""Inline-keyboard callback-query navigation handlers.

Routes ``callback_data`` actions to the appropriate logic:
- ``cat:<key>:<page>`` → show paginated item list
- ``itm:<key>:<index>`` → show item detail
- ``back:main``         → return to top-level categories
- ``noop``              → answer with no action
"""

from __future__ import annotations

import logging
import re
from typing import Any

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from bot.api.client import APIError, dnd_client
from bot.keyboards.builder import (
    PAGE_SIZE,
    build_categories_keyboard,
    build_detail_keyboard,
    build_list_keyboard,
)
from bot.models.state import CATEGORIES, parse_callback

logger = logging.getLogger(__name__)

# Characters that must be escaped in Telegram MarkdownV2
_MD2_ESCAPE_RE = re.compile(r"([_*\[\]()~`>#+\-=|{}.!\\])")


def _esc(text: Any) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    return _MD2_ESCAPE_RE.sub(r"\\\1", str(text))


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

    data = query.data or ""
    parsed = parse_callback(data)

    try:
        if parsed.action == "noop":
            return

        if parsed.action == "back" and parsed.category == "main":
            await _show_main_menu(query)
            return

        if parsed.action == "cat" and parsed.category:
            page = int(parsed.payload) if parsed.payload else 0
            await _show_item_list(query, parsed.category, page)
            return

        if parsed.action == "itm" and parsed.category and parsed.payload:
            await _show_item_detail(query, parsed.category, parsed.payload)
            return

        logger.warning("Unhandled callback_data: %s", data)

    except APIError as exc:
        await _send_error(query, str(exc))
    except BadRequest as exc:
        logger.error("Telegram BadRequest: %s (data=%s)", exc, data)
    except Exception:
        logger.exception("Unexpected error handling callback_data=%s", data)
        await _send_error(query, "An unexpected error occurred. Please try /start again.")


# ------------------------------------------------------------------
# Action handlers
# ------------------------------------------------------------------

async def _show_main_menu(query: Any) -> None:
    """Edit the message to show the top-level category keyboard."""
    keyboard = build_categories_keyboard()
    await query.edit_message_text(
        text="🎲 *D&D 5e Explorer*\n\nChoose a category:",
        reply_markup=keyboard,
        parse_mode="MarkdownV2",
    )


async def _show_item_list(query: Any, category_key: str, page: int) -> None:
    """Fetch and display a paginated list of items for a category."""
    cat = CATEGORIES.get(category_key)
    if cat is None:
        await _send_error(query, "Unknown category.")
        return

    if cat.paginated:
        # Fetch one extra item to detect next page
        items = await dnd_client.fetch_list(
            cat.list_query, cat.list_field,
            skip=page * PAGE_SIZE, limit=PAGE_SIZE + 1,
            paginated=True,
        )
        has_next = len(items) > PAGE_SIZE
        display_items = items[:PAGE_SIZE]
    else:
        items = await dnd_client.fetch_list(
            cat.list_query, cat.list_field, paginated=False,
        )
        has_next = False
        display_items = items

    if not display_items:
        await _send_error(query, "No items found in this category.")
        return

    keyboard = build_list_keyboard(display_items, cat, page, has_next)

    page_info = f" — Page {page + 1}" if cat.paginated else ""
    header = f"{cat.emoji} *{_esc(cat.label)}*{_esc(page_info)}\n\nSelect an item:"

    await query.edit_message_text(
        text=header,
        reply_markup=keyboard,
        parse_mode="MarkdownV2",
    )


async def _show_item_detail(
    query: Any, category_key: str, index: str
) -> None:
    """Fetch and display the full detail of an item."""
    cat = CATEGORIES.get(category_key)
    if cat is None:
        await _send_error(query, "Unknown category.")
        return

    item = await dnd_client.fetch_detail(cat.detail_query, cat.detail_field, index)

    text = _format_detail(category_key, item)

    # Determine the page the user came from (stored via context is
    # not available here, so we default to page 0 — could be enhanced).
    keyboard = build_detail_keyboard(category_key)

    try:
        await query.edit_message_text(
            text=text,
            reply_markup=keyboard,
            parse_mode="MarkdownV2",
        )
    except BadRequest:
        # If MarkdownV2 fails (rare edge case), fall back to plain text
        await query.edit_message_text(
            text=text.replace("\\", ""),
            reply_markup=keyboard,
        )


async def _send_error(query: Any, message: str) -> None:
    """Show an error message with a Menu button."""
    from bot.models.state import BACK_TO_MAIN
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(text="🏠 Menu", callback_data=BACK_TO_MAIN)]]
    )
    try:
        await query.edit_message_text(
            text=f"⚠️ {_esc(message)}",
            reply_markup=keyboard,
            parse_mode="MarkdownV2",
        )
    except BadRequest:
        await query.edit_message_text(text=f"⚠️ {message}", reply_markup=keyboard)


# ------------------------------------------------------------------
# Detail formatters
# ------------------------------------------------------------------

def _format_detail(category_key: str, item: dict[str, Any]) -> str:
    """Dispatch to the appropriate detail formatter."""
    formatter = _FORMATTERS.get(category_key, _format_generic)
    return formatter(item)


def _format_spell(item: dict[str, Any]) -> str:
    name = _esc(item.get("name", "Unknown"))
    level = item.get("level", 0)
    level_str = "Cantrip" if level == 0 else f"Level {level}"
    school = _esc(item.get("school", {}).get("name", ""))
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
        dmg_type = damage.get("damage_type", {}).get("name", "")
        if dmg_type:
            lines.append(f"\n*Damage Type:* {_esc(dmg_type)}")
        slots = damage.get("damage_at_slot_level", [])
        if slots:
            slot_str = ", ".join(
                f"Lvl {s['level']}: {s['damage']}" for s in slots[:5]
            )
            lines.append(f"*Damage by Slot:* {_esc(slot_str)}")

    classes = [c["name"] for c in item.get("classes", [])]
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

    # Core stats
    ac_list = item.get("armor_class", [])
    ac_str = ", ".join(str(a.get("value", "?")) for a in ac_list) if ac_list else "?"
    lines.append(f"*AC:* {_esc(ac_str)}  |  *HP:* {_esc(item.get('hit_points', '?'))} \\({_esc(item.get('hit_dice', ''))}\\)")

    cr = item.get("challenge_rating", "?")
    xp = item.get("xp", "?")
    lines.append(f"*CR:* {_esc(f'{cr:g}' if isinstance(cr, float) else str(cr))}  |  *XP:* {_esc(str(xp))}")

    # Ability scores
    abilities = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]
    abbr = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
    scores = " | ".join(f"{a} {_esc(str(item.get(ab, '—')))}" for a, ab in zip(abbr, abilities))
    lines.append(f"\n{scores}")

    # Speed
    speed = item.get("speed", {})
    if speed:
        parts = [f"{k} {v}" for k, v in speed.items() if v]
        if parts:
            lines.append(f"\n*Speed:* {_esc(', '.join(parts))}")

    # Senses
    senses = item.get("senses", {})
    if senses:
        sense_parts = [f"{k.replace('_', ' ')}: {v}" for k, v in senses.items() if v]
        if sense_parts:
            lines.append(f"*Senses:* {_esc(', '.join(sense_parts))}")

    # Languages
    if item.get("languages"):
        lines.append(f"*Languages:* {_esc(item['languages'])}")

    # Special abilities
    for sa in item.get("special_abilities", []) or []:
        desc_text = (sa.get("desc", "") or "")[:300]
        lines.append(f"\n⭐ *{_esc(sa.get('name', ''))}:* {_esc(desc_text)}")

    # Actions (first 3 to keep message manageable)
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
    saves = [s["name"] for s in item.get("saving_throws", []) or []]
    if saves:
        lines.append(f"*Saving Throws:* {_esc(', '.join(saves))}")

    profs = [p["name"] for p in item.get("proficiencies", []) or []]
    if profs:
        lines.append(f"*Proficiencies:* {_esc(', '.join(profs))}")

    sc = item.get("spellcasting")
    if sc:
        ability = sc.get("spellcasting_ability", {}).get("name", "")
        lines.append(f"\n*Spellcasting Ability:* {_esc(ability)}")

    subclasses = [s["name"] for s in item.get("subclasses", []) or []]
    if subclasses:
        lines.append(f"\n*Subclasses:* {_esc(', '.join(subclasses))}")

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
        parts = [f"{b.get('ability_score', {}).get('name', '?')} +{b.get('bonus', 0)}" for b in bonuses]
        lines.append(f"*Ability Bonuses:* {_esc(', '.join(parts))}")

    langs = [l["name"] for l in item.get("languages", []) or []]
    if langs:
        lines.append(f"*Languages:* {_esc(', '.join(langs))}")

    traits = [t["name"] for t in item.get("traits", []) or []]
    if traits:
        lines.append(f"*Traits:* {_esc(', '.join(traits))}")

    subraces = [s["name"] for s in item.get("subraces", []) or []]
    if subraces:
        lines.append(f"*Subraces:* {_esc(', '.join(subraces))}")

    return "\n".join(lines)


def _format_equipment(item: dict[str, Any]) -> str:
    name = _esc(item.get("name", "Unknown"))
    cat_name = item.get("equipment_category", {}).get("name", "")
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
    text = " ".join(desc) if desc else "No description available."
    return f"🩹 *{name}*\n\n{_esc(text[:1500])}"


def _format_magic_item(item: dict[str, Any]) -> str:
    name = _esc(item.get("name", "Unknown"))
    rarity = item.get("rarity", {}).get("name", "")
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
        parts = [f"{p.get('ability_score', {}).get('name', '?')} ≥ {p.get('minimum_score', '?')}" for p in prereqs]
        lines.append(f"*Prerequisites:* {_esc(', '.join(parts))}\n")

    if desc:
        lines.append(_esc(" ".join(desc)[:1500]))

    return "\n".join(lines)


def _format_rule(item: dict[str, Any]) -> str:
    name = _esc(item.get("name", "Unknown"))
    desc = item.get("desc", "")
    if isinstance(desc, list):
        desc = " ".join(desc)
    # Rules can be very long — truncate
    return f"📖 *{name}*\n\n{_esc(desc[:2000])}"


def _format_background(item: dict[str, Any]) -> str:
    name = _esc(item.get("name", "Unknown"))
    lines = [f"📜 *{name}*\n"]

    profs = [p["name"] for p in item.get("starting_proficiencies", []) or []]
    if profs:
        lines.append(f"*Starting Proficiencies:* {_esc(', '.join(profs))}")

    equip = item.get("starting_equipment", []) or []
    if equip:
        parts = [f"{e.get('equipment', {}).get('name', '?')} ×{e.get('quantity', 1)}" for e in equip]
        lines.append(f"*Starting Equipment:* {_esc(', '.join(parts))}")

    feature = item.get("feature", {})
    if feature:
        lines.append(f"\n⭐ *{_esc(feature.get('name', ''))}*")
        feat_desc = feature.get("desc", [])
        if feat_desc:
            lines.append(_esc(" ".join(feat_desc)[:800]))

    return "\n".join(lines)


def _format_weapon_property(item: dict[str, Any]) -> str:
    name = _esc(item.get("name", "Unknown"))
    desc = item.get("desc", [])
    text = " ".join(desc) if isinstance(desc, list) else (desc or "")
    return f"🗡️ *{name}*\n\n{_esc(text[:1500])}"


def _format_generic(item: dict[str, Any]) -> str:
    """Fallback formatter for unknown categories."""
    name = _esc(item.get("name", "Unknown"))
    desc = item.get("desc", [])
    if isinstance(desc, list):
        desc = " ".join(desc)
    return f"*{name}*\n\n{_esc(str(desc)[:1500])}"


# Formatter dispatch table
_FORMATTERS: dict[str, Any] = {
    "spells": _format_spell,
    "monsters": _format_monster,
    "classes": _format_class,
    "races": _format_race,
    "equipment": _format_equipment,
    "conditions": _format_condition,
    "magicitems": _format_magic_item,
    "feats": _format_feat,
    "rules": _format_rule,
    "backgrounds": _format_background,
    "weaponprops": _format_weapon_property,
}
