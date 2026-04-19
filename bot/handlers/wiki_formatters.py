"""Detail formatters for wiki items fetched from the D&D 5e GraphQL API.

Each ``_format_<type>`` renders a single wiki entity (Spell, Monster,
Class, …) as Telegram MarkdownV2.  :func:`format_detail` is the public
entry point: it looks up the right formatter by GraphQL type name and
falls back to :func:`_format_generic` otherwise.

Also exports :func:`_esc` and :func:`_md_to_telegram`, re-used by the
dispatcher in :mod:`bot.handlers.wiki` for section headers.
"""

from __future__ import annotations

import re
from typing import Any

_MD2_ESCAPE_RE = re.compile(r"([_*\[\]()~`>#+\-=|{}.!\\])")


def _esc(text: Any) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    return _MD2_ESCAPE_RE.sub(r"\\\1", str(text))


_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_MD_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def _md_to_telegram(text: str) -> str:
    """Convert API Markdown (``#`` headings, ``**bold**``) to MarkdownV2.

    The D&D 5e API returns ``desc`` for Rule / RuleSection types in
    Markdown format.  Telegram MarkdownV2 does *not* support ``#``
    headings, so we convert them to bold lines and escape the rest.
    """
    lines: list[str] = []
    for line in text.split("\n"):
        heading = _MD_HEADING_RE.match(line)
        if heading:
            title = heading.group(2).strip()
            lines.append(f"*{_esc(title)}*")
            continue

        parts: list[str] = []
        last = 0
        for m in _MD_BOLD_RE.finditer(line):
            parts.append(_esc(line[last:m.start()]))
            parts.append(f"*{_esc(m.group(1))}*")
            last = m.end()
        parts.append(_esc(line[last:]))
        lines.append("".join(parts))

    return "\n".join(lines)


def format_detail(type_name: str, item: dict[str, Any]) -> str:
    """Render *item* using the formatter registered for *type_name*."""
    formatter = _FORMATTERS.get(type_name, _format_generic)
    return formatter(item)


def _format_spell(item: dict[str, Any]) -> str:
    name = _esc(item.get("name", "Unknown"))
    level = item.get("level", 0)
    level_str = "Cantrip" if level == 0 else f"Level {level}"
    school = _esc((item.get("school") or {}).get("name", ""))
    lines = [
        f"🔮 *{name}*",
        f"_{_esc(level_str)} {school}_\n",
        f"*Casting Time:* {_esc(item.get('casting_time', '—'))}",
        f"*Range:* {_esc(item.get('range', '—'))}",
        f"*Duration:* {_esc(item.get('duration', '—'))}",
        f"*Components:* {_esc(', '.join(item.get('components', [])))}",
    ]
    if item.get("material"):
        lines.append(f"*Material:* {_esc(item['material'])}")
    if item.get("concentration"):
        lines.append("*Concentration:* Yes")
    if item.get("ritual"):
        lines.append("*Ritual:* Yes")

    desc = item.get("desc", [])
    if desc:
        lines.append(f"\n{_esc(' '.join(desc))}")

    higher = item.get("higher_level", [])
    if higher:
        lines.append(f"\n*At Higher Levels:* {_esc(' '.join(higher))}")

    damage = item.get("damage")
    if damage:
        dmg_type = (damage.get("damage_type") or {}).get("name", "")
        if dmg_type:
            lines.append(f"\n*Damage Type:* {_esc(dmg_type)}")
        slots = damage.get("damage_at_slot_level", [])
        if slots:
            slot_str = ", ".join(f"Lvl {s['level']}: {s['value']}" for s in slots[:5])
            lines.append(f"*Damage by Slot:* {_esc(slot_str)}")

    classes = [c["name"] for c in item.get("classes", []) if "name" in c]
    if classes:
        lines.append(f"\n*Classes:* {_esc(', '.join(classes))}")

    return "\n".join(lines)


