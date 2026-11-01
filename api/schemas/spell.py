"""Pydantic schemas for Spell and SpellSlot."""

from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from api.schemas.common import D20Dice, RollMode

_EXTRA_DICE_RE = re.compile(r"^(\d+)d(\d+)([+-]\d+)?$", re.IGNORECASE)


# Bonus opzionale: il dardo extra di Dardo incantato è 1d4+1 per livello.
_UPCAST_PATTERN = r"^\d+d\d+([+-]\d+)?$"


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
    is_prepared: bool = True
    school: Optional[str] = None
    srd_index: Optional[str] = None
    higher_levels_dice: Optional[str] = None

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
    is_prepared: bool = False
    school: Optional[str] = Field(default=None, max_length=30)
    srd_index: Optional[str] = Field(default=None, max_length=80)
    higher_levels_dice: Optional[str] = Field(default=None, pattern=_UPCAST_PATTERN)


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
    is_prepared: Optional[bool] = None
    school: Optional[str] = Field(default=None, max_length=30)
    srd_index: Optional[str] = Field(default=None, max_length=80)
    higher_levels_dice: Optional[str] = Field(default=None, pattern=_UPCAST_PATTERN)


class SpellUseRequest(BaseModel):
    # slot_level è obbligatorio per il lancio normale (validato nel router con
    # 400, non 422, per coerenza con gli altri errori di dominio dell'endpoint).
    slot_level: int | None = None
    as_ritual: bool = False


class SpellAttackRequest(BaseModel):
    slot_level: int | None = None
    ritual: bool = False
    die: int | None = Field(None, ge=1, le=20)
    with_inspiration: bool = False
    mode: RollMode = "normal"
    dice: D20Dice | None = None


class SpellSlotRead(BaseModel):
    id: int
    level: int
    total: int
    used: int
    available: int
    is_pact: bool = False
    # Homebrew rule notifications surfaced when a spell_cast event fired
    # (PATCH /spell_slots/{id} with an incremented `used`). Omitted/None on
    # POST/list responses to match CharacterFull's contract (Phase 2 pattern).
    homebrew_notifications: Optional[list[dict]] = None

    model_config = {"from_attributes": True}


class SpellSlotCreate(BaseModel):
    level: int
    total: int
    used: int = 0
    is_pact: bool = False


class SpellSlotUpdate(BaseModel):
    total: Optional[int] = None
    used: Optional[int] = None


class ConcentrationUpdate(BaseModel):
    spell_id: Optional[int] = None  # null to drop concentration
    rounds: Optional[int] = None


class RollDamageRequest(BaseModel):
    casting_level: int | None = None
    extra_dice: str | None = None
    is_critical: bool = False
    # Optional client-supplied face values from 3D physics. When present, the
    # server validates count/range and uses them instead of random.randint.
    main_rolls: list[int] | None = None
    extra_rolls: list[int] | None = None

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
    scaled_dice: str = ""    # base dice after cantrip scaling, e.g. "2d10"
    # --- new fields for 3D animation ---
    main_kind: str           # e.g. "d6"
    main_rolls: list[int]    # only main dice (not extras)
    extra_kind: str | None = None   # "d4" or None
    extra_rolls: list[int] = []     # [] if no extra_dice
    model_config = {"from_attributes": True}
