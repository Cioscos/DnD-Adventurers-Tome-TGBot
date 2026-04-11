"""Death saving throws handler — track successes/failures when a character reaches 0 HP."""

from __future__ import annotations

import asyncio
import logging
import random

from telegram import Update
from telegram.ext import ContextTypes

from bot.db.engine import get_session
from bot.db.models import Character
from bot.handlers.character import CHAR_DEATH_SAVES_MENU, CHAR_MENU
from bot.keyboards.character import build_death_saves_keyboard
from bot.utils.formatting import format_death_saves
from bot.utils.i18n import get_lang, translator

logger = logging.getLogger(__name__)

_DEFAULT_SAVES: dict = {"successes": 0, "failures": 0, "stable": False}


def _get_saves(char: Character) -> dict:
    """Return the death_saves dict, defaulting to zeros if None."""
    return dict(char.death_saves or _DEFAULT_SAVES)


async def show_death_saves_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
) -> int:
    lang = get_lang(update)

    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU

    saves = _get_saves(char)
    text = format_death_saves(char, lang=lang)
    keyboard = build_death_saves_keyboard(
        char_id,
        successes=saves.get("successes", 0),
        failures=saves.get("failures", 0),
        stable=bool(saves.get("stable", False)),
        lang=lang,
    )

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(
                text=text, reply_markup=keyboard, parse_mode="MarkdownV2"
            )
        except Exception:
            await update.callback_query.message.reply_text(
                text=text, reply_markup=keyboard, parse_mode="MarkdownV2"
            )
    elif update.message:
        await update.message.reply_text(
            text=text, reply_markup=keyboard, parse_mode="MarkdownV2"
        )

    return CHAR_DEATH_SAVES_MENU


async def add_success(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
) -> int:
    lang = get_lang(update)

    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            if update.callback_query:
                await update.callback_query.answer()
            return CHAR_MENU

        saves = _get_saves(char)
        if saves.get("stable"):
            if update.callback_query:
                await update.callback_query.answer(
                    translator.t("character.death_saves.already_stable", lang=lang)
                )
            return await show_death_saves_menu(update, context, char_id)

        saves["successes"] = min(3, saves.get("successes", 0) + 1)

        if saves["successes"] >= 3:
            saves["stable"] = True
            saves["successes"] = 0
            saves["failures"] = 0
            char.death_saves = saves
            asyncio.create_task(_log(char_id, "death_saves", "Personaggio stabilizzato ✅"))
            if update.callback_query:
                await update.callback_query.answer(
                    translator.t("character.death_saves.stabilized", lang=lang)
                )
        else:
            char.death_saves = saves
            if update.callback_query:
                await update.callback_query.answer(
                    translator.t("character.death_saves.success_added", lang=lang)
                )

    asyncio.create_task(_trigger_party_update(char_id, context))
    return await show_death_saves_menu(update, context, char_id)


async def add_failure(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
) -> int:
    lang = get_lang(update)

    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            if update.callback_query:
                await update.callback_query.answer()
            return CHAR_MENU

        saves = _get_saves(char)
        if saves.get("stable"):
            if update.callback_query:
                await update.callback_query.answer(
                    translator.t("character.death_saves.already_stable", lang=lang)
                )
            return await show_death_saves_menu(update, context, char_id)

        saves["failures"] = min(3, saves.get("failures", 0) + 1)
        char.death_saves = saves

    if saves["failures"] >= 3:
        asyncio.create_task(_log(char_id, "death_saves", "Personaggio morto ☠️"))
        if update.callback_query:
            await update.callback_query.answer(
                translator.t("character.death_saves.dead", lang=lang)
            )
    else:
        if update.callback_query:
            await update.callback_query.answer(
                translator.t("character.death_saves.failure_added", lang=lang)
            )

    asyncio.create_task(_trigger_party_update(char_id, context))
    return await show_death_saves_menu(update, context, char_id)


