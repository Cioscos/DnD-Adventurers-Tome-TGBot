"""Inline keyboard builders for the party group feature."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.models.party_state import PartyAction
from bot.utils.i18n import translator


def _btn(text: str, action: PartyAction) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=action)


def build_party_mode_keyboard(group_id: int, lang: str = "it") -> InlineKeyboardMarkup:
    """Keyboard for choosing party display mode: public or private."""
    return InlineKeyboardMarkup([
        [
            _btn(translator.t("party.btn_public", lang=lang),  PartyAction("party_mode", group_id=group_id, extra="public")),
            _btn(translator.t("party.btn_private", lang=lang), PartyAction("party_mode", group_id=group_id, extra="private")),
        ],
    ])


def build_party_master_reveal_keyboard(group_id: int, lang: str = "it") -> InlineKeyboardMarkup:
    """Keyboard with the single button the master presses to receive the private party list."""
    return InlineKeyboardMarkup([
        [_btn(translator.t("party.btn_reveal", lang=lang), PartyAction("party_master_reveal", group_id=group_id))],
    ])
