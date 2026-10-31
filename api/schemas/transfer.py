"""Schema del file di esportazione/importazione personaggio (format_version 1)."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ExportCharacter(BaseModel):
    name: str
    race: Optional[str] = None
    gender: Optional[str] = None
    hit_points: int = 0
    current_hit_points: int = 0
    temp_hp: int = 0
    base_armor_class: int = 10
    shield_armor_class: int = 0
    magic_armor: int = 0
    base_armor_class_override: bool = False
    shield_armor_class_override: bool = False
    unarmored_defense_ability: Optional[str] = None
    carry_capacity: int = 150
    carry_capacity_override: bool = False
    spell_slots_mode: str = "manual"
    heroic_inspiration: bool = False
    experience_points: int = 0
    is_dead: bool = False
    speed: int = 30
    background: Optional[str] = None
    alignment: Optional[str] = None
    settings: dict = Field(default_factory=dict)
    conditions: dict = Field(default_factory=dict)
    skills: dict = Field(default_factory=dict)
    saving_throws: dict = Field(default_factory=dict)
    death_saves: dict = Field(default_factory=dict)
    personality: dict = Field(default_factory=dict)
    languages: list = Field(default_factory=list)
    general_proficiencies: list = Field(default_factory=list)
    damage_modifiers: dict = Field(default_factory=dict)
    # {titolo: {body, created_at, updated_at, tags, was_voice}}; le note vocali hanno body ""
    notes: dict = Field(default_factory=dict)


class ExportClass(BaseModel):
    class_name: str
    level: int = 1
    subclass: Optional[str] = None
    spellcasting_ability: Optional[str] = None
    hit_die: Optional[int] = None
    hit_dice_used: int = 0


class ExportAbilityScore(BaseModel):
    name: str
    value: int = 10


class ExportItem(BaseModel):
    name: str
    description: Optional[str] = None
    weight: float = 0.0
    quantity: int = 1
    item_type: str = "generic"
    item_metadata: dict[str, Any] = Field(default_factory=dict)
    is_equipped: bool = False
    equipment_slot: Optional[str] = None


class ExportSpell(BaseModel):
    export_key: str
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


class ExportSpellSlot(BaseModel):
    level: int
    total: int = 0
    used: int = 0
    is_pact: bool = False


class ExportAbility(BaseModel):
    name: str
    description: Optional[str] = None
    max_uses: Optional[int] = None
    uses: Optional[int] = None
    is_passive: bool = False
    is_active: bool = False
    restoration_type: str = "none"
    is_class_feature: bool = False
    feature_key: Optional[str] = None
    source_class_key: Optional[str] = None  # "c<indice in classes>"


class ExportCurrency(BaseModel):
    copper: int = 0
    silver: int = 0
    electrum: int = 0
    gold: int = 0
    platinum: int = 0


class ExportHomebrewRule(BaseModel):
    name: str
    description: Optional[str] = None
    enabled: bool = True
    dsl: dict = Field(default_factory=dict)
    template_id: Optional[str] = None


class ExportHomebrewResource(BaseModel):
    rule_index: int
    key: str
    name: str
    current: int = 0
    max: int = 0
    restoration_type: str = "none"


class CharacterExport(BaseModel):
    format_version: Literal[1] = 1
    app_version: Optional[str] = None
    exported_at: str
    character: ExportCharacter
    classes: list[ExportClass] = Field(default_factory=list)
    ability_scores: list[ExportAbilityScore] = Field(default_factory=list)
    items: list[ExportItem] = Field(default_factory=list)
    spells: list[ExportSpell] = Field(default_factory=list)
    concentrating_spell_key: Optional[str] = None
    spell_slots: list[ExportSpellSlot] = Field(default_factory=list)
    abilities: list[ExportAbility] = Field(default_factory=list)
    currency: Optional[ExportCurrency] = None
    homebrew_rules: list[ExportHomebrewRule] = Field(default_factory=list)
    homebrew_resources: list[ExportHomebrewResource] = Field(default_factory=list)
    companions: list = Field(default_factory=list)  # riempito dal task compagni (R7)
