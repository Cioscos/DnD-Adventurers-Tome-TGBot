"""Character navigation state — callback data for character management.

Uses PTB's ``arbitrary_callback_data`` feature so that the whole
:class:`CharAction` object is the callback payload (no 64-byte limit).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CharAction:
    """Immutable callback payload for character management inline buttons.

    ``action`` identifies the screen/operation; other fields carry context.
    """

    action: str      # e.g. "char_select" | "char_menu" | "char_hp" | …
    char_id: int = 0
    sub: str = ""    # sub-action within a screen (e.g. "damage", "heal")
    item_id: int = 0 # DB row id for items, spells, abilities, etc.
    page: int = 0    # pagination
    extra: str = ""  # generic extra string (zone name, currency type, …)
    back: tuple[str, ...] = ()  # serialised previous CharAction for ⬅️ Back

    def back_nav(self) -> "CharAction":
        """Reconstruct the :class:`CharAction` for the Back button."""
        if not self.back:
            return CharAction("char_select")
        return CharAction(
            action=self.back[0],
            char_id=int(self.back[1]) if len(self.back) > 1 else 0,
            sub=self.back[2] if len(self.back) > 2 else "",
            item_id=int(self.back[3]) if len(self.back) > 3 else 0,
            page=int(self.back[4]) if len(self.back) > 4 else 0,
            extra=self.back[5] if len(self.back) > 5 else "",
        )


def make_char_back(
    action: str,
    char_id: int = 0,
    sub: str = "",
    item_id: int = 0,
    page: int = 0,
    extra: str = "",
) -> tuple[str, ...]:
    """Create a ``back`` tuple for :class:`CharAction`."""
    return (action, str(char_id), sub, str(item_id), str(page), extra)
