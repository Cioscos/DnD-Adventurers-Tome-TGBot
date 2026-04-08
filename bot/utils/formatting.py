"""Localised text formatters for character display.

All public functions accept an optional ``lang`` parameter (BCP-47 language
code, e.g. ``"it"``, ``"en"``).  When not provided it defaults to ``"it"``
to preserve existing behaviour.  Pass the result of
:func:`bot.utils.i18n.get_lang` from the handler layer to localise output.
"""

from __future__ import annotations

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
from bot.utils.i18n import translator

# ---------------------------------------------------------------------------
# Legacy module-level label constants (Italian default).
# These are kept for backward compatibility; prefer the get_*_labels()
# functions when you have a language code available.
# ---------------------------------------------------------------------------

ABILITY_LABELS: dict[str, tuple[str, str]] = {
    "strength":     ("Forza",         "💪"),
    "dexterity":    ("Destrezza",     "🤸"),
    "constitution": ("Costituzione",  "🛡️"),
    "intelligence": ("Intelligenza",  "🧠"),
    "wisdom":       ("Saggezza",      "🦉"),
    "charisma":     ("Carisma",       "✨"),
}

CURRENCY_LABELS: dict[str, tuple[str, str]] = {
    "copper":   ("Rame",     "🟤"),
    "silver":   ("Argento",  "⚪"),
    "electrum": ("Electrum", "🔵"),
    "gold":     ("Oro",      "🟡"),
    "platinum": ("Platino",  "⬜"),
}

RESTORATION_LABELS: dict[str, str] = {
    "long_rest":  "Riposo lungo",
    "short_rest": "Riposo breve",
    "none":       "Nessuno",
}


# ---------------------------------------------------------------------------
# Localised label helpers
# ---------------------------------------------------------------------------

def get_ability_labels(lang: str = "it") -> dict[str, tuple[str, str]]:
    """Return a dict mapping ability name → (localised label, emoji)."""
    return {
        name: (
            translator.t(f"ability_labels.{name}", lang=lang),
            translator.t(f"ability_labels.{name}_emoji", lang=lang),
        )
        for name in ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")
    }


def get_currency_labels(lang: str = "it") -> dict[str, tuple[str, str]]:
    """Return a dict mapping currency key → (localised label, emoji)."""
    return {
        key: (
            translator.t(f"currency_labels.{key}", lang=lang),
            translator.t(f"currency_labels.{key}_emoji", lang=lang),
        )
        for key in ("copper", "silver", "electrum", "gold", "platinum")
    }


def get_restoration_labels(lang: str = "it") -> dict[str, str]:
    """Return a dict mapping restoration type → localised label."""
    return {
        key: translator.t(f"restoration_labels.{key}", lang=lang)
        for key in ("long_rest", "short_rest", "none")
    }


def modifier_str(value: int) -> str:
    mod = (value - 10) // 2
    return f"+{mod}" if mod >= 0 else str(mod)


def format_character_header(char: Character, lang: str = "it") -> str:
    """Short one-line summary shown at the top of most menus."""
    lvl = char.total_level
    cls = char.class_summary
    hp_bar = _hp_bar(char.current_hit_points, char.hit_points)
    level_label = translator.t("character.common.level_label", lang=lang)
    ac_label = translator.t("character.common.ac_label", lang=lang)
    return (
        f"⚔️ *{_esc(char.name)}*\n"
        f"🎭 {_esc(cls)} — {level_label} {lvl}\n"
        f"❤️ HP: {char.current_hit_points}/{char.hit_points} {hp_bar}\n"
        f"🛡️ {ac_label}: {char.ac}"
    )


def format_character_summary(
    char: Character,
    spells: list[Spell] | None = None,
    abilities: list[Ability] | None = None,
    equipped_items: list | None = None,
    lang: str = "it",
) -> str:
    """Full character sheet summary with active status and equipped items."""
    lines = [format_character_header(char, lang=lang)]
    if char.race:
        race_label = translator.t("character.common.race_label", lang=lang)
        lines.append(f"{race_label}: {_esc(char.race)}")
    if char.gender:
        gender_label = translator.t("character.common.gender_label", lang=lang)
        lines.append(f"{gender_label}: {_esc(char.gender)}")
    if spells is not None and abilities is not None:
        active = format_character_active_status(char, spells, abilities, lang=lang)
        if active:
            lines.append("")
            lines.append(active)
    if equipped_items:
        equip_section = format_equipped_items(equipped_items, lang=lang)
        if equip_section:
            lines.append("")
            lines.append(equip_section)
    return "\n".join(lines)


