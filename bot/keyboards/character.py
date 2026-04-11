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
        (translator.t("character.menu.btn_skills",     lang=lang), CharAction("char_skills",     char_id=cid)),
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
        (translator.t("character.menu.btn_inspiration",    lang=lang), CharAction("char_inspiration",    char_id=cid)),
        (translator.t("character.menu.btn_identity",        lang=lang), CharAction("char_identity",        char_id=cid)),
        (translator.t("character.menu.btn_saving_throws",   lang=lang), CharAction("char_saving_throws",   char_id=cid)),
        (translator.t("character.menu.btn_xp",              lang=lang), CharAction("char_xp",              char_id=cid)),
        (translator.t("character.menu.btn_settings",        lang=lang), CharAction("char_settings",        char_id=cid)),
        (translator.t("character.selection.delete_btn",     lang=lang), CharAction("char_delete",          char_id=cid)),
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

def build_hp_keyboard(
    char_id: int,
    lang: str = "it",
    show_death_saves: bool = False,
) -> InlineKeyboardMarkup:
    cid = char_id
    back = CharAction("char_menu", char_id=cid)
    rows = [
        [
            _btn(translator.t("character.hp.btn_damage",      lang=lang), CharAction("char_hp", char_id=cid, sub="damage")),
            _btn(translator.t("character.hp.btn_heal",        lang=lang), CharAction("char_hp", char_id=cid, sub="heal")),
        ],
        [_btn(translator.t("character.hp.btn_set_max",     lang=lang), CharAction("char_hp", char_id=cid, sub="set_max"))],
        [_btn(translator.t("character.hp.btn_set_current", lang=lang), CharAction("char_hp", char_id=cid, sub="set_current"))],
    ]
    rows.append([_btn(translator.t("character.hp.btn_set_temp", lang=lang), CharAction("char_hp", char_id=cid, sub="set_temp"))])
    if show_death_saves:
        rows.append([_btn(
            translator.t("character.death_saves.btn_open", lang=lang),
            CharAction("char_death_saves", char_id=cid),
        )])
    rows.append(_nav_row(back_action=back, menu_char_id=cid, lang=lang))
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
    if rest_type == "short":
        rows.insert(0, [_btn(translator.t("character.rest.btn_hit_dice", lang=lang), CharAction("char_rest", char_id=cid, sub="hit_dice"))])
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

    _ITEM_ICONS = {
        "weapon": "⚔️",
        "armor": "🛡️",
        "shield": "🛡️",
        "consumable": "🧪",
        "tool": "🔧",
        "generic": "📦",
    }
    rows = []
    for i in page_items:
        icon = _ITEM_ICONS.get(getattr(i, "item_type", "generic"), "📦")
        equip_mark = " ✅" if getattr(i, "is_equipped", False) else ""
        rows.append([_btn(
            f"{icon} {i.name} x{i.quantity}{equip_mark}",
            CharAction("char_bag", char_id=cid, sub="item_detail", item_id=i.id,
                       back=make_char_back("char_bag", cid, page=page)),
        )])
    rows.append([_btn(translator.t("character.bag.btn_add", lang=lang), CharAction("char_bag", char_id=cid, sub="add"))])

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(_btn(translator.t("nav.prev", lang=lang), CharAction("char_bag", char_id=cid, page=page - 1)))
    nav.append(_btn(translator.t("nav.back", lang=lang), back))
    if has_next:
        nav.append(_btn(translator.t("nav.next", lang=lang), CharAction("char_bag", char_id=cid, page=page + 1)))
    rows.append(nav)
    return InlineKeyboardMarkup(rows)


