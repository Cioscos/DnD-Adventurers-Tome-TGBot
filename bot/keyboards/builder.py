"""Dynamic inline-keyboard builders for Telegram bot navigation.

All keyboards are driven by the :class:`~bot.schema.registry.SchemaRegistry`
and use :class:`~bot.models.state.NavAction` objects as callback data
(arbitrary callback data — no 64-byte limit).
"""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.models.state import NavAction, make_back
from bot.schema.registry import MENU_CATEGORIES, registry
from bot.schema.types import TypeInfo

PAGE_SIZE = 10
COLUMNS = 2


# ------------------------------------------------------------------
# Top-level category keyboard
# ------------------------------------------------------------------

def build_categories_keyboard() -> InlineKeyboardMarkup:
    """Build the ``/start`` category-selection keyboard (2-column grid)."""
    buttons: list[InlineKeyboardButton] = []
    for mc in MENU_CATEGORIES:
        ti = registry.get_type(mc.type_name)
        if ti is None or ti.list_query_field is None:
            continue
        buttons.append(
            InlineKeyboardButton(
                text=f"{mc.emoji} {mc.label}",
                callback_data=NavAction("list", type_name=mc.type_name, page=0),
            )
        )
    rows = [buttons[i : i + COLUMNS] for i in range(0, len(buttons), COLUMNS)]
    return InlineKeyboardMarkup(rows)


# ------------------------------------------------------------------
# Item-list keyboard (paginated)
# ------------------------------------------------------------------

def build_list_keyboard(
    items: list[dict],
    type_name: str,
    page: int,
    has_next: bool,
    *,
    back_tuple: tuple[str, ...] = (),
) -> InlineKeyboardMarkup:
    """Build a paginated item-list keyboard.

    *back_tuple* is stored in the Back button's ``NavAction.back`` so the
    user can return to the previous screen.
    """
    ti = registry.get_type(type_name)
    rows: list[list[InlineKeyboardButton]] = []

    for item in items:
        label = item.get("name") or item.get("index", "???")
        extra = _item_label_extra(ti, item)
        if extra:
            label = f"{label}  ({extra})"
        rows.append([
            InlineKeyboardButton(
                text=label,
                callback_data=NavAction(
                    "detail",
                    type_name=type_name,
                    index=item["index"],
                    back=make_back("list", type_name, page=page),
                ),
            )
        ])

    # Navigation row
    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(
            InlineKeyboardButton(
                text="⬅️ Prev",
                callback_data=NavAction(
                    "list", type_name=type_name, page=page - 1,
                    back=back_tuple,
                ),
            )
        )
    nav_row.append(
        InlineKeyboardButton(
            text="🏠 Menu",
            callback_data=NavAction("menu"),
        )
    )
    if has_next:
        nav_row.append(
            InlineKeyboardButton(
                text="Next ➡️",
                callback_data=NavAction(
                    "list", type_name=type_name, page=page + 1,
                    back=back_tuple,
                ),
            )
        )
    rows.append(nav_row)
    return InlineKeyboardMarkup(rows)


# ------------------------------------------------------------------
# Detail keyboard (with dynamic 📂 navigable-field buttons)
# ------------------------------------------------------------------

