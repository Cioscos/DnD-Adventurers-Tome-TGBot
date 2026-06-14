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
    # #47: optional author-declared semantic tone per enum value (overrides the FE
    # heuristic in propertyBadge.utils.ts). Keys must be declared values.
    tone_by_value: Optional[dict[str, Literal["danger", "success", "neutral"]]] = None

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

    @model_validator(mode="after")
    def _value_labels_consistency(self) -> "Property":
        # value_labels_i18n keys must be declared values, and each map must cover
        # it/en (parallels label_i18n). Only meaningful for enum properties (#27).
        if self.value_labels_i18n is not None:
            if self.type != "enum":
                raise ValueError("value_labels_i18n is only valid for type='enum'")
            allowed = set(self.values or [])
            for val, langs in self.value_labels_i18n.items():
                if val not in allowed:
                    raise ValueError(
                        f"value_labels_i18n key '{val}' is not in values {sorted(allowed)}"
                    )
                missing = {"it", "en"} - set(langs.keys())
                if missing:
                    raise ValueError(f"value_labels_i18n['{val}'] missing languages: {missing}")
        return self

    @model_validator(mode="after")
    def _tone_by_value_consistency(self) -> "Property":
        # tone_by_value lets a rule author declare the badge tone per enum value,
        # overriding the FE heuristic. Only valid for enum; keys must be declared
        # values (tone strings are constrained by the Literal type above). (#47)
        if self.tone_by_value is not None:
            if self.type != "enum":
                raise ValueError("tone_by_value is only valid for type='enum'")
            allowed = set(self.values or [])
            for val in self.tone_by_value:
                if val not in allowed:
                    raise ValueError(
                        f"tone_by_value key '{val}' is not in values {sorted(allowed)}"
                    )
        return self


# N and M must be >= 1 (no '1d0' → runtime ValueError); caps avoid pathological rolls (#33).
_DICE_RE = re.compile(r"^([1-9]\d*)d([1-9]\d*)([+-]\d+)?$", re.IGNORECASE)
_DICE_MAX_COUNT = 100
_DICE_MAX_SIDES = 1000


def _validate_dice_notation(v: str) -> str:
    m = _DICE_RE.match(v.strip())
    if not m:
        raise ValueError(f"Invalid dice notation: '{v}' (expected NdM or NdM+K with N,M >= 1)")
    count, sides = int(m.group(1)), int(m.group(2))
    if count > _DICE_MAX_COUNT or sides > _DICE_MAX_SIDES:
        raise ValueError(
            f"Dice '{v}' exceeds limits (count <= {_DICE_MAX_COUNT}, sides <= {_DICE_MAX_SIDES})"
        )
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
    cases: dict[str, list[dict]]  # validated recursively at parse (see _validate_case_actions)

    @model_validator(mode="after")
    def _has_cases(self) -> "ActionMatch":
        if not self.cases:
            raise ValueError("match requires at least one case")
        return self

    @model_validator(mode="after")
    def _validate_case_actions(self) -> "ActionMatch":
        # Recursively validate the nested actions in every case (#8) — previously
        # only top-level effects were checked, so a malformed nested action only
        # failed (silently) at runtime.
        for case_effects in self.cases.values():
            for eff in case_effects:
                parse_action(eff)
        return self


class ActionIf(_ActionBase):
    action: Literal["if"]
    cond: Filter
    then: list[dict] = Field(default_factory=list)
    else_: list[dict] = Field(default_factory=list, alias="else")

    @model_validator(mode="after")
    def _validate_branch_actions(self) -> "ActionIf":
        # Recursively validate nested actions in then/else branches (#8).
        for eff in [*self.then, *self.else_]:
            parse_action(eff)
        return self


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

    @field_validator("key")
    @classmethod
    def _key_format(cls, v: str) -> str:
        return _validate_key(v)

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

    @field_validator("key")
    @classmethod
    def _key_format(cls, v: str) -> str:
        return _validate_key(v)

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
    target: str  # restricted to stored base fields (see validator) — D2
    delta: IntOrDice | str  # int, dice, $var or "N*level" — evaluated at runtime
    label: str = Field(..., min_length=1, max_length=200)

    @field_validator("target")
    @classmethod
    def _target_supported(cls, v: str) -> str:
        # D2: the engine only mutates the two stored base fields. AC / skills /
        # saving throws belong to passive_modifiers (computed, with breakdown).
        if v not in ("character.hit_points_max", "character.speed"):
            raise ValueError(
                "apply_modifier_once target must be 'character.hit_points_max' "
                "or 'character.speed'"
            )
        return v

    @field_validator("delta")
    @classmethod
    def _delta_format(cls, v):
        if isinstance(v, str):
            s = v.strip()
            if s.startswith("$") or re.fullmatch(r"-?\d+\*level", s, re.IGNORECASE):
                return v
            return _validate_dice_notation(v)
        return v


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


# 'ability' removed (#11): the dispatcher never scoped it (subject._id was the
# character id and $subject.name raised), so it was misleading. Scope an ability
# rule via $event.ability_id / $event.ability_name instead.
SubjectType = Literal["item", "character"]


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

    @model_validator(mode="after")
    def _bins_and_cells_non_empty(self) -> "Table":
        # An empty bin list or no rows makes every lookup fail at runtime (#26).
        if not self.col_bins:
            raise ValueError("col_bins must declare at least one bin")
        if not self.cells:
            raise ValueError("cells must declare at least one row")
        return self

    @model_validator(mode="after")
    def _bins_no_overlap(self) -> "Table":
        # Overlapping bins make later bins unreachable (first match wins) (#26).
        ordered = sorted(self.col_bins, key=lambda b: b[0])
        for prev, cur in zip(ordered, ordered[1:]):
            if cur[0] <= prev[1]:
                raise ValueError(f"col_bins must not overlap: {prev} and {cur}")
        return self


