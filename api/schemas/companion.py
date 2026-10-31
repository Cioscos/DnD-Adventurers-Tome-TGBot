"""Companions (familiars, companions, mounts, summons, wild shape forms)."""
from __future__ import annotations

import re
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.schemas.common import D20Dice, RollMode

CompanionKind = Literal["familiar", "companion", "mount", "summon", "wild_shape"]
DICE_RE = re.compile(r"^(\d+)d(\d+)([+-]\d+)?$", re.IGNORECASE)
MAX_COMPANIONS = 30


def validate_statblock(sb: Any) -> dict:
    """Minimal shape check: dict, actions list with typed attack_bonus / damage_dice."""
    if not isinstance(sb, dict):
        raise ValueError("statblock must be an object")
    actions = sb.get("actions", [])
    if not isinstance(actions, list):
        raise ValueError("actions must be a list")
    for a in actions:
        if not isinstance(a, dict):
            raise ValueError("each action must be an object")
        ab = a.get("attack_bonus")
        if ab is not None and (isinstance(ab, bool) or not isinstance(ab, int)):
            raise ValueError("attack_bonus must be an integer")
        dd = a.get("damage_dice")
        if dd is not None and not (isinstance(dd, str) and DICE_RE.match(dd.strip())):
            raise ValueError("damage_dice must be dice notation")
        dt = a.get("damage_type")
        if dt is not None and not isinstance(dt, str):
            raise ValueError("damage_type must be a string")
    return sb


class CompanionCreate(BaseModel):
    kind: CompanionKind
    name: str = Field(min_length=1, max_length=100)
    srd_index: Optional[str] = Field(default=None, max_length=80)
    statblock: dict = Field(default_factory=dict)
    max_hp: int = Field(default=0, ge=0, le=100_000)
    current_hp: Optional[int] = Field(default=None, ge=0, le=100_000)
    temp_hp: int = Field(default=0, ge=0, le=100_000)
    armor_class: int = Field(default=10, ge=0, le=100)
    notes: Optional[str] = Field(default=None, max_length=5000)
    is_active: bool = False

    @field_validator("statblock", mode="before")
    @classmethod
    def _sb(cls, v):
        return validate_statblock(v)


class CompanionUpdate(BaseModel):
    kind: Optional[CompanionKind] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    srd_index: Optional[str] = Field(default=None, max_length=80)
    statblock: Optional[dict] = None
    max_hp: Optional[int] = Field(default=None, ge=0, le=100_000)
    current_hp: Optional[int] = Field(default=None, ge=0, le=100_000)
    temp_hp: Optional[int] = Field(default=None, ge=0, le=100_000)
    armor_class: Optional[int] = Field(default=None, ge=0, le=100)
    notes: Optional[str] = Field(default=None, max_length=5000)
    is_active: Optional[bool] = None

    @field_validator("statblock", mode="before")
    @classmethod
    def _sb(cls, v):
        return None if v is None else validate_statblock(v)


class CompanionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    character_id: int
    kind: str
    name: str
    srd_index: Optional[str] = None
    statblock: dict
    max_hp: int
    current_hp: int
    temp_hp: int
    armor_class: int
    notes: Optional[str] = None
    is_active: bool
    created_at: str
    down: bool = False  # set by the hp endpoint: 0 HP means "a terra" (no death saves)


class CompanionHp(BaseModel):
    op: Literal["damage", "heal", "set_temp"]
    value: int = Field(ge=0, le=100_000)


class CompanionAttack(BaseModel):
    action_index: int = Field(ge=0)
    mode: RollMode = "normal"
    dice: D20Dice | None = None
    damage_rolls: Optional[list[int]] = Field(default=None, max_length=100)


class CompanionAttackResult(BaseModel):
    to_hit_die: int
    to_hit_bonus: int
    to_hit_total: int
    dice: list[int]
    mode: RollMode
    is_critical: bool
    damage_rolls: list[int]
    damage_total: int
    damage_type: Optional[str] = None
