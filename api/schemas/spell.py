"""Pydantic schemas for Spell and SpellSlot."""

from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, field_validator

_EXTRA_DICE_RE = re.compile(r"^(\d+)d(\d+)([+-]\d+)?$", re.IGNORECASE)


class SpellRead(BaseModel):
    id: int
    name: str
    level: int
    description: Optional[str] = None
    casting_time: Optional[str] = None
    range_area: Optional[str] = None
    components: Optional[str] = None
    duration: Optional[str] = None
    is_concentration: bool = False
    is_ritual: bool = False
    higher_level: Optional[str] = None
    attack_save: Optional[str] = None
    damage_dice: Optional[str] = None
    damage_type: Optional[str] = None
    is_pinned: bool = False

    model_config = {"from_attributes": True}


class SpellCreate(BaseModel):
    name: str
    level: int = 0
    description: Optional[str] = None
    casting_time: Optional[str] = None
    range_area: Optional[str] = None
    components: Optional[str] = None
    duration: Optional[str] = None
    is_concentration: bool = False
    is_ritual: bool = False
    higher_level: Optional[str] = None
    attack_save: Optional[str] = None
    damage_dice: Optional[str] = None
    damage_type: Optional[str] = None
    is_pinned: bool = False


class SpellUpdate(BaseModel):
    name: Optional[str] = None
    level: Optional[int] = None
    description: Optional[str] = None
    casting_time: Optional[str] = None
    range_area: Optional[str] = None
    components: Optional[str] = None
    duration: Optional[str] = None
    is_concentration: Optional[bool] = None
    is_ritual: Optional[bool] = None
    higher_level: Optional[str] = None
    attack_save: Optional[str] = None
    damage_dice: Optional[str] = None
    damage_type: Optional[str] = None
    is_pinned: Optional[bool] = None


class SpellUseRequest(BaseModel):
    slot_level: int


class SpellSlotRead(BaseModel):
    id: int
    level: int
    total: int
    used: int
    available: int

    model_config = {"from_attributes": True}


class SpellSlotCreate(BaseModel):
    level: int
    total: int
    used: int = 0


class SpellSlotUpdate(BaseModel):
    total: Optional[int] = None
    used: Optional[int] = None


class ConcentrationUpdate(BaseModel):
    spell_id: Optional[int] = None  # null to drop concentration


class RollDamageRequest(BaseModel):
    casting_level: int | None = None
    extra_dice: str | None = None
    is_critical: bool = False

    @field_validator("extra_dice")
    @classmethod
    def validate_extra_dice(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        if not _EXTRA_DICE_RE.match(v.strip()):
            raise ValueError(
                f"extra_dice must match '<count>d<sides>[+/-bonus]' "
                f"(e.g. '2d6', '1d8+3'), got {v!r}"
            )
        return v.strip()


class RollDamageResult(BaseModel):
    rolls: list[int]
    total: int
    half_damage: int
    damage_type: str | None
    breakdown: str
    casting_level: int
    is_critical: bool
    model_config = {"from_attributes": True}