def format_ability_scores(scores: list[AbilityScore], lang: str = "it") -> str:
    if not scores:
        return translator.t("character.stats.no_scores", lang=lang)
    header = translator.t("character.common.ability_score_header", lang=lang)
    lines = [f"{header}\n"]
    score_map = {s.name: s for s in scores}
    labels = get_ability_labels(lang)
    for name in ABILITY_NAMES:
        label, emoji = labels.get(name, (name, "•"))
        score = score_map.get(name)
        val = score.value if score else 10
        mod = (val - 10) // 2
        mod_str = f"\\+{mod}" if mod >= 0 else f"\\-{abs(mod)}"
        lines.append(f"{emoji} {label}: *{val}* \\({mod_str}\\)")
    return "\n".join(lines)


def format_hp(char: Character, lang: str = "it") -> str:
    bar = _hp_bar(char.current_hit_points, char.hit_points)
    title = translator.t("character.hp.title", lang=lang)
    current_label = translator.t(
        "character.hp.current_label", lang=lang,
        current=char.current_hit_points, max=char.hit_points,
    )
    return f"{title}\n\n{current_label}\n{bar}"


def format_ac(char: Character, lang: str = "it") -> str:
    title = translator.t("character.ac.title", lang=lang)
    base = translator.t("character.ac.base_label", lang=lang, base=char.base_armor_class)
    shield = translator.t("character.ac.shield_label", lang=lang, shield=char.shield_armor_class)
    magic = translator.t("character.ac.magic_label", lang=lang, magic=char.magic_armor)
    total = translator.t("character.ac.total_label", lang=lang, total=char.ac)
    return f"{title}\n\n{base}\n{shield}\n{magic}\n━━━━━━━━\n{total}"


def format_spells(
    spells: list[Spell],
    concentrating_spell_id: int | None = None,
    lang: str = "it",
) -> str:
    """Format spells grouped by level with status indicators."""
    if not spells:
        return translator.t("character.spells.no_spells", lang=lang)
    by_level: dict[int, list[Spell]] = {}
    for s in spells:
        by_level.setdefault(s.level, []).append(s)
    title = translator.t("character.spells.title", lang=lang)
    lines = [f"{title}\n"]
    for lvl in sorted(by_level):
        if lvl == 0:
            label = translator.t("character.spells.level_cantrips", lang=lang)
        else:
            label = translator.t("character.spells.level_generic", lang=lang, level=lvl)
        lines.append(f"*{label}*")
        for s in by_level[lvl]:
            indicators = ""
            if concentrating_spell_id == s.id:
                indicators = "⚡ "
            elif s.is_concentration:
                indicators = "🔮 "
            if s.is_pinned:
                indicators += "📌 "
            if s.is_ritual:
                indicators += "®️ "
            lines.append(f"  • {indicators}{_esc(s.name)}")
    return "\n".join(lines)


def format_spell_detail(spell: Spell, lang: str = "it") -> str:
    """Format full spell detail with all D&D 5e properties."""
    if spell.level == 0:
        level_label = translator.t("character.spells.spell_detail_level_cantrip", lang=lang)
    else:
        level_label = translator.t("character.spells.spell_detail_level", lang=lang, level=spell.level)
    lines = [f"✨ *{_esc(spell.name)}*"]
    lines.append(f"📖 {_esc(level_label)}")

    if spell.casting_time:
        lines.append(translator.t("character.spells.spell_detail_casting_time", lang=lang, val=_esc(spell.casting_time)))
    if spell.range_area:
        lines.append(translator.t("character.spells.spell_detail_range", lang=lang, val=_esc(spell.range_area)))
    if spell.components:
        lines.append(translator.t("character.spells.spell_detail_components", lang=lang, val=_esc(spell.components)))
    if spell.duration:
        lines.append(translator.t("character.spells.spell_detail_duration", lang=lang, val=_esc(spell.duration)))

    flags = []
    if spell.is_concentration:
        flags.append(translator.t("character.spells.spell_detail_concentration_flag", lang=lang))
    if spell.is_ritual:
        flags.append(translator.t("character.spells.spell_detail_ritual_flag", lang=lang))
    if flags:
        lines.append(" \\| ".join(flags))

    if spell.attack_save:
        lines.append(translator.t("character.spells.spell_detail_attack_save", lang=lang, val=_esc(spell.attack_save)))

    if spell.description:
        desc_key = translator.t("character.spells.spell_detail_desc", lang=lang, desc=_esc(spell.description))
        lines.append(f"\n{desc_key}")
    if spell.higher_level:
        lines.append("\n" + translator.t("character.spells.spell_detail_higher_level", lang=lang, val=_esc(spell.higher_level)))

    if spell.is_pinned:
        lines.append("\n" + translator.t("character.spells.spell_detail_pinned", lang=lang))

    return "\n".join(lines)


