"""Pydantic schemas for Item (inventory)."""

from __future__ import annotations

import json
from typing import Any, Optional

from pydantic import BaseModel, field_validator


_ALLOWED_ABILITIES = {
    "strength", "dexterity", "constitution",
    "intelligence", "wisdom", "charisma",
}
_ALLOWED_KINDS = {"absolute", "relative"}


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


class ItemRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    weight: float = 0.0
    quantity: int = 1
    item_type: str = "generic"
    item_metadata: Optional[dict[str, Any]] = None
    is_equipped: bool = False

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

    @field_validator("item_metadata", mode="after")
    @classmethod
    def validate_ability_mods(cls, v: Any) -> Any:
        if isinstance(v, dict) and "ability_modifiers" in v:
            v["ability_modifiers"] = _validate_ability_modifiers(v["ability_modifiers"])
        return v


class ItemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    weight: Optional[float] = None
    quantity: Optional[int] = None
    item_type: Optional[str] = None
    item_metadata: Optional[dict[str, Any]] = None
    is_equipped: Optional[bool] = None

    @field_validator("item_metadata", mode="after")
    @classmethod
    def validate_ability_mods(cls, v: Any) -> Any:
        if isinstance(v, dict) and "ability_modifiers" in v:
            v["ability_modifiers"] = _validate_ability_modifiers(v["ability_modifiers"])
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