def build_detail_keyboard(
    type_name: str,
    index: str,
    detail_data: dict,
    *,
    concrete_type: str = "",
    back_nav: NavAction | None = None,
) -> InlineKeyboardMarkup:
    """Build the keyboard shown below an item detail view.

    Includes a ``📂`` button for every navigable sub-field that has at
    least one item, plus the usual ⬅️ Back / 🏠 Menu row.
    """
    # Determine which TypeInfo to use for navigable fields
    effective_type = concrete_type or type_name
    ti = registry.get_type(effective_type)

    rows: list[list[InlineKeyboardButton]] = []

    if ti:
        for field_name in ti.navigable_fields:
            items_in_field = detail_data.get(field_name)
            if not items_in_field:
                continue
            count = len(items_in_field) if isinstance(items_in_field, list) else 0
            if count == 0:
                continue
            nice_label = field_name.replace("_", " ").title()
            rows.append([
                InlineKeyboardButton(
                    text=f"📂 {nice_label} ({count})",
                    callback_data=NavAction(
                        "sub_list",
                        type_name=type_name,
                        index=index,
                        field=field_name,
                        concrete_type=concrete_type,
                        back=make_back(
                            "detail", type_name, index,
                            concrete_type=concrete_type,
                        ),
                    ),
                )
            ])

    # ⬅️ Back / 🏠 Menu
    nav_row: list[InlineKeyboardButton] = []
    if back_nav is not None:
        nav_row.append(
            InlineKeyboardButton(text="⬅️ Back", callback_data=back_nav)
        )
    nav_row.append(
        InlineKeyboardButton(text="🏠 Menu", callback_data=NavAction("menu"))
    )
    rows.append(nav_row)
    return InlineKeyboardMarkup(rows)


# ------------------------------------------------------------------
# Sub-list keyboard
# ------------------------------------------------------------------

def build_sub_list_keyboard(
    items: list[dict],
    sub_type_name: str,
    page: int,
    has_next: bool,
    *,
    parent_type: str,
    parent_index: str,
    field_name: str,
    parent_concrete: str = "",
) -> InlineKeyboardMarkup:
    """Build a paginated sub-list keyboard (items inside a navigable field)."""
    sub_ti = registry.get_type(sub_type_name)
    rows: list[list[InlineKeyboardButton]] = []

    back_to_sub = make_back(
        "sub_list", parent_type, parent_index, field_name,
        concrete_type=parent_concrete,
    )

    for item in items:
        label = item.get("name") or item.get("index", "???")
        extra = _item_label_extra(sub_ti, item)
        if extra:
            label = f"{label}  ({extra})"

        # Determine the detail type (for union sub-items, use __typename)
        detail_type = item.get("__typename", sub_type_name)

        rows.append([
            InlineKeyboardButton(
                text=label,
                callback_data=NavAction(
                    "detail",
                    type_name=detail_type,
                    index=item["index"],
                    concrete_type=item.get("__typename", ""),
                    back=back_to_sub,
                ),
            )
        ])

    # Pagination + back to parent detail
    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(
            InlineKeyboardButton(
                text="⬅️ Prev",
                callback_data=NavAction(
                    "sub_list",
                    type_name=parent_type,
                    index=parent_index,
                    field=field_name,
                    page=page - 1,
                    concrete_type=parent_concrete,
                ),
            )
        )
    # Back goes to parent detail
    nav_row.append(
        InlineKeyboardButton(
            text="⬅️ Back",
            callback_data=NavAction(
                "detail",
                type_name=parent_type,
                index=parent_index,
                concrete_type=parent_concrete,
                back=make_back("list", parent_type),
            ),
        )
    )
    nav_row.append(
        InlineKeyboardButton(text="🏠 Menu", callback_data=NavAction("menu"))
    )
    if has_next:
        nav_row.append(
            InlineKeyboardButton(
                text="Next ➡️",
                callback_data=NavAction(
                    "sub_list",
                    type_name=parent_type,
                    index=parent_index,
                    field=field_name,
                    page=page + 1,
                    concrete_type=parent_concrete,
                ),
            )
        )
    rows.append(nav_row)
    return InlineKeyboardMarkup(rows)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _item_label_extra(ti: TypeInfo | None, item: dict) -> str:
    """Short badge text for the list buttons (e.g. spell level, CR)."""
    if ti is None:
        return ""
    type_name = ti.name
    if type_name == "Spell":
        lvl = item.get("level")
        if lvl is not None:
            return f"Lvl {lvl}" if lvl > 0 else "Cantrip"
    if type_name == "Monster":
        cr = item.get("challenge_rating")
        if cr is not None:
            return f"CR {cr:g}"
    if type_name == "Class":
        hd = item.get("hit_die")
        if hd is not None:
            return f"d{hd}"
    return ""
