"""Pydantic schemas for Spell and SpellSlot."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


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
