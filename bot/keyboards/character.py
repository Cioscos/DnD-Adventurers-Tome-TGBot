"""Inline keyboard builders for character management screens."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.db.models import (
    ABILITY_NAMES,
    Ability,
    AbilityScore,
    Character,
    Currency,
    Item,
    Map,
    Spell,
    SpellSlot,
)
from bot.models.character_state import CharAction, make_char_back
from bot.utils.formatting import get_currency_labels, CONDITIONS_ORDER
from bot.utils.i18n import translator

PAGE_SIZE = 8
COLUMNS = 2
# Buttons whose label length exceeds this threshold are placed in a single column
_LONG_THRESHOLD = 20


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _btn(text: str, action: CharAction) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=action)


def _nav_row(
    *,
    back_action: CharAction | None = None,
    menu_char_id: int = 0,
    lang: str = "it",
) -> list[InlineKeyboardButton]:
    row: list[InlineKeyboardButton] = []
    if back_action is not None:
        row.append(_btn(translator.t("nav.back", lang=lang), back_action))
    row.append(_btn(translator.t("nav.menu", lang=lang), CharAction("char_menu", char_id=menu_char_id)))
    return row


def build_cancel_keyboard(
    char_id: int, back_action: str = "char_menu", lang: str = "it"
) -> InlineKeyboardMarkup:
    """Return a single-button keyboard with an ❌ Annulla button."""
    return InlineKeyboardMarkup(
        [[_btn(translator.t("nav.cancel", lang=lang), CharAction(back_action, char_id=char_id))]]
    )


# ---------------------------------------------------------------------------
# Character selection
# ---------------------------------------------------------------------------

def build_character_selection_keyboard(
    characters: list[Character],
    lang: str = "it",
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for char in characters:
        lvl = char.total_level
        label = translator.t("character.selection.char_label", lang=lang, name=char.name, level=lvl)
        rows.append([_btn(label, CharAction("char_menu", char_id=char.id))])
    rows.append([_btn(translator.t("character.selection.new_btn", lang=lang), CharAction("char_new"))])
    return InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------------------
# Character main menu
# ---------------------------------------------------------------------------

def build_character_main_menu_keyboard(char_id: int, lang: str = "it") -> InlineKeyboardMarkup:
    cid = char_id
    buttons = [
        (translator.t("character.menu.btn_hp",         lang=lang), CharAction("char_hp",        char_id=cid)),
        (translator.t("character.menu.btn_ac",         lang=lang), CharAction("char_ac",        char_id=cid)),
        (translator.t("character.menu.btn_level",      lang=lang), CharAction("char_level",     char_id=cid)),
        (translator.t("character.menu.btn_stats",      lang=lang), CharAction("char_stats",     char_id=cid)),
        (translator.t("character.menu.btn_spells",     lang=lang), CharAction("char_spells",    char_id=cid)),
        (translator.t("character.menu.btn_slots",      lang=lang), CharAction("char_slots",     char_id=cid)),
        (translator.t("character.menu.btn_bag",        lang=lang), CharAction("char_bag",       char_id=cid)),
        (translator.t("character.menu.btn_currency",   lang=lang), CharAction("char_currency",  char_id=cid)),
        (translator.t("character.menu.btn_abilities",  lang=lang), CharAction("char_abilities", char_id=cid)),
        (translator.t("character.menu.btn_multiclass", lang=lang), CharAction("char_multiclass",char_id=cid)),
        (translator.t("character.menu.btn_dice",       lang=lang), CharAction("char_dice",      char_id=cid)),
        (translator.t("character.menu.btn_notes",      lang=lang), CharAction("char_notes",     char_id=cid)),
        (translator.t("character.menu.btn_maps",       lang=lang), CharAction("char_maps",      char_id=cid)),
        (translator.t("character.menu.btn_rest",       lang=lang), CharAction("char_rest",       char_id=cid)),
        (translator.t("character.menu.btn_conditions", lang=lang), CharAction("char_conditions", char_id=cid)),
        (translator.t("character.menu.btn_history",    lang=lang), CharAction("char_history",    char_id=cid)),
        (translator.t("character.menu.btn_skills",     lang=lang), CharAction("char_skills",     char_id=cid)),
        (translator.t("character.menu.btn_settings",   lang=lang), CharAction("char_settings",   char_id=cid)),
        (translator.t("character.selection.delete_btn",lang=lang), CharAction("char_delete",    char_id=cid)),
    ]
    short_btns = [(t, a) for t, a in buttons if len(t) <= _LONG_THRESHOLD]
    long_btns  = [(t, a) for t, a in buttons if len(t) >  _LONG_THRESHOLD]

    rows: list[list[InlineKeyboardButton]] = []
    # Short buttons: 2 per row
    for i in range(0, len(short_btns), COLUMNS):
        rows.append([_btn(t, a) for t, a in short_btns[i:i + COLUMNS]])
    # Long buttons: 1 per row, after the short ones
    for t, a in long_btns:
        rows.append([_btn(t, a)])
    # "Change character" always last (long label, single column)
    rows.append([_btn(translator.t("character.selection.change_btn", lang=lang), CharAction("char_select"))])
    return InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------------------
# HP / Combat
# ---------------------------------------------------------------------------

def build_hp_keyboard(char_id: int, lang: str = "it") -> InlineKeyboardMarkup:
    cid = char_id
    back = CharAction("char_menu", char_id=cid)
    rows = [
        [
            _btn(translator.t("character.hp.btn_damage",      lang=lang), CharAction("char_hp", char_id=cid, sub="damage")),
            _btn(translator.t("character.hp.btn_heal",        lang=lang), CharAction("char_hp", char_id=cid, sub="heal")),
        ],
        [_btn(translator.t("character.hp.btn_set_max",     lang=lang), CharAction("char_hp", char_id=cid, sub="set_max"))],
        [_btn(translator.t("character.hp.btn_set_current", lang=lang), CharAction("char_hp", char_id=cid, sub="set_current"))],
        _nav_row(back_action=back, menu_char_id=cid, lang=lang),
    ]
    return InlineKeyboardMarkup(rows)


def build_rest_keyboard(char_id: int, lang: str = "it") -> InlineKeyboardMarkup:
    cid = char_id
    back = CharAction("char_menu", char_id=cid)
    rows = [
        [_btn(translator.t("character.rest.btn_long",  lang=lang), CharAction("char_rest", char_id=cid, sub="long"))],
        [_btn(translator.t("character.rest.btn_short", lang=lang), CharAction("char_rest", char_id=cid, sub="short"))],
        _nav_row(back_action=back, menu_char_id=cid, lang=lang),
    ]
    return InlineKeyboardMarkup(rows)


def build_rest_confirm_keyboard(char_id: int, rest_type: str, lang: str = "it") -> InlineKeyboardMarkup:
    cid = char_id
    rows = [
        [
            _btn(translator.t("nav.confirm", lang=lang), CharAction("char_rest", char_id=cid, sub=f"{rest_type}_confirm")),
            _btn(translator.t("nav.cancel",  lang=lang), CharAction("char_rest", char_id=cid)),
        ]
    ]
    return InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------------------
# Armor Class
# ---------------------------------------------------------------------------

def build_ac_keyboard(char_id: int, lang: str = "it") -> InlineKeyboardMarkup:
    cid = char_id
    back = CharAction("char_menu", char_id=cid)
    rows = [
        [_btn(translator.t("character.ac.btn_base",   lang=lang), CharAction("char_ac", char_id=cid, sub="set_base"))],
        [_btn(translator.t("character.ac.btn_shield", lang=lang), CharAction("char_ac", char_id=cid, sub="set_shield"))],
        [_btn(translator.t("character.ac.btn_magic",  lang=lang), CharAction("char_ac", char_id=cid, sub="set_magic"))],
        _nav_row(back_action=back, menu_char_id=cid, lang=lang),
    ]
    return InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------------------
# Ability Scores
# ---------------------------------------------------------------------------

def get_stat_labels(lang: str = "it") -> dict[str, str]:
    """Return {ability_name: 'emoji label'} dict for stats keyboard buttons."""
    from bot.utils.formatting import get_ability_labels
    labels = get_ability_labels(lang)
    return {name: f"{emoji} {label}" for name, (label, emoji) in labels.items()}


def build_stats_keyboard(char_id: int, lang: str = "it") -> InlineKeyboardMarkup:
    cid = char_id
    back = CharAction("char_menu", char_id=cid)
    stat_labels = get_stat_labels(lang)
    rows = [
        [_btn(label, CharAction("char_stats", char_id=cid, sub=name))]
        for name, label in stat_labels.items()
    ]
    rows.append(_nav_row(back_action=back, menu_char_id=cid, lang=lang))
    return InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------------------
# Level / Class
# ---------------------------------------------------------------------------

def build_level_keyboard(char_id: int, lang: str = "it") -> InlineKeyboardMarkup:
    cid = char_id
    back = CharAction("char_menu", char_id=cid)
    rows = [
        [
            _btn(translator.t("character.stats.btn_level_up",   lang=lang), CharAction("char_level", char_id=cid, sub="up")),
            _btn(translator.t("character.stats.btn_level_down", lang=lang), CharAction("char_level", char_id=cid, sub="down")),
        ],
        _nav_row(back_action=back, menu_char_id=cid, lang=lang),
    ]
    return InlineKeyboardMarkup(rows)


def build_level_class_choice_keyboard(
    char_id: int, direction: str, class_names: list[str], lang: str = "it"
) -> InlineKeyboardMarkup:
    cid = char_id
    back = CharAction("char_level", char_id=cid)
    rows = [
        [_btn(cn, CharAction("char_level", char_id=cid, sub=direction, extra=cn))]
        for cn in class_names
    ]
    rows.append(_nav_row(back_action=back, menu_char_id=cid, lang=lang))
    return InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------------------
# Spells
# ---------------------------------------------------------------------------

def build_spell_level_picker_keyboard(
    char_id: int, available_levels: list[int], lang: str = "it",
) -> InlineKeyboardMarkup:
    """Build a level picker keyboard for the 'select_level_directly' mode.

    Shows one button per spell level that has at least one spell, plus a
    ➕ learn button and the standard ⬅️ / 🏠 nav row.
    """
    cid = char_id
    rows: list[list[InlineKeyboardButton]] = []
    level_row: list[InlineKeyboardButton] = []
    for lvl in available_levels:
        label = (
            translator.t("character.spells.level_btn_cantrips", lang=lang)
            if lvl == 0
            else translator.t("character.spells.level_btn_generic", lang=lang, level=lvl)
        )
        level_row.append(
            _btn(label, CharAction("char_spells", char_id=cid, extra=str(lvl)))
        )
        if len(level_row) == 3:
            rows.append(level_row)
            level_row = []
    if level_row:
        rows.append(level_row)
    rows.append([_btn(translator.t("character.spells.btn_search", lang=lang), CharAction("char_spells", char_id=cid, sub="search"))])
    rows.append([_btn(translator.t("character.spells.btn_learn",  lang=lang), CharAction("char_spells", char_id=cid, sub="learn"))])
    rows.append(_nav_row(back_action=CharAction("char_menu", char_id=cid), menu_char_id=cid, lang=lang))
    return InlineKeyboardMarkup(rows)


def build_spells_menu_keyboard(
    char_id: int, spells: list[Spell], page: int,
    concentrating_spell_id: int | None = None,
    level_filter: int | None = None,
    lang: str = "it",
) -> InlineKeyboardMarkup:
    """Build keyboard for viewing spell list with pagination.

    When *level_filter* is set the ⬅️ Indietro navigates back to the level
    picker rather than the character menu.
    """
    cid = char_id
    back = (
        CharAction("char_spells", char_id=cid)          # → level picker
        if level_filter is not None
        else CharAction("char_menu", char_id=cid)        # → char menu
    )
    level_extra = str(level_filter) if level_filter is not None else ""
    start = page * PAGE_SIZE
    page_spells = spells[start: start + PAGE_SIZE]
    has_next = len(spells) > start + PAGE_SIZE

    rows = [
        [_btn(
            _spell_list_label(s, concentrating_spell_id),
            CharAction("char_spells", char_id=cid, sub="detail", item_id=s.id,
                       back=make_char_back("char_spells", cid, page=page, extra=level_extra)),
        )]
        for s in page_spells
    ]
    rows.append([_btn(translator.t("character.spells.btn_search", lang=lang), CharAction("char_spells", char_id=cid, sub="search"))])
    rows.append([_btn(translator.t("character.spells.btn_learn",  lang=lang), CharAction("char_spells", char_id=cid, sub="learn"))])

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(_btn(translator.t("nav.prev", lang=lang), CharAction("char_spells", char_id=cid, page=page - 1, extra=level_extra)))
    nav.append(_btn(translator.t("nav.back", lang=lang), back))
    if has_next:
        nav.append(_btn(translator.t("nav.next", lang=lang), CharAction("char_spells", char_id=cid, page=page + 1, extra=level_extra)))
    rows.append(nav)
    return InlineKeyboardMarkup(rows)


def _spell_list_label(spell: Spell, concentrating_spell_id: int | None = None) -> str:
    """Build the label for a spell in the list view."""
    prefix = "✨" if spell.level == 0 else f"Liv.{spell.level}"
    indicators = ""
    if concentrating_spell_id == spell.id:
        indicators += "⚡"
    elif spell.is_concentration:
        indicators += "🔮"
    if spell.is_ritual:
        indicators += "®️"
    if spell.is_pinned:
        indicators += "📌"
    name = spell.name
    if indicators:
        name = f"{indicators} {name}"
    return f"{prefix} {name}"


def build_spell_search_results_keyboard(
    char_id: int, spells: list[Spell],
    concentrating_spell_id: int | None = None,
    lang: str = "it",
) -> InlineKeyboardMarkup:
    """Build a keyboard showing fuzzy search results for spells.

    Each matched spell opens the detail view; the back button from the detail
    view returns here (via ``extra="search_show"``).  Bottom row has a
    *Nuova Ricerca* shortcut, a *Tutti gli Incantesimi* link, and the 🏠 Menu.
    """
    cid = char_id
    # Back tuple used by each spell button so the detail view can return here
    search_back = make_char_back("char_spells", cid, extra="search_show")
    rows = [
        [_btn(
            _spell_list_label(s, concentrating_spell_id),
            CharAction("char_spells", char_id=cid, sub="detail", item_id=s.id,
                       back=search_back),
        )]
        for s in spells
    ]
    rows.append([_btn(translator.t("character.spells.btn_new_search", lang=lang), CharAction("char_spells", char_id=cid, sub="search"))])
    rows.append([
        _btn(translator.t("character.spells.btn_all",  lang=lang), CharAction("char_spells", char_id=cid)),
        _btn(translator.t("nav.menu",                  lang=lang), CharAction("char_menu",   char_id=cid)),
    ])
    return InlineKeyboardMarkup(rows)





def build_spell_detail_keyboard(
    char_id: int, spell: Spell, back_page: int = 0,
    *, is_concentrating: bool = False, back_extra: str = "", lang: str = "it",
) -> InlineKeyboardMarkup:
    """Build keyboard for spell detail view with all actions."""
    cid = char_id
    sid = spell.id
    back = CharAction("char_spells", char_id=cid, page=back_page, extra=back_extra)
    rows: list[list[InlineKeyboardButton]] = []

    # Use spell
    rows.append([_btn(translator.t("character.spells.btn_use", lang=lang), CharAction("char_spells", char_id=cid, sub="use", item_id=sid))])

    # Concentration controls
    if spell.is_concentration:
        if is_concentrating:
            rows.append([
                _btn(translator.t("character.spells.btn_drop_conc",    lang=lang), CharAction("char_spells", char_id=cid, sub="drop_conc")),
                _btn(translator.t("character.spells.btn_conc_save",    lang=lang), CharAction("char_spells", char_id=cid, sub="conc_save")),
            ])
        else:
            rows.append([
                _btn(translator.t("character.spells.btn_activate_conc", lang=lang), CharAction("char_spells", char_id=cid, sub="activate_conc", item_id=sid)),
            ])

    # Pin / Edit / Forget
    pin_label = (
        translator.t("character.spells.btn_unpin", lang=lang)
        if spell.is_pinned
        else translator.t("character.spells.btn_pin", lang=lang)
    )
    rows.append([
        _btn(pin_label, CharAction("char_spells", char_id=cid, sub="pin", item_id=sid)),
        _btn(translator.t("character.spells.btn_edit", lang=lang), CharAction("char_spells", char_id=cid, sub="edit_menu", item_id=sid)),
    ])
    rows.append([_btn(translator.t("character.spells.btn_forget", lang=lang), CharAction("char_spells", char_id=cid, sub="forget", item_id=sid))])
    rows.append(_nav_row(back_action=back, menu_char_id=cid, lang=lang))
    return InlineKeyboardMarkup(rows)


def build_spell_edit_field_keyboard(
    char_id: int, spell_id: int, lang: str = "it",
) -> InlineKeyboardMarkup:
    """Build keyboard to choose which spell field to edit."""
    cid = char_id
    back = CharAction("char_spells", char_id=cid, sub="detail", item_id=spell_id)

    fields = [
        (translator.t("character.spells.edit_field_level",         lang=lang), "level"),
        (translator.t("character.spells.edit_field_casting_time",   lang=lang), "casting_time"),
        (translator.t("character.spells.edit_field_range_area",     lang=lang), "range_area"),
        (translator.t("character.spells.edit_field_components",     lang=lang), "components"),
        (translator.t("character.spells.edit_field_duration",       lang=lang), "duration"),
        (translator.t("character.spells.edit_field_concentration",  lang=lang), "is_concentration"),
        (translator.t("character.spells.edit_field_ritual",         lang=lang), "is_ritual"),
        (translator.t("character.spells.edit_field_attack_save",    lang=lang), "attack_save"),
        (translator.t("character.spells.edit_field_description",    lang=lang), "description"),
        (translator.t("character.spells.edit_field_higher_level",   lang=lang), "higher_level"),
    ]
    rows = [
        [_btn(label, CharAction("char_spells", char_id=cid, sub=f"edit_{key}", item_id=spell_id))]
        for label, key in fields
    ]
    rows.append(_nav_row(back_action=back, menu_char_id=cid, lang=lang))
    return InlineKeyboardMarkup(rows)


def build_yes_no_keyboard(
    char_id: int, *, yes_sub: str, no_sub: str, action: str = "char_spells", lang: str = "it",
) -> InlineKeyboardMarkup:
    """Generic yes/no keyboard for inline choices."""
    cid = char_id
    rows = [[
        _btn(translator.t("character.spells.yes_btn", lang=lang), CharAction(action, char_id=cid, sub=yes_sub)),
        _btn(translator.t("character.spells.no_btn",  lang=lang), CharAction(action, char_id=cid, sub=no_sub)),
    ]]
    return InlineKeyboardMarkup(rows)


def build_spell_use_level_keyboard(
    char_id: int, spell_id: int, available_slots: list[SpellSlot], lang: str = "it",
) -> InlineKeyboardMarkup:
    cid = char_id
    back = CharAction("char_spells", char_id=cid, sub="detail", item_id=spell_id)
    rows = [
        [_btn(
            translator.t("character.spells.slot_btn", lang=lang, level=s.level, available=s.available, total=s.total),
            CharAction("char_spells", char_id=cid, sub="use_slot", item_id=spell_id, extra=str(s.level)),
        )]
        for s in available_slots
    ]
    rows.append(_nav_row(back_action=back, menu_char_id=cid, lang=lang))
    return InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------------------
# Spell Slots
# ---------------------------------------------------------------------------

def build_spell_slots_keyboard(
    char_id: int, slots: list[SpellSlot], lang: str = "it",
) -> InlineKeyboardMarkup:
    cid = char_id
    back = CharAction("char_menu", char_id=cid)
    rows = [
        [
            _btn(
                f"Liv.{s.level} ({s.available}/{s.total})",
                CharAction("char_slots", char_id=cid, sub="slot_detail", item_id=s.id),
            )
        ]
        for s in sorted(slots, key=lambda x: x.level)
    ]
    rows.append([_btn(translator.t("character.slots.btn_add",       lang=lang), CharAction("char_slots", char_id=cid, sub="add"))])
    rows.append([_btn(translator.t("character.slots.btn_reset_all", lang=lang), CharAction("char_slots", char_id=cid, sub="reset_all"))])
    rows.append(_nav_row(back_action=back, menu_char_id=cid, lang=lang))
    return InlineKeyboardMarkup(rows)


def build_spell_slot_detail_keyboard(
    char_id: int, slot: SpellSlot, lang: str = "it",
) -> InlineKeyboardMarkup:
    cid = char_id
    back = CharAction("char_slots", char_id=cid)
    rows = [
        [_btn(translator.t("character.slots.btn_use",         lang=lang), CharAction("char_slots", char_id=cid, sub="use",     item_id=slot.id))],
        [_btn(translator.t("character.slots.btn_restore_one", lang=lang), CharAction("char_slots", char_id=cid, sub="restore", item_id=slot.id))],
        [_btn(translator.t("character.slots.btn_remove",      lang=lang), CharAction("char_slots", char_id=cid, sub="remove",  item_id=slot.id))],
        _nav_row(back_action=back, menu_char_id=cid, lang=lang),
    ]
    return InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------------------
# Bag / Items
# ---------------------------------------------------------------------------

def build_bag_keyboard(
    char_id: int, items: list[Item], page: int, lang: str = "it",
) -> InlineKeyboardMarkup:
    cid = char_id
    back = CharAction("char_menu", char_id=cid)
    start = page * PAGE_SIZE
    page_items = items[start: start + PAGE_SIZE]
    has_next = len(items) > start + PAGE_SIZE

    rows = [
        [_btn(
            f"📦 {i.name} x{i.quantity}",
            CharAction("char_bag", char_id=cid, sub="item_detail", item_id=i.id,
                       back=make_char_back("char_bag", cid, page=page)),
        )]
        for i in page_items
    ]
    rows.append([_btn(translator.t("character.bag.btn_add", lang=lang), CharAction("char_bag", char_id=cid, sub="add"))])

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(_btn(translator.t("nav.prev", lang=lang), CharAction("char_bag", char_id=cid, page=page - 1)))
    nav.append(_btn(translator.t("nav.back", lang=lang), back))
    if has_next:
        nav.append(_btn(translator.t("nav.next", lang=lang), CharAction("char_bag", char_id=cid, page=page + 1)))
    rows.append(nav)
    return InlineKeyboardMarkup(rows)


def build_item_detail_keyboard(
    char_id: int, item_id: int, back_page: int = 0, lang: str = "it",
) -> InlineKeyboardMarkup:
    cid = char_id
    back = CharAction("char_bag", char_id=cid, page=back_page)
    rows = [
        [
            _btn(translator.t("character.bag.btn_qty_add", lang=lang), CharAction("char_bag", char_id=cid, sub="qty_add", item_id=item_id)),
            _btn(translator.t("character.bag.btn_qty_rem", lang=lang), CharAction("char_bag", char_id=cid, sub="qty_rem", item_id=item_id)),
        ],
        [_btn(translator.t("character.bag.btn_remove_all", lang=lang), CharAction("char_bag", char_id=cid, sub="remove_all", item_id=item_id))],
        _nav_row(back_action=back, menu_char_id=cid, lang=lang),
    ]
    return InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------------------
# Currency
# ---------------------------------------------------------------------------

def build_currency_keyboard(char_id: int, lang: str = "it") -> InlineKeyboardMarkup:
    cid = char_id
    back = CharAction("char_menu", char_id=cid)
    currency_labels = get_currency_labels(lang)
    rows = [
        [_btn(f"{emoji} {label}", CharAction("char_currency", char_id=cid, sub="edit", extra=key))]
        for key, (label, emoji) in currency_labels.items()
    ]
    rows.append([_btn(translator.t("character.currency.btn_convert", lang=lang), CharAction("char_currency", char_id=cid, sub="convert"))])
    rows.append(_nav_row(back_action=back, menu_char_id=cid, lang=lang))
    return InlineKeyboardMarkup(rows)


def build_currency_edit_keyboard(char_id: int, currency_key: str, lang: str = "it") -> InlineKeyboardMarkup:
    cid = char_id
    back = CharAction("char_currency", char_id=cid)
    rows = [
        [
            _btn(translator.t("character.currency.btn_add",    lang=lang), CharAction("char_currency", char_id=cid, sub="add",    extra=currency_key)),
            _btn(translator.t("character.currency.btn_remove", lang=lang), CharAction("char_currency", char_id=cid, sub="remove", extra=currency_key)),
        ],
        _nav_row(back_action=back, menu_char_id=cid, lang=lang),
    ]
    return InlineKeyboardMarkup(rows)


def build_currency_convert_source_keyboard(
    char_id: int, currency_keys: list[str], lang: str = "it",
) -> InlineKeyboardMarkup:
    cid = char_id
    back = CharAction("char_currency", char_id=cid)
    currency_labels = get_currency_labels(lang)
    rows = [
        [_btn(
            f"{currency_labels[k][1]} {currency_labels[k][0]}",
            CharAction("char_currency", char_id=cid, sub="conv_source", extra=k),
        )]
        for k in currency_keys
    ]
    rows.append(_nav_row(back_action=back, menu_char_id=cid, lang=lang))
    return InlineKeyboardMarkup(rows)


def build_currency_convert_target_keyboard(
    char_id: int, source_key: str, currency_keys: list[str], lang: str = "it",
) -> InlineKeyboardMarkup:
    cid = char_id
    back = CharAction("char_currency", char_id=cid, sub="convert")
    currency_labels = get_currency_labels(lang)
    rows = [
        [_btn(
            f"{currency_labels[k][1]} {currency_labels[k][0]}",
            CharAction("char_currency", char_id=cid, sub="conv_target", extra=f"{source_key}|{k}"),
        )]
        for k in currency_keys if k != source_key
    ]
    rows.append(_nav_row(back_action=back, menu_char_id=cid, lang=lang))
    return InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------------------
# Abilities
# ---------------------------------------------------------------------------

def build_abilities_keyboard(
    char_id: int, abilities: list[Ability], page: int, lang: str = "it",
) -> InlineKeyboardMarkup:
    cid = char_id
    back = CharAction("char_menu", char_id=cid)
    start = page * PAGE_SIZE
    page_items = abilities[start: start + PAGE_SIZE]
    has_next = len(abilities) > start + PAGE_SIZE

    rows = [
        [_btn(
            f"{'🔵' if a.is_passive else '⚡'} {a.name}"
            + (f" ({a.uses}/{a.max_uses})" if a.max_uses is not None else ""),
            CharAction("char_abilities", char_id=cid, sub="detail", item_id=a.id,
                       back=make_char_back("char_abilities", cid, page=page)),
        )]
        for a in page_items
    ]
    rows.append([_btn(translator.t("character.abilities.btn_learn", lang=lang), CharAction("char_abilities", char_id=cid, sub="learn"))])

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(_btn(translator.t("nav.prev", lang=lang), CharAction("char_abilities", char_id=cid, page=page - 1)))
    nav.append(_btn(translator.t("nav.back", lang=lang), back))
    if has_next:
        nav.append(_btn(translator.t("nav.next", lang=lang), CharAction("char_abilities", char_id=cid, page=page + 1)))
    rows.append(nav)
    return InlineKeyboardMarkup(rows)


def build_ability_detail_keyboard(
    char_id: int, ability: Ability, back_page: int = 0, lang: str = "it",
) -> InlineKeyboardMarkup:
    cid = char_id
    back = CharAction("char_abilities", char_id=cid, page=back_page)
    rows: list[list[InlineKeyboardButton]] = []
    if not ability.is_passive and ability.max_uses is not None:
        rows.append([_btn(translator.t("character.abilities.btn_use", lang=lang), CharAction("char_abilities", char_id=cid, sub="use", item_id=ability.id))])
    if ability.is_passive:
        label = (
            translator.t("character.abilities.btn_deactivate", lang=lang)
            if ability.is_active
            else translator.t("character.abilities.btn_activate", lang=lang)
        )
        rows.append([_btn(label, CharAction("char_abilities", char_id=cid, sub="toggle", item_id=ability.id))])
    rows.append([_btn(translator.t("character.abilities.btn_forget", lang=lang), CharAction("char_abilities", char_id=cid, sub="forget", item_id=ability.id))])
    rows.append(_nav_row(back_action=back, menu_char_id=cid, lang=lang))
    return InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------------------
# Multiclass
# ---------------------------------------------------------------------------

def build_multiclass_keyboard(char_id: int, classes: list | None = None, lang: str = "it") -> InlineKeyboardMarkup:
    cid = char_id
    back = CharAction("char_menu", char_id=cid)
    rows = [
        [_btn(translator.t("character.multiclass.btn_add",    lang=lang), CharAction("char_multiclass", char_id=cid, sub="add"))],
        [_btn(translator.t("character.multiclass.btn_remove", lang=lang), CharAction("char_multiclass", char_id=cid, sub="remove"))],
    ]
    # Add resource buttons for classes that have resources
    if classes:
        for cls in classes:
            has_resources = hasattr(cls, 'resources') and cls.resources
            if has_resources:
                label = translator.t("character.multiclass.resources_label", lang=lang, resources=cls.class_name)
                rows.append([_btn(label, CharAction("char_class_res", char_id=cid,
                                                     sub="menu", extra=str(cls.id)))])
    rows.append(_nav_row(back_action=back, menu_char_id=cid, lang=lang))
    return InlineKeyboardMarkup(rows)


def build_class_add_mode_keyboard(char_id: int, lang: str = "it") -> InlineKeyboardMarkup:
    """Keyboard to choose between guided class selection and custom entry."""
    cid = char_id
    back = CharAction("char_multiclass", char_id=cid)
    rows = [
        [
            _btn(translator.t("character.multiclass.guided_btn", lang=lang), CharAction("char_multiclass", char_id=cid, sub="guided")),
            _btn(translator.t("character.multiclass.custom_btn", lang=lang), CharAction("char_multiclass", char_id=cid, sub="custom")),
        ],
        _nav_row(back_action=back, menu_char_id=cid, lang=lang),
    ]
    return InlineKeyboardMarkup(rows)


def build_class_guided_keyboard(char_id: int, lang: str = "it") -> InlineKeyboardMarkup:
    """Keyboard listing all predefined D&D 5e classes for guided selection."""
    from bot.data.classes import DND_CLASSES
    cid = char_id
    back = CharAction("char_multiclass", char_id=cid, sub="add")
    rows = []
    # 2 classes per row
    for i in range(0, len(DND_CLASSES), 2):
        row = []
        for cls in DND_CLASSES[i:i + 2]:
            row.append(_btn(cls, CharAction("char_multiclass", char_id=cid, sub="select_guided", extra=cls)))
        rows.append(row)
    rows.append(_nav_row(back_action=back, menu_char_id=cid, lang=lang))
    return InlineKeyboardMarkup(rows)


def build_subclass_input_keyboard(char_id: int, lang: str = "it") -> InlineKeyboardMarkup:
    """Keyboard shown while waiting for subclass text input — offers a skip button."""
    cid = char_id
    rows = [
        [_btn(translator.t("character.multiclass.skip_subclass_btn", lang=lang), CharAction("char_multiclass", char_id=cid, sub="skip_subclass"))],
        [_btn(translator.t("nav.cancel", lang=lang), CharAction("char_multiclass", char_id=cid))],
    ]
    return InlineKeyboardMarkup(rows)


def build_class_resources_keyboard(
    char_id: int, class_id: int, resources: list, lang: str = "it",
) -> InlineKeyboardMarkup:
    """Keyboard for the class resources management screen.

    Shows [➖] [ResourceName: current/total] [➕] for each resource,
    plus a 'Ripristina Tutto' button and navigation.
    """
    cid = char_id
    back = CharAction("char_multiclass", char_id=cid)
    rows = []
    for res in resources:
        total_display = translator.t("character.class_resources.infinity", lang=lang) if res.total >= 99 else str(res.total)
        label = f"🔋 {res.name}: {res.current}/{total_display}"
        rows.append([
            _btn("➖", CharAction("char_class_res", char_id=cid, sub="use",
                                   item_id=res.id, extra=str(class_id))),
            _btn(label, CharAction("char_class_res", char_id=cid, sub="noop",
                                    item_id=res.id, extra=str(class_id))),
            _btn("➕", CharAction("char_class_res", char_id=cid, sub="restore_one",
                                   item_id=res.id, extra=str(class_id))),
        ])
    if resources:
        rows.append([_btn(translator.t("character.class_resources.restore_all_btn", lang=lang),
                          CharAction("char_class_res", char_id=cid, sub="restore_all", extra=str(class_id)))])
    rows.append(_nav_row(back_action=back, menu_char_id=cid, lang=lang))
    return InlineKeyboardMarkup(rows)


def build_multiclass_remove_keyboard(
    char_id: int, class_names: list[str], lang: str = "it",
) -> InlineKeyboardMarkup:
    cid = char_id
    back = CharAction("char_multiclass", char_id=cid)
    rows = [
        [_btn(cn, CharAction("char_multiclass", char_id=cid, sub="remove_confirm", extra=cn))]
        for cn in class_names
    ]
    rows.append(_nav_row(back_action=back, menu_char_id=cid, lang=lang))
    return InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------------------
# Dice
# ---------------------------------------------------------------------------

DICE_TYPES = ["d4", "d6", "d8", "d10", "d12", "d20", "d100"]


def build_dice_keyboard(char_id: int, lang: str = "it") -> InlineKeyboardMarkup:
    cid = char_id
    back = CharAction("char_menu", char_id=cid)
    rows = [
        [_btn(f"🎲 {d}", CharAction("char_dice", char_id=cid, sub=d))]
        for d in DICE_TYPES
    ]
    rows.append([_btn(translator.t("character.dice.btn_clear", lang=lang), CharAction("char_dice", char_id=cid, sub="clear_history"))])
    rows.append(_nav_row(back_action=back, menu_char_id=cid, lang=lang))
    return InlineKeyboardMarkup(rows)


def build_dice_count_keyboard(char_id: int, die: str, lang: str = "it") -> InlineKeyboardMarkup:
    cid = char_id
    back = CharAction("char_dice", char_id=cid)
    counts = [1, 2, 3, 4, 5, 6, 8, 10]
    rows = [
        [_btn(f"{n}{die}", CharAction("char_dice", char_id=cid, sub="roll", extra=f"{n}|{die}"))]
        for n in counts
    ]
    rows.append(_nav_row(back_action=back, menu_char_id=cid, lang=lang))
    return InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------

def build_notes_keyboard(
    char_id: int, note_titles: list[str], page: int, lang: str = "it",
) -> InlineKeyboardMarkup:
    cid = char_id
    back = CharAction("char_menu", char_id=cid)
    start = page * PAGE_SIZE
    page_notes = note_titles[start: start + PAGE_SIZE]
    has_next = len(note_titles) > start + PAGE_SIZE

    rows = [
        [_btn(f"📝 {title}", CharAction("char_notes", char_id=cid, sub="open", extra=title,
                                        back=make_char_back("char_notes", cid, page=page)))]
        for title in page_notes
    ]
    rows.append([_btn(translator.t("character.notes.btn_new",   lang=lang), CharAction("char_notes", char_id=cid, sub="new"))])
    rows.append([_btn(translator.t("character.notes.btn_voice", lang=lang), CharAction("char_notes", char_id=cid, sub="new_voice"))])

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(_btn(translator.t("nav.prev", lang=lang), CharAction("char_notes", char_id=cid, page=page - 1)))
    nav.append(_btn(translator.t("nav.back", lang=lang), back))
    if has_next:
        nav.append(_btn(translator.t("nav.next", lang=lang), CharAction("char_notes", char_id=cid, page=page + 1)))
    rows.append(nav)
    return InlineKeyboardMarkup(rows)


def build_note_detail_keyboard(
    char_id: int, title: str, back_page: int = 0, lang: str = "it",
) -> InlineKeyboardMarkup:
    cid = char_id
    back = CharAction("char_notes", char_id=cid, page=back_page)
    rows = [
        [_btn(translator.t("character.notes.btn_edit",   lang=lang), CharAction("char_notes", char_id=cid, sub="edit",   extra=title))],
        [_btn(translator.t("character.notes.btn_delete", lang=lang), CharAction("char_notes", char_id=cid, sub="delete", extra=title))],
        _nav_row(back_action=back, menu_char_id=cid, lang=lang),
    ]
    return InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------------------
# Maps
# ---------------------------------------------------------------------------

def build_maps_keyboard(
    char_id: int, zone_names: list[str], page: int, lang: str = "it",
) -> InlineKeyboardMarkup:
    cid = char_id
    back = CharAction("char_menu", char_id=cid)
    start = page * PAGE_SIZE
    page_zones = zone_names[start: start + PAGE_SIZE]
    has_next = len(zone_names) > start + PAGE_SIZE

    rows = [
        [_btn(f"📍 {z}", CharAction("char_maps", char_id=cid, sub="zone", extra=z,
                                    back=make_char_back("char_maps", cid, page=page)))]
        for z in page_zones
    ]
    rows.append([_btn(translator.t("character.maps.btn_add_zone", lang=lang), CharAction("char_maps", char_id=cid, sub="new_zone"))])

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(_btn(translator.t("nav.prev", lang=lang), CharAction("char_maps", char_id=cid, page=page - 1)))
    nav.append(_btn(translator.t("nav.back", lang=lang), back))
    if has_next:
        nav.append(_btn(translator.t("nav.next", lang=lang), CharAction("char_maps", char_id=cid, page=page + 1)))
    rows.append(nav)
    return InlineKeyboardMarkup(rows)


def build_map_zone_keyboard(
    char_id: int, zone: str, maps: list[Map], back_page: int = 0, lang: str = "it",
) -> InlineKeyboardMarkup:
    cid = char_id
    back = CharAction("char_maps", char_id=cid, page=back_page)
    rows: list[list[InlineKeyboardButton]] = []
    for i, m in enumerate(maps):
        label = (
            translator.t("character.maps.photo_label",    lang=lang, n=i + 1)
            if m.file_type == "photo"
            else translator.t("character.maps.document_label", lang=lang, n=i + 1)
        )
        rows.append([
            _btn(label, CharAction("char_maps", char_id=cid, sub="view_file", item_id=m.id, extra=zone)),
            _btn("🗑️", CharAction("char_maps", char_id=cid, sub="delete_file", item_id=m.id, extra=zone)),
        ])
    rows.append([_btn(translator.t("character.maps.btn_add_file",    lang=lang), CharAction("char_maps", char_id=cid, sub="add_file",    extra=zone))])
    rows.append([_btn(translator.t("character.maps.btn_delete_zone", lang=lang), CharAction("char_maps", char_id=cid, sub="delete_zone", extra=zone))])
    rows.append(_nav_row(back_action=back, menu_char_id=cid, lang=lang))
    return InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def build_settings_keyboard(
    char_id: int, settings: dict, is_party_active: bool = False, lang: str = "it",
) -> InlineKeyboardMarkup:
    cid = char_id
    back = CharAction("char_menu", char_id=cid)
    spell_mgmt = settings.get("spell_management", "paginate_by_level")
    spell_label = (
        translator.t("character.settings.spell_mgmt_by_level", lang=lang)
        if spell_mgmt == "paginate_by_level"
        else translator.t("character.settings.spell_mgmt_direct", lang=lang)
    )
    party_label_suffix = (
        translator.t("character.settings.party_yes", lang=lang)
        if is_party_active
        else translator.t("character.settings.party_no", lang=lang)
    )
    rows = [
        [_btn(translator.t("character.settings.btn_spell_mgmt",   lang=lang, label=spell_label),
              CharAction("char_settings", char_id=cid, sub="toggle_spell_mgmt"))],
        [_btn(translator.t("character.settings.btn_party_active", lang=lang, label=party_label_suffix),
              CharAction("char_party_active", char_id=cid))],
        _nav_row(back_action=back, menu_char_id=cid, lang=lang),
    ]
    return InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------------------
# Character deletion
# ---------------------------------------------------------------------------

def build_delete_confirm_keyboard(char_id: int, lang: str = "it") -> InlineKeyboardMarkup:
    cid = char_id
    rows = [
        [
            _btn(translator.t("character.selection.delete_confirm_yes", lang=lang), CharAction("char_delete", char_id=cid, sub="confirm")),
            _btn(translator.t("character.selection.delete_confirm_no",  lang=lang), CharAction("char_menu",   char_id=cid)),
        ]
    ]
    return InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------------------
# Conditions
# ---------------------------------------------------------------------------

def build_conditions_keyboard(
    char_id: int, conditions: dict, lang: str = "it"
) -> InlineKeyboardMarkup:
    """Full list of conditions, each as a toggle button showing active/inactive state."""
    cid = char_id
    back = CharAction("char_menu", char_id=cid)
    rows: list[list[InlineKeyboardButton]] = []

    for slug in CONDITIONS_ORDER:
        name = translator.t(f"character.conditions.names.{slug}", lang=lang)
        if slug == "exhaustion":
            level = int(conditions.get("exhaustion", 0))
            marker = f"✅ {level}/6" if level > 0 else "⬛"
        else:
            active = bool(conditions.get(slug, False))
            marker = "✅" if active else "⬛"
        label = f"{marker} {name}"
        rows.append([_btn(label, CharAction("char_conditions", char_id=cid, sub="detail", extra=slug))])

    rows.append(_nav_row(back_action=back, menu_char_id=cid, lang=lang))
    return InlineKeyboardMarkup(rows)


def build_condition_detail_keyboard(
    char_id: int, slug: str, conditions: dict, lang: str = "it"
) -> InlineKeyboardMarkup:
    """Detail view for a single condition: toggle (or +/- for exhaustion)."""
    cid = char_id
    back = CharAction("char_conditions", char_id=cid)
    rows: list[list[InlineKeyboardButton]] = []

    if slug == "exhaustion":
        level = int(conditions.get("exhaustion", 0))
        rows.append([
            _btn(translator.t("character.conditions.btn_exhaust_down", lang=lang),
                 CharAction("char_conditions", char_id=cid, sub="exhaust_down", extra=slug)),
            _btn(translator.t("character.conditions.btn_exhaust_up", lang=lang),
                 CharAction("char_conditions", char_id=cid, sub="exhaust_up", extra=slug)),
        ])
    else:
        active = bool(conditions.get(slug, False))
        if active:
            rows.append([_btn(
                translator.t("character.conditions.btn_deactivate", lang=lang),
                CharAction("char_conditions", char_id=cid, sub="toggle", extra=slug),
            )])
        else:
            rows.append([_btn(
                translator.t("character.conditions.btn_activate", lang=lang),
                CharAction("char_conditions", char_id=cid, sub="toggle", extra=slug),
            )])

    rows.append(_nav_row(back_action=back, menu_char_id=cid, lang=lang))
    return InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------

def build_skills_keyboard(
    char_id: int,
    char: Character,
    ability_scores: list[AbilityScore],
    lang: str = "it",
) -> InlineKeyboardMarkup:
    """Keyboard for the skills screen: one button per skill showing proficiency + bonus."""
    from bot.data.skills import SKILLS

    cid = char_id
    proficiency_bonus = char.proficiency_bonus

    # Build a map ability_name → ability score value for quick lookup
    score_map = {s.name: s.value for s in ability_scores}

    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []

    for slug, ability in SKILLS:
        score_val = score_map.get(ability, 10)
        mod = (score_val - 10) // 2
        skills_data: dict = char.skills or {}
        is_proficient = bool(skills_data.get(slug, False))
        bonus = mod + (proficiency_bonus if is_proficient else 0)

        skill_name = translator.t(f"character.skills.names.{slug}", lang=lang)
        ability_abbr = translator.t(f"character.skills.ability_abbr.{ability}", lang=lang)
        prof_icon = translator.t(
            "character.skills.proficient_icon" if is_proficient else "character.skills.not_proficient_icon",
            lang=lang,
        )
        bonus_str = f"+{bonus}" if bonus >= 0 else str(bonus)
        label = f"{prof_icon} {skill_name} ({ability_abbr}): {bonus_str}"

        btn = _btn(label, CharAction("char_skills", char_id=cid, sub="toggle", extra=slug))
        row.append(btn)
        if len(row) == 2:
            rows.append(row)
            row = []

    if row:
        rows.append(row)

    rows.append(_nav_row(back_action=CharAction("char_menu", char_id=cid), menu_char_id=cid, lang=lang))
    return InlineKeyboardMarkup(rows)