def format_character_active_status(
    char: Character,
    spells: list[Spell],
    abilities: list[Ability],
    lang: str = "it",
) -> str:
    """Format active status section for the character summary.

    Shows: concentration, pinned spells, passive abilities.
    """
    lines: list[str] = []

    if char.concentrating_spell_id:
        conc_spell = next(
            (s for s in spells if s.id == char.concentrating_spell_id), None
        )
        if conc_spell:
            lines.append(translator.t("character.spells.concentration_active", lang=lang, name=_esc(conc_spell.name)))

    pinned = [s for s in spells if s.is_pinned]
    if pinned:
        names = ", ".join(_esc(s.name) for s in pinned)
        lines.append(translator.t("character.spells.pinned_spells", lang=lang, names=names))

    passive_active = [a for a in abilities if a.is_passive and a.is_active]
    if passive_active:
        names = ", ".join(_esc(a.name) for a in passive_active)
        lines.append(translator.t("character.spells.passive_active", lang=lang, names=names))

    return "\n".join(lines) if lines else ""


def format_spell_slots(slots: list[SpellSlot], lang: str = "it") -> str:
    if not slots:
        return translator.t("character.slots.no_slots", lang=lang)
    title = translator.t("character.slots.title", lang=lang)
    lines = [f"{title}\n"]
    for slot in sorted(slots, key=lambda s: s.level):
        avail = slot.available
        pips = "🔵" * avail + "⚫" * (slot.total - avail)
        lines.append(
            f"Liv\\.{slot.level}: {pips} \\({avail}/{slot.total}\\)"
        )
    return "\n".join(lines)


def format_bag(items: list[Item], carry_cap: int, encumbrance: float, lang: str = "it") -> str:
    enc_int = int(encumbrance)
    title = translator.t("character.bag.title", lang=lang)
    _ITEM_ICONS = {
        "weapon": "⚔️",
        "armor": "🛡️",
        "shield": "🛡️",
        "consumable": "🧪",
        "tool": "🔧",
        "generic": "📦",
    }
    if not items:
        items_text = translator.t("character.bag.empty", lang=lang)
    else:
        item_lines = []
        for i in items:
            icon = _ITEM_ICONS.get(getattr(i, "item_type", "generic"), "📦")
            equip = " ✅" if getattr(i, "is_equipped", False) else ""
            item_lines.append(
                f"  {icon} {_esc(i.name)} x{i.quantity}{equip} \\({_esc(f'{i.weight * i.quantity:.1f}')} kg\\)"
            )
        items_text = "\n".join(item_lines)
    bar = _load_bar(enc_int, carry_cap)
    weight_text = translator.t("character.bag.weight_display", lang=lang, current=enc_int, max=carry_cap, bar=bar)
    return f"{title}\n\n{items_text}\n\n{weight_text}"


