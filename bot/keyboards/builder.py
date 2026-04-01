"""Dynamic inline-keyboard builders for Telegram bot navigation.

Provides functions to construct ``InlineKeyboardMarkup`` objects for:
- Top-level category selection (2-column grid)
- Paginated item lists with Next / Prev / Back buttons
- Detail view with a Back button
"""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.models.state import (
    BACK_TO_MAIN,
    CATEGORIES,
    Category,
    encode_category,
    encode_item,
)

PAGE_SIZE = 10
COLUMNS = 2


def build_categories_keyboard() -> InlineKeyboardMarkup:
    """Build the top-level category selection keyboard (2 columns)."""
    buttons: list[InlineKeyboardButton] = []
    for cat in CATEGORIES.values():
        buttons.append(
            InlineKeyboardButton(
                text=f"{cat.emoji} {cat.label}",
                callback_data=encode_category(cat.key, 0),
            )
        )
    # Arrange into rows of COLUMNS buttons each
    rows: list[list[InlineKeyboardButton]] = [
        buttons[i : i + COLUMNS] for i in range(0, len(buttons), COLUMNS)
    ]
    return InlineKeyboardMarkup(rows)


def build_list_keyboard(
    items: list[dict],
    category: Category,
    page: int,
    has_next: bool,
) -> InlineKeyboardMarkup:
    """Build a paginated item-list keyboard.

    Parameters
    ----------
    items:
        The items to display on this page (max ``PAGE_SIZE``).
    category:
        The category metadata.
    page:
        Current zero-based page number.
    has_next:
        Whether a next page exists.
    """
    rows: list[list[InlineKeyboardButton]] = []

    # Item buttons — one per row for readability
    for item in items:
        label = item.get("name", item.get("index", "???"))
        # Add extra info in the button label for some categories
        extra = _item_label_extra(category.key, item)
        if extra:
            label = f"{label}  ({extra})"
        rows.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=encode_item(category.key, item["index"]),
                )
            ]
        )

    # Navigation row: ⬅️ Prev | Back | Next ➡️
    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(
            InlineKeyboardButton(
                text="⬅️ Prev",
                callback_data=encode_category(category.key, page - 1),
            )
        )
    nav_row.append(
        InlineKeyboardButton(text="🏠 Menu", callback_data=BACK_TO_MAIN)
    )
    if has_next:
        nav_row.append(
            InlineKeyboardButton(
                text="Next ➡️",
                callback_data=encode_category(category.key, page + 1),
            )
        )
    rows.append(nav_row)

    return InlineKeyboardMarkup(rows)


def build_detail_keyboard(
    category_key: str, page: int = 0
) -> InlineKeyboardMarkup:
    """Build a keyboard for the detail view with Back and Menu buttons."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text="⬅️ Back",
                    callback_data=encode_category(category_key, page),
                ),
                InlineKeyboardButton(
                    text="🏠 Menu",
                    callback_data=BACK_TO_MAIN,
                ),
            ]
        ]
    )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _item_label_extra(category_key: str, item: dict) -> str:
    """Return a short extra string for item buttons (e.g. spell level)."""
    if category_key == "spells":
        lvl = item.get("level")
        if lvl is not None:
            return f"Lvl {lvl}" if lvl > 0 else "Cantrip"
    if category_key == "monsters":
        cr = item.get("challenge_rating")
        if cr is not None:
            return f"CR {cr:g}"
    if category_key == "classes":
        hd = item.get("hit_die")
        if hd is not None:
            return f"d{hd}"
    return ""
