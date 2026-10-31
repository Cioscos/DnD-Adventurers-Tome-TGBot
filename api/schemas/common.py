"""Shared Pydantic schemas for simple character sub-resources."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from core.db.models import RestorationType
from core.game.actions import ActionType

# Valid restoration_type values, derived from the enum so the schema can never
# drift from the DB column. Accepting an unknown string here would silently
# corrupt the Enum(RestorationType) column (SQLAlchemy passes unrecognized
# strings straight through with validate_strings=False) and brick the character
# on the next read — see the heal migration in core/db/engine.py.
_ALLOWED_RESTORATION = frozenset(e.value for e in RestorationType)


def _validate_restoration_type(value: Optional[str]) -> Optional[str]:
    if value is not None and value not in _ALLOWED_RESTORATION:
        raise ValueError(
            f"restoration_type must be one of {sorted(_ALLOWED_RESTORATION)}"
        )
    return value


# ---------------------------------------------------------------------------
# AbilityScore
# ---------------------------------------------------------------------------

PROFICIENCY_CATEGORIES = ("armor", "weapons", "tools", "other")


def normalize_proficiencies(v: Any) -> dict[str, list[str]]:
    """Legacy plain list -> ``other``; object -> the four known categories only.

    Stored data is migrated lazily: reads always return the object, writes store it.
    """
    if isinstance(v, dict):
        return {k: [str(x) for x in (v.get(k) or [])] for k in PROFICIENCY_CATEGORIES}
    return {**normalize_proficiencies({}), "other": [str(x) for x in (v or [])]}


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
# CharacterClass
# ---------------------------------------------------------------------------

class CharacterClassRead(BaseModel):
    id: int
    class_name: str
    level: int
    subclass: Optional[str] = None
    spellcasting_ability: Optional[str] = None
    hit_die: Optional[int] = None
    hit_dice_used: int = 0

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
    hit_dice_used: Optional[int] = None
    hp_rolls: Optional[list[int]] = None  # one die roll per gained level (not a column)


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
    # One die roll per gained level, in body order (each 1..hit_die). Used when
    # settings.hp_mode == "rolled"; omitted -> fixed value.
    hp_rolls: Optional[list[int]] = None


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
    source_class_id: Optional[int] = None
    is_class_feature: bool = False
    feature_key: Optional[str] = None
    action_type: Optional[str] = None
    # Homebrew rule notifications surfaced when an ability_used event fired
    # (PATCH /abilities/{id} with a decremented `uses`). Omitted/None on
    # POST/list responses to match CharacterFull's contract (Phase 2 pattern).
    homebrew_notifications: Optional[list[dict]] = None

    model_config = {"from_attributes": True}


class AbilityCreate(BaseModel):
    name: str
    description: Optional[str] = None
    max_uses: Optional[int] = None
    uses: Optional[int] = None
    is_passive: bool = False
    is_active: bool = False
    restoration_type: str = "none"
    action_type: Optional[ActionType] = None

    _check_restoration = field_validator("restoration_type")(_validate_restoration_type)


class AbilityUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    max_uses: Optional[int] = None
    uses: Optional[int] = None
    is_passive: Optional[bool] = None
    is_active: Optional[bool] = None
    restoration_type: Optional[str] = None
    action_type: Optional[ActionType] = None

    _check_restoration = field_validator("restoration_type")(_validate_restoration_type)


# ---------------------------------------------------------------------------
# Map
# ---------------------------------------------------------------------------

class MapRead(BaseModel):
    id: int
    zone_name: str
    file_id: str
    file_type: str
    local_file_path: Optional[str] = None
    position: int = 0
    size_bytes: int = 0

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
    was_critical_hit: bool = False
    # Override esplicito: `value` è già il danno applicato dal client (annotazione),
    # tranne "immune" che azzera. Senza override il server applica le resistenze
    # del personaggio al `damage_type`.
    damage_modifier: Literal["half", "double", "none", "immune"] | None = None
    raw_value: int | None = Field(None, ge=0)
    damage_type: str | None = Field(None, max_length=40)


class HPUndoRequest(BaseModel):
    op_id: str


class RestRequest(BaseModel):
    rest_type: str  # "long" | "short"
    hit_dice_used: Optional[int] = None


class ItemChargePreview(BaseModel):
    name: str
    gain: Optional[int] = None  # note when known (recharge to max)
    formula: Optional[str] = None  # dice recharge, e.g. "1d6+1"
    full: bool = False  # recharges to max


class RestPreview(BaseModel):
    """Cosa recupererebbe un riposo (nessuna scrittura)."""
    hp_gain: int = 0
    hit_dice_regain: dict[int, int] = {}  # class_id -> dadi vita
    slots: dict[int, int] = {}  # livello -> slot (non patto) recuperati
    pact_slots: int = 0
    abilities: list[str] = []
    homebrew_resources: list[str] = []
    item_charges: list[ItemChargePreview] = []
    exhaustion_change: int = 0
    ends_concentration: bool = False


class DeathSaveAction(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    RESET = "reset"
    STABILIZE = "stabilize"
    ROLL = "roll"


RollMode = Literal["normal", "advantage", "disadvantage"]
D20Dice = Annotated[list[Annotated[int, Field(ge=1, le=20)]], Field(max_length=2)]


class DeathSaveUpdate(BaseModel):
    action: DeathSaveAction


class DeathSaveRollResult(BaseModel):
    die: int
    dice: list[int] = []
    mode: RollMode = "normal"
    outcome: str  # "nat20" | "nat1" | "success" | "failure"
    successes: int
    failures: int
    stable: bool
    revived: bool = False
    current_hp: int


# ---------------------------------------------------------------------------
# Dice
# ---------------------------------------------------------------------------

class DiceResultEntry(BaseModel):
    kind: Literal["d4", "d6", "d8", "d10", "d12", "d20"]
    value: int


class DiceResultRequest(BaseModel):
    rolls: list[DiceResultEntry] = Field(min_length=1, max_length=200)
    label: str | None = Field(default=None, max_length=120)
    modifier: int = 0
    notation: str | None = Field(default=None, max_length=80)
    with_inspiration: bool = False
    source: Literal["manual", "weapon", "skill", "save", "spell", "init"] | None = None
    # Optional client-supplied total override. Used by stat-rolls (4d6kh3) where the
    # displayed total is the sum of the kept dice, not all rolls.
    total: int | None = None
    # advantage/disadvantage: rolls must be exactly two d20; total computed server-side.
    mode: RollMode = "normal"


class DiceRollResult(BaseModel):
    notation: str
    rolls: list[int]
    total: int
    modifier: int = 0
    timestamp: str | None = None
    source: str | None = None
    label: str | None = None


# ---------------------------------------------------------------------------
# Generic roll result (skill check, saving throw, initiative…)
# ---------------------------------------------------------------------------

class RollResult(BaseModel):
    die: int = 20
    dice: list[int] = []
    mode: RollMode = "normal"
    bonus: int
    total: int
    is_critical: bool = False
    is_fumble: bool = False
    description: str = ""


class D20RollSubmission(BaseModel):
    """Optional client-supplied d20 value (from 3D physics face detection)."""
    die: Optional[int] = Field(default=None, ge=1, le=20)
    with_inspiration: bool = False
    mode: RollMode = "normal"
    dice: Optional[D20Dice] = None


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


class HistoryRetentionPreview(BaseModel):
    """Counts that would be purged under each retention mode.

    Lets the Settings UI show users what they're about to lose before
    they commit a retention mode change.
    """
    total: int
    events_keep: int
    days_window: int
    would_purge_events: int
    would_purge_days: int


# ---------------------------------------------------------------------------
# Consumable use result
# ---------------------------------------------------------------------------

class ConsumableUseResult(BaseModel):
    """Summary of what a single `POST .../items/{id}/use` applied."""
    heal_rolls: list[int] = []
    total_healed: int = 0
    conditions_added: list[str] = []
    conditions_removed: list[str] = []
