"""Inventory (bag) management handler — supports typed items (weapon, armor, shield, consumable, tool)."""

from __future__ import annotations

import json
import logging
import re

from sqlalchemy import delete, select
from telegram import Update
from telegram.ext import ContextTypes

from bot.db.engine import get_session
from bot.db.models import Character, Item
from bot.handlers.character import (
    CHAR_BAG_ADD_AC_VALUE,
    CHAR_BAG_ADD_DAMAGE_DICE,
    CHAR_BAG_ADD_EFFECT,
    CHAR_BAG_ADD_INLINE,
    CHAR_BAG_ADD_NAME,
    CHAR_BAG_ADD_QTY,
    CHAR_BAG_ADD_STR_REQ,
    CHAR_BAG_ADD_TOOL_TYPE,
    CHAR_BAG_ADD_WEIGHT,
    CHAR_BAG_MENU,
    CHAR_MENU,
)
from bot.keyboards.character import (
    build_armor_type_keyboard,
    build_cancel_keyboard,
    build_bag_keyboard,
    build_damage_type_keyboard,
    build_item_detail_keyboard,
    build_item_type_keyboard,
    build_stealth_keyboard,
    build_weapon_properties_keyboard,
    build_weapon_type_keyboard,
)
from bot.utils.formatting import format_bag, format_item_detail
from bot.utils.i18n import get_lang, translator

logger = logging.getLogger(__name__)

_OP_KEY = "char_bag_pending"

# ---------------------------------------------------------------------------
# Bag menu
# ---------------------------------------------------------------------------

async def show_bag_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int, page: int = 0
) -> int:
    lang = get_lang(update)
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU
        result = await session.execute(
            select(Item).where(Item.character_id == char_id).order_by(Item.name)
        )
        items = list(result.scalars().all())

    keyboard = build_bag_keyboard(char_id, items, page, lang=lang)
    text = format_bag(items, char.carry_capacity, char.encumbrance, lang=lang)
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
        item_data = {
            "id": item.id,
            "name": item.name,
            "description": item.description,
            "weight": item.weight,
            "quantity": item.quantity,
            "item_type": item.item_type or "generic",
            "item_metadata": json.loads(item.item_metadata) if item.item_metadata else {},
            "is_equipped": item.is_equipped,
        }

    lang = get_lang(update)
    text = format_item_detail(item_data, lang=lang)
    keyboard = build_item_detail_keyboard(
        char_id, item_id,
        item_type=item_data["item_type"],
        is_equipped=item_data["is_equipped"],
        back_page=back_page,
        lang=lang,
    )
    await _edit_or_reply(update, text, keyboard)
    return CHAR_BAG_MENU

# ---------------------------------------------------------------------------
# Add-item flow — step 1: type selection (inline)
# ---------------------------------------------------------------------------

