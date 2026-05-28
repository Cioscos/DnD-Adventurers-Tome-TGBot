"""Pydantic strict schemas for the Homebrew DSL v1.

See design spec: docs/superpowers/specs/2026-05-27-homebrew-rules-engine-design.md
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class FilterOp(str, Enum):
    EQ = "eq"
    NEQ = "neq"
    LT = "lt"
    LTE = "lte"
    GT = "gt"
    GTE = "gte"
    IN = "in"
    HAS_PROPERTY = "has_property"


class Filter(BaseModel):
    """A single boolean condition. Filters in a list are ANDed."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    path: str = Field(..., min_length=1, max_length=200)
    op: FilterOp
    value: Any = None


_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,59}$")


def _validate_key(v: str) -> str:
    if not _KEY_PATTERN.match(v):
        raise ValueError(
            f"Key '{v}' must match {_KEY_PATTERN.pattern} (lowercase snake_case, max 60 chars)"
        )
    return v


PropertyType = Literal["enum", "number", "boolean", "text"]


class Property(BaseModel):
    """A custom property attached to subjects matching the rule."""
    model_config = ConfigDict(extra="forbid")

    key: str
    type: PropertyType
    values: Optional[list[str]] = None
    default: Any
    label_i18n: dict[str, str]
    value_labels_i18n: Optional[dict[str, dict[str, str]]] = None

    @field_validator("key")
    @classmethod
    def _key_format(cls, v: str) -> str:
        return _validate_key(v)

    @field_validator("label_i18n")
    @classmethod
    def _label_languages(cls, v: dict[str, str]) -> dict[str, str]:
        missing = {"it", "en"} - set(v.keys())
        if missing:
            raise ValueError(f"label_i18n missing languages: {missing}")
        return v

    @model_validator(mode="after")
    def _enum_consistency(self) -> "Property":
        if self.type == "enum":
            if not self.values:
                raise ValueError("type='enum' requires non-empty 'values' list")
            if self.default not in self.values:
                raise ValueError(f"default '{self.default}' must be in values {self.values}")
        return self


_DICE_RE = re.compile(r"^(\d+)d(\d+)([+-]\d+)?$", re.IGNORECASE)


def _validate_dice_notation(v: str) -> str:
    if not _DICE_RE.match(v.strip()):
        raise ValueError(f"Invalid dice notation: '{v}' (expected NdM or NdM+K)")
    return v


# Type alias used inside actions for amount/delta fields.
IntOrDice = int | str


class _ActionBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ActionRollDice(_ActionBase):
    action: Literal["roll_dice"]
    notation: str
    store_as: str

    @field_validator("notation")
    @classmethod
    def _notation_format(cls, v: str) -> str:
        return _validate_dice_notation(v)


class ActionLookupTable(_ActionBase):
    action: Literal["lookup_table"]
    table: str
    row: str
    col: str
    store_as: str


class ActionMatch(_ActionBase):
    action: Literal["match"]
    value: str
    cases: dict[str, list[dict]]  # validated recursively at engine layer

    @model_validator(mode="after")
    def _has_cases(self) -> "ActionMatch":
        if not self.cases:
            raise ValueError("match requires at least one case")
        return self


class ActionIf(_ActionBase):
    action: Literal["if"]
    cond: Filter
    then: list[dict] = Field(default_factory=list)
    else_: list[dict] = Field(default_factory=list, alias="else")


class ActionSetProperty(_ActionBase):
    action: Literal["set_property"]
    target: Literal["subject", "character"]
    key: str
    value: Any

    @field_validator("key")
    @classmethod
    def _key_format(cls, v: str) -> str:
        return _validate_key(v)


class ActionIncProperty(_ActionBase):
    action: Literal["inc_property"]
    target: Literal["subject", "character"]
    key: str
    delta: IntOrDice

    @field_validator("delta")
    @classmethod
    def _delta_format(cls, v):
        if isinstance(v, str):
            # Accept dice notation OR a $var reference resolved at runtime.
            if v.startswith("$"):
                return v
            return _validate_dice_notation(v)
        return v

    @field_validator("key")
    @classmethod
    def _key_format(cls, v: str) -> str:
        return _validate_key(v)


class ActionUnequip(_ActionBase):
    action: Literal["unequip"]
    target: Literal["subject"] = "subject"


