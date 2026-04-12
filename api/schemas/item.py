"""Pydantic schemas for Item (inventory)."""

from __future__ import annotations

import json
from typing import Any, Optional

from pydantic import BaseModel, field_validator


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


class ItemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    weight: Optional[float] = None
    quantity: Optional[int] = None
    item_type: Optional[str] = None
    item_metadata: Optional[dict[str, Any]] = None
    is_equipped: Optional[bool] = None


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
