from typing import List, Optional

from pydantic import BaseModel, Field

from src.model.APIResource import APIResource
from src.model.AbilityScore import AbilityScore
from src.model.DamageType import DamageType
from src.model.Language import LanguageChoice
from src.model.Proficiency import Proficiency, ProficiencyChoice
from src.model.Race import Race, Subrace
from src.model.SpellResource import AreaOfEffect, SpellChoice


class Trait(APIResource):
    desc: List[str]
    language_options: Optional[LanguageChoice] = None
    parent: Optional['Trait'] = None
    proficiencies: Optional[List[Proficiency]] = None
    proficiency_choices: Optional[ProficiencyChoice] = None
    races: Optional[List[Race]] = None
    subraces: Optional[List[Subrace]] = None
    trait_specific: Optional['TraitSpecific'] = None


class TraitOption(BaseModel):
    option_type: str
    item: Trait


class TraitOptionSet(BaseModel):
    option_set_type: str
    options: List[TraitOption]


class TraitChoice(BaseModel):
    type: str
    choose: int
    from_: TraitOptionSet = Field(..., alias='from')


class DamageAtLevel(BaseModel):
    level: int
    damage: str


class BreathWeaponDamage(BaseModel):
    damage_type: DamageType
    damage_at_character_level: DamageAtLevel


class BreathWeaponDc(BaseModel):
    success: str
    type: AbilityScore


class BreathWeaponUsage(BaseModel):
    times: int
    type: str


class BreathWeaponTrait(BaseModel):
    area_of_effect: Optional[AreaOfEffect] = None
    damage: Optional[List[BreathWeaponDamage]] = None
    dc: Optional[BreathWeaponDc] = None
    desc: str
    name: str
    usage: Optional[BreathWeaponUsage] = None


class TraitSpecific(APIResource):
    breath_weapon: Optional[BreathWeaponTrait] = None
    damage_type: Optional[DamageType] = None
    spell_options: Optional[SpellChoice] = None
    subtrait_options: Optional[TraitChoice] = None
