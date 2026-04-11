"""HP management and combat handler (damage, healing, HP set)."""

from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.db.engine import get_session
from bot.db.models import Character
from bot.handlers.character import (
    CHAR_HP_MENU,
    CHAR_HP_SET,
    CHAR_HP_DAMAGE,
    CHAR_HP_HEAL,
    CHAR_HP_TEMP_HP,
    CHAR_HP_HIT_DICE,
    CHAR_MENU,
)
from bot.keyboards.character import build_hp_keyboard, build_cancel_keyboard
from bot.utils.formatting import format_hp
from bot.utils.i18n import get_lang, translator

logger = logging.getLogger(__name__)

# user_data keys for pending HP operations
_OP_KEY = "char_hp_pending_op"


async def show_hp_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    lang = get_lang(update)
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU

    at_zero = char.current_hit_points <= 0
    saves = char.death_saves or {}
    already_stable = bool(saves.get("stable", False))
    show_death_saves = at_zero and not already_stable

    keyboard = build_hp_keyboard(char_id, lang=lang, show_death_saves=show_death_saves)
    text = format_hp(char, lang=lang)
    await _edit_or_reply(update, text, keyboard)
    return CHAR_HP_MENU


async def ask_hp_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    operation: str,
) -> int:
    """Ask the user to type a numeric value for the HP operation."""
    lang = get_lang(update)
    context.user_data[_OP_KEY] = {"char_id": char_id, "op": operation}
    prompts = {
        "set_max":     translator.t("character.hp.prompt_set_max", lang=lang),
        "set_current": translator.t("character.hp.prompt_set_current", lang=lang),
        "damage":      translator.t("character.hp.prompt_damage", lang=lang),
        "heal":        translator.t("character.hp.prompt_heal", lang=lang),
        "set_temp":    translator.t("character.hp.prompt_set_temp", lang=lang),
    }
    text = prompts.get(operation, translator.t("character.hp.prompt_set_max", lang=lang))
    await _edit_or_reply(update, text, build_cancel_keyboard(char_id, "char_hp", lang=lang))
    state_map = {
        "set_max":     CHAR_HP_SET,
        "set_current": CHAR_HP_SET,
        "damage":      CHAR_HP_DAMAGE,
        "heal":        CHAR_HP_HEAL,
        "set_temp":    CHAR_HP_TEMP_HP,
    }
    return state_map.get(operation, CHAR_HP_MENU)