def _format_monster(item: dict[str, Any]) -> str:
    name = _esc(item.get("name", "Unknown"))
    lines = [
        f"🐉 *{name}*",
        f"_{_esc(item.get('size', ''))} {_esc(item.get('type', ''))}"
        + (f" \\({_esc(item.get('subtype', ''))}\\)" if item.get("subtype") else "")
        + f", {_esc(item.get('alignment', ''))}_\n",
    ]

    ac_list = item.get("armor_class", [])
    ac_str = ", ".join(str(a.get("value", "?")) for a in ac_list) if ac_list else "?"
    lines.append(
        f"*AC:* {_esc(ac_str)}  \\|  *HP:* {_esc(item.get('hit_points', '?'))} "
        f"\\({_esc(item.get('hit_dice', ''))}\\)"
    )

    cr = item.get("challenge_rating", "?")
    xp = item.get("xp", "?")
    lines.append(
        f"*CR:* {_esc(f'{cr:g}' if isinstance(cr, float) else str(cr))}  "
        f"\\|  *XP:* {_esc(str(xp))}"
    )

    abilities = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]
    abbr = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
    scores = " \\| ".join(f"{a} {_esc(str(item.get(ab, '—')))}" for a, ab in zip(abbr, abilities))
    lines.append(f"\n{scores}")

    speed = item.get("speed", {})
    if speed:
        parts = [f"{k} {v}" for k, v in speed.items() if v]
        if parts:
            lines.append(f"\n*Speed:* {_esc(', '.join(parts))}")

    senses = item.get("senses", {})
    if senses:
        sense_parts = [f"{k.replace('_', ' ')}: {v}" for k, v in senses.items() if v]
        if sense_parts:
            lines.append(f"*Senses:* {_esc(', '.join(sense_parts))}")

    if item.get("languages"):
        lines.append(f"*Languages:* {_esc(item['languages'])}")

    for sa in item.get("special_abilities", []) or []:
        desc_text = (sa.get("desc", "") or "")[:300]
        lines.append(f"\n⭐ *{_esc(sa.get('name', ''))}:* {_esc(desc_text)}")

    actions = (item.get("actions", []) or [])[:3]
    if actions:
        lines.append("\n*Actions:*")
        for act in actions:
            desc_text = (act.get("desc", "") or "")[:200]
            lines.append(f"• *{_esc(act.get('name', ''))}:* {_esc(desc_text)}")

    return "\n".join(lines)


def _format_class(item: dict[str, Any]) -> str:
    name = _esc(item.get("name", "Unknown"))
    lines = [
        f"⚔️ *{name}*\n",
        f"*Hit Die:* d{_esc(str(item.get('hit_die', '?')))}",
    ]
    saves = [s["name"] for s in item.get("saving_throws", []) or [] if "name" in s]
    if saves:
        lines.append(f"*Saving Throws:* {_esc(', '.join(saves))}")

    profs = [p["name"] for p in item.get("proficiencies", []) or [] if "name" in p]
    if profs:
        lines.append(f"*Proficiencies:* {_esc(', '.join(profs))}")

    sc = item.get("spellcasting")
    if sc:
        ability = (sc.get("spellcasting_ability") or {}).get("name", "")
        lines.append(f"\n*Spellcasting Ability:* {_esc(ability)}")

    return "\n".join(lines)


def _format_race(item: dict[str, Any]) -> str:
    name = _esc(item.get("name", "Unknown"))
    lines = [
        f"🧝 *{name}*\n",
        f"*Speed:* {_esc(str(item.get('speed', '?')))} ft",
        f"*Size:* {_esc(item.get('size', '?'))}",
    ]
    if item.get("alignment"):
        lines.append(f"*Alignment:* {_esc(item['alignment'][:200])}")
    if item.get("age"):
        lines.append(f"*Age:* {_esc(item['age'][:200])}")

    bonuses = item.get("ability_bonuses", []) or []
    if bonuses:
        parts = [
            f"{b.get('ability_score', {}).get('name', '?')} +{b.get('bonus', 0)}"
            for b in bonuses
        ]
        lines.append(f"*Ability Bonuses:* {_esc(', '.join(parts))}")

    langs = [la["name"] for la in item.get("languages", []) or [] if "name" in la]
    if langs:
        lines.append(f"*Languages:* {_esc(', '.join(langs))}")

    traits = [t["name"] for t in item.get("traits", []) or [] if "name" in t]
    if traits:
        lines.append(f"*Traits:* {_esc(', '.join(traits))}")

    return "\n".join(lines)


def _format_equipment(item: dict[str, Any]) -> str:
    name = _esc(item.get("name", "Unknown"))
    cat_name = (item.get("equipment_category") or {}).get("name", "")
    lines = [f"🎒 *{name}*"]
    if cat_name:
        lines.append(f"_{_esc(cat_name)}_\n")
    cost = item.get("cost", {})
    if cost:
        lines.append(f"*Cost:* {_esc(str(cost.get('quantity', '?')))} {_esc(cost.get('unit', ''))}")
    if item.get("weight"):
        lines.append(f"*Weight:* {_esc(str(item['weight']))} lb")
    desc = item.get("desc", [])
    if desc:
        lines.append(f"\n{_esc(' '.join(desc)[:500])}")
    return "\n".join(lines)


def _format_condition(item: dict[str, Any]) -> str:
    name = _esc(item.get("name", "Unknown"))
    desc = item.get("desc", [])
    text = " ".join(desc) if isinstance(desc, list) else str(desc or "")
    return f"🩹 *{name}*\n\n{_esc(text[:1500])}"


def _format_magic_item(item: dict[str, Any]) -> str:
    name = _esc(item.get("name", "Unknown"))
    rarity = (item.get("rarity") or {}).get("name", "")
    lines = [f"✨ *{name}*"]
    if rarity:
        lines.append(f"_{_esc(rarity)}_\n")
    desc = item.get("desc", [])
    if desc:
        lines.append(_esc(" ".join(desc)[:1500]))
    return "\n".join(lines)


