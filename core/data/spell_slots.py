"""D&D 5e spell slot progression tables and automatic slot computation.

This module powers the "automatic spell slots" character setting: given a
character's spellcasting classes and levels, it computes the spell slots the
character should have, following the PHB rules.

Two pools are produced separately:

- **Regular slots** — the shared pool from the Spellcasting feature. For a
  single spellcasting class the class's own table is used (full / half /
  third caster). With two or more spellcasting classes the *multiclass
  spellcaster* rule applies: a combined caster level is computed (full ×1,
  half ⌊/2⌋, third ⌊/3⌋) and read against the full-caster table (which is the
  same as the PHB "Multiclass Spellcaster" table).
- **Pact Magic slots** (Warlock) — a separate pool. Warlock levels never
  count toward the combined caster level (Pact Magic is not the Spellcasting
  feature). All pact slots are of a single level and grow in blocks.

Class identity is resolved through ``normalize_class_name`` which accepts the
localized ``CharacterClass.class_name`` (Italian or English) and custom names
case-insensitively. Eldritch Knight / Arcane Trickster are detected as third
casters via a non-null ``spellcasting_ability`` on a fighter / rogue class.

Tables are transcribed verbatim from the PHB (chap. 3 class tables + chap. 6
multiclassing rules).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from core.db.models import CharacterClass

# ---------------------------------------------------------------------------
# Class identity
# ---------------------------------------------------------------------------

# Canonical English-lowercase keys, mapped from both Italian and English
# display names (CharacterClass.class_name is a localized label).
_NAME_TO_KEY: dict[str, str] = {
    "barbaro": "barbarian", "barbarian": "barbarian",
    "bardo": "bard", "bard": "bard",
    "chierico": "cleric", "cleric": "cleric",
    "druido": "druid", "druid": "druid",
    "guerriero": "fighter", "fighter": "fighter",
    "ladro": "rogue", "rogue": "rogue",
    "mago": "wizard", "wizard": "wizard",
    "monaco": "monk", "monk": "monk",
    "paladino": "paladin", "paladin": "paladin",
    "ranger": "ranger",
    "stregone": "sorcerer", "sorcerer": "sorcerer",
    "warlock": "warlock",
}

FULL_CASTERS: frozenset[str] = frozenset({"bard", "cleric", "druid", "sorcerer", "wizard"})
HALF_CASTERS: frozenset[str] = frozenset({"paladin", "ranger"})
# Fighter (Eldritch Knight) / Rogue (Arcane Trickster) are third casters only
# when they have a spellcasting subclass — detected via spellcasting_ability.
THIRD_CASTER_BASE: frozenset[str] = frozenset({"fighter", "rogue"})
WARLOCK_KEY = "warlock"


def normalize_class_name(name: str | None) -> str | None:
    """Resolve a (possibly localized / custom) class name to its canonical key.

    Returns ``None`` for unknown / custom class names.
    """
    if not name:
        return None
    return _NAME_TO_KEY.get(name.strip().lower())


# ---------------------------------------------------------------------------
# Slot progression tables (index = class level - 1; each row = slots for
# spell levels 1..9)
# ---------------------------------------------------------------------------

# Full casters: Bard, Cleric, Druid, Sorcerer, Wizard.
# Also serves as the "Multiclass Spellcaster" table (indexed by combined level).
FULL_CASTER_SLOTS: list[tuple[int, ...]] = [
    (2, 0, 0, 0, 0, 0, 0, 0, 0),  # 1
    (3, 0, 0, 0, 0, 0, 0, 0, 0),  # 2
    (4, 2, 0, 0, 0, 0, 0, 0, 0),  # 3
    (4, 3, 0, 0, 0, 0, 0, 0, 0),  # 4
    (4, 3, 2, 0, 0, 0, 0, 0, 0),  # 5
    (4, 3, 3, 0, 0, 0, 0, 0, 0),  # 6
    (4, 3, 3, 1, 0, 0, 0, 0, 0),  # 7
    (4, 3, 3, 2, 0, 0, 0, 0, 0),  # 8
    (4, 3, 3, 3, 1, 0, 0, 0, 0),  # 9
    (4, 3, 3, 3, 2, 0, 0, 0, 0),  # 10
    (4, 3, 3, 3, 2, 1, 0, 0, 0),  # 11
    (4, 3, 3, 3, 2, 1, 0, 0, 0),  # 12
    (4, 3, 3, 3, 2, 1, 1, 0, 0),  # 13
    (4, 3, 3, 3, 2, 1, 1, 0, 0),  # 14
    (4, 3, 3, 3, 2, 1, 1, 1, 0),  # 15
    (4, 3, 3, 3, 2, 1, 1, 1, 0),  # 16
    (4, 3, 3, 3, 2, 1, 1, 1, 1),  # 17
    (4, 3, 3, 3, 3, 1, 1, 1, 1),  # 18
    (4, 3, 3, 3, 3, 2, 1, 1, 1),  # 19
    (4, 3, 3, 3, 3, 2, 2, 1, 1),  # 20
]

# Half casters: Paladin, Ranger (first slots at class level 2; up to 5th).
HALF_CASTER_SLOTS: list[tuple[int, ...]] = [
    (0, 0, 0, 0, 0, 0, 0, 0, 0),  # 1
    (2, 0, 0, 0, 0, 0, 0, 0, 0),  # 2
    (3, 0, 0, 0, 0, 0, 0, 0, 0),  # 3
    (3, 0, 0, 0, 0, 0, 0, 0, 0),  # 4
    (4, 2, 0, 0, 0, 0, 0, 0, 0),  # 5
    (4, 2, 0, 0, 0, 0, 0, 0, 0),  # 6
    (4, 3, 0, 0, 0, 0, 0, 0, 0),  # 7
    (4, 3, 0, 0, 0, 0, 0, 0, 0),  # 8
    (4, 3, 2, 0, 0, 0, 0, 0, 0),  # 9
    (4, 3, 2, 0, 0, 0, 0, 0, 0),  # 10
    (4, 3, 3, 0, 0, 0, 0, 0, 0),  # 11
    (4, 3, 3, 0, 0, 0, 0, 0, 0),  # 12
    (4, 3, 3, 1, 0, 0, 0, 0, 0),  # 13
    (4, 3, 3, 1, 0, 0, 0, 0, 0),  # 14
    (4, 3, 3, 2, 0, 0, 0, 0, 0),  # 15
    (4, 3, 3, 2, 0, 0, 0, 0, 0),  # 16
    (4, 3, 3, 3, 1, 0, 0, 0, 0),  # 17
    (4, 3, 3, 3, 1, 0, 0, 0, 0),  # 18
    (4, 3, 3, 3, 2, 0, 0, 0, 0),  # 19
    (4, 3, 3, 3, 2, 0, 0, 0, 0),  # 20
]

# Third casters: Eldritch Knight (Fighter), Arcane Trickster (Rogue).
# First slots at class level 3; up to 4th.
THIRD_CASTER_SLOTS: list[tuple[int, ...]] = [
    (0, 0, 0, 0, 0, 0, 0, 0, 0),  # 1
    (0, 0, 0, 0, 0, 0, 0, 0, 0),  # 2
    (2, 0, 0, 0, 0, 0, 0, 0, 0),  # 3
    (3, 0, 0, 0, 0, 0, 0, 0, 0),  # 4
    (3, 0, 0, 0, 0, 0, 0, 0, 0),  # 5
    (3, 0, 0, 0, 0, 0, 0, 0, 0),  # 6
    (4, 2, 0, 0, 0, 0, 0, 0, 0),  # 7
    (4, 2, 0, 0, 0, 0, 0, 0, 0),  # 8
    (4, 2, 0, 0, 0, 0, 0, 0, 0),  # 9
    (4, 3, 0, 0, 0, 0, 0, 0, 0),  # 10
    (4, 3, 0, 0, 0, 0, 0, 0, 0),  # 11
    (4, 3, 0, 0, 0, 0, 0, 0, 0),  # 12
    (4, 3, 2, 0, 0, 0, 0, 0, 0),  # 13
    (4, 3, 2, 0, 0, 0, 0, 0, 0),  # 14
    (4, 3, 2, 0, 0, 0, 0, 0, 0),  # 15
    (4, 3, 3, 0, 0, 0, 0, 0, 0),  # 16
    (4, 3, 3, 0, 0, 0, 0, 0, 0),  # 17
    (4, 3, 3, 0, 0, 0, 0, 0, 0),  # 18
    (4, 3, 3, 1, 0, 0, 0, 0, 0),  # 19
    (4, 3, 3, 1, 0, 0, 0, 0, 0),  # 20
]

# Warlock Pact Magic: (number_of_slots, slot_level) per warlock level.
WARLOCK_PACT: list[tuple[int, int]] = [
    (1, 1),  # 1
    (2, 1),  # 2
    (2, 2),  # 3
    (2, 2),  # 4
    (2, 3),  # 5
    (2, 3),  # 6
    (2, 4),  # 7
    (2, 4),  # 8
    (2, 5),  # 9
    (2, 5),  # 10
    (3, 5),  # 11
    (3, 5),  # 12
    (3, 5),  # 13
    (3, 5),  # 14
    (3, 5),  # 15
    (3, 5),  # 16
    (4, 5),  # 17
    (4, 5),  # 18
    (4, 5),  # 19
    (4, 5),  # 20
]


def _row(table: list[tuple[int, ...]], level: int) -> tuple[int, ...]:
    """Clamp a class level to [1, 20] and return its slot row."""
    idx = max(1, min(level, 20)) - 1
    return table[idx]


# ---------------------------------------------------------------------------
# Computation
# ---------------------------------------------------------------------------

def _caster_kind(cls: "CharacterClass") -> str | None:
    """Return 'full' / 'half' / 'third' / 'pact' for a class, else None."""
    key = normalize_class_name(cls.class_name)
    if key is None:
        return None
    if key == WARLOCK_KEY:
        return "pact"
    if key in FULL_CASTERS:
        return "full"
    if key in HALF_CASTERS:
        return "half"
    if key in THIRD_CASTER_BASE and cls.spellcasting_ability:
        return "third"
    return None


def compute_regular_slots(classes: Iterable["CharacterClass"]) -> dict[int, int]:
    """Compute the shared (non-pact) spell slots: ``{spell_level: total}``.

    Single spellcasting class → that class's own table (full/half/third).
    Two or more → combined caster level on the full-caster (multiclass) table.
    Warlock and non-casters are ignored here.
    """
    regular: list[tuple[str, int]] = []  # (kind, level)
    for cls in classes:
        kind = _caster_kind(cls)
        if kind in ("full", "half", "third"):
            regular.append((kind, cls.level))

    if not regular:
        return {}

    if len(regular) == 1:
        kind, level = regular[0]
        table = {
            "full": FULL_CASTER_SLOTS,
            "half": HALF_CASTER_SLOTS,
            "third": THIRD_CASTER_SLOTS,
        }[kind]
        row = _row(table, level)
    else:
        combined = 0
        for kind, level in regular:
            if kind == "full":
                combined += level
            elif kind == "half":
                combined += level // 2
            else:  # third
                combined += level // 3
        if combined < 1:
            return {}
        row = _row(FULL_CASTER_SLOTS, combined)

    return {i + 1: n for i, n in enumerate(row) if n > 0}


def compute_pact_slots(classes: Iterable["CharacterClass"]) -> dict[int, int]:
    """Compute Warlock Pact Magic slots: ``{slot_level: total}`` (empty if no warlock)."""
    for cls in classes:
        if normalize_class_name(cls.class_name) == WARLOCK_KEY:
            count, slot_level = WARLOCK_PACT[max(1, min(cls.level, 20)) - 1]
            if count > 0:
                return {slot_level: count}
    return {}
