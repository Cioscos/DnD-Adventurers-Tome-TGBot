"""Navigation state — callback data and menu category config.

Uses PTB's ``arbitrary_callback_data`` feature so that navigation state
is a :class:`NavAction` dataclass (no 64-byte string limit).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NavAction:
    """Immutable callback payload passed through Telegram buttons.

    Because ``arbitrary_callback_data`` is enabled, this whole object is
    stored in an LRU cache and only a UUID goes to Telegram.
    """

    action: str  # "menu" | "list" | "detail" | "sub_list" | "noop"
    type_name: str = ""      # GraphQL type: "Spell", "Class", "AnyEquipment", …
    index: str = ""          # Item slug: "wizard", "fireball", …
    field: str = ""          # Navigable field name (only for sub_list)
    page: int = 0            # Current page
    concrete_type: str = ""  # For union types: actual member type ("Weapon", …)
    # Context for the ⬅️ Back button — enough to reconstruct one step back
    back: tuple[str, ...] = ()  # (action, type_name, index, field, page, concrete_type)

    def back_nav(self) -> "NavAction":
        """Reconstruct the :class:`NavAction` for the Back button."""
        if not self.back:
            return NavAction("menu")
        return NavAction(
            action=self.back[0],
            type_name=self.back[1] if len(self.back) > 1 else "",
            index=self.back[2] if len(self.back) > 2 else "",
            field=self.back[3] if len(self.back) > 3 else "",
            page=int(self.back[4]) if len(self.back) > 4 else 0,
            concrete_type=self.back[5] if len(self.back) > 5 else "",
        )


def make_back(
    action: str,
    type_name: str = "",
    index: str = "",
    field: str = "",
    page: int = 0,
    concrete_type: str = "",
) -> tuple[str, ...]:
    """Create a ``back`` tuple for :class:`NavAction`."""
    return (action, type_name, index, field, str(page), concrete_type)
