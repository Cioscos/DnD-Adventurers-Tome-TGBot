"""Party group feature — handler for /party and /party_stop commands.

This module provides:
- ``party_command``: the /party command (group-only)
- ``party_stop_command``: the /party_stop command
- ``party_callback_handler``: handles :class:`PartyAction` callbacks
- ``track_group_member``: ``MessageHandler`` that records group members
- ``maybe_update_party_message``: utility to update party messages when HP changes
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from telegram import Bot, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden
from telegram.ext import ContextTypes

from bot.db.engine import get_session
from bot.db.models import Character, GroupMember, PartySession, PartyMode
from bot.keyboards.party import build_party_master_reveal_keyboard, build_party_mode_keyboard
from bot.models.party_state import PartyAction
from bot.utils.i18n import get_lang, translator
from bot.utils.party_formatting import format_party_message

logger = logging.getLogger(__name__)

_SESSION_HOURS = 48


# ---------------------------------------------------------------------------
# Group member tracking
# ---------------------------------------------------------------------------

async def track_group_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Record the sender's user_id for the current group (INSERT OR IGNORE)."""
    chat = update.effective_chat
    user = update.effective_user
    if chat is None or user is None:
        return
    if chat.type not in ("group", "supergroup"):
        return

    async with get_session() as session:
        # Use INSERT OR IGNORE via merge-on-conflict: check then insert
        result = await session.execute(
            select(GroupMember).where(
                GroupMember.group_id == chat.id,
                GroupMember.user_id == user.id,
            )
        )
        if result.scalar_one_or_none() is None:
            session.add(GroupMember(group_id=chat.id, user_id=user.id))


# ---------------------------------------------------------------------------
# /party command
# ---------------------------------------------------------------------------