class ActionDamageCharacter(_ActionBase):
    action: Literal["damage_character"]
    amount: IntOrDice
    type: Optional[str] = None
    was_critical: bool = False

    @field_validator("amount")
    @classmethod
    def _amount_format(cls, v):
        if isinstance(v, str):
            # Accept dice notation OR a path reference ($var) — engine resolves at runtime.
            if v.startswith("$"):
                return v
            return _validate_dice_notation(v)
        return v


class ActionHealCharacter(_ActionBase):
    action: Literal["heal_character"]
    amount: IntOrDice

    @field_validator("amount")
    @classmethod
    def _amount_format(cls, v):
        if isinstance(v, str):
            if v.startswith("$"):
                return v
            return _validate_dice_notation(v)
        return v


class ActionChangeResource(_ActionBase):
    action: Literal["change_resource"]
    key: str
    delta: IntOrDice

    @field_validator("delta")
    @classmethod
    def _delta_format(cls, v):
        if isinstance(v, str):
            if v.startswith("$"):
                return v
            return _validate_dice_notation(v)
        return v


class ActionRestoreResource(_ActionBase):
    action: Literal["restore_resource"]
    key: str
    amount: IntOrDice | Literal["max"]

    @field_validator("amount")
    @classmethod
    def _amount_format(cls, v):
        if isinstance(v, str) and v != "max" and not v.startswith("$"):
            return _validate_dice_notation(v)
        return v


class ActionApplyCondition(_ActionBase):
    action: Literal["apply_condition"]
    key: str
    params: Optional[dict] = None


class ActionRemoveCondition(_ActionBase):
    action: Literal["remove_condition"]
    key: str


class ActionApplyModifierOnce(_ActionBase):
    action: Literal["apply_modifier_once"]
    target: str  # e.g. "character.hit_points_max"
    delta: IntOrDice | str  # accepts "2*level" syntax — evaluated at runtime
    label: str = Field(..., min_length=1, max_length=200)


class ActionNotify(_ActionBase):
    action: Literal["notify"]
    severity: Literal["info", "warning", "error", "success"]
    message: str = Field(..., min_length=1, max_length=500)


class ActionAddHistory(_ActionBase):
    action: Literal["add_history"]
    description: str = Field(..., min_length=1, max_length=500)
    meta: Optional[dict] = None


Action = (
    ActionRollDice | ActionLookupTable | ActionMatch | ActionIf
    | ActionSetProperty | ActionIncProperty | ActionUnequip
    | ActionDamageCharacter | ActionHealCharacter
    | ActionChangeResource | ActionRestoreResource
    | ActionApplyCondition | ActionRemoveCondition | ActionApplyModifierOnce
    | ActionNotify | ActionAddHistory
)


_ACTION_REGISTRY: dict[str, type[_ActionBase]] = {
    "roll_dice": ActionRollDice,
    "lookup_table": ActionLookupTable,
    "match": ActionMatch,
    "if": ActionIf,
    "set_property": ActionSetProperty,
    "inc_property": ActionIncProperty,
    "unequip": ActionUnequip,
    "damage_character": ActionDamageCharacter,
    "heal_character": ActionHealCharacter,
    "change_resource": ActionChangeResource,
    "restore_resource": ActionRestoreResource,
    "apply_condition": ActionApplyCondition,
    "remove_condition": ActionRemoveCondition,
    "apply_modifier_once": ActionApplyModifierOnce,
    "notify": ActionNotify,
    "add_history": ActionAddHistory,
}


def parse_action(raw: dict) -> Action:
    """Discriminator parser. Raises ValueError on unknown action."""
    name = raw.get("action")
    if name not in _ACTION_REGISTRY:
        raise ValueError(f"Unknown action: '{name}' (allowed: {sorted(_ACTION_REGISTRY)})")
    return _ACTION_REGISTRY[name].model_validate(raw)


class EventType(str, Enum):
    """Auto-fired and manual trigger events."""
    # Auto-fired
    ATTACK_ROLLED = "attack_rolled"
    DAMAGE_TAKEN = "damage_taken"
    DROPPED_TO_ZERO = "dropped_to_zero"
    HP_HEALED = "hp_healed"
    LONG_REST_TAKEN = "long_rest_taken"
    SHORT_REST_TAKEN = "short_rest_taken"
    SPELL_CAST = "spell_cast"
    ABILITY_USED = "ability_used"
    ITEM_EQUIPPED = "item_equipped"
    ITEM_UNEQUIPPED = "item_unequipped"
    LEVEL_UP = "level_up"
    RESOURCE_CHANGED = "resource_changed"
    RESOURCE_DEPLETED = "resource_depleted"
    # Manual
    TURN_STARTED = "turn_started"
    MANUAL_TRIGGER = "manual_trigger"


