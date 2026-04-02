"""Italian-language text formatters for character display."""

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

# Mapping ability internal name → Italian label + emoji
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


def modifier_str(value: int) -> str:
    mod = (value - 10) // 2
    return f"+{mod}" if mod >= 0 else str(mod)


def format_character_header(char: Character) -> str:
    """Short one-line summary shown at the top of most menus."""
    lvl = char.total_level
    cls = char.class_summary
    hp_bar = _hp_bar(char.current_hit_points, char.hit_points)
    return (
        f"⚔️ *{_esc(char.name)}*\n"
        f"🎭 {_esc(cls)} — Livello {lvl}\n"
        f"❤️ HP: {char.current_hit_points}/{char.hit_points} {hp_bar}\n"
        f"🛡️ CA: {char.ac}"
    )


def format_character_summary(
    char: Character,
    spells: list[Spell] | None = None,
    abilities: list[Ability] | None = None,
) -> str:
    """Full character sheet summary with active status."""
    lines = [format_character_header(char)]
    if char.race:
        lines.append(f"🧝 Razza: {_esc(char.race)}")
    if char.gender:
        lines.append(f"👤 Genere: {_esc(char.gender)}")
    # Active status (concentration, pinned spells, passive abilities)
    if spells is not None and abilities is not None:
        active = format_character_active_status(char, spells, abilities)
        if active:
            lines.append("")
            lines.append(active)
    return "\n".join(lines)


def format_ability_scores(scores: list[AbilityScore]) -> str:
    if not scores:
        return "Nessun punteggio impostato\\."
    lines = ["*Punteggi Abilità*\n"]
    score_map = {s.name: s for s in scores}
    for name in ABILITY_NAMES:
        label, emoji = ABILITY_LABELS.get(name, (name, "•"))
        score = score_map.get(name)
        val = score.value if score else 10
        mod = (val - 10) // 2
        mod_str = f"\\+{mod}" if mod >= 0 else str(mod)
        lines.append(f"{emoji} {label}: *{val}* \\({mod_str}\\)")
    return "\n".join(lines)


def format_hp(char: Character) -> str:
    bar = _hp_bar(char.current_hit_points, char.hit_points)
    return (
        f"❤️ *Punti Vita*\n\n"
        f"Attuali: *{char.current_hit_points}* / {char.hit_points}\n"
        f"{bar}"
    )


def format_ac(char: Character) -> str:
    return (
        f"🛡️ *Classe Armatura*\n\n"
        f"Base: *{char.base_armor_class}*\n"
        f"Scudo: *{char.shield_armor_class}*\n"
        f"Magica: *{char.magic_armor}*\n"
        f"━━━━━━━━\n"
        f"Totale: *{char.ac}*"
    )


def format_spells(spells: list[Spell], concentrating_spell_id: int | None = None) -> str:
    """Format spells grouped by level with status indicators."""
    if not spells:
        return "Nessun incantesimo conosciuto\\."
    by_level: dict[int, list[Spell]] = {}
    for s in spells:
        by_level.setdefault(s.level, []).append(s)
    lines = ["*Incantesimi*\n"]
    for lvl in sorted(by_level):
        label = "Trucchetti" if lvl == 0 else f"Livello {lvl}"
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


def format_spell_detail(spell: Spell) -> str:
    """Format full spell detail with all D&D 5e properties."""
    level_label = "Trucchetto" if spell.level == 0 else f"Livello {spell.level}"
    lines = [f"✨ *{_esc(spell.name)}*"]
    lines.append(f"📖 {_esc(level_label)}")

    if spell.casting_time:
        lines.append(f"⏱️ Tempo di lancio: {_esc(spell.casting_time)}")
    if spell.range_area:
        lines.append(f"📏 Gittata: {_esc(spell.range_area)}")
    if spell.components:
        lines.append(f"🧩 Componenti: {_esc(spell.components)}")
    if spell.duration:
        lines.append(f"⏳ Durata: {_esc(spell.duration)}")

    flags = []
    if spell.is_concentration:
        flags.append("🔮 Concentrazione")
    if spell.is_ritual:
        flags.append("📖 Rituale")
    if flags:
        lines.append(" \\| ".join(flags))

    if spell.attack_save:
        lines.append(f"🎯 Attacco/TS: {_esc(spell.attack_save)}")

    if spell.description:
        lines.append(f"\n📜 {_esc(spell.description)}")
    if spell.higher_level:
        lines.append(f"\n📈 *A livelli superiori:* {_esc(spell.higher_level)}")

    if spell.is_pinned:
        lines.append("\n📌 _Fissato nel menù_")

    return "\n".join(lines)