def build_item_type_keyboard(char_id: int, lang: str = "it") -> InlineKeyboardMarkup:
    """Type selection keyboard shown at the start of the add-item flow."""
    cid = char_id
    types = [
        ("type_generic", "generic"),
        ("type_weapon", "weapon"),
        ("type_armor", "armor"),
        ("type_shield", "shield"),
        ("type_consumable", "consumable"),
        ("type_tool", "tool"),
    ]
    rows = [
        [_btn(translator.t(f"character.bag.{key}", lang=lang),
              CharAction("char_bag", char_id=cid, sub="select_type", extra=itype))]
        for key, itype in types
    ]
    rows.append([_btn(translator.t("nav.cancel", lang=lang), CharAction("char_bag", char_id=cid))])
    return InlineKeyboardMarkup(rows)


def build_damage_type_keyboard(char_id: int, lang: str = "it") -> InlineKeyboardMarkup:
    """Damage type selection keyboard for weapons."""
    cid = char_id
    dmg_keys = [
        "dmg_slashing", "dmg_piercing", "dmg_bludgeoning", "dmg_fire",
        "dmg_cold", "dmg_lightning", "dmg_acid", "dmg_poison",
        "dmg_necrotic", "dmg_radiant", "dmg_force", "dmg_psychic",
        "dmg_thunder", "dmg_other",
    ]
    rows: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(dmg_keys), 2):
        row = [_btn(translator.t(f"character.bag.{dmg_keys[i]}", lang=lang),
                    CharAction("char_bag", char_id=cid, sub="set_damage_type", extra=dmg_keys[i]))]
        if i + 1 < len(dmg_keys):
            row.append(_btn(translator.t(f"character.bag.{dmg_keys[i+1]}", lang=lang),
                            CharAction("char_bag", char_id=cid, sub="set_damage_type", extra=dmg_keys[i+1])))
        rows.append(row)
    rows.append([_btn(translator.t("nav.cancel", lang=lang), CharAction("char_bag", char_id=cid))])
    return InlineKeyboardMarkup(rows)


def build_weapon_type_keyboard(char_id: int, lang: str = "it") -> InlineKeyboardMarkup:
    """Melee / Ranged selection keyboard."""
    cid = char_id
    return InlineKeyboardMarkup([
        [
            _btn(translator.t("character.bag.weapon_type_melee", lang=lang),
                 CharAction("char_bag", char_id=cid, sub="set_weapon_type", extra="melee")),
            _btn(translator.t("character.bag.weapon_type_ranged", lang=lang),
                 CharAction("char_bag", char_id=cid, sub="set_weapon_type", extra="ranged")),
        ],
        [_btn(translator.t("nav.cancel", lang=lang), CharAction("char_bag", char_id=cid))],
    ])


def build_weapon_properties_keyboard(
    char_id: int, selected: list[str], lang: str = "it"
) -> InlineKeyboardMarkup:
    """Multi-select properties keyboard; selected items show ✅."""
    cid = char_id
    prop_keys = [
        "prop_finesse", "prop_versatile", "prop_heavy", "prop_light",
        "prop_thrown", "prop_two_handed", "prop_ammunition", "prop_loading",
        "prop_reach", "prop_special",
    ]
    rows: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(prop_keys), 2):
        row = []
        for k in prop_keys[i:i+2]:
            label = translator.t(f"character.bag.{k}", lang=lang)
            mark = "✅ " if k in selected else ""
            row.append(_btn(f"{mark}{label}", CharAction("char_bag", char_id=cid, sub="toggle_prop", extra=k)))
        rows.append(row)
    rows.append([_btn(translator.t("character.bag.btn_confirm_properties", lang=lang),
                      CharAction("char_bag", char_id=cid, sub="confirm_props"))])
    rows.append([_btn(translator.t("nav.cancel", lang=lang), CharAction("char_bag", char_id=cid))])
    return InlineKeyboardMarkup(rows)


def build_armor_type_keyboard(char_id: int, lang: str = "it") -> InlineKeyboardMarkup:
    """Light / Medium / Heavy selection keyboard."""
    cid = char_id
    return InlineKeyboardMarkup([
        [
            _btn(translator.t("character.bag.armor_type_light", lang=lang),
                 CharAction("char_bag", char_id=cid, sub="set_armor_type", extra="light")),
            _btn(translator.t("character.bag.armor_type_medium", lang=lang),
                 CharAction("char_bag", char_id=cid, sub="set_armor_type", extra="medium")),
            _btn(translator.t("character.bag.armor_type_heavy", lang=lang),
                 CharAction("char_bag", char_id=cid, sub="set_armor_type", extra="heavy")),
        ],
        [_btn(translator.t("nav.cancel", lang=lang), CharAction("char_bag", char_id=cid))],
    ])