def _format_feat(item: dict[str, Any]) -> str:
    name = _esc(item.get("name", "Unknown"))
    desc = item.get("desc", [])
    lines = [f"💪 *{name}*\n"]
    prereqs = item.get("prerequisites", []) or []
    if prereqs:
        parts = [
            f"{p.get('ability_score', {}).get('name', '?')} ≥ {p.get('minimum_score', '?')}"
            for p in prereqs
            if isinstance(p, dict) and "ability_score" in p
        ]
        if parts:
            lines.append(f"*Prerequisites:* {_esc(', '.join(parts))}\n")
    if desc:
        lines.append(_esc(" ".join(desc)[:1500]))
    return "\n".join(lines)


def _format_rule(item: dict[str, Any]) -> str:
    name = _esc(item.get("name", "Unknown"))
    desc = item.get("desc", "")
    if isinstance(desc, list):
        desc = "\n".join(desc)
    return f"📖 *{name}*\n\n{_md_to_telegram(desc[:2000])}"


def _format_rule_section(item: dict[str, Any]) -> str:
    name = _esc(item.get("name", "Unknown"))
    desc = item.get("desc", "")
    if isinstance(desc, list):
        desc = "\n".join(desc)
    return f"📖 *{name}*\n\n{_md_to_telegram(desc[:3000])}"


def _format_background(item: dict[str, Any]) -> str:
    name = _esc(item.get("name", "Unknown"))
    lines = [f"📜 *{name}*\n"]
    profs = [p["name"] for p in item.get("starting_proficiencies", []) or [] if "name" in p]
    if profs:
        lines.append(f"*Starting Proficiencies:* {_esc(', '.join(profs))}")
    equip = item.get("starting_equipment", []) or []
    if equip:
        parts = [
            f"{e.get('equipment', {}).get('name', '?')} ×{e.get('quantity', 1)}"
            for e in equip
        ]
        lines.append(f"*Starting Equipment:* {_esc(', '.join(parts))}")
    feature = item.get("feature", {})
    if feature:
        lines.append(f"\n⭐ *{_esc(feature.get('name', ''))}*")
        feat_desc = feature.get("desc", [])
        if feat_desc:
            text = " ".join(feat_desc) if isinstance(feat_desc, list) else str(feat_desc)
            lines.append(_esc(text[:800]))
    return "\n".join(lines)


def _format_weapon_property(item: dict[str, Any]) -> str:
    name = _esc(item.get("name", "Unknown"))
    desc = item.get("desc", [])
    text = " ".join(desc) if isinstance(desc, list) else (desc or "")
    return f"🗡️ *{name}*\n\n{_esc(text[:1500])}"


def _format_generic(item: dict[str, Any]) -> str:
    """Fallback formatter for types without a custom one.

    Shows the item name as a header, then all scalar fields as
    ``*Key:* value`` pairs, and any list-of-string fields inline.
    """
    name = _esc(item.get("name", "Unknown"))
    lines = [f"📋 *{name}*\n"]

    desc_text = ""
    for key, value in item.items():
        if key in ("index", "name", "__typename", "updated_at"):
            continue

        if key == "desc":
            if isinstance(value, list):
                desc_text = " ".join(str(v) for v in value)
            else:
                desc_text = str(value or "")
            continue

        nice_key = key.replace("_", " ").title()

        if isinstance(value, (str, int, float, bool)):
            lines.append(f"*{_esc(nice_key)}:* {_esc(str(value))}")
        elif isinstance(value, list):
            if not value:
                continue
            if isinstance(value[0], str):
                lines.append(f"*{_esc(nice_key)}:* {_esc(', '.join(value))}")
            elif isinstance(value[0], dict):
                names = [v.get("name", v.get("index", "")) for v in value if isinstance(v, dict)]
                names = [n for n in names if n]
                if names:
                    lines.append(f"*{_esc(nice_key)}:* {_esc(', '.join(names[:20]))}")
        elif isinstance(value, dict):
            obj_name = value.get("name", "")
            if obj_name:
                lines.append(f"*{_esc(nice_key)}:* {_esc(obj_name)}")

    if desc_text:
        lines.append(f"\n{_esc(desc_text[:1500])}")

    return "\n".join(lines)


_FORMATTERS: dict[str, Any] = {
    "Spell": _format_spell,
    "Monster": _format_monster,
    "Class": _format_class,
    "Race": _format_race,
    "Gear": _format_equipment,
    "Weapon": _format_equipment,
    "Armor": _format_equipment,
    "Tool": _format_equipment,
    "Pack": _format_equipment,
    "Ammunition": _format_equipment,
    "Vehicle": _format_equipment,
    "Condition": _format_condition,
    "MagicItem": _format_magic_item,
    "Feat": _format_feat,
    "Rule": _format_rule,
    "RuleSection": _format_rule_section,
    "Background": _format_background,
    "WeaponProperty": _format_weapon_property,
}