def format_item_detail(item_data: dict, lang: str = "it") -> str:
    """Format a typed item's detail screen text."""
    name = item_data["name"]
    qty = item_data["quantity"]
    weight = item_data["weight"]
    item_type = item_data.get("item_type", "generic")
    meta = item_data.get("item_metadata", {})
    is_equipped = item_data.get("is_equipped", False)
    description = item_data.get("description")

    _TYPE_ICONS = {
        "weapon": "⚔️",
        "armor": "🛡️",
        "shield": "🛡️",
        "consumable": "🧪",
        "tool": "🔧",
        "generic": "📦",
    }
    icon = _TYPE_ICONS.get(item_type, "📦")

    lines = [f"{icon} *{_esc(name)}*\n"]
    # Equipped status for equippable types
    if item_type in ("weapon", "armor", "shield"):
        if is_equipped:
            lines.append(translator.t("character.bag.equipped_label", lang=lang))
        else:
            lines.append(translator.t("character.bag.not_equipped_label", lang=lang))
        lines.append("")

    # Common fields
    lines.append(translator.t("character.bag.item_detail_qty", lang=lang, qty=qty))
    lines.append(translator.t("character.bag.item_detail_weight_unit", lang=lang, weight=_esc(f"{weight:.1f}")))
    lines.append(translator.t("character.bag.item_detail_weight_total", lang=lang, total_weight=_esc(f"{weight * qty:.1f}")))

    # Type-specific fields
    if item_type == "weapon" and meta:
        lines.append("")
        damage_dice = meta.get("damage_dice", "")
        damage_type_key = meta.get("damage_type", "")
        damage_type_label = translator.t(f"character.bag.{damage_type_key}", lang=lang) if damage_type_key else ""
        if damage_dice or damage_type_label:
            lines.append(translator.t(
                "character.bag.weapon_damage_label", lang=lang,
                dice=_esc(damage_dice) if damage_dice else "—",
                dtype=_esc(damage_type_label),
            ))
        wtype_raw = meta.get("weapon_type", "")
        if wtype_raw:
            wtype_label_key = f"character.bag.weapon_type_{wtype_raw}"
            wtype_label = translator.t(wtype_label_key, lang=lang)
            lines.append(translator.t("character.bag.weapon_type_label", lang=lang, wtype=_esc(wtype_label)))
        props: list[str] = meta.get("properties", [])
        if props:
            prop_labels = ", ".join(translator.t(f"character.bag.{p}", lang=lang) for p in props)
            lines.append(translator.t("character.bag.weapon_props_label", lang=lang, props=_esc(prop_labels)))
        else:
            lines.append(translator.t("character.bag.weapon_no_props", lang=lang))

    elif item_type == "armor" and meta:
        lines.append("")
        atype_raw = meta.get("armor_type", "")
        if atype_raw:
            atype_label = translator.t(f"character.bag.armor_type_{atype_raw}", lang=lang)
            lines.append(translator.t("character.bag.armor_type_label", lang=lang, atype=_esc(atype_label)))
        ac = meta.get("ac_value", 10)
        lines.append(translator.t("character.bag.armor_ac_label", lang=lang, ac=ac))
        stealth = meta.get("stealth_disadvantage", False)
        stealth_val = _esc("Sì" if lang == "it" else "Yes") if stealth else _esc("No")
        lines.append(translator.t("character.bag.armor_stealth_label", lang=lang, val=stealth_val))
        str_req = meta.get("strength_req", 0)
        if str_req:
            lines.append(translator.t("character.bag.armor_str_req_label", lang=lang, val=str_req))
        else:
            none_label = translator.t("character.bag.armor_str_none", lang=lang)
            lines.append(translator.t("character.bag.armor_str_req_label", lang=lang, val=_esc(none_label)))

    elif item_type == "shield" and meta:
        lines.append("")
        bonus = meta.get("ac_bonus", 2)
        lines.append(translator.t("character.bag.shield_bonus_label", lang=lang, bonus=bonus))

    elif item_type == "consumable" and meta:
        effect = meta.get("effect", "")
        if effect:
            lines.append("")
            lines.append(translator.t("character.bag.consumable_effect_label", lang=lang, effect=_esc(effect)))

    elif item_type == "tool" and meta:
        ttype = meta.get("tool_type", "")
        if ttype:
            lines.append("")
            lines.append(translator.t("character.bag.tool_type_label", lang=lang, ttype=_esc(ttype)))

    # Description
    if description:
        lines.append("")
        lines.append(_esc(description))
    else:
        lines.append("")
        lines.append(translator.t("character.bag.no_description", lang=lang))

    return "\n".join(lines)