def build_stealth_keyboard(char_id: int, lang: str = "it") -> InlineKeyboardMarkup:
    """Yes / No stealth disadvantage keyboard."""
    cid = char_id
    return InlineKeyboardMarkup([
        [
            _btn(translator.t("character.bag.stealth_yes", lang=lang),
                 CharAction("char_bag", char_id=cid, sub="set_stealth", extra="yes")),
            _btn(translator.t("character.bag.stealth_no", lang=lang),
                 CharAction("char_bag", char_id=cid, sub="set_stealth", extra="no")),
        ],
        [_btn(translator.t("nav.cancel", lang=lang), CharAction("char_bag", char_id=cid))],
    ])


def build_item_detail_keyboard(
    char_id: int, item_id: int, item_type: str = "generic",
    is_equipped: bool = False, back_page: int = 0, lang: str = "it",
) -> InlineKeyboardMarkup:
    cid = char_id
    back = CharAction("char_bag", char_id=cid, page=back_page)
    rows: list[list[InlineKeyboardButton]] = [
        [
            _btn(translator.t("character.bag.btn_qty_add", lang=lang), CharAction("char_bag", char_id=cid, sub="qty_add", item_id=item_id)),
            _btn(translator.t("character.bag.btn_qty_rem", lang=lang), CharAction("char_bag", char_id=cid, sub="qty_rem", item_id=item_id)),
        ],
        [_btn(translator.t("character.bag.btn_remove_all", lang=lang), CharAction("char_bag", char_id=cid, sub="remove_all", item_id=item_id))],
    ]
    if item_type in ("weapon", "armor", "shield"):
        if is_equipped:
            equip_label = translator.t("character.bag.btn_unequip", lang=lang)
        else:
            equip_label = translator.t("character.bag.btn_equip", lang=lang)
        rows.insert(0, [_btn(equip_label, CharAction("char_bag", char_id=cid, sub="equip", item_id=item_id))])
    if item_type == "weapon":
        rows.insert(1, [_btn(translator.t("character.bag.btn_attack", lang=lang), CharAction("char_bag", char_id=cid, sub="attack", item_id=item_id))])
    rows.append(_nav_row(back_action=back, menu_char_id=cid, lang=lang))
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
    # Add per-class buttons: hit die editor + resource manager
    if classes:
        for cls in classes:
            die_label = translator.t(
                "character.multiclass.btn_set_hit_die", lang=lang,
                cls=cls.class_name,
                current=f"d{cls.hit_die}" if cls.hit_die else "—",
            )
            rows.append([_btn(die_label, CharAction("char_multiclass", char_id=cid,
                                                     sub="set_hit_die", extra=str(cls.id)))])
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
    rows.append([_btn(translator.t("character.dice.btn_initiative", lang=lang), CharAction("char_dice", char_id=cid, sub="initiative"))])
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

    from bot.handlers.character.skills import _get_skill_level_from_dict, _skill_bonus

    for slug, ability in SKILLS:
        score_val = score_map.get(ability, 10)
        mod = (score_val - 10) // 2
        skills_data: dict = char.skills or {}
        skill_level = _get_skill_level_from_dict(skills_data, slug)
        bonus = _skill_bonus(char, slug, mod)

        skill_name = translator.t(f"character.skills.names.{slug}", lang=lang)
        ability_abbr = translator.t(f"character.skills.ability_abbr.{ability}", lang=lang)
        if skill_level == "expert":
            prof_icon = translator.t("character.skills.expert_icon", lang=lang)
        elif skill_level == "proficient":
            prof_icon = translator.t("character.skills.proficient_icon", lang=lang)
        else:
            prof_icon = translator.t("character.skills.not_proficient_icon", lang=lang)
        bonus_str = f"+{bonus}" if bonus >= 0 else str(bonus)
        label = f"{prof_icon} {skill_name} ({ability_abbr}): {bonus_str}"

        btn = _btn(label, CharAction("char_skills", char_id=cid, sub="detail", extra=slug))
        row.append(btn)
        if len(row) == 2:
            rows.append(row)
            row = []

    if row:
        rows.append(row)

    rows.append(_nav_row(back_action=CharAction("char_menu", char_id=cid), menu_char_id=cid, lang=lang))
    return InlineKeyboardMarkup(rows)