async def handle_hp_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Process the numeric text input for HP operations."""
    from bot.handlers.character.menu import show_character_menu

    if update.message is None:
        return CHAR_HP_MENU

    lang = get_lang(update)
    pending = context.user_data.pop(_OP_KEY, None)
    if pending is None:
        return CHAR_HP_MENU

    char_id: int = pending["char_id"]
    operation: str = pending["op"]

    try:
        value = int(update.message.text.strip())
        if value < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            translator.t("character.common.invalid_number", lang=lang),
            parse_mode="MarkdownV2",
        )
        context.user_data[_OP_KEY] = pending
        state_map = {"set_max": CHAR_HP_SET, "set_current": CHAR_HP_SET,
                     "damage": CHAR_HP_DAMAGE, "heal": CHAR_HP_HEAL,
                     "set_temp": CHAR_HP_TEMP_HP}
        return state_map.get(operation, CHAR_HP_MENU)

    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU

        old_hp = char.current_hit_points
        old_max = char.hit_points
        old_temp = getattr(char, "temp_hp", 0) or 0

        if operation == "set_max":
            char.hit_points = max(0, value)
            desc = f"HP Max: {old_max} → {char.hit_points}"
        elif operation == "set_current":
            char.current_hit_points = max(0, min(value, char.hit_points))
            desc = f"HP Attuali: {old_hp} → {char.current_hit_points}"
        elif operation == "set_temp":
            char.temp_hp = max(0, value)
            desc = f"HP Temporanei: {old_temp} → {char.temp_hp}"
        elif operation == "damage":
            # Damage absorbs temp HP first, then regular HP
            temp = getattr(char, "temp_hp", 0) or 0
            if temp > 0:
                absorbed = min(temp, value)
                char.temp_hp = temp - absorbed
                remaining = value - absorbed
            else:
                remaining = value
            char.current_hit_points = max(0, char.current_hit_points - remaining)
            temp_note = f" (temp: {old_temp}→{char.temp_hp})" if old_temp > 0 else ""
            desc = f"HP: {old_hp} → {char.current_hit_points}{temp_note} (danno: -{value})"
        elif operation == "heal":
            new_hp = char.current_hit_points + value
            if new_hp > char.hit_points:
                char.current_hit_points = char.hit_points
            else:
                char.current_hit_points = new_hp
            actual = char.current_hit_points - old_hp
            desc = f"HP: {old_hp} → {char.current_hit_points} (cura: +{actual})"
        else:
            desc = "HP modificati"

        # Reset death saves when healed from 0
        healed_from_zero = (
            (operation in ("heal", "set_current"))
            and old_hp <= 0
            and char.current_hit_points > 0
        )

    import asyncio as _asyncio
    _asyncio.create_task(_log(char_id, "hp_change", desc))
    if healed_from_zero:
        from bot.handlers.character.death_saves import reset_death_saves
        _asyncio.create_task(reset_death_saves(char_id))
    await update.message.reply_text(translator.t("character.common.updated", lang=lang), parse_mode="MarkdownV2")
    # Fire-and-forget: update any active party messages for this character
    asyncio.create_task(_trigger_party_update(char_id, context))
    return await show_hp_menu(update, context, char_id)


async def handle_rest(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    rest_type: str,
) -> int:
    """Perform a short or long rest."""
    from bot.db.models import Ability, RestorationType, SpellSlot
    from bot.handlers.character.class_resources import restore_class_resources_on_rest
    from sqlalchemy import select

    lang = get_lang(update)

    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU

        if rest_type == "long":
            char.current_hit_points = char.hit_points
            char.temp_hp = 0
            # Clear active concentration
            was_concentrating = char.concentrating_spell_id is not None
            char.concentrating_spell_id = None
            # Reset death saving throws on long rest
            char.death_saves = {"successes": 0, "failures": 0, "stable": False}
            # Restore all spell slots
            slots_res = await session.execute(
                select(SpellSlot).where(SpellSlot.character_id == char_id)
            )
            for slot in slots_res.scalars():
                slot.restore_all()
            # Restore long-rest abilities
            abilities_res = await session.execute(
                select(Ability).where(Ability.character_id == char_id)
            )
            for ability in abilities_res.scalars():
                if ability.restoration_type == RestorationType.LONG_REST:
                    ability.restore()
            msg = translator.t("character.rest.long_completed", lang=lang)
            if was_concentrating:
                msg += translator.t("character.rest.conc_interrupted", lang=lang)
        else:
            # Short rest: clear concentration + restore short-rest abilities
            was_concentrating = char.concentrating_spell_id is not None
            char.concentrating_spell_id = None
            abilities_res = await session.execute(
                select(Ability).where(Ability.character_id == char_id)
            )
            for ability in abilities_res.scalars():
                if ability.restoration_type == RestorationType.SHORT_REST:
                    ability.restore()
            msg = translator.t("character.rest.short_completed", lang=lang)
            if was_concentrating:
                msg += translator.t("character.rest.conc_interrupted", lang=lang)

    # Restore class resources outside the session to avoid nested session issues
    await restore_class_resources_on_rest(char_id, rest_type)

    rest_label = "Lungo" if rest_type == "long" else "Breve"
    asyncio.create_task(_log(char_id, "rest", f"Riposo {rest_label} eseguito"))

    if update.callback_query:
        await update.callback_query.answer()

    await _edit_or_reply(update, msg)
    from bot.handlers.character.menu import show_character_menu
    # Fire-and-forget: update any active party messages for this character
    asyncio.create_task(_trigger_party_update(char_id, context))
    return await show_character_menu(update, context, char_id=char_id)


async def ask_hit_dice_count(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
) -> int:
    """Ask how many hit dice to spend during short rest healing."""
    from sqlalchemy import select
    from bot.db.models import CharacterClass

    lang = get_lang(update)

    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU
        classes_res = await session.execute(
            select(CharacterClass).where(CharacterClass.character_id == char_id)
        )
        classes = list(classes_res.scalars())

    # Build summary of available hit dice
    if not classes:
        if update.callback_query:
            await update.callback_query.answer(
                translator.t("character.rest.no_hit_dice", lang=lang)
            )
        return await show_hp_menu(update, context, char_id)

    # Use first class hit die for the prompt
    primary_die = classes[0].hit_die or 8
    total_dice = sum(cls.level for cls in classes)
    die_str = f"d{primary_die}"

    text = translator.t(
        "character.rest.prompt_hit_dice", lang=lang, max=total_dice, die=_esc(die_str)
    )
    context.user_data[_OP_KEY] = {"char_id": char_id, "op": "hit_dice", "max_dice": total_dice}
    await _edit_or_reply(update, text, build_cancel_keyboard(char_id, "char_hp", lang=lang))
    return CHAR_HP_HIT_DICE


async def handle_hit_dice_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Process the number of hit dice to spend and apply healing."""
    import random
    from sqlalchemy import select
    from bot.db.models import CharacterClass

    if update.message is None:
        return CHAR_HP_HIT_DICE

    lang = get_lang(update)
    pending = context.user_data.pop(_OP_KEY, None)
    if pending is None:
        return CHAR_HP_MENU

    char_id: int = pending["char_id"]

    try:
        count = int(update.message.text.strip())
        if count < 1:
            raise ValueError
    except ValueError:
        max_dice = pending.get("max_dice", 20)
        await update.message.reply_text(
            translator.t("character.rest.hit_dice_invalid", lang=lang, max=max_dice),
            parse_mode="MarkdownV2",
        )
        context.user_data[_OP_KEY] = pending
        return CHAR_HP_HIT_DICE

    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU
        classes_res = await session.execute(
            select(CharacterClass).where(CharacterClass.character_id == char_id)
        )
        classes = list(classes_res.scalars())

        # Pick first class hit die (or 8 default)
        hit_die = 8
        if classes:
            hit_die = classes[0].hit_die or 8

        # Get CON modifier
        from bot.db.models import AbilityScore
        scores_res = await session.execute(
            select(AbilityScore).where(AbilityScore.character_id == char_id)
        )
        scores = {s.name: s.value for s in scores_res.scalars()}
        con_mod = (scores.get("constitution", 10) - 10) // 2

        old_hp = char.current_hit_points
        total_healing = 0
        rolls = []
        for _ in range(count):
            roll = random.randint(1, hit_die)
            healing = max(1, roll + con_mod)
            rolls.append(roll)
            total_healing += healing

        new_hp = min(char.hit_points, char.current_hit_points + total_healing)
        actual = new_hp - old_hp
        char.current_hit_points = new_hp

    rolls_str = ", ".join(str(r) for r in rolls)
    con_str = f"+{con_mod}" if con_mod >= 0 else str(con_mod)
    msg = translator.t(
        "character.rest.hit_dice_result", lang=lang,
        count=count, die=f"d{hit_die}", rolls=_esc(rolls_str),
        con_str=_esc(con_str), healed=actual,
        before=old_hp, after=new_hp, max=char.hit_points,
    )
    await update.message.reply_text(msg, parse_mode="MarkdownV2")
    asyncio.create_task(_log(char_id, "hp_change", f"Hit Dice: {count}d{hit_die} → +{actual} HP"))
    asyncio.create_task(_trigger_party_update(char_id, context))
    return await show_hp_menu(update, context, char_id)


def _esc(text: str) -> str:
    special = r"\_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in str(text))


# ---------------------------------------------------------------------------
# Helpers
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


async def _trigger_party_update(char_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fire-and-forget wrapper that calls maybe_update_party_message."""
    try:
        from bot.handlers.party import maybe_update_party_message
        await maybe_update_party_message(char_id, context.bot)
    except Exception as e:
        logger.warning("Party update trigger failed for char %s: %s", char_id, e)
