"""Shared Pydantic schemas for simple character sub-resources."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# AbilityScore
# ---------------------------------------------------------------------------

class AbilityScoreRead(BaseModel):
    id: int
    name: str
    value: int
    modifier: int

    model_config = {"from_attributes": True}


class AbilityScoreUpdate(BaseModel):
    value: int  # 1–30


# ---------------------------------------------------------------------------
# ClassResource
# ---------------------------------------------------------------------------

class ClassResourceRead(BaseModel):
    id: int
    name: str
    current: int
    total: int
    restoration_type: str
    note: Optional[str] = None

    model_config = {"from_attributes": True}


class ClassResourceCreate(BaseModel):
    name: str
    current: int = 0
    total: int
    restoration_type: str = "none"
    note: Optional[str] = None


class ClassResourceUpdate(BaseModel):
    name: Optional[str] = None
    current: Optional[int] = None
    total: Optional[int] = None
    restoration_type: Optional[str] = None
    note: Optional[str] = None


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
    resources: list[ClassResourceRead] = []

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

    model_config = {"from_attributes": True}


class AbilityCreate(BaseModel):
    name: str
    description: Optional[str] = None
    max_uses: Optional[int] = None
    uses: Optional[int] = None
    is_passive: bool = False
    is_active: bool = False
    restoration_type: str = "none"


class AbilityUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    max_uses: Optional[int] = None
    uses: Optional[int] = None
    is_passive: Optional[bool] = None
    is_active: Optional[bool] = None
    restoration_type: Optional[str] = None


# ---------------------------------------------------------------------------
# Map
# ---------------------------------------------------------------------------

class MapRead(BaseModel):
    id: int
    zone_name: str
    file_id: str
    file_type: str

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


class RestRequest(BaseModel):
    rest_type: str  # "long" | "short"
    hit_dice_used: Optional[int] = None


class DeathSaveAction(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    RESET = "reset"
    STABILIZE = "stabilize"


class DeathSaveUpdate(BaseModel):
    action: DeathSaveAction


# ---------------------------------------------------------------------------
# Dice
# ---------------------------------------------------------------------------

class DiceRollRequest(BaseModel):
    count: int = 1
    die: str  # "d4" | "d6" | "d8" | "d10" | "d12" | "d20" | "d100"


class DiceRollResult(BaseModel):
    notation: str
    rolls: list[int]
    total: int
    modifier: int = 0


# ---------------------------------------------------------------------------
# Generic roll result (skill check, saving throw, initiative…)
# ---------------------------------------------------------------------------

class RollResult(BaseModel):
    die: int = 20
    bonus: int
    total: int
    is_critical: bool = False
    is_fumble: bool = False
    description: str = ""


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

class HistoryEntryRead(BaseModel):
    id: int
    timestamp: str
    event_type: str
    description: str

    model_config = {"from_attributes": True}