def format_equipped_items(items: list, lang: str = "it") -> str:
    """Format the equipped items section for the character summary.

    ``items`` is a list of dicts with keys: name, item_type, metadata.
    """
    if not items:
        return ""

    title = translator.t("character.bag.equipped_title", lang=lang)
    lines = [title]
    for item in items:
        item_type = item.get("item_type", "generic")
        name = item.get("name", "")
        meta = item.get("item_metadata", {}) or {}

        if item_type == "weapon":
            damage_dice = meta.get("damage_dice", "")
            damage_type_key = meta.get("damage_type", "")
            damage_type_label = translator.t(f"character.bag.{damage_type_key}", lang=lang) if damage_type_key else ""
            if damage_dice or damage_type_label:
                dmg_suffix = translator.t(
                    "character.bag.equipped_weapon_damage", lang=lang,
                    dice=_esc(damage_dice), dtype=_esc(damage_type_label),
                )
            else:
                dmg_suffix = ""
            weapon_line = translator.t("character.bag.equipped_weapon", lang=lang, name=_esc(name))
            lines.append(weapon_line + dmg_suffix)
        elif item_type == "armor":
            ac = meta.get("ac_value", 10)
            lines.append(translator.t("character.bag.equipped_armor", lang=lang, name=_esc(name), ac=ac))
        elif item_type == "shield":
            bonus = meta.get("ac_bonus", 2)
            lines.append(translator.t("character.bag.equipped_shield", lang=lang, name=_esc(name), bonus=bonus))

    return "\n".join(lines) if len(lines) > 1 else ""


def format_currency(cur: Currency | None, lang: str = "it") -> str:
    if cur is None:
        return translator.t("character.currency.no_currency", lang=lang)
    title = translator.t("character.currency.title", lang=lang)
    lines = [f"{title}\n"]
    currency_labels = get_currency_labels(lang)
    for key, (label, emoji) in currency_labels.items():
        val = getattr(cur, key, 0)
        lines.append(f"{emoji} {label}: *{val}*")
    total_text = translator.t("character.currency.total_copper", lang=lang, total=cur.total_in_copper())
    lines.append(f"\n{total_text}")
    return "\n".join(lines)


def format_abilities(abilities: list[Ability], lang: str = "it") -> str:
    if not abilities:
        return translator.t("character.abilities.no_abilities", lang=lang)
    title = translator.t("character.abilities.title", lang=lang)
    lines = [f"{title}\n"]
    passive_label = translator.t("character.abilities.passive_label", lang=lang)
    for a in abilities:
        passive = passive_label if a.is_passive else ""
        active_mark = "✅" if a.is_active else ""
        uses = ""
        if a.max_uses is not None:
            uses = translator.t("character.abilities.uses_label", lang=lang, uses=a.uses, max=a.max_uses)
        lines.append(f"⚡ *{_esc(a.name)}* {passive}{active_mark}{uses}")
    return "\n".join(lines)


def format_maps(maps: list[Map], lang: str = "it") -> str:
    if not maps:
        return translator.t("character.maps.no_maps", lang=lang)
    title = translator.t("character.maps.title", lang=lang)
    zones: dict[str, int] = {}
    for m in maps:
        zones[m.zone_name] = zones.get(m.zone_name, 0) + 1
    lines = [f"{title}\n"]
    for zone, count in zones.items():
        lines.append(translator.t("character.maps.zones_entry", lang=lang, zone=_esc(zone), count=count))
    return "\n".join(lines)


def format_dice_history(rolls_history: list | None, lang: str = "it") -> str:
    if not rolls_history:
        return translator.t("character.dice.no_history", lang=lang)
    title = translator.t("character.dice.history_title", lang=lang)
    lines = [f"{title}\n"]
    for die_name, results in rolls_history[-10:]:
        total = sum(results)
        results_str = ", ".join(str(r) for r in results)
        lines.append(translator.t(
            "character.dice.history_entry", lang=lang,
            die=_esc(die_name), results=_esc(results_str), total=total,
        ))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _hp_bar(current: int, maximum: int, length: int = 10) -> str:
    if maximum <= 0:
        return ""
    ratio = max(0.0, min(1.0, current / maximum))
    filled = round(ratio * length)
    return "❤️" * filled + "🖤" * (length - filled)


def _load_bar(current: int, maximum: int, length: int = 10) -> str:
    if maximum <= 0:
        return ""
    ratio = max(0.0, min(1.0, current / maximum))
    filled = round(ratio * length)
    return "🟩" * filled + "⬛" * (length - filled)


