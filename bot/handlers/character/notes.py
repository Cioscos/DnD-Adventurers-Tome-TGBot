"""Notes management handler (text notes and voice messages)."""

from __future__ import annotations

import logging
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from bot.db.engine import get_session
from bot.db.models import Character
from bot.handlers.character import (
    CHAR_MENU,
    CHAR_NOTES_MENU,
    CHAR_NOTE_NEW_BODY,
    CHAR_NOTE_NEW_TITLE,
    CHAR_NOTE_EDIT,
    CHAR_VOICE_NOTE_TITLE,
)
from bot.keyboards.character import build_note_detail_keyboard, build_notes_keyboard

logger = logging.getLogger(__name__)

_OP_KEY = "char_note_pending"
_FILES_DIR = Path("files")


async def show_notes_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int, page: int = 0
) -> int:
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU
        notes: dict = char.notes or {}

    titles = sorted(notes.keys())
    keyboard = build_notes_keyboard(char_id, titles, page)
    text = f"📝 *Note*\n\n{len(titles)} note totali\\."
    await _edit_or_reply(update, text, keyboard)
    return CHAR_NOTES_MENU


async def show_note(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    title: str,
    back_page: int = 0,
) -> int:
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU
        notes: dict = char.notes or {}

    body = notes.get(title, "")
    keyboard = build_note_detail_keyboard(char_id, title, back_page)

    if body.startswith("[VOICE:") and body.endswith("]"):
        voice_ref = body[7:-1]
        chat_id = update.effective_chat.id

        if update.callback_query:
            await update.callback_query.answer()

        try:
            voice_path = Path(voice_ref)
            if not voice_path.is_file():
                raise FileNotFoundError(f"Voice file not found: {voice_ref}")
            with open(voice_path, "rb") as f:
                await context.bot.send_document(
                    chat_id=chat_id, document=f,
                    filename=f"{title}.ogg",
                    caption=f"🎤 {title}",
                    disable_content_type_detection=True,
                )
        except Exception as e:
            logger.exception("Failed to send voice note '%s'", title)
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ Impossibile riprodurre la nota vocale *{_esc(title)}*\\.",
                parse_mode="MarkdownV2",
            )

        await context.bot.send_message(
            chat_id=chat_id,
            text=f"📝 *{_esc(title)}* \\(nota vocale\\)",
            parse_mode="MarkdownV2",
            reply_markup=keyboard,
        )
        return CHAR_NOTES_MENU

    # Regular text note
    display_body = _esc(body) if body else "_Nota vuota_"
    text = f"📝 *{_esc(title)}*\n\n{display_body}"
    await _edit_or_reply(update, text, keyboard)
    return CHAR_NOTES_MENU


async def ask_new_note_title(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    context.user_data[_OP_KEY] = {"char_id": char_id, "step": "title", "type": "text"}
    await _edit_or_reply(update, "📝 Inserisci il *titolo* della nota:")
    return CHAR_NOTE_NEW_TITLE


async def ask_voice_note_title(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    context.user_data[_OP_KEY] = {"char_id": char_id, "step": "title", "type": "voice"}
    await _edit_or_reply(update, "🎤 Inserisci il *titolo* della nota vocale:")
    return CHAR_VOICE_NOTE_TITLE


async def handle_note_title_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if update.message is None:
        return CHAR_NOTE_NEW_TITLE

    pending = context.user_data.get(_OP_KEY, {})
    char_id: int = pending.get("char_id")
    note_type: str = pending.get("type", "text")
    title = update.message.text.strip()

    if not title:
        await update.message.reply_text("❌ Titolo non valido\\.", parse_mode="MarkdownV2")
        return CHAR_NOTE_NEW_TITLE

    context.user_data[_OP_KEY]["title"] = title

    if note_type == "voice":
        context.user_data[_OP_KEY]["step"] = "voice_body"
        await update.message.reply_text(
            "🎤 Invia ora il *messaggio vocale*:", parse_mode="MarkdownV2"
        )
        return CHAR_VOICE_NOTE_TITLE

    context.user_data[_OP_KEY]["step"] = "body"
    await update.message.reply_text(
        f"📝 Inserisci il *contenuto* della nota *{_esc(title)}*:",
        parse_mode="MarkdownV2",
    )
    return CHAR_NOTE_NEW_BODY


async def handle_note_body_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if update.message is None:
        return CHAR_NOTE_NEW_BODY

    pending = context.user_data.pop(_OP_KEY, None)
    if pending is None:
        return CHAR_NOTES_MENU

    char_id: int = pending["char_id"]
    title: str = pending["title"]
    body = update.message.text.strip()

    await _save_note(char_id, title, body)
    await update.message.reply_text(
        f"✅ Nota *{_esc(title)}* salvata\\!", parse_mode="MarkdownV2"
    )
    return await show_notes_menu(update, context, char_id)


async def handle_voice_note(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Receive a voice message and download it to the local files/ directory."""
    if update.message is None or update.message.voice is None:
        return CHAR_VOICE_NOTE_TITLE

    pending = context.user_data.pop(_OP_KEY, None)
    if pending is None:
        return CHAR_NOTES_MENU

    char_id: int = pending["char_id"]
    title: str = pending.get("title", "Nota vocale")

    voice = update.message.voice

    # Ensure the files directory exists
    voice_dir = _FILES_DIR / str(char_id)
    voice_dir.mkdir(parents=True, exist_ok=True)

    # Download the voice file locally
    safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)
    file_path = voice_dir / f"{safe_title}.ogg"

    tg_file = await context.bot.get_file(voice.file_id)
    await tg_file.download_to_drive(custom_path=str(file_path))

    # Store the local path reference in DB
    await _save_note(char_id, title, f"[VOICE:{file_path}]")
    await update.message.reply_text(
        f"✅ Nota vocale *{_esc(title)}* salvata\\!", parse_mode="MarkdownV2"
    )
    return await show_notes_menu(update, context, char_id)


async def ask_edit_note(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    title: str,
) -> int:
    context.user_data[_OP_KEY] = {"char_id": char_id, "step": "edit", "title": title}
    await _edit_or_reply(
        update, f"✏️ Inserisci il nuovo contenuto per *{_esc(title)}*:"
    )
    return CHAR_NOTE_EDIT


async def handle_edit_note_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if update.message is None:
        return CHAR_NOTE_EDIT

    pending = context.user_data.pop(_OP_KEY, None)
    if pending is None:
        return CHAR_NOTES_MENU

    char_id: int = pending["char_id"]
    title: str = pending["title"]
    new_body = update.message.text.strip()

    await _save_note(char_id, title, new_body)
    await update.message.reply_text("✅ Nota aggiornata\\!", parse_mode="MarkdownV2")
    return await show_notes_menu(update, context, char_id)


async def delete_note(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    title: str,
) -> int:
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char and char.notes:
            notes = dict(char.notes)
            body = notes.pop(title, "")
            char.notes = notes

            # Remove local voice file if present
            if body.startswith("[VOICE:") and body.endswith("]"):
                voice_path = Path(body[7:-1])
                if voice_path.is_file():
                    try:
                        voice_path.unlink()
                    except OSError:
                        logger.warning("Could not delete voice file %s", voice_path)

    if update.callback_query:
        await update.callback_query.answer("Nota eliminata.")
    return await show_notes_menu(update, context, char_id)


# ---------------------------------------------------------------------------

async def _save_note(char_id: int, title: str, body: str) -> None:
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char:
            notes = dict(char.notes or {})
            notes[title] = body
            char.notes = notes


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
