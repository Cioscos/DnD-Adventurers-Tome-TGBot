"""D&D 5e class configuration: predefined class list and class-specific resource formulas.

This module provides:
- DND_CLASSES: list of Italian-named D&D 5e classes for guided selection
- ResourceConfig: dataclass describing a class resource with a level-scaling formula
- CLASS_RESOURCES: dict mapping class name to its list of ResourceConfig
- get_resources_for_class(): instantiate resource dicts for a given class/level/character
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.db.models import Character

from core.db.models import RestorationType

# ---------------------------------------------------------------------------
# Predefined D&D 5e classes (Italian names)
# ---------------------------------------------------------------------------

DND_CLASSES: list[str] = [
    "Barbaro",
    "Bardo",
    "Chierico",
    "Druido",
    "Guerriero",
    "Ladro",
    "Mago",
    "Monaco",
    "Paladino",
    "Ranger",
    "Stregone",
    "Warlock",
]

# Spellcasting ability per class (None = non-caster / depends on subclass)
CLASS_SPELLCASTING: dict[str, str | None] = {
    "Barbaro":   None,
    "Bardo":     "charisma",
    "Chierico":  "wisdom",
    "Druido":    "wisdom",
    "Guerriero": None,        # Eldritch Knight uses INT, but depends on subclass
    "Ladro":     None,        # Arcane Trickster uses INT, but depends on subclass
    "Mago":      "intelligence",
    "Monaco":    None,
    "Paladino":  "charisma",
    "Ranger":    "wisdom",
    "Stregone":  "charisma",
    "Warlock":   "charisma",
}

# Hit die per class
CLASS_HIT_DIE: dict[str, int] = {
    "Barbaro":   12,
    "Bardo":     8,
    "Chierico":  8,
    "Druido":    8,
    "Guerriero": 10,
    "Ladro":     8,
    "Mago":      6,
    "Monaco":    8,
    "Paladino":  10,
    "Ranger":    10,
    "Stregone":  6,
    "Warlock":   8,
}


# ---------------------------------------------------------------------------
# ResourceConfig dataclass
# ---------------------------------------------------------------------------

@dataclass
class ResourceConfig:
    """Describes a class-specific resource with a level-based formula.

    Attributes:
        name: Display name of the resource (Italian).
        formula: Callable (level: int) -> int returning the max uses at that level.
            Returns 0 when the resource is not yet available.
        restoration_type: When this resource recharges.
        note: Optional explanatory note shown in the UI.
        cha_based: If True, the formula uses the character's Charisma modifier
            instead of level. The formula is ignored; CHA mod is used directly.
    """
    name: str
    formula: Callable[[int], int]
    restoration_type: RestorationType
    note: Optional[str] = None
    cha_based: bool = False


# ---------------------------------------------------------------------------
# Per-class resource configurations
# ---------------------------------------------------------------------------

# Level-indexed lookup tables (index = level - 1)
_BARBARO_FURIE = [2, 2, 3, 3, 3, 4, 4, 4, 4, 4, 4, 5, 5, 5, 5, 5, 6, 6, 6, 99]
_CHIERICO_CD   = [0, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3]
_GUERRIERO_AS  = [0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 3]
_GUERRIERO_IN  = [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3]
_GUERRIERO_DS  = [0, 0, 4, 4, 4, 4, 5, 5, 5, 5, 5, 5, 5, 5, 6, 6, 6, 6, 6, 6]
_PALADINO_CD   = [0, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2]
_WARLOCK_PATTO = [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4]


def _lookup(table: list[int], level: int) -> int:
    idx = max(0, min(level - 1, len(table) - 1))
    return table[idx]


CLASS_RESOURCES: dict[str, list[ResourceConfig]] = {
    "Barbaro": [
        ResourceConfig(
            name="Furia",
            formula=lambda lv: _lookup(_BARBARO_FURIE, lv),
            restoration_type=RestorationType.LONG_REST,
        ),
    ],
    "Bardo": [
        ResourceConfig(
            name="Ispirazione Bardica",
            formula=lambda lv: lv,  # overridden by cha_based=True
            restoration_type=RestorationType.SHORT_REST,
            cha_based=True,
        ),
    ],
    "Chierico": [
        ResourceConfig(
            name="Incanalare la Divinità",
            formula=lambda lv: _lookup(_CHIERICO_CD, lv),
            restoration_type=RestorationType.SHORT_REST,
        ),
    ],
    "Druido": [
        ResourceConfig(
            name="Forma Selvatica",
            formula=lambda lv: 2 if lv >= 2 else 0,
            restoration_type=RestorationType.SHORT_REST,
        ),
    ],
    "Guerriero": [
        ResourceConfig(
            name="Dadi Superiorità",
            formula=lambda lv: _lookup(_GUERRIERO_DS, lv),
            restoration_type=RestorationType.SHORT_REST,
            note="⚠️ I Dadi Superiorità sono inclusi per semplicità. Sono disponibili solo per il Battle Master.",
        ),
        ResourceConfig(
            name="Action Surge",
            formula=lambda lv: _lookup(_GUERRIERO_AS, lv),
            restoration_type=RestorationType.SHORT_REST,
        ),
        ResourceConfig(
            name="Secondo Vento",
            formula=lambda lv: 1,
            restoration_type=RestorationType.SHORT_REST,
        ),
        ResourceConfig(
            name="Indomabile",
            formula=lambda lv: _lookup(_GUERRIERO_IN, lv),
            restoration_type=RestorationType.LONG_REST,
        ),
    ],
    "Monaco": [
        ResourceConfig(
            name="Punti Ki",
            formula=lambda lv: lv if lv >= 2 else 0,
            restoration_type=RestorationType.SHORT_REST,
        ),
    ],
    "Paladino": [
        ResourceConfig(
            name="Imposizione delle Mani",
            formula=lambda lv: 5 * lv,
            restoration_type=RestorationType.LONG_REST,
            note="Pool di PF curabili (non usi singoli).",
        ),
        ResourceConfig(
            name="Incanalare la Divinità",
            formula=lambda lv: _lookup(_PALADINO_CD, lv),
            restoration_type=RestorationType.SHORT_REST,
        ),
    ],
    "Stregone": [
        ResourceConfig(
            name="Punti Stregoneria",
            formula=lambda lv: lv if lv >= 2 else 0,
            restoration_type=RestorationType.LONG_REST,
        ),
    ],
    "Warlock": [
        ResourceConfig(
            name="Slot Patto",
            formula=lambda lv: _lookup(_WARLOCK_PATTO, lv),
            restoration_type=RestorationType.SHORT_REST,
            note="Gli Slot Patto si recuperano con il riposo breve, a differenza degli altri caster.",
        ),
    ],
    "Mago": [
        ResourceConfig(
            name="Recupero Arcano",
            formula=lambda lv: 1,
            restoration_type=RestorationType.LONG_REST,
            note="Permette di recuperare slot incantesimo durante un riposo breve (una volta per riposo lungo).",
        ),
    ],
    # Ranger and Ladro have no base class resources
    "Ranger": [],
    "Ladro": [],
}


# ---------------------------------------------------------------------------
# Helper: build resource dicts for DB insertion
# ---------------------------------------------------------------------------

def get_resources_for_class(
    class_name: str,
    level: int,
    char: Optional["Character"] = None,
) -> list[dict]:
    """Return a list of resource init dicts for the given class and level.

    Each dict has keys: name, current, total, restoration_type, note.
    Resources with total == 0 (not yet available at this level) are excluded.
    """
    configs = CLASS_RESOURCES.get(class_name, [])
    result = []
    for cfg in configs:
        if cfg.cha_based and char is not None:
            cha_score = next(
                (a.value for a in char.ability_scores if a.name == "charisma"), 10
            )
            total = max(1, (cha_score - 10) // 2)
        elif cfg.cha_based:
            total = 3  # sensible default if character not yet available
        else:
            total = cfg.formula(level)

        if total <= 0:
            continue  # not available at this level

        result.append({
            "name": cfg.name,
            "current": total,
            "total": total,
            "restoration_type": cfg.restoration_type,
            "note": cfg.note,
        })
    return result


def update_resources_for_level(
    class_name: str,
    new_level: int,
    existing_resources: list,  # list of ClassResource ORM objects
    char: Optional["Character"] = None,
) -> None:
    """Update existing ClassResource ORM objects in-place after a level change.

    - Recalculates total for each resource using the new level formula.
    - Caps current to the new total (does not reset current).
    - Resources newly becoming available are NOT auto-added here (handled in multiclass.py).
    """
    configs = CLASS_RESOURCES.get(class_name, [])
    config_by_name = {cfg.name: cfg for cfg in configs}

    for resource in existing_resources:
        cfg = config_by_name.get(resource.name)
        if cfg is None:
            continue
        if cfg.cha_based:
            # Don't recalculate CHA-based resources on level change
            continue
        new_total = cfg.formula(new_level)
        if new_total <= 0:
            new_total = 0
        resource.total = new_total
        if resource.current > new_total:
            resource.current = new_total