async def party_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /party command — initiates a party tracking session."""
    chat = update.effective_chat
    message = update.message

    if chat is None or message is None:
        return

    # Only allowed in groups
    if chat.type not in ("group", "supergroup"):
        lang = get_lang(update)
        await message.reply_text(
            translator.t("party.group_only", lang=lang),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    group_id = chat.id
    lang = get_lang(update)

    # Check for an existing active session
    async with get_session() as session:
        existing = await session.execute(
            select(PartySession).where(PartySession.group_id == group_id)
        )
        existing_session = existing.scalar_one_or_none()

    if existing_session is not None:
        # Check if it has expired
        try:
            expires = datetime.fromisoformat(existing_session.expires_at)
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires > datetime.now(tz=timezone.utc):
                await message.reply_text(
                    translator.t("party.already_active", lang=lang),
                    parse_mode=ParseMode.MARKDOWN_V2,
                )
                return
        except Exception:
            pass
        # Expired session — clean it up
        async with get_session() as session:
            stale = await session.get(PartySession, existing_session.id)
            if stale:
                await session.delete(stale)

    # Also track the command issuer as a group member
    user = update.effective_user
    if user:
        async with get_session() as session:
            result = await session.execute(
                select(GroupMember).where(
                    GroupMember.group_id == group_id,
                    GroupMember.user_id == user.id,
                )
            )
            if result.scalar_one_or_none() is None:
                session.add(GroupMember(group_id=group_id, user_id=user.id))

    # Find members with active characters; pass the issuer so they are always
    # included even if GroupMember tracking hasn't persisted yet.
    chars_with_users = await _get_party_characters(
        group_id, issuer_user_id=user.id if user else None
    )

    if not chars_with_users:
        await message.reply_text(
            translator.t("party.no_members", lang=lang),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    await message.reply_text(
        translator.t("party.mode_title", lang=lang),
        reply_markup=build_party_mode_keyboard(group_id, lang=lang),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


# ---------------------------------------------------------------------------
# /party_stop command
# ---------------------------------------------------------------------------

async def party_stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /party_stop command — terminates the active party session."""
    chat = update.effective_chat
    message = update.message

    if chat is None or message is None:
        return

    if chat.type not in ("group", "supergroup"):
        lang = get_lang(update)
        await message.reply_text(
            translator.t("party.stop_group_only", lang=lang),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    group_id = chat.id
    lang = get_lang(update)

    async with get_session() as session:
        result = await session.execute(
            select(PartySession).where(PartySession.group_id == group_id)
        )
        party_session = result.scalar_one_or_none()

        if party_session is None:
            await message.reply_text(
                translator.t("party.no_session", lang=lang),
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            return

        msg_chat_id = party_session.message_chat_id
        msg_id = party_session.message_id
        await session.delete(party_session)

    # Try to edit the party message to show it's been stopped
    if msg_chat_id and msg_id:
        try:
            await context.bot.edit_message_text(
                chat_id=msg_chat_id,
                message_id=msg_id,
                text=translator.t("party.stop_message", lang=lang),
                parse_mode=ParseMode.MARKDOWN_V2,
            )
        except (BadRequest, Exception) as e:
            logger.warning("Could not edit party message on stop: %s", e)

    await message.reply_text(
        translator.t("party.stop_completed", lang=lang),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


# ---------------------------------------------------------------------------
# Party callback handler (PartyAction)
# ---------------------------------------------------------------------------

async def party_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route PartyAction callbacks to the appropriate handler."""
    query = update.callback_query
    if query is None:
        return

    data: PartyAction = query.data
    if not isinstance(data, PartyAction):
        await query.answer()
        return

    action = data.action

    if action == "party_mode":
        await _handle_party_mode(update, context, data)
    elif action == "party_master_reveal":
        await _handle_party_master_reveal(update, context, data)
    elif action == "party_noop":
        await query.answer()
    else:
        await query.answer()


async def _handle_party_mode(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data: PartyAction
) -> None:
    """Create the party session with the chosen mode (public or private)."""
    query = update.callback_query
    group_id = data.group_id
    mode = data.extra
    lang = get_lang(update)

    await query.answer()

    chat = update.effective_chat
    group_title = chat.title if chat else None

    chars_with_users = await _get_party_characters(group_id)

    now = datetime.now(tz=timezone.utc)
    expires = now + timedelta(hours=_SESSION_HOURS)

    if mode == "public":
        dummy_session = PartySession(
            group_id=group_id,
            group_title=group_title,
            mode=PartyMode.PUBLIC,
            expires_at=expires.isoformat(),
        )
        text = format_party_message(chars_with_users, dummy_session, lang=lang)

        try:
            sent_msg = await context.bot.send_message(
                chat_id=group_id,
                text=text,
                parse_mode=ParseMode.MARKDOWN_V2,
            )
        except Exception as e:
            logger.error("Failed to send public party message: %s", e)
            await query.edit_message_text(
                translator.t("party.send_error", lang=lang),
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            return

        async with get_session() as session:
            party_session = PartySession(
                group_id=group_id,
                group_title=group_title,
                mode=PartyMode.PUBLIC,
                message_chat_id=group_id,
                message_id=sent_msg.message_id,
                started_at=now.isoformat(),
                expires_at=expires.isoformat(),
            )
            session.add(party_session)

        try:
            await query.delete_message()
        except Exception:
            pass

    else:
        async with get_session() as session:
            party_session = PartySession(
                group_id=group_id,
                group_title=group_title,
                mode=PartyMode.PRIVATE,
                message_chat_id=None,
                message_id=None,
                started_at=now.isoformat(),
                expires_at=expires.isoformat(),
            )
            session.add(party_session)

        await query.edit_message_text(
            translator.t("party.private_waiting", lang=lang),
            reply_markup=build_party_master_reveal_keyboard(group_id, lang=lang),
            parse_mode=ParseMode.MARKDOWN_V2,
        )


async def _handle_party_master_reveal(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data: PartyAction
) -> None:
    """Send the party status privately to the master who pressed the button."""
    query = update.callback_query
    master_user = update.effective_user
    group_id = data.group_id
    lang = get_lang(update)

    if master_user is None:
        await query.answer(translator.t("party.reveal_error_user", lang=lang))
        return

    # Load session
    async with get_session() as session:
        result = await session.execute(
            select(PartySession).where(PartySession.group_id == group_id)
        )
        party_session = result.scalar_one_or_none()

    if party_session is None:
        await query.answer(translator.t("party.session_not_found", lang=lang))
        return

    # Check expiry
    try:
        expires = datetime.fromisoformat(party_session.expires_at)
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= datetime.now(tz=timezone.utc):
            await query.answer(translator.t("party.session_expired_toast", lang=lang))
            return
    except Exception:
        pass

    chars_with_users = await _get_party_characters(group_id)
    text = format_party_message(chars_with_users, party_session, lang=lang)

    # Send private message to master
    try:
        sent_msg = await context.bot.send_message(
            chat_id=master_user.id,
            text=text,
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    except Forbidden:
        await query.answer(
            translator.t("party.reveal_error_private", lang=lang),
            show_alert=True,
        )
        return
    except Exception as e:
        logger.error("Failed to send private party message to master: %s", e)
        await query.answer(translator.t("party.reveal_error_generic", lang=lang))
        return

    # Save the private message reference into the session
    async with get_session() as session:
        ps = await session.get(PartySession, party_session.id)
        if ps:
            ps.message_chat_id = master_user.id
            ps.message_id = sent_msg.message_id

    await query.answer(translator.t("party.reveal_sent", lang=lang), show_alert=False)


# ---------------------------------------------------------------------------
# Utility: update party messages when a character's state changes
# ---------------------------------------------------------------------------

async def maybe_update_party_message(char_id: int, bot: Bot) -> None:
    """Edit all active party messages that include the given character's party.

    Called fire-and-forget via ``asyncio.create_task`` after HP changes.
    Silently ignores errors (expired messages, network issues, etc.).
    """
    try:
        # Find the character's user_id
        async with get_session() as session:
            char = await session.get(Character, char_id)
            if char is None:
                return
            user_id = char.user_id

        # Find all active party sessions for groups that contain this user
        now_iso = datetime.now(tz=timezone.utc).isoformat()
        async with get_session() as session:
            result = await session.execute(
                select(PartySession)
                .join(GroupMember, GroupMember.group_id == PartySession.group_id)
                .where(
                    GroupMember.user_id == user_id,
                    PartySession.expires_at > now_iso,
                    PartySession.message_id.is_not(None),
                    PartySession.message_chat_id.is_not(None),
                )
            )
            sessions = list(result.scalars().all())

        for ps in sessions:
            await _refresh_single_party_message(ps, bot)

    except Exception as e:
        logger.warning("maybe_update_party_message error for char %s: %s", char_id, e)


async def _refresh_single_party_message(ps: PartySession, bot: Bot) -> None:
    """Rebuild and edit one party message. Deletes the session on unrecoverable failure."""
    try:
        chars_with_users = await _get_party_characters(ps.group_id)
        text = format_party_message(chars_with_users, ps)
        await bot.edit_message_text(
            chat_id=ps.message_chat_id,
            message_id=ps.message_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    except BadRequest as e:
        err = str(e).lower()
        if "message is not modified" in err:
            return  # No change — silently skip
        # Message too old or deleted — clean up the session
        logger.info("Party message uneditable (%s), removing session %s.", e, ps.id)
        await _delete_session(ps.id)
    except Exception as e:
        logger.warning("Failed to refresh party message (session %s): %s", ps.id, e)


async def _delete_session(session_id: int) -> None:
    """Remove a party session by id."""
    try:
        async with get_session() as session:
            ps = await session.get(PartySession, session_id)
            if ps:
                await session.delete(ps)
    except Exception as e:
        logger.warning("Failed to delete party session %s: %s", session_id, e)


# ---------------------------------------------------------------------------
# Internal helper: collect characters for a group party
# ---------------------------------------------------------------------------

async def _get_party_characters(
    group_id: int,
    issuer_user_id: int | None = None,
) -> list[tuple[Character, str | None]]:
    """Return (Character, username) tuples for all active party characters in the group.

    If a group member has exactly one character and has not explicitly set
    ``is_party_active``, that character is included automatically.

    ``issuer_user_id`` is always added to the candidate set regardless of whether
    the user appears in the ``GroupMember`` table, ensuring the ``/party`` command
    issuer is never excluded due to a read-after-write timing gap or because
    Telegram Privacy Mode prevented their messages from being tracked.
    """
    async with get_session() as session:
        # Get all user_ids that have written in this group
        members_result = await session.execute(
            select(GroupMember.user_id).where(GroupMember.group_id == group_id)
        )
        member_user_ids_set: set[int] = {row[0] for row in members_result.all()}

    # Always include the party initiator even if not yet persisted in GroupMember
    if issuer_user_id is not None:
        member_user_ids_set.add(issuer_user_id)

    member_user_ids = list(member_user_ids_set)

    if not member_user_ids:
        logger.debug("_get_party_characters: no members found for group %s", group_id)
        return []

    result: list[tuple[Character, str | None]] = []

    async with get_session() as session:
        # For each member, find their characters
        chars_result = await session.execute(
            select(Character).where(Character.user_id.in_(member_user_ids))
        )
        all_chars = list(chars_result.scalars().all())

        # Group by user_id
        by_user: dict[int, list[Character]] = {}
        for char in all_chars:
            by_user.setdefault(char.user_id, []).append(char)

        for user_id, chars in by_user.items():
            # Load classes for each character
            for char in chars:
                await session.refresh(char, ["classes"])

            active_chars = [c for c in chars if c.is_party_active]

            if active_chars:
                # Use the explicitly activated character
                result.append((active_chars[0], None))
            elif len(chars) == 1:
                # Single character — include automatically
                result.append((chars[0], None))
            # else: multiple characters, none active → skip user

    return result