def format_character_active_status(
    char: Character,
    spells: list[Spell],
    abilities: list[Ability],
) -> str:
    """Format active status section for the character summary.

    Shows: concentration, pinned spells, passive abilities.
    """
    lines: list[str] = []

    # Active concentration
    if char.concentrating_spell_id:
        conc_spell = next(
            (s for s in spells if s.id == char.concentrating_spell_id), None
        )
        if conc_spell:
            lines.append(f"🔮 Concentrazione: *{_esc(conc_spell.name)}*")

    # Pinned spells
    pinned = [s for s in spells if s.is_pinned]
    if pinned:
        names = ", ".join(_esc(s.name) for s in pinned)
        lines.append(f"📌 Fissati: {names}")

    # Passive abilities that are active
    passive_active = [a for a in abilities if a.is_passive and a.is_active]
    if passive_active:
        names = ", ".join(_esc(a.name) for a in passive_active)
        lines.append(f"⚡ Passivi attivi: {names}")

    return "\n".join(lines) if lines else ""


def format_spell_slots(slots: list[SpellSlot]) -> str:
    if not slots:
        return "Nessuno slot incantesimo\\."
    lines = ["*Slot Incantesimi*\n"]
    for slot in sorted(slots, key=lambda s: s.level):
        avail = slot.available
        pips = "🔵" * avail + "⚫" * (slot.total - avail)
        lines.append(
            f"Liv\\.{slot.level}: {pips} \\({avail}/{slot.total}\\)"
        )
    return "\n".join(lines)


def format_bag(items: list[Item], carry_cap: int, encumbrance: float) -> str:
    enc_int = int(encumbrance)
    if not items:
        items_text = "_Zaino vuoto_"
    else:
        item_lines = [
            f"  • {_esc(i.name)} x{i.quantity} \\({_esc(f'{i.weight * i.quantity:.1f}')} kg\\)"
            for i in items
        ]
        items_text = "\n".join(item_lines)
    bar = _load_bar(enc_int, carry_cap)
    return (
        f"📦 *Zaino*\n\n"
        f"{items_text}\n\n"
        f"Peso: {enc_int}/{carry_cap} kg {bar}"
    )


def format_currency(cur: Currency | None) -> str:
    if cur is None:
        return "Nessuna moneta\\."
    lines = ["💰 *Monete*\n"]
    for key, (label, emoji) in CURRENCY_LABELS.items():
        val = getattr(cur, key, 0)
        lines.append(f"{emoji} {label}: *{val}*")
    lines.append(f"\nTotale in rame: *{cur.total_in_copper()}* 🟤")
    return "\n".join(lines)


def format_abilities(abilities: list[Ability]) -> str:
    if not abilities:
        return "Nessuna abilità speciale\\."
    lines = ["*Abilità Speciali*\n"]
    for a in abilities:
        passive = "\\[Passiva\\]" if a.is_passive else ""
        active_mark = "✅" if a.is_active else ""
        uses = ""
        if a.max_uses is not None:
            uses = f" — Usi: {a.uses}/{a.max_uses}"
        lines.append(f"⚡ *{_esc(a.name)}* {passive}{active_mark}{uses}")
    return "\n".join(lines)


def format_maps(maps: list[Map]) -> str:
    if not maps:
        return "Nessuna mappa\\."
    zones: dict[str, int] = {}
    for m in maps:
        zones[m.zone_name] = zones.get(m.zone_name, 0) + 1
    lines = ["🗺️ *Mappe*\n"]
    for zone, count in zones.items():
        lines.append(f"📍 *{_esc(zone)}* — {count} file")
    return "\n".join(lines)


def format_dice_history(rolls_history: list | None) -> str:
    if not rolls_history:
        return "_Nessun tiro registrato\\._"
    lines = ["🎲 *Storico Tiri*\n"]
    for die_name, results in rolls_history[-10:]:
        total = sum(results)
        results_str = ", ".join(str(r) for r in results)
        lines.append(
            f"{_esc(die_name)}: \\[{_esc(results_str)}\\] \\= *{total}*"
        )
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


def _esc(text: str) -> str:
    """Escape special MarkdownV2 characters."""
    special = r"\_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in str(text))
