"""Pydantic schemas for Character (summary, full, create, update)."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel

from api.schemas.common import (
    AbilityRead,
    AbilityScoreRead,
    CharacterClassRead,
    CurrencyRead,
    MapRead,
)
from api.schemas.item import ItemRead
from api.schemas.spell import SpellRead, SpellSlotRead


class CharacterSummary(BaseModel):
    """Lightweight model returned in the character list."""

    id: int
    name: str
    race: Optional[str] = None
    gender: Optional[str] = None
    hit_points: int
    current_hit_points: int
    temp_hp: int = 0
    ac: int
    total_level: int
    class_summary: str
    is_party_active: bool = False
    heroic_inspiration: bool = False
    experience_points: int = 0

    model_config = {"from_attributes": True}


class CharacterFull(BaseModel):
    """Complete character data with all relations."""

    id: int
    name: str
    race: Optional[str] = None
    gender: Optional[str] = None
    background: Optional[str] = None
    alignment: Optional[str] = None
    speed: int = 30

    # HP
    hit_points: int
    current_hit_points: int
    temp_hp: int = 0

    # AC components (for display and editing)
    base_armor_class: int
    shield_armor_class: int
    magic_armor: int
    ac: int

    # Carry
    carry_capacity: int
    encumbrance: float

    # Computed
    total_level: int = 0
    class_summary: str = ""
    proficiency_bonus: int = 2

    # Meta
    experience_points: int = 0
    heroic_inspiration: bool = False
    is_party_active: bool = False
    spell_slots_mode: str = "manual"
    concentrating_spell_id: Optional[int] = None

    # JSON fields
    rolls_history: Optional[list] = None
    notes: Optional[dict[str, Any]] = None
    settings: Optional[dict[str, Any]] = None
    conditions: Optional[dict[str, Any]] = None
    skills: Optional[dict[str, Any]] = None
    saving_throws: Optional[dict[str, Any]] = None
    death_saves: Optional[dict[str, Any]] = None
    personality: Optional[dict[str, Any]] = None
    languages: Optional[list] = None
    general_proficiencies: Optional[list] = None
    damage_modifiers: Optional[dict[str, Any]] = None

    # Relations
    classes: list[CharacterClassRead] = []
    ability_scores: list[AbilityScoreRead] = []
    spells: list[SpellRead] = []
    spell_slots: list[SpellSlotRead] = []
    items: list[ItemRead] = []
    currency: Optional[CurrencyRead] = None
    abilities: list[AbilityRead] = []
    maps: list[MapRead] = []

    model_config = {"from_attributes": True}


class CharacterCreate(BaseModel):
    name: str


class CharacterUpdate(BaseModel):
    """Partial update for identity / metadata fields."""
    name: Optional[str] = None
    race: Optional[str] = None
    gender: Optional[str] = None
    background: Optional[str] = None
    alignment: Optional[str] = None
    speed: Optional[int] = None
    personality: Optional[dict[str, Any]] = None
    languages: Optional[list[str]] = None
    general_proficiencies: Optional[list[str]] = None
    damage_modifiers: Optional[dict[str, Any]] = None
    is_party_active: Optional[bool] = None
    spell_slots_mode: Optional[str] = None
    settings: Optional[dict[str, Any]] = None


class SkillsUpdate(BaseModel):
    """Map of skill_slug → proficiency level (null/false = none, true = proficient, "expert" = expertise)."""
    skills: dict[str, Any]


class SavingThrowsUpdate(BaseModel):
    """Map of ability_slug → bool (proficient or not)."""
    saving_throws: dict[str, bool]


class ConditionsUpdate(BaseModel):
    """Map of condition_slug → bool or int (exhaustion level)."""
    conditions: dict[str, Any]


class InspirationUpdate(BaseModel):
    heroic_inspiration: bool


class XPUpdate(BaseModel):
    add: Optional[int] = None
    set: Optional[int] = None
