"""Pydantic schemas for Character (summary, full, create, update)."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator

from api.schemas.common import (
    AbilityRead,
    AbilityScoreRead,
    CharacterClassCreate,
    CharacterClassRead,
    ConcentrationSaveResult,
    CurrencyRead,
    MapRead,
)
from api.schemas.item import ItemRead
from api.schemas.spell import SpellRead, SpellSlotRead


class AcBreakdown(BaseModel):
    """AC component breakdown: base, shield, magic, and homebrew modifiers."""

    base: int
    shield: int
    magic: int
    homebrew: int


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
    base_armor_class_override: bool = False
    shield_armor_class_override: bool = False
    # Unarmored Defense second ability ('wisdom'/'constitution'); None = disabled.
    unarmored_defense_ability: Optional[str] = None
    ac: int

    # Homebrew passive-modifier breakdown (populated by router after model_validate)
    ac_breakdown: Optional[AcBreakdown] = None
    hp_max_homebrew_modifier: int = 0
    speed_homebrew_modifier: int = 0
    skills_homebrew_modifiers: dict[str, int] = Field(default_factory=dict)
    saves_homebrew_modifiers: dict[str, int] = Field(default_factory=dict)

    # Carry
    carry_capacity: int
    carry_capacity_override: bool = False
    encumbrance: float

    # Computed
    total_level: int = 0
    class_summary: str = ""
    proficiency_bonus: int = 2

    # Meta
    experience_points: int = 0
    heroic_inspiration: bool = False
    spell_slots_mode: str = "manual"
    concentrating_spell_id: Optional[int] = None

    # Populated only by PATCH /xp when a level-up occurs
    hp_gained: Optional[int] = None

    # Populated only by POST /hp when op=DAMAGE on a concentrating character
    concentration_save: Optional[ConcentrationSaveResult] = None

    # Populated only by endpoints that fire homebrew rules (POST /hp, POST /attack, etc.).
    homebrew_notifications: Optional[list[dict]] = None

    has_custom_silhouette: bool = False

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

    @model_validator(mode="before")
    @classmethod
    def _resolve_abilities(cls, data: Any) -> Any:
        """Resolve each AbilityScore to include effective value + modifiers_applied."""
        from api.schemas.common import _resolve_ability_effective

        if isinstance(data, dict):
            # Already a dict — don't re-resolve
            return data

        # ORM path: mutate a shallow dict representation
        if not hasattr(data, "ability_scores"):
            return data
        equipped = [i for i in getattr(data, "items", []) if i.is_equipped]
        raw_abilities = list(data.ability_scores)
        resolved = [_resolve_ability_effective(a, equipped) for a in raw_abilities]

        # Pydantic v2: build a dict from ORM attributes, then override ability_scores
        as_dict: dict[str, Any] = {}
        for k in dir(data):
            if k.startswith("_"):
                continue
            try:
                v = getattr(data, k)
            except Exception:
                continue
            # Skip methods
            if callable(v):
                continue
            as_dict[k] = v
        as_dict["ability_scores"] = resolved
        return as_dict

    model_config = {"from_attributes": True}


class CharacterIdentityCreate(BaseModel):
    """Optional identity fields captured during the creation wizard.
    Mirrors the columns already handled by CharacterUpdate; all optional."""

    race: Optional[str] = None
    gender: Optional[str] = None
    alignment: Optional[str] = None
    background: Optional[str] = None
    languages: Optional[list[str]] = None
    personality: Optional[dict[str, Any]] = None  # { "traits": "..." }


class CharacterCreate(BaseModel):
    name: str
    # Optional initial class — when provided the character + first class are
    # created atomically. Avoids the orphan-character risk of the previous
    # two-step client flow (POST /characters then POST /classes).
    initial_class: Optional[CharacterClassCreate] = None
    # Optional identity — applied in the same transaction (see create_character).
    identity: Optional[CharacterIdentityCreate] = None


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
