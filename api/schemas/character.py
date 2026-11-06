"""Pydantic schemas for Character (summary, full, create, update)."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, TypeAdapter, field_validator, model_validator

from api.schemas.common import (
    PROFICIENCY_CATEGORIES,
    normalize_proficiencies,
    AbilityRead,
    AbilityScoreRead,
    CharacterClassCreate,
    CharacterClassRead,
    ConcentrationSaveResult,
    ZeroHpSaveResult,
    ConsumableUseResult,
    OptionResult,
    absent_when_none,
    CurrencyRead,
    MapRead,
    RollMode,
)
from core.rules.types import Edition
from api.schemas.condition_effects import ConditionEffectRead, PendingSaveRead
from api.schemas.container import CoinLocationRead
from api.schemas.rules import RollOptionRead
from api.schemas.item import ItemRead
from api.schemas.spell import SpellRead, SpellSlotRead


class AcBreakdown(BaseModel):
    """AC component breakdown: base, shield, magic, and homebrew modifiers."""

    base: int
    shield: int
    magic: int
    homebrew: int
    items: int = 0
    rules: int = 0


class ComputedStats(BaseModel):
    """Valori derivati dalle regole (condizioni, privilegi) sommati a homebrew e oggetti."""

    speed: int = 30
    hp_max_effective: int = 0
    resistances: list[str] = []
    immunities: list[str] = []
    incapacitated: bool = False
    surprised: bool = False  # 2014: è il turno della sorpresa
    surprise_exit_features: list[str] = []  # da sorpreso: i privilegi il cui «Usa» permette di agire (Ira)
    save_flat: dict[str, int] = {}
    fly_speed: Optional[int] = None  # volo concesso da un privilegio: pari alla velocità a terra (Aquila in ira) o fisso (Angelo Vendicatore)


class SpellCasterStats(BaseModel):
    """CD e bonus di attacco incantesimi di una classe che lancia incantesimi."""

    class_id: int
    class_name: str
    ability: str
    save_dc: int
    attack_bonus: int


class ClassSpellLimits(BaseModel):
    """Limiti di una classe e quanti ne ha assegnati. ``None``: il limite non vale per questa classe."""

    class_id: int
    class_name: str
    cantrips_count: int = 0
    cantrips_limit: Optional[int] = None
    known_count: int = 0
    known_limit: Optional[int] = None
    prepared_count: int = 0
    prepared_limit: Optional[int] = None
    # Cavaliere Mistico: scuole ammesse, quanti incantesimi conosciuti possono essere di altre scuole e quanti lo sono
    school_names: Optional[list[str]] = None
    school_free_limit: Optional[int] = None
    school_outside_count: int = 0


class SpellcastingInfo(BaseModel):
    """Blocco derivato: preparazione incantesimi + capacità rituali (spec 2026-06-10)."""

    has_preparing_class: bool = False
    prepared_cap: Optional[int] = None
    prepared_count: int = 0
    cap_mode: str = "auto"
    has_ritual_caster: bool = False
    ritual_only_spell_ids: list[int] = []  # concessi da un privilegio come soli rituali (Cercatore di Spiriti)
    has_wizard: bool = False
    casters: list[SpellCasterStats] = []
    limits: list[ClassSpellLimits] = []


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
    hp_max_homebrew_modifier: int = 0
    hp_max_effective: Optional[int] = None
    ac_homebrew_modifier: int = 0
    ac_items_modifier: int = 0
    is_dead: bool = False

    model_config = {"from_attributes": True}


class ActiveForm(BaseModel):
    companion_id: int
    name: str
    current_hp: int
    max_hp: int
    temp_hp: int
    armor_class: int
    own_hp: bool = True  # 2014: la forma ha PF propri; 2024: PF del druido con i temporanei


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
    is_dead: bool = False

    # AC components (for display and editing)
    base_armor_class: int
    shield_armor_class: int
    magic_armor: int
    base_armor_class_override: bool = False
    shield_armor_class_override: bool = False
    # Unarmored Defense second ability ('wisdom'/'constitution'); None = disabled.
    unarmored_defense_ability: Optional[str] = None
    # Caratteristiche della formula senza armatura in vigore (privilegio o interruttore).
    unarmored_formula: Optional[list[str]] = None
    ac: int

    # Homebrew passive-modifier breakdown (populated by router after model_validate)
    ac_breakdown: Optional[AcBreakdown] = None
    hp_max_homebrew_modifier: int = 0
    hp_max_effective: Optional[int] = None
    speed_homebrew_modifier: int = 0
    speed_items_modifier: int = 0
    # DEX effective mod + item initiative bonus (+ homebrew initiative, Task 21)
    initiative_bonus: int = 0
    computed: ComputedStats = ComputedStats()
    skills_homebrew_modifiers: dict[str, int] = Field(default_factory=dict)
    saves_homebrew_modifiers: dict[str, int] = Field(default_factory=dict)
    # Server-computed totals shared by rolls and the sheet (skill_bonus / passive_score).
    skill_bonuses: dict[str, int] = Field(default_factory=dict)
    passives: dict[str, int] = Field(default_factory=dict)
    jack_of_all_trades: bool = False
    saves_items_modifiers: dict[str, int] = Field(default_factory=dict)

    # Carry
    carry_capacity: int
    carry_capacity_override: bool = False
    encumbrance: float
    # Server-computed (items + coins if enabled) and variant level; see character_response.
    encumbrance_total: float = 0.0
    encumbrance_level: str = "none"
    speed_encumbrance_penalty_ft: int = 0
    # Purse + container coins; breakdown lists only locations holding coins (purse first).
    coin_totals: dict[str, int] = Field(default_factory=dict)
    coin_breakdown: list[CoinLocationRead] = Field(default_factory=list)
    unequipped_item_names: list[str] = []

    # Computed
    total_level: int = 0
    class_summary: str = ""
    proficiency_bonus: int = 2
    attacks_per_action: int = 1

    # Meta
    experience_points: int = 0
    heroic_inspiration: bool = False
    inspiration_extra: bool = False  # 2024: ricevuta un'altra mentre se ne aveva già una, da cedere o persa
    hiding_dc: Optional[int] = None  # 2024: CD per trovarlo mentre è nascosto (totale di Furtività)
    spell_slots_mode: str = "manual"
    rules_edition: Edition = "2014"
    concentrating_spell_id: Optional[int] = None
    active_states: Optional[list[dict[str, Any]]] = None

    # Populated only by PATCH /xp when a level-up occurs
    hp_gained: Optional[int] = None

    # Populated only by POST /hp when op=DAMAGE on a concentrating character
    concentration_save: Optional[ConcentrationSaveResult] = None

    # Populated only by PATCH /hp when the damage brings the character to 0 HP under a ``zero_hp_save`` feature
    zero_hp_save: Optional[ZeroHpSaveResult] = None

    # Active wild shape form (populated by build_character_response); FE shows its AC/HP.
    active_form: Optional[ActiveForm] = None

    # Populated only by PATCH /hp: id dell'operazione annullabile via POST /hp/undo
    hp_undo_id: Optional[str] = None

    # Populated only by PATCH /hp dopo un danno: le reazioni che il danno ha aperto (Ritorsione), da proporre subito
    reactions: list[RollOptionRead] = []

    # Populated only by endpoints that fire homebrew rules (POST /hp, POST /attack, etc.).
    homebrew_notifications: Optional[list[dict]] = None

    # Populated only by POST /rounds/tick: labels of effects that just expired.
    expired_effects: Optional[list[str]] = None

    condition_effects: list[ConditionEffectRead] = []
    pending_saves: list[PendingSaveRead] = []

    # Populated only by POST /items/{id}/use (consumable use result).
    consumable_use: Optional[ConsumableUseResult] = None
    option_result: OptionResult | None = absent_when_none()
    # POST /spells/{id}/use: l'incantesimo ha dadi di danno che il server non sa tirare (si lancia lo stesso, senza danno)
    damage_unrollable: bool = False

    has_custom_silhouette: bool = False

    # Scelte di livello in sospeso (ASI / talento), popolato da build_character_response
    pending_choices: Optional[list[dict[str, Any]]] = None

    # Preparazione incantesimi + rituali (popolato da build_character_response)
    spellcasting: Optional[SpellcastingInfo] = None

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
    general_proficiencies: Optional[dict[str, list[str]]] = None
    damage_modifiers: Optional[dict[str, Any]] = None

    @field_validator("general_proficiencies", mode="before")
    @classmethod
    def _proficiency_categories(cls, v: Any) -> dict[str, list[str]]:
        return normalize_proficiencies(v)

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


class SpeciesTrait(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)


class SpeciesSense(BaseModel):
    type: Literal["darkvision", "blindsight", "truesight", "tremorsense"]
    range_ft: int = Field(ge=0, le=1000)


class OtherSpeed(BaseModel):
    """Velocità diverse da quella a piedi (che resta la colonna ``speed``), in settings.speeds."""
    type: Literal["fly", "swim", "climb", "burrow"]
    range_ft: int = Field(ge=0, le=1000)


class SpeciesApply(BaseModel):
    """Species picked in the creation wizard; applied once by create_character.

    ``ability_bonuses`` keys are short (str/dex/con/int/wis/cha) or full ability names.
    """
    name: str = Field(min_length=1, max_length=100)
    speed_ft: Optional[int] = Field(default=None, ge=0, le=500)
    senses: list[SpeciesSense] = Field(default_factory=list, max_length=8)
    languages: list[str] = Field(default_factory=list, max_length=20)
    ability_bonuses: dict[str, int] = Field(default_factory=dict)
    roll_notes: dict[str, str] = Field(default_factory=dict)
    traits: list[SpeciesTrait] = Field(default_factory=list, max_length=30)


class CharacterCreate(BaseModel):
    name: str
    # Base scores WITHOUT species bonuses; each 3-20 after bonuses (checked in the router).
    ability_scores: Optional[dict[str, int]] = None
    species: Optional[SpeciesApply] = None
    # skill_slug -> proficient (e.g. from the background).
    skills: Optional[dict[str, bool]] = None
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
    speed: Optional[int] = Field(default=None, ge=0)
    personality: Optional[dict[str, Any]] = None
    languages: Optional[list[str]] = None
    general_proficiencies: Optional[list[str] | dict[str, list[str]]] = None
    damage_modifiers: Optional[dict[str, Any]] = None
    spell_slots_mode: Optional[str] = None
    rules_edition: Optional[Edition] = None
    settings: Optional[dict[str, Any]] = None

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("name must not be blank")
        return v

    @field_validator("general_proficiencies")
    @classmethod
    def _proficiency_categories(cls, v: Any) -> Any:
        if isinstance(v, dict) and set(v) - set(PROFICIENCY_CATEGORIES):
            raise ValueError("unknown proficiency category")
        return None if v is None else normalize_proficiencies(v)

    @field_validator("settings")
    @classmethod
    def _validate_senses(cls, v: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        if v is not None and "senses" in v:
            TypeAdapter(list[SpeciesSense]).validate_python(v["senses"])
        if v is not None and "speeds" in v:
            TypeAdapter(list[OtherSpeed]).validate_python(v["speeds"])
        return v


class SkillsUpdate(BaseModel):
    """Map of skill_slug → proficiency level (null/false = none, true = proficient, "expert" = expertise)."""
    skills: dict[str, Any]


class SavingThrowsUpdate(BaseModel):
    """Map of ability_slug → bool (proficient or not)."""
    saving_throws: dict[str, bool]


class ConditionsUpdate(BaseModel):
    """Map of condition_slug → bool or int (exhaustion level)."""
    conditions: dict[str, Any]
    # slug -> rounds left; None removes the duration
    durations: Optional[dict[str, Optional[int]]] = None


class InspirationUpdate(BaseModel):
    heroic_inspiration: bool


class XPUpdate(BaseModel):
    add: Optional[int] = None
    set: Optional[int] = None
    # Single class, XP mode: one die roll per gained level (1..hit_die). Omitted -> fixed HP.
    hp_rolls: Optional[list[int]] = None

class SpellAttackResult(BaseModel):
    """Esito di POST /characters/{id}/spells/{spell_id}/attack.

    Vive qui (non in schemas/spell.py) per evitare l'import circolare con CharacterFull.
    """

    spell_name: str
    to_hit_die: int
    dice: list[int] = []
    mode: RollMode = "normal"
    mode_applied: RollMode = "normal"
    notes: list[str] = []
    to_hit_bonus: int
    to_hit_total: int
    is_critical: bool
    is_fumble: bool
    caster_class: Optional[str] = None
    cast_option_result: OptionResult | None = absent_when_none()
    character: CharacterFull
    homebrew_notifications: Optional[list[dict]] = None