async def ask_add_item(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    lang = get_lang(update)
    context.user_data[_OP_KEY] = {"char_id": char_id, "step": "type"}
    await _edit_or_reply(
        update,
        translator.t("character.bag.prompt_type", lang=lang),
        build_item_type_keyboard(char_id, lang=lang),
    )
    return CHAR_BAG_ADD_INLINE


async def handle_bag_add_inline(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle all inline-only steps of the add-item flow."""
    if update.callback_query is None:
        return CHAR_BAG_MENU
    await update.callback_query.answer()

    lang = get_lang(update)
    pending = context.user_data.get(_OP_KEY, {})
    char_id: int = pending.get("char_id", 0)
    step: str = pending.get("step", "type")
    data = update.callback_query.data

    # ── Type selection ──
    if step == "type":
        if not (hasattr(data, "sub") and data.sub == "select_type"):
            # User hit cancel / back
            context.user_data.pop(_OP_KEY, None)
            return await show_bag_menu(update, context, char_id)
        item_type = data.extra
        context.user_data[_OP_KEY]["item_type"] = item_type
        return await _ask_name(update, context, char_id, lang)

    # ── Weapon: damage type ──
    if step == "damage_type":
        if not (hasattr(data, "sub") and data.sub == "set_damage_type"):
            context.user_data.pop(_OP_KEY, None)
            return await show_bag_menu(update, context, char_id)
        context.user_data[_OP_KEY]["damage_type"] = data.extra
        return await _ask_weapon_type(update, context, char_id, lang)

    # ── Weapon: melee / ranged ──
    if step == "weapon_type":
        if not (hasattr(data, "sub") and data.sub == "set_weapon_type"):
            context.user_data.pop(_OP_KEY, None)
            return await show_bag_menu(update, context, char_id)
        context.user_data[_OP_KEY]["weapon_type"] = data.extra
        context.user_data[_OP_KEY]["properties"] = []
        return await _ask_properties(update, context, char_id, lang)

    # ── Weapon: property multi-select toggle ──
    if step == "properties":
        if hasattr(data, "sub") and data.sub == "toggle_prop":
            props: list[str] = context.user_data[_OP_KEY].get("properties", [])
            key = data.extra
            if key in props:
                props.remove(key)
            else:
                props.append(key)
            context.user_data[_OP_KEY]["properties"] = props
            await update.callback_query.edit_message_text(
                translator.t("character.bag.prompt_properties", lang=lang),
                reply_markup=build_weapon_properties_keyboard(char_id, props, lang=lang),
                parse_mode="MarkdownV2",
            )
            return CHAR_BAG_ADD_INLINE
        if hasattr(data, "sub") and data.sub == "confirm_props":
            return await _ask_weight(update, context, char_id, lang)
        # Cancel
        context.user_data.pop(_OP_KEY, None)
        return await show_bag_menu(update, context, char_id)

    # ── Armor: armor type ──
    if step == "armor_type":
        if not (hasattr(data, "sub") and data.sub == "set_armor_type"):
            context.user_data.pop(_OP_KEY, None)
            return await show_bag_menu(update, context, char_id)
        context.user_data[_OP_KEY]["armor_type"] = data.extra
        return await _ask_ac_value(update, context, char_id, lang)

    # ── Armor: stealth disadvantage ──
    if step == "stealth":
        if not (hasattr(data, "sub") and data.sub == "set_stealth"):
            context.user_data.pop(_OP_KEY, None)
            return await show_bag_menu(update, context, char_id)
        context.user_data[_OP_KEY]["stealth_disadvantage"] = (data.extra == "yes")
        return await _ask_str_req(update, context, char_id, lang)

    context.user_data.pop(_OP_KEY, None)
    return await show_bag_menu(update, context, char_id)


# ---------------------------------------------------------------------------
# Add-item flow — text input steps
# ---------------------------------------------------------------------------

async def handle_bag_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if update.message is None:
        return CHAR_BAG_MENU

    lang = get_lang(update)
    pending = context.user_data.get(_OP_KEY, {})
    char_id: int = pending.get("char_id", 0)
    step: str = pending.get("step", "name")
    text = update.message.text.strip()

    if step == "name":
        if not text:
            await update.message.reply_text(
                translator.t("character.bag.name_invalid", lang=lang),
                parse_mode="MarkdownV2",
            )
            return CHAR_BAG_ADD_NAME
        context.user_data[_OP_KEY]["item_name"] = text
        item_type = pending.get("item_type", "generic")
        return await _route_after_name(update, context, char_id, item_type, lang)

    if step == "damage_dice":
        # Accept free text like "1d8", "2d6+3", or "-" to skip
        if text != "-" and not re.match(r"^\d+d\d+([+-]\d+)?$", text, re.IGNORECASE):
            await update.message.reply_text(
                translator.t("character.bag.damage_dice_invalid", lang=lang),
                parse_mode="MarkdownV2",
            )
            return CHAR_BAG_ADD_DAMAGE_DICE
        context.user_data[_OP_KEY]["damage_dice"] = "" if text == "-" else text
        return await _ask_damage_type(update, context, char_id, lang)

    if step == "effect":
        context.user_data[_OP_KEY]["effect"] = "" if text == "-" else text
        return await _ask_weight(update, context, char_id, lang)

    if step == "ac_value":
        try:
            ac = int(text)
            if ac <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                translator.t("character.bag.ac_value_invalid", lang=lang),
                parse_mode="MarkdownV2",
            )
            return CHAR_BAG_ADD_AC_VALUE
        context.user_data[_OP_KEY]["ac_value"] = ac
        item_type = pending.get("item_type", "armor")
        if item_type == "shield":
            return await _ask_weight(update, context, char_id, lang)
        return await _ask_stealth(update, context, char_id, lang)

    if step == "str_req":
        try:
            req = int(text)
            if req < 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                translator.t("character.bag.str_req_invalid", lang=lang),
                parse_mode="MarkdownV2",
            )
            return CHAR_BAG_ADD_STR_REQ
        context.user_data[_OP_KEY]["str_req"] = req
        return await _ask_weight(update, context, char_id, lang)

    if step == "tool_type":
        context.user_data[_OP_KEY]["tool_type"] = "" if text == "-" else text
        return await _ask_weight(update, context, char_id, lang)

    if step == "weight":
        try:
            weight = float(text.replace(",", "."))
            if weight < 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                translator.t("character.bag.weight_invalid", lang=lang),
                parse_mode="MarkdownV2",
            )
            return CHAR_BAG_ADD_WEIGHT
        context.user_data[_OP_KEY]["item_weight"] = weight
        context.user_data[_OP_KEY]["step"] = "qty"
        await update.message.reply_text(
            translator.t("character.bag.prompt_qty", lang=lang),
            reply_markup=build_cancel_keyboard(char_id, "char_bag", lang=lang),
            parse_mode="MarkdownV2",
        )
        return CHAR_BAG_ADD_QTY

    if step == "qty":
        try:
            qty = int(text)
            if qty < 1:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                translator.t("character.bag.qty_invalid", lang=lang),
                parse_mode="MarkdownV2",
            )
            return CHAR_BAG_ADD_QTY
        return await _save_item(update, context, char_id, qty, lang)

    return CHAR_BAG_MENU


# ---------------------------------------------------------------------------
# Equip / Unequip
# ---------------------------------------------------------------------------

async def toggle_equip_item(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    item_id: int,
) -> int:
    """Toggle the equipped state of an item; armor/shield update character AC."""
    lang = get_lang(update)
    if update.callback_query:
        await update.callback_query.answer()

    async with get_session() as session:
        item = await session.get(Item, item_id)
        if item is None or item.character_id != char_id:
            return await show_bag_menu(update, context, char_id)

        item_type = item.item_type or "generic"
        meta = json.loads(item.item_metadata) if item.item_metadata else {}
        new_equipped = not item.is_equipped
        ac_note = ""

        if item_type == "armor":
            if new_equipped:
                # Unequip any currently equipped armor first
                result = await session.execute(
                    select(Item).where(
                        Item.character_id == char_id,
                        Item.item_type == "armor",
                        Item.is_equipped == True,  # noqa: E712
                        Item.id != item_id,
                    )
                )
                for other in result.scalars():
                    other.is_equipped = False
                # Update character base AC
                char = await session.get(Character, char_id)
                if char:
                    char.base_armor_class = meta.get("ac_value", 10)
                    ac_note = translator.t(
                        "character.bag.armor_equip_note",
                        lang=lang, ac=meta.get("ac_value", 10),
                    )
            else:
                char = await session.get(Character, char_id)
                if char:
                    char.base_armor_class = 10
                    ac_note = translator.t("character.bag.armor_unequip_note", lang=lang)

        elif item_type == "shield":
            if new_equipped:
                # Unequip any currently equipped shield first
                result = await session.execute(
                    select(Item).where(
                        Item.character_id == char_id,
                        Item.item_type == "shield",
                        Item.is_equipped == True,  # noqa: E712
                        Item.id != item_id,
                    )
                )
                for other in result.scalars():
                    other.is_equipped = False
                char = await session.get(Character, char_id)
                if char:
                    char.shield_armor_class = meta.get("ac_bonus", 2)
                    ac_note = translator.t(
                        "character.bag.shield_equip_note",
                        lang=lang, bonus=meta.get("ac_bonus", 2),
                    )
            else:
                char = await session.get(Character, char_id)
                if char:
                    char.shield_armor_class = 0
                    ac_note = translator.t("character.bag.shield_unequip_note", lang=lang)

        item.is_equipped = new_equipped
        item_name = item.name

    if new_equipped:
        msg = translator.t("character.bag.equip_done", lang=lang, name=_esc(item_name)) + ac_note
    else:
        msg = translator.t("character.bag.unequip_done", lang=lang, name=_esc(item_name)) + ac_note

    if update.callback_query:
        await update.callback_query.edit_message_text(msg, parse_mode="MarkdownV2")
    elif update.message:
        await update.message.reply_text(msg, parse_mode="MarkdownV2")

    import asyncio as _asyncio
    action_str = "Equipaggiato" if new_equipped else "De-equipaggiato"
    _asyncio.create_task(_log(char_id, "bag_change", f"{action_str}: {item_name}"))

    # Trigger party update if AC changed
    if item_type in ("armor", "shield"):
        from bot.handlers.party import maybe_update_party_message
        bot = update.get_bot()
        if bot:
            _asyncio.create_task(maybe_update_party_message(char_id, bot))

    return await show_item_detail(update, context, char_id, item_id)


# ---------------------------------------------------------------------------
# Quantity modify / remove
# ---------------------------------------------------------------------------

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
        item_name = item.name
        old_qty = item.quantity
        item.quantity += delta
        removed = item.quantity <= 0
        if removed:
            await session.delete(item)
        new_qty = max(0, item.quantity)
        char = await session.get(Character, char_id)
        if char:
            all_items_res = await session.execute(
                select(Item).where(Item.character_id == char_id)
            )
            char.encumbrance = sum(i.weight * i.quantity for i in all_items_res.scalars())

    import asyncio as _asyncio
    if removed:
        _asyncio.create_task(_log(char_id, "bag_change", f"Rimosso: {item_name}"))
    else:
        sign = "+" if delta > 0 else ""
        _asyncio.create_task(_log(char_id, "bag_change", f"{item_name}: qty {old_qty} → {new_qty} ({sign}{delta})"))
    if update.callback_query:
        await update.callback_query.answer()
    return await show_bag_menu(update, context, char_id)


async def attack_with_weapon(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    item_id: int,
) -> int:
    """Roll to-hit and damage for a weapon item."""
    import random as _random
    from sqlalchemy import select as _select
    from bot.db.models import AbilityScore, CharacterClass

    lang = get_lang(update)
    if update.callback_query:
        await update.callback_query.answer()

    async with get_session() as session:
        item = await session.get(Item, item_id)
        if item is None or item.character_id != char_id:
            return await show_bag_menu(update, context, char_id)
        if item.item_type != "weapon":
            return await show_item_detail(update, context, char_id, item_id)

        meta = json.loads(item.item_metadata) if item.item_metadata else {}
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU
        await session.refresh(char, ["classes"])

        scores_res = await session.execute(
            _select(AbilityScore).where(AbilityScore.character_id == char_id)
        )
        scores = {s.name: s.value for s in scores_res.scalars()}
        str_mod = (scores.get("strength", 10) - 10) // 2
        dex_mod = (scores.get("dexterity", 10) - 10) // 2

        props: list[str] = meta.get("properties", [])
        weapon_type = meta.get("weapon_type", "melee")
        # Finesse: use best of STR/DEX; ranged: use DEX
        if "finesse" in props:
            atk_mod = max(str_mod, dex_mod)
        elif weapon_type == "ranged":
            atk_mod = dex_mod
        else:
            atk_mod = str_mod

        prof_bonus = char.proficiency_bonus
        to_hit_bonus = atk_mod + prof_bonus

        # Roll to-hit
        d20 = _random.randint(1, 20)
        total_hit = d20 + to_hit_bonus
        is_crit = d20 == 20
        is_fumble = d20 == 1

        # Roll damage
        damage_dice_str = meta.get("damage_dice", "")
        dmg_rolled = 0
        dmg_detail = "—"
        total_mod = atk_mod  # combined modifier (atk_mod + flat weapon bonus)
        if damage_dice_str:
            try:
                import re as _re
                m = _re.match(r"(\d+)d(\d+)([+-]\d+)?", damage_dice_str, _re.IGNORECASE)
                if m:
                    num_dice = int(m.group(1))
                    die_size = int(m.group(2))
                    flat_bonus = int(m.group(3)) if m.group(3) else 0
                    total_mod = atk_mod + flat_bonus
                    if is_crit:
                        rolls_d = [_random.randint(1, die_size) for _ in range(num_dice * 2)]
                    else:
                        rolls_d = [_random.randint(1, die_size) for _ in range(num_dice)]
                    dmg_rolled = max(0, sum(rolls_d) + total_mod)
                    rolls_str = ", ".join(str(r) for r in rolls_d)
                    # dmg_detail = just the dice rolls; modifier shown separately via mod_str
                    dmg_detail = f"\\[{_esc(rolls_str)}\\]"
            except Exception:
                pass

        item_name = item.name

    def _signed(n: int) -> str:
        return f"\\+{n}" if n >= 0 else _esc(str(n))

    # Build result message
    hit_line = translator.t(
        "character.bag.attack_hit", lang=lang,
        class_name=_esc(item_name), die=d20, bonus_str=_signed(to_hit_bonus), total=total_hit,
    )
    lines = [f"⚔️ *{_esc(item_name)}*\n", hit_line]
    if is_crit:
        lines.append(translator.t("character.bag.attack_crit", lang=lang))
        if damage_dice_str:
            lines.append(translator.t(
                "character.bag.attack_crit_dmg", lang=lang,
                dice=dmg_detail, mod_str=_signed(total_mod), total=dmg_rolled,
            ))
    elif is_fumble:
        lines.append(translator.t("character.bag.attack_fumble", lang=lang))
    elif damage_dice_str:
        lines.append(translator.t(
            "character.bag.attack_dmg", lang=lang,
            dice=dmg_detail, mod_str=_signed(total_mod), total=dmg_rolled,
        ))

    msg = "\n".join(lines)
    # Send as a new message so the item detail screen stays intact
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=msg,
        parse_mode="MarkdownV2",
    )

    import asyncio as _asyncio
    log_txt = f"Attacco con {item_name}: d20({d20}){'+' if to_hit_bonus>=0 else ''}{to_hit_bonus}={total_hit}"
    _asyncio.create_task(_log(char_id, "dice_roll", log_txt))
    return CHAR_BAG_MENU


async def remove_all_item(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    item_id: int,
) -> int:
    async with get_session() as session:
        item = await session.get(Item, item_id)
        item_name = item.name if item and item.character_id == char_id else "?"
        await session.execute(
            delete(Item).where(Item.id == item_id, Item.character_id == char_id)
        )
        char = await session.get(Character, char_id)
        if char:
            all_items_res = await session.execute(
                select(Item).where(Item.character_id == char_id)
            )
            char.encumbrance = sum(i.weight * i.quantity for i in all_items_res.scalars())

    import asyncio as _asyncio
    _asyncio.create_task(_log(char_id, "bag_change", f"Rimosso tutto: {item_name}"))
    if update.callback_query:
        await update.callback_query.answer("Oggetto rimosso.")
    return await show_bag_menu(update, context, char_id)


# ---------------------------------------------------------------------------
# Internal helpers: add-flow prompt functions
# ---------------------------------------------------------------------------

async def _ask_name(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int, lang: str
) -> int:
    context.user_data[_OP_KEY]["step"] = "name"
    await _edit_or_reply(
        update,
        translator.t("character.bag.prompt_name", lang=lang),
        build_cancel_keyboard(char_id, "char_bag", lang=lang),
    )
    return CHAR_BAG_ADD_NAME


async def _route_after_name(
    update: Update, context: ContextTypes.DEFAULT_TYPE,
    char_id: int, item_type: str, lang: str,
) -> int:
    """Dispatch to the first type-specific step after the name is captured."""
    if item_type == "weapon":
        context.user_data[_OP_KEY]["step"] = "damage_dice"
        await update.message.reply_text(
            translator.t("character.bag.prompt_damage_dice", lang=lang),
            reply_markup=_skip_keyboard(char_id, lang),
            parse_mode="MarkdownV2",
        )
        return CHAR_BAG_ADD_DAMAGE_DICE
    if item_type == "armor":
        context.user_data[_OP_KEY]["step"] = "armor_type"
        await update.message.reply_text(
            translator.t("character.bag.prompt_armor_type", lang=lang),
            reply_markup=build_armor_type_keyboard(char_id, lang=lang),
            parse_mode="MarkdownV2",
        )
        return CHAR_BAG_ADD_INLINE
    if item_type == "shield":
        context.user_data[_OP_KEY]["step"] = "ac_value"
        await update.message.reply_text(
            translator.t("character.bag.prompt_ac_bonus", lang=lang),
            reply_markup=build_cancel_keyboard(char_id, "char_bag", lang=lang),
            parse_mode="MarkdownV2",
        )
        return CHAR_BAG_ADD_AC_VALUE
    if item_type == "consumable":
        context.user_data[_OP_KEY]["step"] = "effect"
        await update.message.reply_text(
            translator.t("character.bag.prompt_effect", lang=lang),
            reply_markup=_skip_keyboard(char_id, lang),
            parse_mode="MarkdownV2",
        )
        return CHAR_BAG_ADD_EFFECT
    if item_type == "tool":
        context.user_data[_OP_KEY]["step"] = "tool_type"
        await update.message.reply_text(
            translator.t("character.bag.prompt_tool_type", lang=lang),
            reply_markup=_skip_keyboard(char_id, lang),
            parse_mode="MarkdownV2",
        )
        return CHAR_BAG_ADD_TOOL_TYPE
    # generic → straight to weight
    return await _ask_weight_msg(update, context, char_id, lang)


async def _ask_damage_type(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int, lang: str
) -> int:
    context.user_data[_OP_KEY]["step"] = "damage_type"
    await _edit_or_reply(
        update,
        translator.t("character.bag.prompt_damage_type", lang=lang),
        build_damage_type_keyboard(char_id, lang=lang),
    )
    return CHAR_BAG_ADD_INLINE


async def _ask_weapon_type(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int, lang: str
) -> int:
    context.user_data[_OP_KEY]["step"] = "weapon_type"
    await _edit_or_reply(
        update,
        translator.t("character.bag.prompt_weapon_type", lang=lang),
        build_weapon_type_keyboard(char_id, lang=lang),
    )
    return CHAR_BAG_ADD_INLINE


async def _ask_properties(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int, lang: str
) -> int:
    context.user_data[_OP_KEY]["step"] = "properties"
    props = context.user_data[_OP_KEY].get("properties", [])
    await _edit_or_reply(
        update,
        translator.t("character.bag.prompt_properties", lang=lang),
        build_weapon_properties_keyboard(char_id, props, lang=lang),
    )
    return CHAR_BAG_ADD_INLINE


async def _ask_ac_value(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int, lang: str
) -> int:
    context.user_data[_OP_KEY]["step"] = "ac_value"
    await _edit_or_reply(
        update,
        translator.t("character.bag.prompt_ac_value", lang=lang),
        build_cancel_keyboard(char_id, "char_bag", lang=lang),
    )
    return CHAR_BAG_ADD_AC_VALUE


async def _ask_stealth(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int, lang: str
) -> int:
    context.user_data[_OP_KEY]["step"] = "stealth"
    await _edit_or_reply(
        update,
        translator.t("character.bag.prompt_stealth", lang=lang),
        build_stealth_keyboard(char_id, lang=lang),
    )
    return CHAR_BAG_ADD_INLINE


async def _ask_str_req(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int, lang: str
) -> int:
    context.user_data[_OP_KEY]["step"] = "str_req"
    await _edit_or_reply(
        update,
        translator.t("character.bag.prompt_str_req", lang=lang),
        _skip_keyboard_cancel(char_id, lang),
    )
    return CHAR_BAG_ADD_STR_REQ


async def _ask_weight(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int, lang: str
) -> int:
    """Send weight prompt via edit_message (from inline flow)."""
    context.user_data[_OP_KEY]["step"] = "weight"
    await _edit_or_reply(
        update,
        translator.t("character.bag.prompt_weight", lang=lang),
        build_cancel_keyboard(char_id, "char_bag", lang=lang),
    )
    return CHAR_BAG_ADD_WEIGHT


async def _ask_weight_msg(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int, lang: str
) -> int:
    """Send weight prompt via reply_text (from text input flow)."""
    context.user_data[_OP_KEY]["step"] = "weight"
    await update.message.reply_text(
        translator.t("character.bag.prompt_weight", lang=lang),
        reply_markup=build_cancel_keyboard(char_id, "char_bag", lang=lang),
        parse_mode="MarkdownV2",
    )
    return CHAR_BAG_ADD_WEIGHT


# ---------------------------------------------------------------------------
# Save item to DB
# ---------------------------------------------------------------------------

async def _save_item(
    update: Update, context: ContextTypes.DEFAULT_TYPE,
    char_id: int, qty: int, lang: str,
) -> int:
    pending = context.user_data.get(_OP_KEY, {})
    item_name = pending["item_name"]
    item_weight = pending.get("item_weight", 0.0)
    item_type = pending.get("item_type", "generic")
    meta = _build_metadata(pending, item_type)

    async with get_session() as session:
        # Deduplication only for generic items with same name
        existing = None
        if item_type == "generic":
            result = await session.execute(
                select(Item).where(
                    Item.character_id == char_id,
                    Item.name == item_name,
                    Item.item_type == "generic",
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
                item_type=item_type,
                item_metadata=json.dumps(meta) if meta else None,
            ))

        char = await session.get(Character, char_id)
        if char:
            all_items_res = await session.execute(
                select(Item).where(Item.character_id == char_id)
            )
            char.encumbrance = sum(i.weight * i.quantity for i in all_items_res.scalars())

    context.user_data.pop(_OP_KEY, None)
    import asyncio as _asyncio
    _asyncio.create_task(_log(char_id, "bag_change", f"Aggiunto ({item_type}): {item_name} x{qty} ({item_weight} kg)"))
    await update.message.reply_text(
        translator.t("character.bag.item_added", lang=lang, name=_esc(item_name)),
        parse_mode="MarkdownV2",
    )
    return await show_bag_menu(update, context, char_id)


def _build_metadata(pending: dict, item_type: str) -> dict:
    """Extract type-specific metadata from the pending dict."""
    if item_type == "weapon":
        return {
            "damage_dice": pending.get("damage_dice", ""),
            "damage_type": pending.get("damage_type", ""),
            "weapon_type": pending.get("weapon_type", "melee"),
            "properties": pending.get("properties", []),
        }
    if item_type == "armor":
        return {
            "armor_type": pending.get("armor_type", "light"),
            "ac_value": pending.get("ac_value", 10),
            "stealth_disadvantage": pending.get("stealth_disadvantage", False),
            "strength_req": pending.get("str_req", 0),
        }
    if item_type == "shield":
        return {"ac_bonus": pending.get("ac_value", 2)}
    if item_type == "consumable":
        return {"effect": pending.get("effect", "")}
    if item_type == "tool":
        return {"tool_type": pending.get("tool_type", "")}
    return {}


# ---------------------------------------------------------------------------
# Skip handler (callback for optional steps)
# ---------------------------------------------------------------------------

async def handle_bag_skip(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle ⏭️ Salta for optional text-input steps."""
    if update.callback_query is None:
        return CHAR_BAG_MENU
    await update.callback_query.answer()

    lang = get_lang(update)
    pending = context.user_data.get(_OP_KEY, {})
    char_id: int = pending.get("char_id", 0)
    step: str = pending.get("step", "")

    if step == "damage_dice":
        context.user_data[_OP_KEY]["damage_dice"] = ""
        return await _ask_damage_type(update, context, char_id, lang)
    if step == "effect":
        context.user_data[_OP_KEY]["effect"] = ""
        return await _ask_weight(update, context, char_id, lang)
    if step == "tool_type":
        context.user_data[_OP_KEY]["tool_type"] = ""
        return await _ask_weight(update, context, char_id, lang)
    if step == "str_req":
        context.user_data[_OP_KEY]["str_req"] = 0
        return await _ask_weight(update, context, char_id, lang)

    context.user_data.pop(_OP_KEY, None)
    return await show_bag_menu(update, context, char_id)


# ---------------------------------------------------------------------------
# Keyboard helpers
# ---------------------------------------------------------------------------

def _skip_keyboard(char_id: int, lang: str):
    """Cancel keyboard augmented with a Skip button."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    from bot.models.character_state import CharAction
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            text=translator.t("character.bag.btn_skip", lang=lang),
            callback_data=CharAction("char_bag", char_id=char_id, sub="skip"),
        )],
        [InlineKeyboardButton(
            text=translator.t("nav.cancel", lang=lang),
            callback_data=CharAction("char_bag", char_id=char_id),
        )],
    ])


def _skip_keyboard_cancel(char_id: int, lang: str):
    """Cancel keyboard with Skip for str_req step."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    from bot.models.character_state import CharAction
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            text=translator.t("character.bag.btn_skip", lang=lang),
            callback_data=CharAction("char_bag", char_id=char_id, sub="skip"),
        )],
        [InlineKeyboardButton(
            text=translator.t("nav.cancel", lang=lang),
            callback_data=CharAction("char_bag", char_id=char_id),
        )],
    ])


# ---------------------------------------------------------------------------
# Logging / utility
# ---------------------------------------------------------------------------

async def _log(char_id: int, event_type: str, description: str) -> None:
    """Fire-and-forget wrapper for history logging."""
    try:
        from bot.db.history import log_history_event
        await log_history_event(char_id, event_type, description)
    except Exception as exc:
        logger.warning("History log failed for char %s: %s", char_id, exc)


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

