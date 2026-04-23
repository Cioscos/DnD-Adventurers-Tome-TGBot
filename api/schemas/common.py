"""Shared Pydantic schemas for simple character sub-resources."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# AbilityScore
# ---------------------------------------------------------------------------

class AppliedModifierRead(BaseModel):
    """A single equipped-item modifier applied to an ability score."""
    source: str
    ability: str
    kind: str  # "absolute" | "relative"
    value: int
    item_id: int
    model_config = {"from_attributes": True}


def _resolve_ability_effective(ability_obj: Any, equipped_items: list[Any]) -> dict:
    """Build response payload for a single AbilityScore given equipped items.

    Imports stats lazily to avoid circular imports.
    """
    from core.game.stats import effective_ability_score

    base_value = ability_obj.value
    effective, applied = effective_ability_score(
        ability_obj.name,
        base_value,
        equipped_items,
    )
    return {
        "id": ability_obj.id,
        "name": ability_obj.name,
        "value": effective,
        "base_value": base_value,
        "modifier": (effective - 10) // 2,
        "modifiers_applied": [
            {
                "source": m.source,
                "ability": m.ability,
                "kind": m.kind,
                "value": m.value,
                "item_id": m.item_id,
            }
            for m in applied
        ],
    }


class AbilityScoreRead(BaseModel):
    id: int
    name: str
    value: int           # effective value (after equipped-item modifiers)
    base_value: int      # raw value stored on AbilityScore row
    modifier: int        # derived from effective value
    modifiers_applied: list[AppliedModifierRead] = []

    model_config = {"from_attributes": True}


class AbilityScoreUpdate(BaseModel):
    value: int  # 1–30


# ---------------------------------------------------------------------------
# ClassResource
# ---------------------------------------------------------------------------

class ClassResourceRead(BaseModel):
    id: int
    name: str
    current: int
    total: int
    restoration_type: str
    note: Optional[str] = None

    model_config = {"from_attributes": True}


class ClassResourceCreate(BaseModel):
    name: str
    current: int = 0
    total: int
    restoration_type: str = "none"
    note: Optional[str] = None


class ClassResourceUpdate(BaseModel):
    name: Optional[str] = None
    current: Optional[int] = None
    total: Optional[int] = None
    restoration_type: Optional[str] = None
    note: Optional[str] = None


# ---------------------------------------------------------------------------
# CharacterClass
# ---------------------------------------------------------------------------

class CharacterClassRead(BaseModel):
    id: int
    class_name: str
    level: int
    subclass: Optional[str] = None
    spellcasting_ability: Optional[str] = None
    hit_die: Optional[int] = None
    resources: list[ClassResourceRead] = []

    model_config = {"from_attributes": True}


class CharacterClassCreate(BaseModel):
    class_name: str
    level: int = 1
    subclass: Optional[str] = None
    spellcasting_ability: Optional[str] = None
    hit_die: Optional[int] = None


class CharacterClassUpdate(BaseModel):
    level: Optional[int] = None
    subclass: Optional[str] = None
    spellcasting_ability: Optional[str] = None
    hit_die: Optional[int] = None


class ClassLevelEntry(BaseModel):
    """One (class_id, level) pair for the distribute endpoint."""
    class_id: int
    level: int = Field(ge=1, le=20)


class ClassDistribute(BaseModel):
    """Atomic redistribution of class levels for a character.

    The body must cover every existing class on the character; the sum of
    `level` values must equal the character's XP-derived total level.
    """
    classes: list[ClassLevelEntry]


# ---------------------------------------------------------------------------
# Currency
# ---------------------------------------------------------------------------

class CurrencyRead(BaseModel):
    id: int
    copper: int = 0
    silver: int = 0
    electrum: int = 0
    gold: int = 0
    platinum: int = 0

    model_config = {"from_attributes": True}


class CurrencyUpdate(BaseModel):
    copper: Optional[int] = None
    silver: Optional[int] = None
    electrum: Optional[int] = None
    gold: Optional[int] = None
    platinum: Optional[int] = None


class CurrencyConvert(BaseModel):
    source: str   # "copper" | "silver" | "electrum" | "gold" | "platinum"
    target: str
    amount: int


# ---------------------------------------------------------------------------
# Ability (special features)
# ---------------------------------------------------------------------------

class AbilityRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    max_uses: Optional[int] = None
    uses: Optional[int] = None
    is_passive: bool = False
    is_active: bool = False
    restoration_type: str = "none"

    model_config = {"from_attributes": True}


class AbilityCreate(BaseModel):
    name: str
    description: Optional[str] = None
    max_uses: Optional[int] = None
    uses: Optional[int] = None
    is_passive: bool = False
    is_active: bool = False
    restoration_type: str = "none"


class AbilityUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    max_uses: Optional[int] = None
    uses: Optional[int] = None
    is_passive: Optional[bool] = None
    is_active: Optional[bool] = None
    restoration_type: Optional[str] = None


# ---------------------------------------------------------------------------
# Map
# ---------------------------------------------------------------------------

class MapRead(BaseModel):
    id: int
    zone_name: str
    file_id: str
    file_type: str
    local_file_path: Optional[str] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# HP operations
# ---------------------------------------------------------------------------

class HPOp(str, Enum):
    DAMAGE = "damage"
    HEAL = "heal"
    SET_MAX = "set_max"
    SET_CURRENT = "set_current"
    SET_TEMP = "set_temp"


class HPUpdate(BaseModel):
    op: HPOp
    value: int


class RestRequest(BaseModel):
    rest_type: str  # "long" | "short"
    hit_dice_used: Optional[int] = None


class DeathSaveAction(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    RESET = "reset"
    STABILIZE = "stabilize"
    ROLL = "roll"


class DeathSaveUpdate(BaseModel):
    action: DeathSaveAction


class DeathSaveRollResult(BaseModel):
    die: int
    outcome: str  # "nat20" | "nat1" | "success" | "failure"
    successes: int
    failures: int
    stable: bool
    revived: bool = False
    current_hp: int


# ---------------------------------------------------------------------------
# Dice
# ---------------------------------------------------------------------------

class DiceRollRequest(BaseModel):
    count: int = 1
    die: str  # "d4" | "d6" | "d8" | "d10" | "d12" | "d20" | "d100"


class DiceRollResult(BaseModel):
    notation: str
    rolls: list[int]
    total: int
    modifier: int = 0


# ---------------------------------------------------------------------------
# Generic roll result (skill check, saving throw, initiative…)
# ---------------------------------------------------------------------------

class RollResult(BaseModel):
    die: int = 20
    bonus: int
    total: int
    is_critical: bool = False
    is_fumble: bool = False
    description: str = ""


class ConcentrationSaveResult(RollResult):
    """Result of a concentration saving throw.

    Extends RollResult with the DC rolled against, the binary outcome,
    and whether the character lost concentration as a result.
    """
    dc: int
    success: bool
    lost_concentration: bool


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

class HistoryEntryRead(BaseModel):
    id: int
    timestamp: str
    event_type: str
    description: str

    model_config = {"from_attributes": True}