def build_skill_detail_keyboard(
    char_id: int,
    slug: str,
    skill_level: str,
    bonus: int,
    lang: str = "it",
) -> InlineKeyboardMarkup:
    """Keyboard for the skill detail screen: toggle proficiency/expertise, roll dice, and back.

    skill_level: "none" | "proficient" | "expert"
    """
    cid = char_id
    bonus_str = f"+{bonus}" if bonus >= 0 else str(bonus)
    roll_label = translator.t("character.skills.btn_roll", lang=lang, bonus=bonus_str)

    if skill_level == "none":
        toggle_label = translator.t("character.skills.btn_toggle_proficient", lang=lang)
    elif skill_level == "proficient":
        toggle_label = translator.t("character.skills.btn_toggle_expert", lang=lang)
    else:  # expert
        toggle_label = translator.t("character.skills.btn_toggle_not_proficient", lang=lang)

    rows = [
        [_btn(toggle_label, CharAction("char_skills", char_id=cid, sub="toggle", extra=slug))],
        [_btn(roll_label, CharAction("char_skills", char_id=cid, sub="roll", extra=slug))],
        _nav_row(back_action=CharAction("char_skills", char_id=cid), menu_char_id=cid, lang=lang),
    ]
    return InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------------------
# Identity (race / gender)
# ---------------------------------------------------------------------------

def build_identity_keyboard(char_id: int, lang: str = "it") -> InlineKeyboardMarkup:
    cid = char_id
    t = translator.t
    rows = [
        [_btn(t("character.identity.btn_race",   lang=lang), CharAction("char_identity", char_id=cid, sub="race"))],
        [_btn(t("character.identity.btn_gender", lang=lang), CharAction("char_identity", char_id=cid, sub="gender"))],
        [_btn(t("character.identity.btn_speed",  lang=lang), CharAction("char_identity", char_id=cid, sub="speed"))],
        [_btn(t("character.identity.btn_background",  lang=lang), CharAction("char_identity", char_id=cid, sub="background"))],
        [_btn(t("character.identity.btn_alignment",   lang=lang), CharAction("char_identity", char_id=cid, sub="alignment"))],
        [_btn(t("character.identity.btn_personality", lang=lang), CharAction("char_identity", char_id=cid, sub="personality"))],
        [_btn(t("character.identity.btn_languages",   lang=lang), CharAction("char_identity", char_id=cid, sub="languages"))],
        [_btn(t("character.identity.btn_proficiencies", lang=lang), CharAction("char_identity", char_id=cid, sub="proficiencies"))],
        [_btn(t("character.identity.btn_damage_modifiers", lang=lang), CharAction("char_identity", char_id=cid, sub="damage_modifiers"))],
        _nav_row(back_action=CharAction("char_menu", char_id=cid), menu_char_id=cid, lang=lang),
    ]
    return InlineKeyboardMarkup(rows)


def build_identity_personality_keyboard(char_id: int, lang: str = "it") -> InlineKeyboardMarkup:
    cid = char_id
    t = translator.t
    rows = [
        [_btn(t("character.identity.btn_traits", lang=lang), CharAction("char_identity", char_id=cid, sub="personality_traits"))],
        [_btn(t("character.identity.btn_ideals", lang=lang), CharAction("char_identity", char_id=cid, sub="personality_ideals"))],
        [_btn(t("character.identity.btn_bonds",  lang=lang), CharAction("char_identity", char_id=cid, sub="personality_bonds"))],
        [_btn(t("character.identity.btn_flaws",  lang=lang), CharAction("char_identity", char_id=cid, sub="personality_flaws"))],
        _nav_row(back_action=CharAction("char_identity", char_id=cid), menu_char_id=cid, lang=lang),
    ]
    return InlineKeyboardMarkup(rows)