_PASSIVE_TARGET_RE = re.compile(
    r"^character\.(ac|hit_points_max|speed|skill\.[a-z_]+|saving_throw\.[a-z]+)$"
)


class PassiveModifier(BaseModel):
    """A passive effect that applies automatically when a condition is met."""
    model_config = ConfigDict(extra="forbid")
    when: Filter
    target: str
    value: int  # MVP: integer deltas only — dice/random are deferred (#23)
    label_i18n: dict[str, str]

    @field_validator("target")
    @classmethod
    def _target_supported(cls, v: str) -> str:
        if not _PASSIVE_TARGET_RE.match(v):
            raise ValueError(
                f"Target '{v}' not supported. Allowed: character.ac, character.hit_points_max, "
                f"character.speed, character.skill.<slug>, character.saving_throw.<slug>"
            )
        # Restrict skill / saving_throw slugs to the ones the response builder
        # actually applies, so an unknown slug is rejected at create instead of
        # silently dropped at runtime (#28).
        if v.startswith("character.skill."):
            from core.data.skills import SKILL_ABILITY_MAP
            slug = v[len("character.skill."):]
            if slug not in SKILL_ABILITY_MAP:
                raise ValueError(f"Unknown skill slug '{slug}' in target '{v}'")
        elif v.startswith("character.saving_throw."):
            from core.game.stats import ABILITY_NAMES
            slug = v[len("character.saving_throw."):]
            if slug not in ABILITY_NAMES:
                raise ValueError(f"Unknown saving-throw ability '{slug}' in target '{v}'")
        return v

    @field_validator("label_i18n")
    @classmethod
    def _label_languages(cls, v: dict[str, str]) -> dict[str, str]:
        missing = {"it", "en"} - set(v.keys())
        if missing:
            raise ValueError(f"label_i18n missing languages: {missing}")
        return v


# Defensive caps on a single trigger's effect tree (#45). Recursive validation of
# match.cases / if.then / if.else and MAX_DEPTH on event re-emits already prevent
# runaway recursion, but neither bounds nesting depth nor how many actions a single
# trigger runs. Generous limits — no real rule comes close.
_MAX_NESTING_DEPTH = 10
_MAX_TRIGGER_ACTIONS = 200


def _effect_tree_stats(effects: list, depth: int = 1) -> tuple[int, int]:
    """(total action count, max nesting depth) over an effect tree.

    Recurses into match.cases / if.then / if.else. ``depth`` is 1-based, so a flat
    trigger is depth 1. Raises early once the depth cap is exceeded, bounding the
    recursion itself so a pathologically deep tree can't blow the Python stack.
    """
    if depth > _MAX_NESTING_DEPTH:
        raise ValueError(
            f"trigger effects nested too deep (max {_MAX_NESTING_DEPTH} levels)"
        )
    total = 0
    max_depth = depth
    for eff in effects:
        if not isinstance(eff, dict):
            continue
        total += 1
        action = eff.get("action")
        branches: list[list] = []
        if action == "if":
            branches = [eff.get("then") or [], eff.get("else") or []]
        elif action == "match":
            branches = [c for c in (eff.get("cases") or {}).values() if isinstance(c, list)]
        for branch in branches:
            sub_total, sub_depth = _effect_tree_stats(branch, depth + 1)
            total += sub_total
            max_depth = max(max_depth, sub_depth)
    return total, max_depth


class Trigger(BaseModel):
    """An event-driven trigger with filters and effects."""
    model_config = ConfigDict(extra="forbid")
    event: EventType
    filters: list[Filter] = Field(default_factory=list)
    effects: list[dict] = Field(default_factory=list)  # validated recursively at parse

    @field_validator("effects")
    @classmethod
    def _within_caps(cls, v: list[dict]) -> list[dict]:
        # #45: enforce generous depth/action caps BEFORE parse_action recurses, so a
        # pathologically deep tree fails cleanly here instead of via RecursionError.
        total, _ = _effect_tree_stats(v)
        if total > _MAX_TRIGGER_ACTIONS:
            raise ValueError(
                f"trigger has too many actions ({total}; max {_MAX_TRIGGER_ACTIONS})"
            )
        return v

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
    restoration_type: Literal["long_rest", "short_rest", "none", "manual"] = "none"

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

    @model_validator(mode="after")
    def _lookup_tables_exist(self) -> "RuleDSL":
        # Every lookup_table action (incl. nested in if/match) must reference a
        # declared table id (#25) — caught at create, not silently at runtime.
        table_ids = {t.id for t in self.tables}

        def _scan(effects: list) -> None:
            for eff in effects:
                if not isinstance(eff, dict):
                    continue
                action = eff.get("action")
                if action == "lookup_table":
                    tid = eff.get("table")
                    if tid not in table_ids:
                        raise ValueError(
                            f"lookup_table references unknown table '{tid}' "
                            f"(declared: {sorted(table_ids)})"
                        )
                elif action == "if":
                    _scan(eff.get("then") or [])
                    _scan(eff.get("else") or [])
                elif action == "match":
                    for case in (eff.get("cases") or {}).values():
                        if isinstance(case, list):
                            _scan(case)

        for trig in self.triggers:
            _scan(trig.effects)
        return self
