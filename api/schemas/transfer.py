"""Schema del file di esportazione/importazione personaggio (format_version 1)."""
from __future__ import annotations

from typing import Annotated, Any, Literal, Optional

from pydantic import AfterValidator, BaseModel, Field, ValidationInfo, field_validator

from api.schemas.companion import validate_statblock
from api.schemas.item import _validate_weapon_meta
from api.schemas.item_magic import validate_magic_meta
from core.db.models import EquipmentSlot
from core.game.actions import ActionType




def _rng(lo: float, hi: float) -> AfterValidator:
    """Limite numerico: attivo in import, saltato con context={"lenient": True} (export)."""
    def check(v, info: ValidationInfo):
        if not (info.context or {}).get("lenient") and not (lo <= v <= hi):
            raise ValueError(f"must be between {lo} and {hi}")
        return v
    return AfterValidator(check)


def _cap(n: int) -> AfterValidator:
    """Tetto sulla lunghezza di una lista: attivo in import, saltato in export."""
    def check(v, info: ValidationInfo):
        if not (info.context or {}).get("lenient") and len(v) > n:
            raise ValueError(f"at most {n} entries")
        return v
    return AfterValidator(check)


Int0 = Annotated[int, _rng(0, 1_000_000)]
Restoration = Literal["long_rest", "short_rest", "none", "manual"]


class ExportChoice(BaseModel):
    id: str = Field(max_length=64)
    kind: Literal["asi"] = "asi"
    class_key: str = Field(max_length=100)
    level: Annotated[int, _rng(1, 20)]
    created_at: str = Field("", max_length=50)


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
    # legacy exports carry a plain list, newer ones the {armor,weapons,tools,other} object
    general_proficiencies: list | dict = Field(default_factory=list)
    damage_modifiers: dict = Field(default_factory=dict)
    pending_choices: list[ExportChoice] = Field(default_factory=list, max_length=40)
    # {titolo: {body, created_at, updated_at, tags, was_voice}}; le note vocali hanno body ""
    notes: dict = Field(default_factory=dict)


class ExportClass(BaseModel):
    class_name: str = Field(max_length=100)
    level: Annotated[int, _rng(1, 20)] = 1
    subclass: Optional[str] = None
    spellcasting_ability: Optional[str] = None
    hit_die: Optional[Annotated[int, _rng(1, 100)]] = None
    hit_dice_used: Int0 = 0


class ExportAbilityScore(BaseModel):
    name: str = Field(max_length=50)
    value: Annotated[int, _rng(1, 30)] = 10


class ExportItem(BaseModel):
    name: str = Field(max_length=200)
    description: Optional[str] = None
    weight: Annotated[float, _rng(0, 1_000_000)] = 0.0
    quantity: Int0 = 1
    item_type: str = Field("generic", max_length=20)
    item_metadata: dict[str, Any] = Field(default_factory=dict)
    is_equipped: bool = False
    equipment_slot: Optional[EquipmentSlot] = None

    @field_validator("item_metadata")
    @classmethod
    def _check_meta(cls, v: dict[str, Any], info: ValidationInfo) -> dict[str, Any]:
        # Same rules as item create/patch; export (lenient) keeps legacy data as-is.
        if not (info.context or {}).get("lenient"):
            _validate_weapon_meta(v)
            validate_magic_meta(v)
        return v


class ExportSpell(BaseModel):
    export_key: str = Field(max_length=20)
    name: str = Field(max_length=200)
    level: Annotated[int, _rng(0, 9)] = 0
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
    higher_levels_dice: Optional[str] = Field(default=None, pattern=r"^\d+d\d+([+-]\d+)?$")


class ExportSpellSlot(BaseModel):
    level: Annotated[int, _rng(1, 9)]
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
    action_type: Optional[ActionType] = None
    source_class_key: Optional[str] = None  # "c<indice in classes>"

    @field_validator("action_type", mode="wrap")
    @classmethod
    def _lenient_action_type(cls, v, handler, info: ValidationInfo):
        # Export (lenient) non deve fallire su valori salvati inattesi: li esporta come None.
        try:
            return handler(v)
        except ValueError:
            if (info.context or {}).get("lenient"):
                return None
            raise


class ExportCurrency(BaseModel):
    copper: Int0 = 0
    silver: Int0 = 0
    electrum: Int0 = 0
    gold: Int0 = 0
    platinum: Int0 = 0


class ExportHomebrewRule(BaseModel):
    name: str = Field(max_length=100)
    version: Annotated[int, _rng(1, 1_000_000)] = 1
    description: Optional[str] = None
    enabled: bool = True
    dsl: dict = Field(default_factory=dict)
    template_id: Optional[str] = None


class ExportHomebrewResource(BaseModel):
    rule_index: Int0
    key: str = Field(max_length=60)
    name: str = Field(max_length=100)
    current: Int0 = 0
    max: Int0 = 0
    restoration_type: Restoration = "none"


class ExportCompanion(BaseModel):
    kind: Literal["familiar", "companion", "mount", "summon", "wild_shape"]
    name: str = Field(min_length=1, max_length=100)
    srd_index: Optional[str] = Field(default=None, max_length=80)
    statblock: dict = Field(default_factory=dict)
    max_hp: Int0 = 0
    current_hp: Int0 = 0
    temp_hp: Int0 = 0
    armor_class: Annotated[int, _rng(0, 100)] = 10
    notes: Optional[str] = None
    is_active: bool = False

    @field_validator("statblock")
    @classmethod
    def _statblock(cls, v, info: ValidationInfo):
        if not (info.context or {}).get("lenient"):
            validate_statblock(v)
        return v


class CharacterExport(BaseModel):
    format_version: Literal[1] = 1
    app_version: Optional[str] = None
    exported_at: str
    character: ExportCharacter
    classes: Annotated[list[ExportClass], _cap(20)] = Field(default_factory=list)
    ability_scores: Annotated[list[ExportAbilityScore], _cap(20)] = Field(default_factory=list)
    items: Annotated[list[ExportItem], _cap(500)] = Field(default_factory=list)
    spells: Annotated[list[ExportSpell], _cap(500)] = Field(default_factory=list)
    concentrating_spell_key: Optional[str] = None
    spell_slots: Annotated[list[ExportSpellSlot], _cap(40)] = Field(default_factory=list)
    abilities: Annotated[list[ExportAbility], _cap(500)] = Field(default_factory=list)
    currency: Optional[ExportCurrency] = None
    homebrew_rules: Annotated[list[ExportHomebrewRule], _cap(50)] = Field(default_factory=list)
    homebrew_resources: Annotated[list[ExportHomebrewResource], _cap(500)] = Field(default_factory=list)
    companions: Annotated[list[ExportCompanion], _cap(30)] = Field(default_factory=list)