def build_identity_list_keyboard(
    char_id: int, sub: str, items: list[str], lang: str = "it"
) -> InlineKeyboardMarkup:
    """Generic keyboard for managing a list (languages / proficiencies / damage modifiers)."""
    cid = char_id
    t = translator.t
    rows: list[list[InlineKeyboardButton]] = [
        [_btn(f"➖ {item}", CharAction("char_identity", char_id=cid, sub=f"{sub}_remove", extra=item))]
        for item in items
    ]
    if sub == "languages":
        add_label = t("character.identity.btn_add_language", lang=lang)
    elif sub in ("resistances", "immunities", "vulnerabilities"):
        add_label = t("character.identity.btn_add_modifier", lang=lang)
    else:
        add_label = t("character.identity.btn_add_proficiency", lang=lang)
    rows.append([_btn(add_label, CharAction("char_identity", char_id=cid, sub=f"{sub}_add"))])
    rows.append(_nav_row(back_action=CharAction("char_identity", char_id=cid), menu_char_id=cid, lang=lang))
    return InlineKeyboardMarkup(rows)


def build_identity_damage_modifiers_keyboard(char_id: int, lang: str = "it") -> InlineKeyboardMarkup:
    cid = char_id
    t = translator.t
    rows = [
        [_btn(t("character.identity.btn_resistances",    lang=lang), CharAction("char_identity", char_id=cid, sub="resistances"))],
        [_btn(t("character.identity.btn_immunities",     lang=lang), CharAction("char_identity", char_id=cid, sub="immunities"))],
        [_btn(t("character.identity.btn_vulnerabilities", lang=lang), CharAction("char_identity", char_id=cid, sub="vulnerabilities"))],
        _nav_row(back_action=CharAction("char_identity", char_id=cid), menu_char_id=cid, lang=lang),
    ]
    return InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------------------
# Saving Throws
# ---------------------------------------------------------------------------

def build_saving_throws_keyboard(
    char_id: int,
    char: Character,
    ability_scores: list[AbilityScore],
    lang: str = "it",
) -> InlineKeyboardMarkup:
    """One button per ability showing saving throw proficiency + bonus."""
    cid = char_id
    proficiency_bonus = char.proficiency_bonus
    score_map = {s.name: s.value for s in ability_scores}
    saves_data: dict = char.saving_throws or {}

    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []

    for ability in ABILITY_NAMES:
        score_val = score_map.get(ability, 10)
        mod = (score_val - 10) // 2
        is_proficient = bool(saves_data.get(ability, False))
        bonus = mod + (proficiency_bonus if is_proficient else 0)

        name = translator.t(f"character.saving_throws.names.{ability}", lang=lang)
        prof_icon = translator.t(
            "character.saving_throws.proficient_icon" if is_proficient
            else "character.saving_throws.not_proficient_icon",
            lang=lang,
        )
        bonus_str = f"+{bonus}" if bonus >= 0 else str(bonus)
        label = f"{prof_icon} {name}: {bonus_str}"

        btn = _btn(label, CharAction("char_saving_throws", char_id=cid, sub="detail", extra=ability))
        row.append(btn)
        if len(row) == 2:
            rows.append(row)
            row = []

    if row:
        rows.append(row)

    rows.append(_nav_row(back_action=CharAction("char_menu", char_id=cid), menu_char_id=cid, lang=lang))
    return InlineKeyboardMarkup(rows)


