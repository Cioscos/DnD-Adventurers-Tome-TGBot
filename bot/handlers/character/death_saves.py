"""Death saving throws handler — track successes/failures when a character reaches 0 HP."""

from __future__ import annotations

import logging

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
            import asyncio as _asyncio
            _asyncio.create_task(_log(char_id, "death_saves", "Personaggio stabilizzato ✅"))
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

    import asyncio as _asyncio
    if saves["failures"] >= 3:
        _asyncio.create_task(_log(char_id, "death_saves", "Personaggio morto ☠️"))
        if update.callback_query:
            await update.callback_query.answer(
                translator.t("character.death_saves.dead", lang=lang)
            )
    else:
        if update.callback_query:
            await update.callback_query.answer(
                translator.t("character.death_saves.failure_added", lang=lang)
            )

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
