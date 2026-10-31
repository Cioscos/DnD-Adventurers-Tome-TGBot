"""Schema del file di esportazione/importazione personaggio (format_version 1)."""
from __future__ import annotations

from typing import Annotated, Any, Literal, Optional

from pydantic import BaseModel, Field

from core.db.models import EquipmentSlot


Int0 = Annotated[int, Field(ge=0, le=1_000_000)]
Restoration = Literal["long_rest", "short_rest", "none", "manual"]


class ExportCharacter(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    race: Optional[str] = Field(None, max_length=100)
    gender: Optional[str] = Field(None, max_length=50)
    hit_points: Int0 = 0
    current_hit_points: Int0 = 0
    temp_hp: Int0 = 0
    base_armor_class: int = 10
    shield_armor_class: int = 0
    magic_armor: int = 0
    base_armor_class_override: bool = False
    shield_armor_class_override: bool = False
    unarmored_defense_ability: Optional[str] = None
    carry_capacity: Int0 = 150
    carry_capacity_override: bool = False
    spell_slots_mode: Literal["automatic", "manual"] = "manual"
    heroic_inspiration: bool = False
    experience_points: Int0 = 0
    is_dead: bool = False
    speed: Int0 = 30
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
    class_name: str = Field(max_length=100)
    level: int = Field(1, ge=1, le=20)
    subclass: Optional[str] = None
    spellcasting_ability: Optional[str] = None
    hit_die: Optional[int] = Field(None, ge=1, le=100)
    hit_dice_used: Int0 = 0


class ExportAbilityScore(BaseModel):
    name: str = Field(max_length=50)
    value: int = Field(10, ge=1, le=30)


class ExportItem(BaseModel):
    name: str = Field(max_length=200)
    description: Optional[str] = None
    weight: float = Field(0.0, ge=0, le=1_000_000)
    quantity: Int0 = 1
    item_type: str = Field("generic", max_length=20)
    item_metadata: dict[str, Any] = Field(default_factory=dict)
    is_equipped: bool = False
    equipment_slot: Optional[EquipmentSlot] = None


class ExportSpell(BaseModel):
    export_key: str = Field(max_length=20)
    name: str = Field(max_length=200)
    level: int = Field(0, ge=0, le=9)
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
    level: int = Field(ge=1, le=9)
    total: Int0 = 0
    used: Int0 = 0
    is_pact: bool = False


class ExportAbility(BaseModel):
    name: str = Field(max_length=200)
    description: Optional[str] = None
    max_uses: Optional[Int0] = None
    uses: Optional[Int0] = None
    is_passive: bool = False
    is_active: bool = False
    restoration_type: Restoration = "none"
    is_class_feature: bool = False
    feature_key: Optional[str] = None
    source_class_key: Optional[str] = None  # "c<indice in classes>"


class ExportCurrency(BaseModel):
    copper: Int0 = 0
    silver: Int0 = 0
    electrum: Int0 = 0
    gold: Int0 = 0
    platinum: Int0 = 0


class ExportHomebrewRule(BaseModel):
    name: str = Field(max_length=100)
    version: int = Field(1, ge=1)
    description: Optional[str] = None
    enabled: bool = True
    dsl: dict = Field(default_factory=dict)
    template_id: Optional[str] = None


class ExportHomebrewResource(BaseModel):
    rule_index: int = Field(ge=0)
    key: str = Field(max_length=60)
    name: str = Field(max_length=100)
    current: Int0 = 0
    max: Int0 = 0
    restoration_type: Restoration = "none"


class CharacterExport(BaseModel):
    format_version: Literal[1] = 1
    app_version: Optional[str] = None
    exported_at: str
    character: ExportCharacter
    classes: list[ExportClass] = Field(default_factory=list, max_length=20)
    ability_scores: list[ExportAbilityScore] = Field(default_factory=list, max_length=20)
    items: list[ExportItem] = Field(default_factory=list, max_length=500)
    spells: list[ExportSpell] = Field(default_factory=list, max_length=500)
    concentrating_spell_key: Optional[str] = None
    spell_slots: list[ExportSpellSlot] = Field(default_factory=list, max_length=40)
    abilities: list[ExportAbility] = Field(default_factory=list, max_length=500)
    currency: Optional[ExportCurrency] = None
    homebrew_rules: list[ExportHomebrewRule] = Field(default_factory=list, max_length=50)
    homebrew_resources: list[ExportHomebrewResource] = Field(default_factory=list, max_length=500)
    companions: list = Field(default_factory=list)  # riempito dal task compagni (R7)
