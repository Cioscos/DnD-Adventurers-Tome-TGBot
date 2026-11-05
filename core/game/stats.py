"""Pure compute functions for D&D 5e character mechanics.

No side effects, no database access. Safe to unit-test in isolation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal, Mapping


ABILITY_NAMES = (
    "strength",
    "dexterity",
    "constitution",
    "intelligence",
    "wisdom",
    "charisma",
)

ModifierKind = Literal["absolute", "relative"]

AC_MIGRATED_FLAG = "ac_migrated"
# Valore massimo senza bonus magici: oltre, `ac_value` può già comprendere la Destrezza.
_MAX_PLAIN_ARMOR = {"light": 12, "medium": 15}


@dataclass(frozen=True)
class AppliedModifier:
    """A single ability modifier applied from an equipped item.

    Used for response breakdown on the frontend (Stats page).
    """
    source: str          # item name
    ability: str         # one of ABILITY_NAMES
    kind: ModifierKind
    value: int
    item_id: int


def hit_points_for_level(hit_die: int, con_mod: int, level: int) -> int:
    """HP gained for a single level-up event.

    Level 1: ``hit_die + con_mod`` (PHB max die value).
    Level 2+: ``(hit_die // 2 + 1) + con_mod`` (fixed method).

    The result is always clamped to a minimum of 1 (PHB rule:
    a level gives at least 1 HP even with very negative CON).
    """
    if level < 1:
        raise ValueError(f"level must be >= 1, got {level}")
    if hit_die <= 0:
        raise ValueError(f"hit_die must be > 0, got {hit_die}")

    if level == 1:
        raw = hit_die + con_mod
    else:
        raw = (hit_die // 2 + 1) + con_mod

    return max(1, raw)


def ability_modifier(score: int) -> int:
    """D&D 5e ability modifier: ``(score - 10) // 2`` (floor division)."""
    return (score - 10) // 2


def cantrip_dice_multiplier(total_level: int) -> int:
    """Cantrip damage dice multiplier by total character level (5e 2014)."""
    if total_level >= 17:
        return 4
    if total_level >= 11:
        return 3
    return 2 if total_level >= 5 else 1


def total_base_hp(
    classes: "Iterable[_ClassLike]",
    con_mod: int,
    rolls: "Mapping[int, Mapping[int, int]] | None" = None,
) -> int:
    """Sum of HP across every level of every class.

    ``rolls`` (class id -> class level -> raw die roll) replaces the fixed value
    of non-first levels: ``max(1, roll + con_mod)``.

    The 'first class' (lowest id, i.e. DB insertion order) owns the
    character's level-1 slot and uses the level-1 formula.
    All other levels (including level 1 of any additional multiclass)
    use the level 2+ formula.

    Returns 0 if classes is empty.
    """
    sorted_classes = sorted(classes, key=lambda c: c.id)
    if not sorted_classes:
        return 0

    total = 0
    first_level_consumed = False

    for cls in sorted_classes:
        if not cls.hit_die:  # classe personalizzata senza dado vita: nessun PF
            continue
        for level_within_class in range(1, cls.level + 1):
            if not first_level_consumed:
                total += hit_points_for_level(cls.hit_die, con_mod, 1)
                first_level_consumed = True
            elif rolled := (rolls or {}).get(cls.id, {}).get(level_within_class):
                total += max(1, rolled + con_mod)
            else:
                total += hit_points_for_level(cls.hit_die, con_mod, 2)

    return total


def effective_ability_score(
    ability_name: str,
    base_value: int,
    equipped_items: "Iterable[_ItemLike]",
) -> tuple[int, list[AppliedModifier]]:
    """Compute the effective ability score after equipped-item modifiers.

    Stacking rule:
      - Sum of all *relative* modifiers for this ability
      - Max of all *absolute* modifiers for this ability (if any)
      - Final = max(base + sum(rel), max(abs)) if any absolute exists,
                else base + sum(rel)

    No cap applied (homebrew-friendly).

    Returns (effective_value, list_of_applied_modifiers_for_breakdown).
    """
    if ability_name not in ABILITY_NAMES:
        raise ValueError(f"unknown ability: {ability_name}")

    applied: list[AppliedModifier] = []
    relative_sum = 0
    absolutes: list[int] = []

    for item in equipped_items:
        mods = _extract_ability_modifiers(item)
        for mod in mods:
            if mod.get("ability") != ability_name:
                continue
            kind = mod.get("kind")
            value = mod.get("value")
            if not isinstance(value, int):
                continue
            if kind == "relative":
                relative_sum += value
                applied.append(AppliedModifier(
                    source=item.name,
                    ability=ability_name,
                    kind="relative",
                    value=value,
                    item_id=item.id,
                ))
            elif kind == "absolute":
                absolutes.append(value)
                applied.append(AppliedModifier(
                    source=item.name,
                    ability=ability_name,
                    kind="absolute",
                    value=value,
                    item_id=item.id,
                ))

    base_plus_rel = base_value + relative_sum
    if absolutes:
        effective = max(base_plus_rel, max(absolutes))
    else:
        effective = base_plus_rel

    return effective, applied


def effective_ability_mod(char, ability: str) -> int:
    """Effective modifier for `ability` (base score + modifiers from equipped
    items), the same value the character sheet shows."""
    row = next((a for a in char.ability_scores if a.name == ability), None)
    if row is None:
        return 0
    eq_items = [i for i in char.items if i.is_equipped]
    effective, _ = effective_ability_score(ability, row.value, eq_items)
    return (effective - 10) // 2


def roll_ability_mod(char, ability: str) -> int:
    """Modificatore per prove, TS, iniziativa e attacchi: in Forma Selvatica Forza, Destrezza e Costituzione
    sono quelli della bestia (2014) o il più alto fra druido e bestia (2024). Non serve a PF né CA."""
    mod = effective_ability_mod(char, ability)
    form = next((s for s in char.active_states or [] if s.get("key") == "wild_shape"), None)
    score = ((form or {}).get("data") or {}).get("abilities", {}).get(ability)
    if score is None:
        return mod
    beast = (score - 10) // 2
    return max(mod, beast) if form["data"].get("mode") == "max" else beast


def _worn(char, item_type: str):
    """Oggetto indossato di quel tipo; quelli senza slot sono dati legacy, ma contano ancora come indossati."""
    worn = [i for i in char.items or () if i.is_equipped and i.item_type == item_type]
    return min(worn, key=lambda i: i.equipment_slot is None, default=None)


def _armor_value(armor) -> int:
    try:
        return int(_item_meta(armor).get("ac_value", 10))
    except (TypeError, ValueError):  # si ricalcola a ogni lettura: un dato sporco non deve rompere la scheda
        return 10


def _unarmored_options(char) -> list:
    """Formule senza armatura valide adesso: privilegi dell'edizione e interruttore manuale."""
    from core.rules.catalog import active_features  # i moduli del catalogo possono usare questo file
    from core.rules.types import UnarmoredAc

    if _worn(char, "armor") is not None:
        return []
    options = [spec.unarmored for spec, _row in active_features(char) if spec.unarmored]
    if char.unarmored_defense_ability:
        options.append(UnarmoredAc(("dexterity", char.unarmored_defense_ability),
                                   no_shield=char.unarmored_defense_ability == "wisdom"))
    if _worn(char, "shield") is not None:
        options = [o for o in options if not o.no_shield]
    return options


def _unarmored_value(char, option) -> int:
    return option.base + sum(effective_ability_mod(char, a) for a in option.abilities)


def unarmored_formula(char) -> tuple[str, ...] | None:
    """Caratteristiche della migliore formula senza armatura in vigore, ``None`` se nessuna vale."""
    best = max(_unarmored_options(char), key=lambda o: _unarmored_value(char, o), default=None)
    return best.abilities if best else None


def computed_base_ac(char) -> int:
    """CA base secondo armatura e caratteristiche effettive; un override manuale resta com'è."""
    if char.base_armor_class_override:
        return char.base_armor_class
    dex = effective_ability_mod(char, "dexterity")
    armor = _worn(char, "armor")
    if armor is None:
        return max([10 + dex] + [_unarmored_value(char, o) for o in _unarmored_options(char)])
    bonus = {"light": dex, "medium": min(dex, 2)}.get(_item_meta(armor).get("armor_type"), 0)
    return _armor_value(armor) + bonus


def sync_base_ac(char) -> None:
    char.base_armor_class = computed_base_ac(char)


def _ac_was_derived(char) -> bool:
    """La base salvata viene con certezza dalla vecchia logica, senza Destrezza inserita a mano?"""
    if (char.settings or {}).get("import_source"):
        return False
    if char.unarmored_defense_ability:
        # Vecchia logica: formula sui punteggi base, anche con armatura o scudo addosso. Ricalcolabile solo se
        # vale ancora e la base è proprio quella (la formula DDB può avere un bonus in più).
        scores = {a.name: a.value for a in char.ability_scores}
        old = 10 + sum(ability_modifier(scores.get(a, 10)) for a in ("dexterity", char.unarmored_defense_ability))
        return unarmored_formula(char) is not None and char.base_armor_class == old
    armor = _worn(char, "armor")
    if armor is None:
        return char.base_armor_class == 10
    value = _armor_value(armor)
    plain_max = _MAX_PLAIN_ARMOR.get(_item_meta(armor).get("armor_type"), value)
    return char.base_armor_class == value and value <= plain_max


def migrate_character_ac(char) -> None:
    """Una tantum (`settings.ac_migrated`): la base copiata dalla vecchia logica passa al calcolo nuovo.

    Ogni altro valore (manuale, importato, con la Destrezza già inclusa) diventa override: la CA mostrata non cambia.
    """
    settings = char.settings or {}
    if settings.get(AC_MIGRATED_FLAG):
        return
    char.settings = {**settings, AC_MIGRATED_FLAG: True}
    if char.base_armor_class_override:
        return
    new_value = computed_base_ac(char)
    if char.base_armor_class == new_value:
        return
    if _ac_was_derived(char):
        char.base_armor_class = new_value
    else:
        char.base_armor_class_override = True


def _item_meta(item: "_ItemLike") -> dict:
    """Parsed item metadata. Defensive: empty dict on any parse / structure error."""
    import json as _json

    raw = item.item_metadata
    if isinstance(raw, str):
        try:
            raw = _json.loads(raw)
        except (ValueError, TypeError):
            return {}
    return raw if isinstance(raw, dict) else {}


def _extract_ability_modifiers(item: "_ItemLike") -> list[dict]:
    """Read `ability_modifiers` from an item's metadata (parsed JSON).

    Defensive: returns empty list on any parse / structure error.
    """
    mods = _item_meta(item).get("ability_modifiers")
    if not isinstance(mods, list):
        return []
    return [m for m in mods if isinstance(m, dict)]


# --- Structural typing (Protocol-like) ----------------------------------
# We intentionally avoid `Protocol` here so the module stays dependency-free
# and does not require importing SQLAlchemy models. Callers pass in anything
# with matching attribute shape.

class _ClassLike:
    id: int
    level: int
    hit_die: int


class _ItemLike:
    id: int
    name: str
    item_metadata: str | dict | None