async def reset_death_saves_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
) -> int:
    await reset_death_saves(char_id)
    if update.callback_query:
        await update.callback_query.answer(
            translator.t("character.death_saves.reset", lang=get_lang(update))
        )
    asyncio.create_task(_trigger_party_update(char_id, context))
    return await show_death_saves_menu(update, context, char_id)


async def roll_death_save(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
) -> int:
    """Roll a d20 for a death saving throw, applying critical/fumble rules.

    - Natural 20: character immediately regains 1 HP (stabilised).
    - Natural 1: counts as 2 failures.
    - 10+: 1 success.
    - <10: 1 failure.
    """
    lang = get_lang(update)

    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            if update.callback_query:
                await update.callback_query.answer()
            return CHAR_MENU

        saves = _get_saves(char)
        if saves.get("stable"):
            if update.callback_query:
                await update.callback_query.answer(
                    translator.t("character.death_saves.already_stable", lang=lang)
                )
            return await show_death_saves_menu(update, context, char_id)

        die_result = random.randint(1, 20)

        if die_result == 20:
            # Nat 20: stabilise with 1 HP
            char.current_hit_points = 1
            char.death_saves = {"successes": 0, "failures": 0, "stable": False}
            toast = translator.t("character.death_saves.nat20_revived", lang=lang)
            asyncio.create_task(_log(char_id, "death_saves", f"NAT 20! Revived with 1 HP (rolled {die_result})"))
            if update.callback_query:
                await update.callback_query.answer(toast)
        elif die_result == 1:
            # Nat 1: 2 failures
            saves["failures"] = min(3, saves.get("failures", 0) + 2)
            char.death_saves = saves
            toast = translator.t("character.death_saves.nat1_double_failure", lang=lang)
            asyncio.create_task(_log(char_id, "death_saves", f"NAT 1! Double failure (rolled {die_result})"))
            if update.callback_query:
                await update.callback_query.answer(toast)
        elif die_result >= 10:
            saves["successes"] = min(3, saves.get("successes", 0) + 1)
            if saves["successes"] >= 3:
                saves["stable"] = True
                saves["successes"] = 0
                saves["failures"] = 0
                asyncio.create_task(_log(char_id, "death_saves", f"Stabilised (rolled {die_result})"))
                if update.callback_query:
                    await update.callback_query.answer(
                        translator.t("character.death_saves.stabilized", lang=lang)
                    )
            else:
                asyncio.create_task(_log(char_id, "death_saves", f"Success (rolled {die_result})"))
                if update.callback_query:
                    await update.callback_query.answer(
                        translator.t("character.death_saves.roll_success", lang=lang, roll=die_result)
                    )
            char.death_saves = saves
        else:
            saves["failures"] = min(3, saves.get("failures", 0) + 1)
            char.death_saves = saves
            asyncio.create_task(_log(char_id, "death_saves", f"Failure (rolled {die_result})"))
            if update.callback_query:
                await update.callback_query.answer(
                    translator.t("character.death_saves.roll_failure", lang=lang, roll=die_result)
                )

    asyncio.create_task(_trigger_party_update(char_id, context))
    return await show_death_saves_menu(update, context, char_id)


async def reset_death_saves(char_id: int) -> None:
    """Utility: reset death saves to zero (call on heal or long rest)."""
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is not None:
            char.death_saves = {"successes": 0, "failures": 0, "stable": False}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _log(char_id: int, event_type: str, description: str) -> None:
    try:
        from bot.db.history import log_history_event
        await log_history_event(char_id, event_type, description)
    except Exception as exc:
        logger.warning("History log failed for char %s: %s", char_id, exc)


async def _trigger_party_update(char_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fire-and-forget wrapper that calls maybe_update_party_message."""
    try:
        from bot.handlers.party import maybe_update_party_message
        await maybe_update_party_message(char_id, context.bot)
    except Exception as e:
        logger.warning("Party update trigger failed for char %s: %s", char_id, e)