def build_saving_throw_detail_keyboard(
    char_id: int,
    ability_slug: str,
    is_proficient: bool,
    bonus: int,
    lang: str = "it",
) -> InlineKeyboardMarkup:
    cid = char_id
    bonus_str = f"+{bonus}" if bonus >= 0 else str(bonus)

    toggle_label = translator.t(
        "character.saving_throws.btn_toggle_not_proficient" if is_proficient
        else "character.saving_throws.btn_toggle_proficient",
        lang=lang,
    )
    roll_label = translator.t("character.saving_throws.btn_roll", lang=lang, bonus=bonus_str)

    rows = [
        [_btn(toggle_label, CharAction("char_saving_throws", char_id=cid, sub="toggle", extra=ability_slug))],
        [_btn(roll_label,   CharAction("char_saving_throws", char_id=cid, sub="roll",   extra=ability_slug))],
        _nav_row(back_action=CharAction("char_saving_throws", char_id=cid), menu_char_id=cid, lang=lang),
    ]
    return InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------------------
# Experience Points
# ---------------------------------------------------------------------------

def build_xp_keyboard(char_id: int, char: Character, lang: str = "it") -> InlineKeyboardMarkup:
    from bot.data.xp_thresholds import xp_to_level, XP_THRESHOLDS
    cid = char_id
    current_xp = char.experience_points or 0
    xp_level = xp_to_level(current_xp)
    actual_level = char.total_level

    rows: list[list[InlineKeyboardButton]] = [
        [_btn(translator.t("character.xp.btn_add", lang=lang), CharAction("char_xp", char_id=cid, sub="add"))],
    ]
    # Shortcut to multiclass if XP suggests a higher level
    if xp_level > actual_level:
        rows.append([_btn(
            translator.t("character.xp.btn_level_up", lang=lang, level=xp_level),
            CharAction("char_multiclass", char_id=cid),
        )])
    rows.append(_nav_row(back_action=CharAction("char_menu", char_id=cid), menu_char_id=cid, lang=lang))
    return InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------------------
# Death Saving Throws
# ---------------------------------------------------------------------------

def build_death_saves_keyboard(
    char_id: int,
    successes: int,
    failures: int,
    stable: bool,
    lang: str = "it",
) -> InlineKeyboardMarkup:
    cid = char_id
    rows: list[list[InlineKeyboardButton]] = []

    if stable:
        rows.append([_btn(
            translator.t("character.death_saves.btn_reset", lang=lang),
            CharAction("char_death_saves", char_id=cid, sub="reset"),
        )])
    else:
        rows.append([
            _btn(
                translator.t("character.death_saves.btn_success", lang=lang),
                CharAction("char_death_saves", char_id=cid, sub="success"),
            ),
            _btn(
                translator.t("character.death_saves.btn_failure", lang=lang),
                CharAction("char_death_saves", char_id=cid, sub="failure"),
            ),
        ])
        rows.append([_btn(
            translator.t("character.death_saves.btn_roll", lang=lang),
            CharAction("char_death_saves", char_id=cid, sub="roll"),
        )])
        rows.append([_btn(
            translator.t("character.death_saves.btn_reset", lang=lang),
            CharAction("char_death_saves", char_id=cid, sub="reset"),
        )])

    rows.append(_nav_row(back_action=CharAction("char_hp", char_id=cid), menu_char_id=cid, lang=lang))
    return InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------------------
# Heroic Inspiration
# ---------------------------------------------------------------------------

def build_inspiration_keyboard(
    char_id: int,
    has_inspiration: bool,
    lang: str = "it",
) -> InlineKeyboardMarkup:
    """Keyboard for the Heroic Inspiration screen: grant/spend toggle and back."""
    cid = char_id
    if has_inspiration:
        toggle_label = translator.t("character.inspiration.btn_spend", lang=lang)
    else:
        toggle_label = translator.t("character.inspiration.btn_grant", lang=lang)
    rows = [
        [_btn(toggle_label, CharAction("char_inspiration", char_id=cid, sub="toggle"))],
        _nav_row(menu_char_id=cid, lang=lang),
    ]
    return InlineKeyboardMarkup(rows)