"""Pydantic schemas for Item (inventory)."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from pydantic import BaseModel, ValidationInfo, field_validator

from core.db.models import EquipmentSlot
from api.services.equipment import slot_allowed_for_type


_ALLOWED_ABILITIES = {
    "strength", "dexterity", "constitution",
    "intelligence", "wisdom", "charisma",
}
_ALLOWED_KINDS = {"absolute", "relative"}

_ALLOWED_EFFECT_KINDS = {"heal", "add_condition", "remove_condition"}
_ALLOWED_CONDITIONS = {
    "blinded", "charmed", "deafened", "frightened", "grappled",
    "incapacitated", "invisible", "paralyzed", "petrified", "poisoned",
    "prone", "restrained", "stunned", "unconscious",
}
_ALLOWED_SUBTYPES = {"potion", "scroll", "food", "other"}
_HEAL_AMOUNT_RE = re.compile(r"^(\d+d\d+([+-]\d+)?|\d+)$", re.IGNORECASE)


def _validate_ability_modifiers(mods: Any) -> list[dict]:
    """Normalize and validate item_metadata.ability_modifiers array.

    Raises ValueError with descriptive message on invalid entry.
    """
    if mods is None:
        return []
    if not isinstance(mods, list):
        raise ValueError("ability_modifiers must be an array")
    result: list[dict] = []
    for i, m in enumerate(mods):
        if not isinstance(m, dict):
            raise ValueError(f"ability_modifiers[{i}] must be an object")
        ability = m.get("ability")
        kind = m.get("kind")
        value = m.get("value")
        if ability not in _ALLOWED_ABILITIES:
            raise ValueError(
                f"ability_modifiers[{i}].ability must be one of "
                f"{sorted(_ALLOWED_ABILITIES)}, got {ability!r}"
            )
        if kind not in _ALLOWED_KINDS:
            raise ValueError(
                f"ability_modifiers[{i}].kind must be 'absolute' or "
                f"'relative', got {kind!r}"
            )
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(
                f"ability_modifiers[{i}].value must be an integer, "
                f"got {type(value).__name__}"
            )
        result.append({"ability": ability, "kind": kind, "value": value})
    return result


def _validate_effects(effects: Any) -> list[dict]:
    """Normalize and validate item_metadata.effects. Raises ValueError on bad data."""
    if effects is None:
        return []
    if not isinstance(effects, list):
        raise ValueError("effects must be an array")
    result: list[dict] = []
    for i, e in enumerate(effects):
        if not isinstance(e, dict):
            raise ValueError(f"effects[{i}] must be an object")
        kind = e.get("kind")
        if kind not in _ALLOWED_EFFECT_KINDS:
            raise ValueError(
                f"effects[{i}].kind must be one of {sorted(_ALLOWED_EFFECT_KINDS)}, got {kind!r}"
            )
        if kind == "heal":
            amount = str(e.get("amount", "")).strip()
            if not _HEAL_AMOUNT_RE.match(amount):
                raise ValueError(
                    f"effects[{i}].amount must be dice notation or an integer, got {amount!r}"
                )
            result.append({"kind": "heal", "amount": amount})
        else:  # add_condition / remove_condition
            cond = e.get("condition")
            if cond not in _ALLOWED_CONDITIONS:
                raise ValueError(
                    f"effects[{i}].condition must be one of {sorted(_ALLOWED_CONDITIONS)}, got {cond!r}"
                )
            result.append({"kind": kind, "condition": cond})
    return result


class ItemRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    weight: float = 0.0
    quantity: int = 1
    item_type: str = "generic"
    item_metadata: Optional[dict[str, Any]] = None
    is_equipped: bool = False
    equipment_slot: Optional[EquipmentSlot] = None

    model_config = {"from_attributes": True}

    @field_validator("item_metadata", mode="before")
    @classmethod
    def parse_metadata(cls, v: Any) -> Optional[dict]:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return None
        return v


class ItemCreate(BaseModel):
    name: str
    description: Optional[str] = None
    weight: float = 0.0
    quantity: int = 1
    item_type: str = "generic"
    item_metadata: Optional[dict[str, Any]] = None
    is_equipped: bool = False
    equipment_slot: Optional[EquipmentSlot] = None

    @field_validator("item_metadata", mode="after")
    @classmethod
    def validate_metadata(cls, v: Any) -> Any:
        if isinstance(v, dict):
            if "ability_modifiers" in v:
                v["ability_modifiers"] = _validate_ability_modifiers(v["ability_modifiers"])
            if "effects" in v:
                v["effects"] = _validate_effects(v["effects"])
            if "subtype" in v and v["subtype"] not in _ALLOWED_SUBTYPES:
                raise ValueError(
                    f"subtype must be one of {sorted(_ALLOWED_SUBTYPES)}, got {v['subtype']!r}"
                )
        return v

    @field_validator("equipment_slot", mode="after")
    @classmethod
    def validate_slot(cls, v: Optional[EquipmentSlot], info: ValidationInfo) -> Optional[EquipmentSlot]:
        if v is None:
            return v
        item_type = info.data.get("item_type", "generic")
        if not slot_allowed_for_type(item_type, v):
            raise ValueError(
                f"equipment_slot {v.value!r} is not allowed for item_type {item_type!r}"
            )
        return v


class ItemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    weight: Optional[float] = None
    quantity: Optional[int] = None
    item_type: Optional[str] = None
    item_metadata: Optional[dict[str, Any]] = None
    is_equipped: Optional[bool] = None
    equipment_slot: Optional[EquipmentSlot] = None

    @field_validator("item_metadata", mode="after")
    @classmethod
    def validate_metadata(cls, v: Any) -> Any:
        if isinstance(v, dict):
            if "ability_modifiers" in v:
                v["ability_modifiers"] = _validate_ability_modifiers(v["ability_modifiers"])
            if "effects" in v:
                v["effects"] = _validate_effects(v["effects"])
            if "subtype" in v and v["subtype"] not in _ALLOWED_SUBTYPES:
                raise ValueError(
                    f"subtype must be one of {sorted(_ALLOWED_SUBTYPES)}, got {v['subtype']!r}"
                )
        return v


class WeaponAttackResult(BaseModel):
    weapon_name: str
    to_hit_die: int
    to_hit_bonus: int
    to_hit_total: int
    is_critical: bool
    is_fumble: bool
    damage_dice: str
    damage_rolls: list[int]
    damage_bonus: int
    damage_total: int
    homebrew_notifications: Optional[list[dict]] = None