class SubjectFilter(BaseModel):
    """Optional filter criteria for the subject of a rule."""
    model_config = ConfigDict(extra="forbid")
    item_types: Optional[list[str]] = None
    name_contains: Optional[str] = None


SubjectType = Literal["item", "character", "ability"]


class Subject(BaseModel):
    """Identifies what a rule applies to (items, characters, abilities)."""
    model_config = ConfigDict(extra="forbid")
    type: SubjectType
    filter: Optional[SubjectFilter] = None


class Table(BaseModel):
    """A lookup table for cross-referencing two axes."""
    model_config = ConfigDict(extra="forbid")
    id: str
    row_axis: str
    col_axis: str
    col_bins: list[list[int]]
    cells: dict[str, list[str]]

    @model_validator(mode="after")
    def _cells_match_bins(self) -> "Table":
        if not all(len(row) == len(self.col_bins) for row in self.cells.values()):
            raise ValueError(
                f"cells row length must match col_bins ({len(self.col_bins)} cols)"
            )
        return self

    @model_validator(mode="after")
    def _bins_well_formed(self) -> "Table":
        for b in self.col_bins:
            if len(b) != 2 or b[0] > b[1]:
                raise ValueError(f"col_bins entries must be [lo, hi] with lo<=hi: {b}")
        return self


_PASSIVE_TARGET_RE = re.compile(
    r"^character\.(ac|hit_points_max|speed|skill\.[a-z_]+|saving_throw\.[a-z]+)$"
)


class PassiveModifier(BaseModel):
    """A passive effect that applies automatically when a condition is met."""
    model_config = ConfigDict(extra="forbid")
    when: Filter
    target: str
    value: int | str  # int or dice notation (for future random deltas; MVP only int)
    label_i18n: dict[str, str]

    @field_validator("target")
    @classmethod
    def _target_supported(cls, v: str) -> str:
        if not _PASSIVE_TARGET_RE.match(v):
            raise ValueError(
                f"Target '{v}' not supported. Allowed: character.ac, character.hit_points_max, "
                f"character.speed, character.skill.<slug>, character.saving_throw.<slug>"
            )
        return v

    @field_validator("label_i18n")
    @classmethod
    def _label_languages(cls, v: dict[str, str]) -> dict[str, str]:
        missing = {"it", "en"} - set(v.keys())
        if missing:
            raise ValueError(f"label_i18n missing languages: {missing}")
        return v


class Trigger(BaseModel):
    """An event-driven trigger with filters and effects."""
    model_config = ConfigDict(extra="forbid")
    event: EventType
    filters: list[Filter] = Field(default_factory=list)
    effects: list[dict] = Field(default_factory=list)  # validated recursively at parse

    @field_validator("effects")
    @classmethod
    def _validate_each_effect(cls, v: list[dict]) -> list[dict]:
        # Validate every action — raise if any is malformed.
        for eff in v:
            parse_action(eff)
        return v


class ResourceDef(BaseModel):
    """Declaration of a custom runtime resource (e.g. Luck Points).

    Materialized into a HomebrewResource row at rule install/create time.
    """
    model_config = ConfigDict(extra="forbid")
    key: str
    name: str
    max: int = Field(..., ge=0)
    restoration_type: Literal["long_rest", "short_rest", "none"] = "none"

    @field_validator("key")
    @classmethod
    def _key_format(cls, v: str) -> str:
        return _validate_key(v)


class RuleDSL(BaseModel):
    """Top-level rule definition. Version-pinned (MVP = 1)."""
    model_config = ConfigDict(extra="forbid")

    version: Literal[1]
    subject: Subject
    properties: list[Property] = Field(default_factory=list)
    tables: list[Table] = Field(default_factory=list)
    passive_modifiers: list[PassiveModifier] = Field(default_factory=list)
    triggers: list[Trigger] = Field(default_factory=list)
    resources: list[ResourceDef] = Field(default_factory=list)

    @model_validator(mode="after")
    def _has_at_least_one_behavior(self) -> "RuleDSL":
        if not self.triggers and not self.passive_modifiers:
            raise ValueError("Rule must declare at least one trigger or passive_modifier")
        return self