# ---------------------------------------------------------------------------
# Conditions
# ---------------------------------------------------------------------------

# Ordered list of all D&D 5e condition slugs (shared with keyboards/character.py).
CONDITIONS_ORDER = [
    "blinded", "charmed", "deafened", "frightened", "grappled",
    "incapacitated", "invisible", "paralyzed", "petrified", "poisoned",
    "prone", "restrained", "stunned", "unconscious", "exhaustion",
]


def format_conditions(conditions: dict, lang: str = "it") -> str:
    """Return a MarkdownV2 summary of all character conditions."""
    lines: list[str] = [translator.t("character.conditions.title", lang=lang), ""]
    has_active = False

    for slug in CONDITIONS_ORDER:
        name = translator.t(f"character.conditions.names.{slug}", lang=lang)
        if slug == "exhaustion":
            level = int(conditions.get("exhaustion", 0))
            if level > 0:
                has_active = True
                lines.append(f"✅ *{_esc(name)}*: {level}/6")
            else:
                lines.append(f"⬛ *{_esc(name)}*")
        else:
            active = bool(conditions.get(slug, False))
            if active:
                has_active = True
            marker = "✅" if active else "⬛"
            lines.append(f"{marker} *{_esc(name)}*")

    if not has_active:
        lines.append("")
        lines.append(f"_{_esc(translator.t('character.conditions.no_conditions', lang=lang))}_")

    return "\n".join(lines)


def format_condition_detail(slug: str, conditions: dict, lang: str = "it") -> str:
    """Return a MarkdownV2 detail view for a single condition.

    Note: description strings in locale files are already pre-escaped MarkdownV2
    so they must NOT be passed through _esc().
    """
    name = translator.t(f"character.conditions.names.{slug}", lang=lang)
    desc = translator.t(f"character.conditions.desc.{slug}", lang=lang)

    if slug == "exhaustion":
        level = int(conditions.get("exhaustion", 0))
        # exhaustion_level / exhaustion_inactive are pre-formatted MarkdownV2 — no _esc()
        status = (
            translator.t("character.conditions.exhaustion_level", lang=lang, level=level)
            if level > 0
            else translator.t("character.conditions.exhaustion_inactive", lang=lang)
        )
        marker = "✅" if level > 0 else "⬛"
        status_line = f"{marker} {status}"
    else:
        active = bool(conditions.get(slug, False))
        # active_label / inactive_label are plain text after locale fix — _esc() is safe
        raw_label = (
            translator.t("character.conditions.active_label", lang=lang)
            if active
            else translator.t("character.conditions.inactive_label", lang=lang)
        )
        marker = "✅" if active else "⬛"
        status_line = f"{marker} {_esc(raw_label)}"

    return (
        f"⚠️ *{_esc(name)}*\n\n"
        f"{desc}\n\n"
        f"{status_line}"
    )


def _esc(text: str) -> str:
    """Escape special MarkdownV2 characters."""
    special = r"\_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in str(text))


def format_skills(
    char: "Character",
    ability_scores: "list[AbilityScore]",
    lang: str = "it",
) -> str:
    """Format the skills screen header showing proficiency bonus and instructions."""
    title = translator.t("character.skills.title", lang=lang)
    level = char.total_level
    bonus = char.proficiency_bonus
    # Pre-escape the sign (+ and - are reserved in MarkdownV2)
    bonus_esc = f"\\+{bonus}" if bonus >= 0 else f"\\-{abs(bonus)}"
    prof_line = translator.t(
        "character.skills.prof_bonus_label", lang=lang, bonus=bonus_esc, level=level
    )
    instruction = translator.t("character.skills.instruction", lang=lang)
    return f"{title}\n\n{prof_line}\n{instruction}"


