"""Special abilities / features handler."""

from __future__ import annotations

import logging

from sqlalchemy import delete, select
from telegram import Update
from telegram.ext import ContextTypes

from bot.db.engine import get_session
from bot.db.models import Ability, Character, RestorationType
from bot.handlers.character import (
    CHAR_ABILITIES_MENU,
    CHAR_ABILITY_LEARN_DESC,
    CHAR_ABILITY_LEARN_NAME,
    CHAR_ABILITY_LEARN_USES,
    CHAR_MENU,
)
from bot.keyboards.character import build_abilities_keyboard, build_ability_detail_keyboard
from bot.utils.formatting import RESTORATION_LABELS, format_abilities

logger = logging.getLogger(__name__)

_OP_KEY = "char_ability_pending"


async def show_abilities_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int, page: int = 0
) -> int:
    async with get_session() as session:
        result = await session.execute(
            select(Ability).where(Ability.character_id == char_id).order_by(Ability.name)
        )
        abilities = list(result.scalars().all())

    keyboard = build_abilities_keyboard(char_id, abilities, page)
    text = format_abilities(abilities)
    await _edit_or_reply(update, text, keyboard)
    return CHAR_ABILITIES_MENU


async def show_ability_detail(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    ability_id: int,
    back_page: int = 0,
) -> int:
    async with get_session() as session:
        ability = await session.get(Ability, ability_id)
        if ability is None or ability.character_id != char_id:
            return await show_abilities_menu(update, context, char_id)

    passive_label = "✅ Passiva" if ability.is_passive else "⚡ Attiva"
    active_mark = "✅ Attivata" if ability.is_active else "⬛ Non attivata"
    uses_text = (
        f"Usi: *{ability.uses}*/*{ability.max_uses}*"
        if ability.max_uses is not None
        else "Usi: illimitati"
    )
    rest_label = RESTORATION_LABELS.get(ability.restoration_type, "—")
    desc = ability.description or "_Nessuna descrizione_"
    text = (
        f"⚡ *{_esc(ability.name)}*\n\n"
        f"{desc}\n\n"
        f"{passive_label} | {active_mark}\n"
        f"{uses_text}\n"
        f"Ripristino: {rest_label}"
    )
    keyboard = build_ability_detail_keyboard(char_id, ability, back_page)
    await _edit_or_reply(update, text, keyboard)
    return CHAR_ABILITIES_MENU


async def ask_learn_ability(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    context.user_data[_OP_KEY] = {"char_id": char_id, "step": "name"}
    await _edit_or_reply(update, "⚡ Inserisci il *nome* dell'abilità:")
    return CHAR_ABILITY_LEARN_NAME


async def handle_ability_learn_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if update.message is None:
        return CHAR_ABILITY_LEARN_NAME

    pending = context.user_data.get(_OP_KEY, {})
    char_id: int = pending.get("char_id")
    step: str = pending.get("step", "name")
    text = update.message.text.strip()

    if step == "name":
        if not text:
            await update.message.reply_text("❌ Nome non valido\\.", parse_mode="MarkdownV2")
            return CHAR_ABILITY_LEARN_NAME
        context.user_data[_OP_KEY]["ability_name"] = text
        context.user_data[_OP_KEY]["step"] = "desc"
        await update.message.reply_text(
            "📝 Inserisci la *descrizione* \\(o \\- per saltare\\):",
            parse_mode="MarkdownV2",
        )
        return CHAR_ABILITY_LEARN_DESC

    if step == "desc":
        context.user_data[_OP_KEY]["ability_desc"] = None if text == "-" else text
        context.user_data[_OP_KEY]["step"] = "passive"
        await update.message.reply_text(
            "🔵 È un'abilità *passiva*? Rispondi *si* o *no*:",
            parse_mode="MarkdownV2",
        )
        return CHAR_ABILITY_LEARN_USES

    if step == "passive":
        is_passive = text.lower() in ("si", "sì", "yes", "y")
        context.user_data[_OP_KEY]["is_passive"] = is_passive
        context.user_data[_OP_KEY]["step"] = "uses"
        await update.message.reply_text(
            "🔢 Quanti *usi massimi* ha? \\(0 = illimitati\\):",
            parse_mode="MarkdownV2",
        )
        return CHAR_ABILITY_LEARN_USES

    if step == "uses":
        try:
            uses = int(text)
            if uses < 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❌ Valore non valido\\.", parse_mode="MarkdownV2")
            return CHAR_ABILITY_LEARN_USES
        context.user_data[_OP_KEY]["max_uses"] = uses if uses > 0 else None
        context.user_data[_OP_KEY]["step"] = "restoration"
        restoration_options = "\\- `long_rest` \\(riposo lungo\\)\n\\- `short_rest` \\(riposo breve\\)\n\\- `none` \\(mai\\)"
        await update.message.reply_text(
            f"😴 *Tipo di ripristino*:\n{restoration_options}",
            parse_mode="MarkdownV2",
        )
        return CHAR_ABILITY_LEARN_USES

    if step == "restoration":
        rest_map = {
            "long_rest": RestorationType.LONG_REST,
            "short_rest": RestorationType.SHORT_REST,
            "none": RestorationType.NONE,
        }
        restoration = rest_map.get(text.lower(), RestorationType.NONE)

        ability_name = pending["ability_name"]
        ability_desc = pending.get("ability_desc")
        is_passive = pending.get("is_passive", False)
        max_uses = pending.get("max_uses")

        async with get_session() as session:
            session.add(Ability(
                character_id=char_id,
                name=ability_name,
                description=ability_desc,
                is_passive=is_passive,
                max_uses=max_uses,
                uses=max_uses,
                restoration_type=restoration,
            ))

        context.user_data.pop(_OP_KEY, None)
        await update.message.reply_text(
            f"✅ Abilità *{_esc(ability_name)}* imparata\\!", parse_mode="MarkdownV2"
        )
        return await show_abilities_menu(update, context, char_id)

    return CHAR_ABILITY_LEARN_NAME


async def use_ability(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    ability_id: int,
) -> int:
    async with get_session() as session:
        ability = await session.get(Ability, ability_id)
        if ability is None or ability.character_id != char_id:
            return await show_abilities_menu(update, context, char_id)
        try:
            ability.use()
        except ValueError as e:
            if update.callback_query:
                await update.callback_query.answer(str(e))
            return await show_ability_detail(update, context, char_id, ability_id)

    if update.callback_query:
        await update.callback_query.answer("Abilità usata.")
    return await show_ability_detail(update, context, char_id, ability_id)


async def toggle_ability(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    ability_id: int,
) -> int:
    async with get_session() as session:
        ability = await session.get(Ability, ability_id)
        if ability and ability.character_id == char_id:
            ability.is_active = not ability.is_active

    if update.callback_query:
        await update.callback_query.answer()
    return await show_ability_detail(update, context, char_id, ability_id)


async def forget_ability(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    ability_id: int,
) -> int:
    async with get_session() as session:
        await session.execute(
            delete(Ability).where(Ability.id == ability_id, Ability.character_id == char_id)
        )
    if update.callback_query:
        await update.callback_query.answer("Abilità dimenticata.")
    return await show_abilities_menu(update, context, char_id)


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
