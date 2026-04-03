"""Party feature navigation state — callback data for party group commands.

Uses PTB's ``arbitrary_callback_data`` feature so the full :class:`PartyAction`
object is the callback payload (no 64-byte string limit).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PartyAction:
    """Immutable callback payload for party feature inline buttons.

    ``action`` identifies the operation; other fields carry context.
    """

    action: str       # e.g. "party_mode" | "party_master_reveal" | "party_noop"
    group_id: int = 0 # Telegram group chat_id
    extra: str = ""   # e.g. "public" or "private" for party_mode selection