def format_skill_detail(
    slug: str,
    char: "Character",
    ability_scores: "list[AbilityScore]",
    lang: str = "it",
    last_roll: "tuple[int, int] | None" = None,
) -> str:
    """Format a single skill's detail screen.

    Args:
        slug: Snake-case skill identifier (e.g. ``"athletics"``).
        char: The character record.
        ability_scores: All ability score rows for this character.
        lang: UI language code.
        last_roll: Optional ``(die_result, total)`` tuple from the last d20 roll
            to show the roll result line at the bottom.
    """
    from bot.data.skills import SKILL_ABILITY_MAP

    ability = SKILL_ABILITY_MAP.get(slug, "strength")
    score_map = {s.name: s.value for s in ability_scores}
    score_val = score_map.get(ability, 10)
    mod = (score_val - 10) // 2
    is_proficient = bool((char.skills or {}).get(slug, False))
    prof_bonus = char.proficiency_bonus
    bonus = mod + (prof_bonus if is_proficient else 0)

    skill_name = translator.t(f"character.skills.names.{slug}", lang=lang)
    ability_abbr = translator.t(f"character.skills.ability_abbr.{ability}", lang=lang)
    description = translator.t(f"character.skills.desc.{slug}", lang=lang)

    bonus_str = f"\\+{bonus}" if bonus >= 0 else f"\\-{abs(bonus)}"
    prof_status = translator.t(
        "character.skills.detail_proficient" if is_proficient else "character.skills.detail_not_proficient",
        lang=lang,
    )

    lines = [
        f"🎯 *{_esc(skill_name)}*",
        f"⚡ {_esc(ability_abbr)} \\| Bonus: *{bonus_str}*",
        f"{prof_status}",
        "",
        _esc(description),
    ]

    if last_roll is not None:
        die_result, total = last_roll
        bonus_display = f"\\+{bonus}" if bonus >= 0 else f"\\-{abs(bonus)}"
        roll_line = translator.t(
            "character.skills.roll_result",
            lang=lang,
            die=die_result,
            bonus=bonus_display,
            total=total,
        )
        lines.extend(["", roll_line])

    return "\n".join(lines)



    """Format the multiclass menu display with subclass and resource summary."""
    title = translator.t("character.multiclass.title", lang=lang)
    if not classes:
        no_classes = translator.t("character.multiclass.no_classes", lang=lang)
        return f"{title}\n\n{no_classes}"

    level_label = translator.t("character.common.level_label", lang=lang)
    infinity = translator.t("character.class_resources.infinity", lang=lang)
    lines = [f"{title}\n"]
    for cls in classes:
        subclass_str = f" \\({_esc(cls.subclass)}\\)" if cls.subclass else ""
        lines.append(f"  • *{_esc(cls.class_name)}* {cls.level}{subclass_str}")
        if hasattr(cls, 'resources') and cls.resources:
            res_parts = []
            for r in cls.resources:
                total_display = infinity if r.total >= 99 else str(r.total)
                res_parts.append(f"{_esc(r.name)}: {r.current}/{total_display}")
            lines.append("    🔋 " + " \\| ".join(res_parts))

    total = sum(c.level for c in classes)
    lines.append("\n" + translator.t("character.multiclass.total_level", lang=lang, total=total))
    return "\n".join(lines)


def format_class_resources(
    class_name: str,
    subclass: str | None,
    level: int,
    resources: list,
    lang: str = "it",
) -> str:
    """Format the class resource management screen."""
    level_label = translator.t("character.common.level_label", lang=lang)
    subclass_str = f" \\({_esc(subclass)}\\)" if subclass else ""
    res_title = translator.t("character.class_resources.title", lang=lang)
    infinity = translator.t("character.class_resources.infinity", lang=lang)
    restoration_labels = get_restoration_labels(lang)
    lines = [
        f"🎭 *{_esc(class_name)}*{subclass_str} — {level_label} {level}",
        "",
        res_title,
    ]
    for res in resources:
        total_display = infinity if res.total >= 99 else str(res.total)
        bar = _resource_bar(res.current, res.total)
        rest_label = restoration_labels.get(res.restoration_type, str(res.restoration_type))
        lines.append(f"🔋 *{_esc(res.name)}*: {res.current}/{total_display} {bar}")
        lines.append(
            translator.t("character.class_resources.restoration_label", lang=lang, label=_esc(rest_label))
        )
        if res.note:
            lines.append(f"   📝 _{_esc(res.note)}_")
    return "\n".join(lines)


def _resource_bar(current: int, total: int) -> str:
    """Visual bar for resource usage (capped at 10 segments)."""
    if total <= 0 or total >= 99:
        return ""
    segments = min(total, 10)
    filled = round(current * segments / total) if total > 0 else 0
    return "▓" * filled + "░" * (segments - filled)
